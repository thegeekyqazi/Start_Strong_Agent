"""Supported public entry points of the funding feature (owner: Dev B funding/B1).

Other features (automation's context selection; a future Dev C requirement consumer) may
import only these factories plus the models, protocol and errors in
``strongstart_contracts.funding_review`` (and ``strongstart_contracts.discovery`` for the
capture reader/catalog). Everything else in this package is private.

``FundingCaseReader.get_version(org, case_id, version)`` returns one exact immutable
version with its digest, review record (if any), source status and projections;
``get_current`` returns the latest. Unknown and other-organization IDs raise
``FundingCaseNotFound`` identically; production raises ``CapabilityUnavailable``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from strongstart_contracts.funding_review import (
    FundingCaseReader,
    UnconfiguredFundingCaseReader,
)

from ...config import Settings, get_settings
from ..dev_b_store.factory import local_store
from .cases import FundingCaseRepository
from .deps import get_capture_store


def build_funding_case_repository(settings: Settings) -> FundingCaseRepository | None:
    store = local_store(settings)
    if store is None:
        return None
    return FundingCaseRepository(store, get_capture_store(settings))


def build_funding_case_reader(settings: Settings) -> FundingCaseReader:
    repo = build_funding_case_repository(settings)
    return repo if repo is not None else UnconfiguredFundingCaseReader()


def get_funding_case_reader(
    settings: Annotated[Settings, Depends(get_settings)],
) -> FundingCaseReader:
    return build_funding_case_reader(settings)


__all__ = [
    "build_funding_case_reader",
    "build_funding_case_repository",
    "get_funding_case_reader",
]
