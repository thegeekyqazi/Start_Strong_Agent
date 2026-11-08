"""Idempotent demo seed: upserts synthetic fixture organizations. Never targets production."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import func

from strongstart_contracts import load_fixture_bundle

from .config import get_settings
from .db import bootstrap_metadata, get_engine, organizations

DEFAULT_BUNDLE = Path("tests/fixtures/demo/demo-bundle-v1.json")


def seed_demo(engine: Engine, bundle_path: Path) -> int:
    bundle = load_fixture_bundle(bundle_path)
    if not bundle.provenance.is_simulated:
        raise ValueError("refusing to seed a bundle that is not labelled simulated")
    with engine.begin() as conn:
        for org in bundle.organizations:
            stmt = insert(organizations).values(
                id=org.organization_id,
                display_name=org.display_name,
                provenance_class=org.provenance.provenance_class.value,
                is_simulated=org.provenance.is_simulated,
            )
            conn.execute(
                stmt.on_conflict_do_update(
                    index_elements=[organizations.c.id],
                    set_={
                        "display_name": stmt.excluded.display_name,
                        "provenance_class": stmt.excluded.provenance_class,
                        "is_simulated": stmt.excluded.is_simulated,
                        "updated_at": func.now(),
                    },
                )
            )
        meta = insert(bootstrap_metadata).values(
            key="demo_seed_bundle",
            value=f"{bundle.fixture_bundle_id}@{bundle.fixture_version}",
        )
        conn.execute(
            meta.on_conflict_do_update(
                index_elements=[bootstrap_metadata.c.key],
                set_={"value": meta.excluded.value, "updated_at": func.now()},
            )
        )
    return len(bundle.organizations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed synthetic demo metadata (idempotent).")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    args = parser.parse_args(argv)
    settings = get_settings()
    if settings.environment == "production":
        print("refusing to seed demo data in production", file=sys.stderr)
        return 1
    if not settings.database_url:
        print("STRONGSTART_DATABASE_URL is not set", file=sys.stderr)
        return 1
    count = seed_demo(get_engine(settings.database_url), args.bundle)
    print(f"seeded {count} synthetic organization(s) from {args.bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
