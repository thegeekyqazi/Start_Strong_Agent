from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory

from strongstart_api.db import REQUIRED_MIGRATION_REVISION
from tests.conftest import REPO_ROOT


def test_single_head_matches_required_revision() -> None:
    script = ScriptDirectory.from_config(Config(str(REPO_ROOT / "alembic.ini")))
    assert script.get_heads() == [REQUIRED_MIGRATION_REVISION]
