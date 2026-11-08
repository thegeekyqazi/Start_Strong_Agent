from __future__ import annotations

import ast
from pathlib import Path

from strongstart_api.features.validation.registry import DEFINITIONS
from tests.conftest import REPO_ROOT

RULES = (
    REPO_ROOT
    / "services"
    / "api"
    / "src"
    / "strongstart_api"
    / "features"
    / "validation"
    / "rules.py"
)


def test_rule_ids_and_evaluators_are_unique() -> None:
    assert len({item.rule_id for item in DEFINITIONS}) == len(DEFINITIONS)
    assert len({item.evaluator for item in DEFINITIONS}) == len(DEFINITIONS)


def test_pure_evaluator_module_has_no_effectful_imports() -> None:
    tree = ast.parse(Path(RULES).read_text(encoding="utf-8"))
    forbidden = {"sqlalchemy", "httpx", "requests", "socket", "subprocess"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(forbidden)
    assert "datetime.now" not in Path(RULES).read_text(encoding="utf-8")
