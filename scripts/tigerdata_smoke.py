"""Explicit isolated hosted gate. No Docker, Compose, reset or default target.

All connection secrets come from private environment configuration, never CLI arguments.
Preflight is read-only; migration, synthetic verification and owned cleanup are separate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal

from alembic import command
from alembic.config import Config
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, delete, insert, select, text

from strongstart_api.config import Settings
from strongstart_api.database_profile import build_engine, postgres_url
from strongstart_api.db import APPLICATION_TABLES, REQUIRED_MIGRATION_REVISION, organizations

ROOT = Path(__file__).resolve().parents[1]
OPT_IN = "isolated-development-test"


class GateError(ValueError):
    pass


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    target_id: str = Field(pattern=r"^[a-z0-9-]{3,80}$")
    provider: Literal["tigerdata"]
    environment: Literal["isolated-development-test"]
    owner_selected: Literal[True]
    host: str
    database: str
    migration_role: str
    runtime_role: str
    allow_migrate: bool = False
    allow_test_writes: bool = False


def selected(path: Path | None) -> tuple[Target, Settings]:
    if os.environ.get("DATA001_TIGERDATA_OPT_IN") != OPT_IN or path is None:
        raise GateError("explicit isolated target manifest and opt-in required")
    target = Target.model_validate_json(path.read_text())
    if target.migration_role == target.runtime_role:
        raise GateError("separate migration and runtime roles required")
    settings = Settings(_env_file=None)
    if settings.database_profile != "tigerdata" or not settings.database_url:
        raise GateError("explicit TigerData runtime profile/URL required")
    if settings.db_connection_budget is None or settings.db_connection_budget < 7:
        raise GateError(
            "hosted verifier needs an explicit temporary budget of at least 7 connections"
        )
    check_target(settings.database_url, settings, target, target.runtime_role)
    return target, settings


def check_target(raw: str, settings: Settings, target: Target, role: str) -> None:
    url = postgres_url(raw, "tigerdata", settings.db_sslrootcert)
    if (url.host, url.database, url.username) != (target.host, target.database, role):
        raise GateError("connection does not match owner-selected target and role")


def engine_for(raw: str, settings: Settings) -> Engine:
    return build_engine(
        raw,
        profile="tigerdata",
        root_cert=settings.db_sslrootcert,
        pool_size=1,
        max_overflow=0,
        connect_timeout=settings.db_connect_timeout_seconds,
        lock_timeout_ms=settings.db_lock_timeout_ms,
        statement_timeout_ms=settings.db_statement_timeout_ms,
    )


def preflight(engine: Engine, target: Target, runtime: bool = True) -> dict[str, Any]:
    with engine.connect() as conn, conn.begin():
        conn.execute(text("SET TRANSACTION READ ONLY"))
        database, role, version = conn.execute(
            text("select current_database(), current_user, current_setting('server_version')")
        ).one()
        if database != target.database or role != (
            target.runtime_role if runtime else target.migration_role
        ):
            raise GateError("server identity differs from manifest")
        ssl = conn.execute(
            text("select ssl, version, cipher from pg_stat_ssl where pid=pg_backend_pid()")
        ).one_or_none()
        if ssl is None or not ssl.ssl:
            raise GateError("negotiated TLS required")
        if runtime:
            flags = conn.execute(
                text(
                    "select rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                    "from pg_roles where rolname=current_user"
                )
            ).one()
            owner = conn.execute(
                text(
                    "select exists(select 1 from pg_class c join pg_namespace n "
                    "on n.oid=c.relnamespace where c.relowner=(select oid from pg_roles "
                    "where rolname=current_user) and n.nspname='public')"
                )
            ).scalar_one()
            ddl = conn.execute(
                text("select has_schema_privilege(current_user, 'public', 'CREATE')")
            ).scalar_one()
            if any(flags) or owner or ddl:
                raise GateError("runtime role has owner/DDL/elevated privileges")
        installed = conn.execute(text("select to_regclass('public.alembic_version')")).scalar_one()
        head = (
            conn.execute(text("select version_num from alembic_version")).scalar_one()
            if installed
            else None
        )
    return {
        "target_fingerprint": hashlib.sha256(
            (target.target_id + "|" + target.host + "|" + target.database).encode()
        ).hexdigest()[:16],
        "server_version": version,
        "tls": True,
        "tls_version": ssl.version,
        "tls_cipher": ssl.cipher,
        "verification": "verify-full with explicit root",
        "migration_head": head,
        "runtime_nonowner": runtime,
    }


def write_private(path: Path, data: dict[str, Any]) -> None:
    # Exclusive creation avoids replacing any operator report or following a symlink.
    with open(path, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as out:
        json.dump(data, out, indent=2)


def run(args: argparse.Namespace) -> None:
    target, settings = selected(args.manifest)
    assert settings.database_url is not None
    engine = engine_for(settings.database_url, settings)
    try:
        report = preflight(engine, target)
        if args.phase == "preflight":
            print(json.dumps(report, sort_keys=True))
            return
        raw = os.environ.get("DATA001_MIGRATION_DATABASE_URL")
        if not raw:
            raise GateError("migration/operator connection required for this phase")
        check_target(raw, settings, target, target.migration_role)
        owner = engine_for(raw, settings)
        try:
            preflight(owner, target, runtime=False)
            if args.phase == "migrate":
                if not target.allow_migrate:
                    raise GateError("manifest does not permit migrations")
                cfg = Config(str(ROOT / "alembic.ini"))
                cfg.attributes["database_url"] = raw
                command.upgrade(cfg, "head")
                assert preflight(engine, target)["migration_head"] == REQUIRED_MIGRATION_REVISION
                print("Approved migration applied; runtime head verified.")
                return
            if not target.allow_test_writes:
                raise GateError("manifest does not permit namespaced synthetic writes")
            if report["migration_head"] != REQUIRED_MIGRATION_REVISION:
                raise GateError("migration head unavailable; use separate migration phase")
            if args.receipt is None:
                raise GateError("private receipt path required before any synthetic writes")
            if args.phase == "cleanup":
                receipt = json.loads(args.receipt.read_text())
                org = receipt.get("organization_id", "")
                if (
                    receipt.get("target_fingerprint") != report["target_fingerprint"]
                    or not isinstance(org, str)
                    or not org.startswith("data001-")
                    or len(org) != 40
                ):
                    raise GateError("cleanup requires this target's exact owned receipt")
                with owner.begin() as conn:
                    row = (
                        conn.execute(
                            select(organizations).where(organizations.c.id == org).with_for_update()
                        )
                        .mappings()
                        .one()
                    )
                    if (
                        row["display_name"] != "SYNTHETIC DATA-001 " + org
                        or not row["is_simulated"]
                    ):
                        raise GateError("cleanup ownership label mismatch")
                    for table in reversed(APPLICATION_TABLES):
                        conn.execute(delete(table).where(table.c.organization_id == org))
                    conn.execute(delete(organizations).where(organizations.c.id == org))
                print(
                    "Only receipt-owned synthetic organization/C rows removed; "
                    "B temp files were local."
                )
                return
            org = "data001-" + secrets.token_hex(16)
            write_private(
                args.receipt,
                {**report, "organization_id": org, "status": "started-retain-for-reconciliation"},
            )
            with owner.begin() as conn:
                conn.execute(
                    insert(organizations).values(
                        id=org,
                        display_name="SYNTHETIC DATA-001 " + org,
                        provenance_class="simulated",
                        is_simulated=True,
                    )
                )
            from scripts.data001_workflow import verify_workflow

            with TemporaryDirectory(prefix="data001-b-fixture-") as directory:
                test_settings = settings.model_copy(
                    update={
                        "environment": "test",
                        "auth_mode": "fixture",
                        "answer_store_backend": "postgres",
                        "dev_b_store_dir": Path(directory),
                        "db_pool_size": 1,
                        "db_max_overflow": 0,
                    }
                )
                evidence = verify_workflow(test_settings, org)
            # Keep the original ownership receipt even on failure; write a separate success report.
            write_private(
                args.receipt.with_suffix(".verified.json"),
                {**report, **evidence, "status": "TigerData-verified"},
            )
            print(
                "TigerData verification passed; sanitized private evidence written. "
                "Explicit owned cleanup remains separate."
            )
        finally:
            owner.dispose()
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--phase", choices=("preflight", "migrate", "verify", "cleanup"), default="preflight"
    )
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        run(args)
        return 0
    except GateError as exc:
        print("TigerData gate refused: " + str(exc), file=sys.stderr)
        return 2
    except Exception:
        # External DB/driver errors may contain endpoint or submitted values. Never print them.
        print(
            "TigerData gate unavailable/failed. Check isolated manifest, opt-in, TLS roots, "
            "role credentials, migration head and private reconciliation receipt; "
            "no fallback or automatic retry.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
