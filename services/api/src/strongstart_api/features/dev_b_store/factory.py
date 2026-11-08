"""Composition helper: the Dev B local store for these settings, or None in production."""

from __future__ import annotations

from ...config import Settings
from .core import LocalVersionStore


def local_store(settings: Settings) -> LocalVersionStore | None:
    if settings.environment == "production":
        return None  # development/test only; production uses unconfigured adapters
    return LocalVersionStore(
        settings.dev_b_store_dir,
        allow_reduced_durability=settings.dev_b_store_allow_reduced_durability,
    )
