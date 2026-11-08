"""Bounded Chromium entry and read-back for a registered fixture (B2-AUTO-002 s8).

Reuses the inspector's restricted session (ephemeral loopback fixture server, request
routing, blocked WebSockets/popups/downloads/service workers, ``finally`` cleanup).

The only operations are Playwright ``fill``, ``select_option`` and ``check``, on selectors
from the trusted registry. There is no click, keyboard, submit, upload, navigation or
untrusted script. DOM reads use the fixed scripts below (trusted application code).

In one document:

1. inspect the structure before any mutation, and compare the fingerprint and page hash;
2. for each action: check the control state and branch, call ``before_write`` (C
   recheck plus persisted intent), do one registered operation, read the **live**
   property back, compare it exactly, then call ``after_write`` (postcheck);
3. reread every written field once at the end.

Stops at the first mismatch, stale input or unexpected state. It never retries a write or
repairs a value. A timeout after a possible write is ``outcome_unknown``.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from strongstart_contracts.automation_prefill import PrefillGrant

from ..dev_b_store.core import canonical_json, sha256_hex
from .inspection import fingerprint, observed_fields
from .inspector import ENUMERATE_JS, READY_JS, ActivityLog, InspectionFailure, RestrictedSession
from .inspector import restricted_fixture_session as _session
from .prefill_deps import PrefillBrowserConfig
from .registry import PrefillControl

SAFE_OPTION = re.compile(r"^[a-z0-9_-]{1,64}$")

STATE_JS = r"""
(selector) => {
  const vis = (el) => typeof el.checkVisibility === 'function' ? el.checkVisibility()
    : !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  return Array.from(document.querySelectorAll(selector)).map((el) => {
    const tag = el.tagName.toLowerCase();
    return {
      tag, type: tag === 'input' ? (el.getAttribute('type') || 'text').toLowerCase() : null,
      visible: vis(el), disabled: !!el.disabled, readonly: el.hasAttribute('readonly'),
      optionValue: (el.type === 'radio' || el.type === 'checkbox') ? el.value : null,
      options: tag === 'select' ? Array.from(el.options).map((o) => o.value) : [],
      maxLength: (tag === 'input' || tag === 'textarea') && el.maxLength >= 0 ? el.maxLength : null,
    };
  });
}
"""

SETTLE_JS = "() => new Promise((resolve) => setTimeout(resolve, 0))"

READBACK_JS = r"""
(spec) => {
  const els = Array.from(document.querySelectorAll(spec.selector));
  if (spec.group) {
    return { count: els.length, checked: els.filter((e) => e.checked).map((e) => e.value) };
  }
  if (els.length !== 1) return { count: els.length };
  const el = els[0];
  if (el.tagName.toLowerCase() === 'select') {
    return { count: 1, checked: Array.from(el.selectedOptions).map((o) => o.value) };
  }
  return { count: 1, value: el.value };
}
"""


@dataclass(frozen=True)
class BrowserAction:
    index: int
    control: PrefillControl
    operation: Literal["fill", "select_option", "check"]
    value: str | None
    choices: tuple[str, ...]
    comparison: str
    conditional: bool


@dataclass
class ReadBack:
    value: str | None
    choices: list[str] | None
    count: int


@dataclass
class FieldOutcome:
    index: int
    state: str
    reason: str | None = None
    actual_value: str | None = None
    actual_sha256: str | None = None
    actual_length_utf16: int | None = None
    compared_intended_sha256: str | None = None
    compared_actual_sha256: str | None = None
    result: Literal["match", "mismatch", "not_compared"] = "not_compared"


class Hooks(Protocol):
    def before_write(self, index: int) -> str | None:
        """Live rechecks plus persisted intent. Returns a stop reason, or None to proceed."""
        ...

    def after_write(self, index: int, outcome: FieldOutcome) -> str | None:
        """Persist the read-back and postcheck. Returns a stop reason, or None to continue."""
        ...


@dataclass
class BrowserOutcome:
    stage: Literal["blocked_before_entry", "completed", "stopped", "unknown"]
    reason: str | None
    fields: dict[int, FieldOutcome] = field(default_factory=dict)
    final_reread: Literal["all_match", "mismatch", "not_run"] = "not_run"
    activity: ActivityLog | None = None
    fixture_server_mutation_hits: int = 0
    browser_version: str | None = None
    operations: list[str] = field(default_factory=list)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utf16(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def compare(action: BrowserAction, rb: ReadBack) -> FieldOutcome:
    out = FieldOutcome(index=action.index, state="mismatch")
    if action.value is not None:
        actual = rb.value
        if actual is None:
            out.reason = "control_missing_at_readback"
            return out
        out.actual_value = actual
        out.actual_sha256 = _sha(actual)
        out.actual_length_utf16 = _utf16(actual)
        intended = action.value
        if action.comparison == "b2-readback-textarea-crlf/1":
            intended, actual = intended.replace("\r\n", "\n"), actual.replace("\r\n", "\n")
        out.compared_intended_sha256 = _sha(intended)
        out.compared_actual_sha256 = _sha(actual)
        ok = intended == actual
    else:
        got = rb.choices
        if got is None:
            out.reason = "control_missing_at_readback"
            return out
        out.actual_value = ",".join(got)
        out.actual_sha256 = sha256_hex(canonical_json(got))
        out.compared_intended_sha256 = sha256_hex(canonical_json(list(action.choices)))
        out.compared_actual_sha256 = out.actual_sha256
        ok = list(action.choices) == got
    out.result = "match" if ok else "mismatch"
    if ok:
        out.state = "entered_verified"
    else:
        out.reason = "readback_mismatch"
    return out


def _state_problem(control: PrefillControl, states: list[dict[str, Any]]) -> str | None:
    if control.is_group:
        if [s.get("optionValue") for s in states] != list(control.options):
            return "group_options_changed"
        if any(s.get("type") != control.control for s in states):
            return "control_type_changed"
    else:
        if len(states) != 1:
            return "control_missing" if not states else "control_ambiguous"
        s = states[0]
        expected = {"text": ("input", "text"), "number": ("input", "number"),
                    "textarea": ("textarea", None), "select": ("select", None)}  # fmt: skip
        if (s.get("tag"), s.get("type")) != expected[control.control]:
            return "control_type_changed"
        if control.control == "select" and list(s.get("options") or []) != list(control.options):
            return "select_options_changed"
        if (
            control.native_max_length is not None
            and s.get("maxLength") != control.native_max_length
        ):
            return "native_constraint_changed"
    for s in states:
        if not s.get("visible"):
            return "control_not_visible"
        if s.get("disabled"):
            return "control_disabled"
        if s.get("readonly"):
            return "control_readonly"
    return None


def _readback(session: RestrictedSession, control: PrefillControl) -> ReadBack:
    raw = session.page.evaluate(
        READBACK_JS, {"selector": control.selector, "group": control.is_group}
    )
    return ReadBack(value=raw.get("value"), choices=raw.get("checked"), count=int(raw["count"]))


def _structure_fp(session: RestrictedSession, config: PrefillBrowserConfig) -> str:
    raw = session.page.evaluate(
        ENUMERATE_JS,
        {
            "maxFields": config.max_fields,
            "maxText": config.max_text_chars,
            "maxOptions": config.max_options,
        },
    )
    if raw.get("truncated"):
        return "truncated"
    return fingerprint(observed_fields(list(raw["fields"])))


def execute_actions(
    page_html: bytes,
    *,
    ready_selector: str,
    expected_fingerprint: str,
    expected_page_sha256: str,
    actions: list[BrowserAction],
    hooks: Hooks,
    config: PrefillBrowserConfig,
    extra_pages: dict[str, bytes] | None = None,
    grant: PrefillGrant | None = None,
) -> BrowserOutcome:
    outcome = BrowserOutcome(stage="blocked_before_entry", reason=None)
    # Even an internal caller must supply the claimed, exact command. Live expiry,
    # epoch and approval checks remain in the persisted runner hooks before each write.
    if not _grant_matches(grant, actions, expected_fingerprint, expected_page_sha256):
        outcome.reason = "invalid_execution_grant"
        return outcome
    written: list[BrowserAction] = []
    in_flight: int | None = None
    live: list[RestrictedSession] = []
    try:
        with _session(
            page_html,
            ready_selector=ready_selector,
            timeout_ms=config.execution_timeout_ms,
            executable_path=config.executable_path,
            extra_pages=extra_pages,
        ) as s:
            live.append(s)
            outcome.activity = s.log
            outcome.browser_version = str(s.browser.version)
            portal_url = s.page.url
            op_ms = float(config.operation_timeout_ms)
            # 1. Execution-time inspection in this same document, before any mutation.
            if _sha_bytes(page_html) != expected_page_sha256:
                outcome.reason = "page_hash_changed"
                return outcome
            if _structure_fp(s, config) != expected_fingerprint:
                outcome.reason = "fingerprint_changed"
                return outcome
            navigations = s.log.navigations_blocked
            for action in actions:
                ctl = action.control
                # Let pending route events settle, then refuse to continue on a page that tried
                # to navigate/submit: a blocked navigation leaves the frame mid-navigation.
                s.page.evaluate(SETTLE_JS)
                if s.page.url != portal_url or s.log.navigations_blocked > navigations:
                    outcome.stage, outcome.reason = _stop(written), "page_attempted_navigation"
                    break
                if action.conditional:
                    # Wait only for the registered branch condition, then re-check the
                    # structure: only the declared visibility transition is allowed.
                    ready = False
                    waited = 0.0
                    while waited < config.reveal_timeout_ms:
                        if s.page.evaluate(READY_JS, ctl.reveal_selector):
                            ready = True
                            break
                        s.page.wait_for_timeout(50)
                        waited += 50
                    if not ready:
                        outcome.fields[action.index] = FieldOutcome(
                            action.index, "blocked_before_write", "branch_not_revealed"
                        )
                        outcome.stage, outcome.reason = _stop(written), "branch_not_revealed"
                        break
                    if _structure_fp(s, config) != expected_fingerprint:
                        outcome.fields[action.index] = FieldOutcome(
                            action.index, "blocked_before_write", "structure_changed"
                        )
                        outcome.stage, outcome.reason = _stop(written), "structure_changed"
                        break
                problem = _state_problem(ctl, s.page.evaluate(STATE_JS, ctl.selector))
                if problem is None and action.operation == "check":
                    problem = next(
                        (f"unsafe_option:{v}" for v in action.choices if not SAFE_OPTION.match(v)),
                        None,
                    )
                if problem is not None:
                    outcome.fields[action.index] = FieldOutcome(
                        action.index, "blocked_before_write", problem
                    )
                    outcome.stage, outcome.reason = _stop(written), problem
                    break
                stop = hooks.before_write(action.index)
                if stop is not None:
                    outcome.fields[action.index] = FieldOutcome(
                        action.index, "blocked_before_write", stop
                    )
                    outcome.stage, outcome.reason = _stop(written), stop
                    break
                in_flight = action.index
                locator = s.page.locator(ctl.selector)
                try:
                    if action.operation == "fill":
                        assert action.value is not None
                        locator.fill(action.value, timeout=min(op_ms, s.remaining()))
                    elif action.operation == "select_option":
                        locator.select_option(
                            value=list(action.choices), timeout=min(op_ms, s.remaining())
                        )
                    else:
                        for v in action.choices:
                            s.page.locator(f'{ctl.selector}[value="{v}"]').check(
                                timeout=min(op_ms, s.remaining())
                            )
                    outcome.operations.append(f"{action.operation}:{ctl.field_id}")
                except s.playwright_timeout:
                    outcome.operations.append(f"{action.operation}:{ctl.field_id}:timeout")
                    outcome.fields[action.index] = FieldOutcome(
                        action.index, "outcome_unknown", "operation_timeout_after_possible_write"
                    )
                    outcome.stage, outcome.reason = "unknown", "operation_timeout"
                    return outcome
                except s.playwright_error:
                    outcome.operations.append(f"{action.operation}:{ctl.field_id}:error")
                    written.append(action)
                    rb = _readback(s, ctl)
                    result = compare(action, rb)
                    result.state = "write_failed"
                    result.reason = "operation_rejected_by_browser"
                    outcome.fields[action.index] = result
                    hooks.after_write(action.index, result)
                    outcome.stage, outcome.reason = "stopped", "operation_rejected_by_browser"
                    in_flight = None
                    break
                written.append(action)
                result = compare(action, _readback(s, ctl))
                in_flight = None
                stop = hooks.after_write(action.index, result)
                if result.state == "entered_verified" and stop is not None:
                    result.state, result.reason = "entered_then_stale", stop
                outcome.fields[action.index] = result
                if result.state != "entered_verified":
                    outcome.stage, outcome.reason = "stopped", result.reason
                    break
            else:
                outcome.stage = "completed" if actions else "blocked_before_entry"
                s.page.evaluate(SETTLE_JS)
                if s.page.url != portal_url or s.log.navigations_blocked > navigations:
                    outcome.stage, outcome.reason = "stopped", "page_attempted_navigation"
            # 3. Final reread: a later script must not silently overwrite a verified value.
            if written:
                all_ok = True
                for action in written:
                    current = outcome.fields[action.index]
                    if current.state not in ("entered_verified", "entered_then_stale"):
                        continue
                    again = compare(action, _readback(s, action.control))
                    if again.result != "match":
                        all_ok = False
                        again.state, again.reason = "overwritten_after_verify", "final_reread"
                        outcome.fields[action.index] = again
                outcome.final_reread = "all_match" if all_ok else "mismatch"
                if not all_ok and outcome.stage == "completed":
                    outcome.stage, outcome.reason = "stopped", "final_reread_mismatch"
    except InspectionFailure as exc:
        if in_flight is not None or written:
            if in_flight is not None:
                outcome.fields[in_flight] = FieldOutcome(
                    in_flight, "outcome_unknown", "budget_exhausted_after_possible_write"
                )
            outcome.stage, outcome.reason = "unknown", f"{exc.reason}_after_entry"
        else:
            outcome.stage, outcome.reason = "blocked_before_entry", exc.reason
    finally:
        if live:  # read after the session closed (browser and server are shut down)
            outcome.fixture_server_mutation_hits = live[0].server.mutation_hits
    return outcome


def _stop(written: list[BrowserAction]) -> Literal["blocked_before_entry", "stopped"]:
    return "stopped" if written else "blocked_before_entry"


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _grant_matches(
    grant: PrefillGrant | None, actions: list[BrowserAction], fp: str, page_sha: str
) -> bool:
    if grant is None:
        return False
    record = grant.model_dump(mode="json")
    record.pop("grant_sha256")
    if sha256_hex(canonical_json(record)) != grant.grant_sha256:
        return False
    if grant.expected_fingerprint != fp or grant.page_sha256 != page_sha:
        return False
    expected = [
        (o.action_index, o.field_id, o.operation, o.intended_sha256) for o in grant.operations
    ]
    actual = [
        (
            a.index,
            a.control.field_id,
            a.operation,
            _sha(a.value) if a.value is not None else sha256_hex(canonical_json(list(a.choices))),
        )
        for a in actions
    ]
    return bool(actions) and expected == actual
