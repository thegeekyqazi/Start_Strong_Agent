"""Opt-in local synthetic managed A4 rehearsal. No approvals are injected.

Uses migrated PostgreSQL and the explicitly labelled test workspace; stops and removes
only its own synthetic SQL rows on Ctrl+C. Never enabled by the normal runtime factory.
Start the web dev server separately and approve through the normal C routes/UI.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import uvicorn

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.applications.deps import get_policy, get_workspace_source
from strongstart_api.features.automation.public import build_application_definition_reader
from tests.integration.a4_support import managed_environment
from tests.integration.managed_workspace import ManagedWorkspace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be 1..65535")
    configured = Settings()
    if not configured.database_url or configured.environment == "production":
        raise SystemExit("Local PostgreSQL required; production is refused.")
    with (
        managed_environment(configured.database_url) as managed,
        tempfile.TemporaryDirectory(prefix="int001-managed-") as temporary,
    ):
        settings = Settings(
            _env_file=None,
            environment="local",
            auth_mode="fixture",
            database_url=configured.database_url,
            dev_b_store_dir=Path(temporary) / "b-store",
        )
        app = create_app(settings)
        source = ManagedWorkspace(build_application_definition_reader(settings), managed)
        app.dependency_overrides[get_workspace_source] = lambda: source
        app.dependency_overrides[get_policy] = lambda: None
        print("SYNTHETIC managed rehearsal; temporary B files and process-local C approvals.")
        print("Test workspace uses real A4 DB evidence. No live provider calls.")
        print("Context:", managed.context)
        print(
            "Fact tokens:",
            " ".join(
                "{{fact:" + f.fact_id + "}}"
                for f in source.managed.facade.resolve_active("demo-org", managed.context).facts
            ),
        )
        print(
            "Replacement: POST /api/knowledge/packs/contexts/"
            + managed.context
            + "/activate/"
            + managed.manifests[1].pack_version_id
        )
        print(
            "Body:",
            json.dumps({"expected_active_pack_version_id": managed.manifests[0].pack_version_id}),
        )
        uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
