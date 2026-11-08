"""Feature registry. Routers are registered once here during INIT-001.

| Package       | Owner | UI entry point                         |
| ------------- | ----- | -------------------------------------- |
| knowledge     | A     | apps/web/src/features/knowledge        |
| funding       | B1    | apps/web/src/features/funding          |
| automation    | B2    | apps/web/src/features/automation       |
| applications  | C     | apps/web/src/features/{applications,review,skills} |
"""

from fastapi import APIRouter

from strongstart_contracts import Capability

from . import applications, automation, funding, knowledge

FEATURE_ROUTERS: list[APIRouter] = [
    knowledge.router,
    funding.router,
    automation.router,
    applications.router,
]

FEATURE_CAPABILITIES: list[Capability] = [
    *knowledge.CAPABILITIES,
    *funding.CAPABILITIES,
    *automation.CAPABILITIES,
    *applications.CAPABILITIES,
]
