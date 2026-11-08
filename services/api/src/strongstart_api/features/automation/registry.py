"""Server-registered automation fixtures (B2-AUTO-001 s5). Clients choose IDs, never paths/URLs.

Every fixture here is the Strong Start team's own synthetic, engineering-derived
material (engineering plan v1.1 s7; ``original_guide_present=false``). The
representative portal is not the United Way portal and is not a verified grant cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from strongstart_contracts.automation_intake import FixtureEntry
from strongstart_contracts.common import Provenance, ProvenanceClass

FIXTURE_DIR = Path(__file__).parent / "fixtures"

FIXTURE_PROVENANCE = Provenance(
    provenance_class=ProvenanceClass.ENGINEERING_DERIVED,
    is_simulated=True,
    note=(
        "B2-AUTO-001 representative fixture derived from engineering plan v1.1 s7 "
        "(original_guide_present=false). Not the United Way portal, not verbatim funder "
        "questions, not a verified open grant cycle."
    ),
)
FIXTURE_LABEL = (
    "FIXTURE - engineering-derived representative material; not a funder source; "
    "original guide not parsed."
)


@dataclass(frozen=True)
class IntakeFixture:
    fixture_id: str
    kind: Literal["structured_definition", "html_form"]
    relative_path: str
    description: str


INTAKE_FIXTURES: dict[str, IntakeFixture] = {
    f.fixture_id: f
    for f in [
        IntakeFixture(
            "rep-portal-definition-v1",
            "structured_definition",
            "definitions/rep-portal-definition-v1.json",
            "Structured definition of the representative portal (9 questions incl. 350/500 "
            "conflict, Max 300 unknown unit, conditional section, attachment).",
        ),
        IntakeFixture(
            "rep-portal-v1-html",
            "html_form",
            "portal/rep-portal-v1.html",
            "Saved HTML of the representative portal page, parsed statically.",
        ),
    ]
}


@dataclass(frozen=True)
class ExpectedField:
    question_id: str
    field_id: str
    kind: Literal["single", "group"]
    key: str  # DOM id for single, control name for group
    field_type: Literal["text", "textarea", "number", "select", "file", "checkbox", "radio"]

    @property
    def selector(self) -> str:
        if self.kind == "single":
            return f"#{self.key}"
        return f'input[type="{self.field_type}"][name="{self.key}"]'


REP_PORTAL_EXPECTED_MAP: tuple[ExpectedField, ...] = (
    ExpectedField("rp-mission", "mission-field", "single", "mission", "textarea"),
    ExpectedField("rp-services", "services-field", "single", "services", "textarea"),
    ExpectedField("rp-service-area", "service-area-field", "group", "service_area", "radio"),
    ExpectedField(
        "rp-pending-applications",
        "pending-applications-field",
        "single",
        "pending-applications",
        "textarea",
    ),
    ExpectedField("rp-other-funding", "other-funding-field", "single", "other-funding", "textarea"),
    ExpectedField("rp-has-partners", "has-partners-field", "group", "has_partners", "radio"),
    ExpectedField("rp-partnership", "partnership-field", "single", "partnership", "textarea"),
    ExpectedField(
        "rp-request-amount", "request-amount-field", "single", "request-amount", "number"
    ),
    ExpectedField(
        "rp-financial-statement",
        "financial-statement-field",
        "single",
        "financial-statement",
        "file",
    ),
)

# Stored form-map versions: form_id -> {version: fingerprint (b2-form-fp/1)}.
# Recorded from a real Chromium inspection of portal/rep-portal-v1.html; a changed
# portal must get a new version rather than silently reusing this one.
FORM_VERSIONS: dict[str, dict[int, str]] = {
    "rep-portal": {1: "41ccba87c5f2a8be646e8883a8eed85920d71b8d3179cc4688fa57b0874716ac"},
}


@dataclass(frozen=True)
class PortalFixture:
    fixture_id: str
    page_file: str
    variant: Literal["representative", "malformed"]
    description: str
    form_id: str = "rep-portal"
    definition_fixture_id: str = "rep-portal-definition-v1"
    ready_selector: str = 'body[data-fixture-ready="true"]'
    origin_label: str = "fixture://rep-portal.local"


PORTAL_FIXTURES: dict[str, PortalFixture] = {
    p.fixture_id: p
    for p in [
        PortalFixture("rep-portal-v1", "rep-portal-v1.html", "representative",
                      "Representative portal v1 (all minimum cases)."),
        PortalFixture("rep-portal-v1-duplicate", "rep-portal-v1-duplicate.html", "malformed",
                      "Two controls share id=services (ambiguous mapping)."),
        PortalFixture("rep-portal-v1-missing-label", "rep-portal-v1-missing-label.html",
                      "malformed", "other-funding control has no label."),
        PortalFixture("rep-portal-v1-unsupported-widget", "rep-portal-v1-unsupported-widget.html",
                      "malformed", "services is a contenteditable widget."),
        PortalFixture("rep-portal-v1-altered", "rep-portal-v1-altered.html", "malformed",
                      "Form changed after mapping (renamed control, changed option)."),
        PortalFixture("rep-portal-v1-dynamic", "rep-portal-v1-dynamic.html", "malformed",
                      "Conditional section inserted by script before readiness."),
        PortalFixture("rep-portal-v1-hostile", "rep-portal-v1-hostile.html", "malformed",
                      "Page attempts external/private loads, POST, popup, download, navigation."),
        PortalFixture("rep-portal-v1-never-ready", "rep-portal-v1-never-ready.html", "malformed",
                      "Readiness is never declared (timeout)."),
    ]
}  # fmt: skip


def read_fixture_bytes(relative_path: str) -> bytes:
    """Read a registered fixture file, confined to the fixture directory."""
    base = FIXTURE_DIR.resolve()
    path = (base / relative_path).resolve()
    if base not in path.parents or not path.is_file():
        raise FileNotFoundError("fixture file is not inside the fixture directory")
    return path.read_bytes()


def portal_page(fixture: PortalFixture) -> bytes:
    return read_fixture_bytes(f"portal/{fixture.page_file}")


def fixture_entries(capture_entries: list[FixtureEntry]) -> list[FixtureEntry]:
    out = [
        FixtureEntry(
            fixture_id=f.fixture_id,
            kind=f.kind,
            variant="representative",
            label=FIXTURE_LABEL,
            description=f.description,
        )
        for f in INTAKE_FIXTURES.values()
    ]
    out += [
        FixtureEntry(
            fixture_id=p.fixture_id,
            kind="portal",
            variant=p.variant,
            label=FIXTURE_LABEL,
            description=p.description,
        )
        for p in PORTAL_FIXTURES.values()
    ]
    return out + capture_entries
