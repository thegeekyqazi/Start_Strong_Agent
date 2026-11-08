"""Server-registered automation fixtures (B2-AUTO-001 s5). Clients choose IDs, never paths/URLs.

Every fixture here is the Strong Start team's own synthetic, engineering-derived
material (engineering plan v1.1 s7; ``original_guide_present=false``). The
representative portal is not the United Way portal and is not a verified grant cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

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
            "rep-prefill-definition-v1",
            "structured_definition",
            "definitions/rep-prefill-definition-v1.json",
            "B2-AUTO-002 prefill demonstration definition (unambiguous native constraints, "
            "typed choices, one conditional child, one word-limited and one attachment field).",
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


# --------------------------------------------------------------------------- prefill targets
# B2-AUTO-002 s6.1: registered prefill targets. The server derives every selector, control
# type, option set and native constraint from this trusted registry; clients send IDs only.

PrefillControlType = Literal["text", "textarea", "number", "select", "radio", "checkbox", "file"]


@dataclass(frozen=True)
class PrefillControl:
    original_question_id: str
    field_id: str
    control: PrefillControlType
    dom_key: str  # DOM id for single controls, control name for radio/checkbox groups
    options: tuple[str, ...] = ()
    native_max_length: int | None = None
    minimum: str | None = None
    maximum: str | None = None
    condition: tuple[str, str] | None = None  # (parent original question ID, expected value)
    reveal_selector: str | None = None  # registered ready condition after the parent entry

    @property
    def is_group(self) -> bool:
        return self.control in ("radio", "checkbox")

    @property
    def selector(self) -> str:
        if self.is_group:
            return f'input[type="{self.control}"][name="{self.dom_key}"]'
        return f"#{self.dom_key}"


@dataclass(frozen=True)
class PrefillPortal:
    fixture_id: str
    page_file: str
    variant: Literal["prefill_positive", "prefill_negative", "representative_negative"]
    description: str
    form_id: str
    form_version: int
    definition_fixture_id: str
    controls: tuple[PrefillControl, ...]
    ready_selector: str = 'body[data-fixture-ready="true"]'
    origin_label: str = "fixture://rep-prefill.local"


REP_PREFILL_CONTROLS: tuple[PrefillControl, ...] = (
    PrefillControl("pf-org-name", "org-name-field", "text", "org-name", native_max_length=120),
    PrefillControl("pf-summary", "summary-field", "textarea", "summary", native_max_length=1000),
    PrefillControl(
        "pf-service-area", "service-area-field", "select", "service-area",
        options=("", "city", "region", "province"),
    ),
    PrefillControl(
        "pf-languages", "languages-field", "checkbox", "languages", options=("en", "fr", "other")
    ),
    PrefillControl(
        "pf-has-partners", "has-partners-field", "radio", "has_partners", options=("yes", "no")
    ),
    PrefillControl(
        "pf-partnership", "partnership-field", "textarea", "partnership",
        native_max_length=600, condition=("pf-has-partners", "yes"),
        reveal_selector="#partnership-section:not([hidden])",
    ),
    PrefillControl("pf-mission-words", "mission-words-field", "textarea", "mission-words"),
    PrefillControl(
        "pf-request-amount", "request-amount-field", "number", "request-amount",
        minimum="1000", maximum="50000",
    ),
    PrefillControl("pf-budget", "budget-field", "file", "budget"),
)  # fmt: skip

REP_PORTAL_PREFILL_CONTROLS: tuple[PrefillControl, ...] = (
    PrefillControl("rp-mission", "mission-field", "textarea", "mission", native_max_length=2000),
    PrefillControl("rp-services", "services-field", "textarea", "services"),
    PrefillControl(
        "rp-service-area", "service-area-field", "radio", "service_area",
        options=("city", "region", "province"),
    ),
    PrefillControl(
        "rp-pending-applications", "pending-applications-field", "textarea",
        "pending-applications", native_max_length=250,
    ),
    PrefillControl("rp-other-funding", "other-funding-field", "textarea", "other-funding"),
    PrefillControl(
        "rp-has-partners", "has-partners-field", "radio", "has_partners", options=("yes", "no")
    ),
    PrefillControl(
        "rp-partnership", "partnership-field", "textarea", "partnership",
        condition=("rp-has-partners", "yes"),
        reveal_selector="#partnership-section:not([hidden])",
    ),
    PrefillControl(
        "rp-request-amount", "request-amount-field", "number", "request-amount",
        minimum="20000", maximum="100000",
    ),
    PrefillControl("rp-financial-statement", "financial-statement-field", "file",
                   "financial-statement"),
)  # fmt: skip

# Prefill form versions: form_id -> {version: b2-form-fp/1 fingerprint}. Recorded from a real
# Chromium inspection of the registered page; a structural change needs a new version.
PREFILL_FORM_VERSIONS: dict[str, dict[int, str]] = {
    "rep-prefill": {1: "68587a4fb70f3db598a4d935adef1ec5c2c9faa602386dc4aefb38290f12ca35"},
    "rep-portal": FORM_VERSIONS["rep-portal"],
}


def _prefill(fixture_id: str, page: str, variant: Any, description: str) -> PrefillPortal:
    return PrefillPortal(
        fixture_id, page, variant, description, "rep-prefill", 1, "rep-prefill-definition-v1",
        REP_PREFILL_CONTROLS,
    )  # fmt: skip


PREFILL_PORTALS: dict[str, PrefillPortal] = {
    p.fixture_id: p
    for p in [
        _prefill("rep-prefill-v1", "rep-prefill-v1.html", "prefill_positive",
                 "Dedicated prefill form with unambiguous constraints."),
        _prefill("rep-prefill-v1-altered", "rep-prefill-v1-altered.html", "prefill_negative",
                 "Structure changed after mapping (control type and options)."),
        _prefill("rep-prefill-v1-truncating", "rep-prefill-v1-truncating.html",
                 "prefill_negative", "Page shrinks maxlength on focus (truncation)."),
        _prefill("rep-prefill-v1-replacing", "rep-prefill-v1-replacing.html", "prefill_negative",
                 "Page script replaces an entered value."),
        _prefill("rep-prefill-v1-overwrite", "rep-prefill-v1-overwrite.html", "prefill_negative",
                 "Page script overwrites an earlier verified field."),
        _prefill("rep-prefill-v1-stalling", "rep-prefill-v1-stalling.html", "prefill_negative",
                 "Page blocks its main thread during entry (timeout)."),
        _prefill("rep-prefill-v1-hostile", "rep-prefill-v1-hostile.html", "prefill_negative",
                 "Page attempts exfiltration, navigation, popups, downloads and submission."),
        PrefillPortal(
            "rep-portal-v1", "rep-portal-v1.html", "representative_negative",
            "B2-AUTO-001 representative portal: 350/500, Max 300 and 300/250 stay held.",
            "rep-portal", 1, "rep-portal-definition-v1", REP_PORTAL_PREFILL_CONTROLS,
            origin_label="fixture://rep-portal.local",
        ),
    ]
}  # fmt: skip


def prefill_page(portal: PrefillPortal) -> bytes:
    return read_fixture_bytes(f"portal/{portal.page_file}")
