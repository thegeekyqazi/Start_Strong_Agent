"""Clean imports of every workspace module (catches missing deps / circular imports)."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import strongstart_api
import strongstart_contracts

MODULES = sorted(
    m.name
    for pkg in (strongstart_api, strongstart_contracts)
    for m in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + ".")
)


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name: str) -> None:
    importlib.import_module(name)
