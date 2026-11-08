"""Hosted gate refuses unsafe selection before opening any connection."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

import pytest
from pydantic import ValidationError

from scripts.tigerdata_smoke import GateError, Target, check_target, selected, write_private
from strongstart_api.config import Settings


def manifest() -> dict[str, Any]:
    return dict(
        target_id="owner-isolated-test",
        provider="tigerdata",
        environment="isolated-development-test",
        owner_selected=True,
        host="isolated.example",
        database="owned_test",
        migration_role="migrator",
        runtime_role="application",
    )


def test_no_configuration_refuses_before_connection(tmp_path, monkeypatch):
    monkeypatch.delenv("DATA001_TIGERDATA_OPT_IN", raising=False)
    with pytest.raises(GateError, match="explicit isolated"):
        selected(None)
    result = subprocess.run(
        [sys.executable, "-m", "scripts.tigerdata_smoke"],
        env={k: v for k, v in os.environ.items() if k not in {"DATA001_TIGERDATA_OPT_IN"}},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2 and "explicit isolated target" in result.stderr
    assert "postgresql" not in result.stderr


@pytest.mark.parametrize(
    "field,value",
    [
        ("environment", "production"),
        ("environment", "shared"),
        ("provider", "guessed-from-hostname"),
        ("owner_selected", False),
    ],
)
def test_manifest_requires_owner_selected_isolation(field, value):
    data = manifest()
    data[field] = value
    with pytest.raises(ValidationError):
        Target.model_validate(data)


def test_target_cannot_silently_switch_database_or_role():
    target = Target.model_validate(manifest())
    settings = Settings(
        _env_file=None,
        database_profile="tigerdata",
        db_connection_budget=7,
        db_sslrootcert="system",
    )
    for host, database, user in [
        ("other.example", "owned_test", "application"),
        ("isolated.example", "shared", "application"),
        ("isolated.example", "owned_test", "migrator"),
    ]:
        with pytest.raises(GateError, match="does not match"):
            check_target(
                f"postgresql://{user}:private-canary@{host}/{database}?sslmode=verify-full",
                settings,
                target,
                target.runtime_role,
            )


def test_private_receipt_is_exclusive_and_contains_only_supplied_evidence(tmp_path):
    receipt = tmp_path / "receipt.json"
    write_private(receipt, {"organization_id": "data001-example"})
    assert receipt.stat().st_mode & 0o777 == 0o600
    assert json.loads(receipt.read_text()) == {"organization_id": "data001-example"}
    with pytest.raises(FileExistsError):
        write_private(receipt, {"overwrite": True})
