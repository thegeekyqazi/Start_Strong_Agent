"""Feature registry. Routers are registered once here during INIT-001.

| Package       | Owner | UI entry point                         |
| ------------- | ----- | -------------------------------------- |
| knowledge     | A     | apps/web/src/features/knowledge        |
| funding       | B1    | apps/web/src/features/funding          |
| automation    | B2    | apps/web/src/features/automation       |
| applications  | C     | apps/web/src/features/{applications,review}        |
| skills        | C     | apps/web/src/features/skills (C4-SKL-001)          |
"""

from fastapi import APIRouter

from strongstart_contracts import Capability

from ..config import Settings

# Load B before C: their supported factories now compose both directions. C's
# workspace imports B's public definition reader; B's prefill imports C's reader.
from . import automation

# isort: split
from . import applications, funding, knowledge, skills, validation

FEATURE_ROUTERS: list[APIRouter] = [
    knowledge.router,
    funding.router,
    automation.router,
    applications.router,
    skills.router,
    validation.router,
]

FEATURE_CAPABILITIES: list[Capability] = [
    *knowledge.CAPABILITIES,
    *funding.CAPABILITIES,
    *automation.CAPABILITIES,
    *applications.CAPABILITIES,
    *skills.CAPABILITIES,
    *validation.CAPABILITIES,
]


def feature_capabilities(settings: Settings) -> list[Capability]:
    """Runtime capabilities. A feature module may expose ``capabilities_for(settings)``
    to report configuration-dependent status; otherwise its static CAPABILITIES apply.
    """
    out: list[Capability] = []
    for module in (knowledge, funding, automation, applications, skills, validation):
        provider = getattr(module, "capabilities_for", None)
        out.extend(provider(settings) if provider is not None else module.CAPABILITIES)
    return out
