"""Grant derivation, single-use claim and bounded execution of a prefill plan (s7, s8).

Order for POST /prefill-plans/{id}/execute:

1. load the exact saved plan and compare its hash with the request;
2. a completed or claimed idempotent command replays first. No browser is launched and
   nothing is rewritten;
3. derive the grant. It is refused (409, nothing claimed) when the plan is empty or
   expired, or when the runtime epoch differs;
4. claim atomically (run v1). Another command for the same plan gets 409;
5. pre-execution checks: definition and case currentness, a live C recheck of every
   action, and dependency currentness. Any failure becomes ``blocked_before_entry``;
   the browser is not launched;
6. Chromium entry with ``before_write``/``after_write`` hooks: live rechecks, intent
   recorded before each mutation, read-back persisted after;
7. completion recheck, then a final run version.

No store lock is held while C is called or Chromium runs.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from strongstart_contracts import CapabilityUnavailable, Provenance, ProvenanceClass
from strongstart_contracts.application_publication import (
    ApplicationDefinitionReader,
    QuestionIdMapping,
)
from strongstart_contracts.automation_prefill import (
    ApprovedPrefillReader,
    CurrentnessCheck,
    ExecutePrefillRequest,
    ExecutePrefillResult,
    FieldReceipt,
    FieldState,
    GrantedFieldOperation,
    PlannedFieldAction,
    PrefillActivity,
    PrefillDependencyCurrentness,
    PrefillGrant,
    PrefillPlan,
    PrefillRun,
    PrefillRunView,
    PrefillSelection,
    RunOutcome,
)
from strongstart_contracts.fixture_adapters import ApprovalNotUsable
from strongstart_contracts.funding_review import FundingCaseReader

from ..dev_b_store.core import canonical_json, sha256_hex
from . import prefill_browser
from .prefill_browser import BrowserAction, BrowserOutcome, FieldOutcome
from .prefill_deps import Clock, PrefillBrowserConfig
from .prefill_plan import content_problem
from .prefill_store import AlreadyClaimed, PrefillRepository, run_id_for
from .registry import PREFILL_PORTALS, PrefillPortal, prefill_page

RECEIPT_NOTE = (
    "Local demo receipt from real Chromium read-back of the registered fixture page. The "
    "ephemeral fixture page and browser closed after the run; nothing was submitted, signed, "
    "uploaded or saved to a funder portal."
)
HISTORY_NOTE = (
    "Historical receipt. It is not re-evaluated against current approvals; any new entry needs "
    "a newly prepared plan."
)
RUN_PROVENANCE = Provenance(
    provenance_class=ProvenanceClass.ENGINEERING_DERIVED,
    is_simulated=True,
    note="B2-AUTO-002 fixture prefill run (registered local fixture portal).",
)
DEADLINE_SLACK = timedelta(seconds=10)


class GrantRefused(Exception):
    def __init__(self, reason: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.details = details


def command_hash(plan: PrefillPlan) -> str:
    return sha256_hex(
        canonical_json({"op": "execute", "plan_id": plan.plan_id, "plan_sha256": plan.plan_sha256})
    )


def derive_grant(plan: PrefillPlan, actor_id: str, now: datetime) -> PrefillGrant:
    body: dict[str, Any] = {
        "grant_id": "grant-" + secrets.token_hex(12),
        "grant_sha256": "0" * 64,
        "plan_id": plan.plan_id,
        "plan_sha256": plan.plan_sha256,
        "organization_id": plan.organization_id,
        "actor_id": actor_id,
        "portal_fixture_id": plan.portal.portal_fixture_id,
        "logical_origin": plan.portal.logical_origin,
        "form_id": plan.portal.form_id,
        "form_version": plan.portal.form_version,
        "expected_fingerprint": plan.portal.expected_fingerprint,
        "operations": [
            GrantedFieldOperation(
                action_index=a.action_index,
                field_id=a.field_id,
                operation=a.operation,
                published_question_id=a.published_question_id,
                approval_snapshot_id=a.approval_snapshot_id,
                rendered_sha256=a.rendered_sha256,
                intended_sha256=a.intended_sha256,
            )
            for a in plan.actions
        ],
        "created_at": now,
        "expires_at": plan.expires_at,  # a grant never outlives its plan
        "nonce": secrets.token_hex(16),
        "runtime_epoch": plan.runtime_epoch,
        "budgets": plan.budgets,
    }
    draft = PrefillGrant.model_validate(body)
    record = draft.model_dump(mode="json")
    record.pop("grant_sha256")
    return PrefillGrant.model_validate(
        {**draft.model_dump(), "grant_sha256": sha256_hex(canonical_json(record))}
    )


def grant_problem(grant: PrefillGrant, plan: PrefillPlan) -> str | None:
    """Every action-critical value of the grant must still equal the plan (AUTO2-09)."""
    record = grant.model_dump(mode="json")
    record.pop("grant_sha256")
    if sha256_hex(canonical_json(record)) != grant.grant_sha256:
        return "grant_integrity"
    expected = (
        plan.plan_id,
        plan.plan_sha256,
        plan.organization_id,
        plan.portal.portal_fixture_id,
        plan.portal.logical_origin,
        plan.portal.form_id,
        plan.portal.form_version,
        plan.portal.expected_fingerprint,
        plan.runtime_epoch,
        plan.expires_at,
    )
    actual = (
        grant.plan_id,
        grant.plan_sha256,
        grant.organization_id,
        grant.portal_fixture_id,
        grant.logical_origin,
        grant.form_id,
        grant.form_version,
        grant.expected_fingerprint,
        grant.runtime_epoch,
        grant.expires_at,
    )
    if expected != actual:
        return "grant_mismatch"
    ops = [(o.action_index, o.field_id, o.operation, o.rendered_sha256) for o in grant.operations]
    if ops != [(a.action_index, a.field_id, a.operation, a.rendered_sha256) for a in plan.actions]:
        return "grant_operations_mismatch"
    return None


def _receipt(
    action: PlannedFieldAction, state: FieldState, out: FieldOutcome | None = None
) -> FieldReceipt:
    next_action = {
        "entered_verified": "Review the value in the portal before any staff submission.",
        "not_attempted": "Prepare a new plan to enter this field.",
        "blocked_before_write": "Resolve the reason, then prepare a new plan.",
        "write_in_flight": "Effect unknown: check the field manually before any action.",
        "outcome_unknown": "Effect unknown: check the field manually before any action.",
    }.get(state, "Do not rely on this field; review, edit or reapprove, then prepare a new plan.")
    return FieldReceipt(
        action_index=action.action_index,
        published_question_id=action.published_question_id,
        field_id=action.field_id,
        operation=action.operation,
        approval_snapshot_id=action.approval_snapshot_id,
        answer_version_id=action.answer_version_id,
        rendered_sha256=action.rendered_sha256,
        state=state,
        intended_sha256=action.intended_sha256,
        intended_length_utf16=action.intended_length_utf16,
        actual_value=out.actual_value if out else None,
        actual_sha256=out.actual_sha256 if out else None,
        actual_length_utf16=out.actual_length_utf16 if out else None,
        compared_intended_sha256=out.compared_intended_sha256 if out else None,
        compared_actual_sha256=out.compared_actual_sha256 if out else None,
        comparison=action.comparison,
        result=out.result if out else "not_compared",
        reason=out.reason if out else None,
        next_action=next_action,
    )


@dataclass
class ExecutionDeps:
    repo: PrefillRepository
    definitions: ApplicationDefinitionReader
    cases: FundingCaseReader | None
    reader: ApprovedPrefillReader
    currentness: PrefillDependencyCurrentness | None
    clock: Clock
    runtime_epoch: Callable[[], str]
    config: PrefillBrowserConfig
    browser: Callable[..., BrowserOutcome] | None = None  # None: real Chromium executor


def view_of(deps: ExecutionDeps, run: PrefillRun) -> PrefillRunView:
    """Read-time labels only; stored versions are never rewritten."""
    interrupted = run.status != "completed" and deps.clock() > run.deadline_at
    if run.status != "completed":
        steps = deps.repo.steps(run.organization_id, run.run_id, len(run.fields))
        fields = []
        for f in run.fields:
            step = steps.get(f.action_index)
            if step is not None:
                f = step
            if interrupted and f.state == "write_in_flight":
                f = f.model_copy(update={"state": "outcome_unknown", "reason": "interrupted"})
            fields.append(f)
        run = run.model_copy(update={"fields": fields})
    effective: RunOutcome = "outcome_unknown" if interrupted else run.outcome
    return PrefillRunView(
        run=run, effective_outcome=effective, interrupted=interrupted, history_note=HISTORY_NOTE
    )


def _definition_problem(deps: ExecutionDeps, plan: PrefillPlan) -> str | None:
    org, ref = plan.organization_id, plan.definition
    try:
        exact = deps.definitions.get_version(org, ref.question_set_id)
        current = deps.definitions.get_current(org, ref.definition_id)
    except Exception:
        return "definition_unavailable"
    if exact.integrity.normalized_digest != ref.publication_digest:
        return "definition_integrity"
    if current.version != ref.definition_version:
        return "definition_changed"
    if ref.funding_case_id is not None:
        if deps.cases is None:
            return "context_unavailable"
        try:
            case = deps.cases.get_current(org, ref.funding_case_id)
        except Exception:
            return "context_unavailable"
        if (
            case.version.version != ref.funding_case_version
            or case.version_digest != ref.funding_case_digest
        ):
            return "context_changed"
    return None


def _approval_problem(deps: ExecutionDeps, plan: PrefillPlan, a: PlannedFieldAction) -> str | None:
    try:
        content = deps.reader.resolve_for_prefill(plan.organization_id, a.approval_snapshot_id)
    except ApprovalNotUsable as exc:
        return f"approval_not_usable:{exc.reason}"
    except CapabilityUnavailable:
        return "approval_reader_unavailable"
    mapping = QuestionIdMapping(
        original_question_id=a.original_question_id,
        published_question_id=a.published_question_id,
        question_version=a.question_version,
        order=0,
    )
    problem = content_problem(
        content,
        organization_id=plan.organization_id,
        selection=PrefillSelection(
            published_question_id=a.published_question_id,
            approval_snapshot_id=a.approval_snapshot_id,
        ),
        mapping=mapping,
        question_set_id=plan.definition.question_set_id,
    )
    if problem is not None:
        return f"approval_changed:{problem[0]}"
    if (
        content.answer_version_id != a.answer_version_id
        or content.template_sha256 != a.template_sha256
        or content.rendered_sha256 != a.rendered_sha256
        or content.dependency_snapshot_sha256 != a.dependency_snapshot_sha256
    ):
        return "approval_changed:content_or_dependencies"
    if deps.currentness is not None:
        state = deps.currentness.check(plan.organization_id, plan.plan_id, list(a.dependencies))
        if state.status != "current":
            return f"dependency_{state.status}"
    return None


def _portal(plan: PrefillPlan) -> PrefillPortal | None:
    portal = PREFILL_PORTALS.get(plan.portal.portal_fixture_id)
    if portal is None or portal.form_id != plan.portal.form_id:
        return None
    return portal


def _browser_actions(plan: PrefillPlan, portal: PrefillPortal) -> list[BrowserAction] | None:
    controls = {c.field_id: c for c in portal.controls}
    bound = {f.field_id: f for f in plan.portal.fields}
    out: list[BrowserAction] = []
    for a in plan.actions:
        c, b = controls.get(a.field_id), bound.get(a.field_id)
        if (
            c is None
            or b is None
            or c.control != a.control
            or list(c.options) != b.options
            or c.native_max_length != b.native_max_length
        ):
            return None  # registry changed since planning
        out.append(
            BrowserAction(
                index=a.action_index,
                control=c,
                operation=a.operation,
                value=a.intended_value,
                choices=tuple(a.intended_choices),
                comparison=a.comparison,
                conditional=a.condition is not None,
            )
        )
    return out


class _Hooks:
    def __init__(self, deps: ExecutionDeps, plan: PrefillPlan, run: PrefillRun) -> None:
        self.deps, self.plan, self.run = deps, plan, run
        self.checks: list[CurrentnessCheck] = []

    def _check(self, stage: str, problem: str | None) -> str | None:
        self.checks.append(
            CurrentnessCheck(
                stage=stage,
                status="current" if problem is None else "stale",
                detail=problem or "approval, definition, grant and dependencies current",
            )
        )
        return problem

    def _live_problem(self, action: PlannedFieldAction) -> str | None:
        if self.deps.clock() > self.run.grant.expires_at:
            return "grant_expired"
        if self.deps.runtime_epoch() != self.run.grant.runtime_epoch:
            return "runtime_epoch_changed"
        return _definition_problem(self.deps, self.plan) or _approval_problem(
            self.deps, self.plan, action
        )

    def before_write(self, index: int) -> str | None:
        action = self.plan.actions[index]
        problem = self._check(f"before:{index}", self._live_problem(action))
        if problem is not None:
            return problem
        self.deps.repo.record_step(
            self.plan.organization_id, self.run.run_id, _receipt(action, "write_in_flight")
        )
        return None

    def after_write(self, index: int, outcome: FieldOutcome) -> str | None:
        action = self.plan.actions[index]
        problem = self._check(f"after:{index}", self._live_problem(action))
        state = outcome.state
        if state == "entered_verified" and problem is not None:
            state = "entered_then_stale"
        receipt = _receipt(action, state, outcome)  # type: ignore[arg-type]
        if problem is not None and state == "entered_then_stale":
            receipt = receipt.model_copy(update={"reason": problem})
        self.deps.repo.record_step(self.plan.organization_id, self.run.run_id, receipt)
        return problem


def _activity(outcome: BrowserOutcome) -> PrefillActivity:
    log = outcome.activity
    if log is None:
        return PrefillActivity(operations_performed=outcome.operations)
    return PrefillActivity(
        operations_performed=outcome.operations,
        requests_allowed=log.allowed,
        requests_blocked=log.blocked,
        mutation_requests_blocked=log.mutation_blocked,
        fixture_server_mutation_hits=outcome.fixture_server_mutation_hits,
        popups_blocked=log.popups,
        downloads_blocked=log.downloads,
        navigations_blocked=log.navigations_blocked,
        websockets_blocked=log.websockets_blocked,
        blocked_log=list(log.entries),
        blocked_log_truncated=log.truncated,
    )


def _finish(
    deps: ExecutionDeps,
    run: PrefillRun,
    *,
    outcome: RunOutcome,
    reason: str | None,
    fields: list[FieldReceipt],
    checks: list[CurrentnessCheck],
    browser: BrowserOutcome | None = None,
) -> PrefillRun:
    final = run.model_copy(
        update={
            "run_version": run.run_version + 1,
            "status": "completed",
            "outcome": outcome,
            "outcome_reason": reason,
            "finished_at": deps.clock(),
            "fields": fields,
            "checks": [*run.checks, *checks],
            "final_reread": browser.final_reread if browser else "not_run",
            "activity": _activity(browser) if browser else run.activity,
            "browser_version": browser.browser_version if browser else None,
        }
    )
    return deps.repo.append_run(run.organization_id, PrefillRun.model_validate(final.model_dump()))


def execute(
    deps: ExecutionDeps, plan: PrefillPlan, body: ExecutePrefillRequest, actor_id: str
) -> ExecutePrefillResult:
    org = plan.organization_id
    if body.expected_plan_sha256 != plan.plan_sha256:
        raise GrantRefused("plan_hash_mismatch", "the plan hash does not match the request")
    cmd = command_hash(plan)
    # Replay first: never relaunch or rewrite, regardless of expiry or later staleness.
    done = deps.repo.store.collection(org, "prefill-runs").replay(body.idempotency_key, cmd)
    if done is not None:
        latest = deps.repo.latest_run(org, run_id_for(plan.plan_id))
        return ExecutePrefillResult(replayed=True, run=view_of(deps, latest))
    existing = deps.repo.run_for_plan(org, plan.plan_id)
    if existing is not None:  # single use: another command already claimed this plan
        raise AlreadyClaimed(existing.run_id)
    now = deps.clock()
    if not plan.executable or not plan.actions:
        raise GrantRefused("plan_not_executable", "the plan has no eligible selected fields")
    if now > plan.expires_at:
        raise GrantRefused("grant_expired", "the plan expired; prepare a new plan")
    if deps.runtime_epoch() != plan.runtime_epoch:
        raise GrantRefused(
            "runtime_epoch_changed",
            "the API process restarted since planning (C's fixture store is process-local)",
        )
    grant = derive_grant(plan, actor_id, now)

    def build() -> PrefillRun:
        return PrefillRun(
            run_id=run_id_for(plan.plan_id),
            run_version=1,
            plan_id=plan.plan_id,
            plan_sha256=plan.plan_sha256,
            organization_id=org,
            actor_id=actor_id,
            status="claimed",
            outcome="in_progress",
            grant=grant,
            claimed_at=now,
            deadline_at=now
            + timedelta(milliseconds=deps.config.execution_timeout_ms)
            + DEADLINE_SLACK,
            fields=[_receipt(a, "not_attempted") for a in plan.actions],
            receipt_note=RECEIPT_NOTE,
            provenance=RUN_PROVENANCE,
            is_fixture=True,
        )

    run, replayed = deps.repo.claim(org, plan.plan_id, body.idempotency_key, cmd, build)
    if replayed:
        return ExecutePrefillResult(replayed=True, run=view_of(deps, run))
    return ExecutePrefillResult(replayed=False, run=view_of(deps, _run_claimed(deps, plan, run)))


def _run_claimed(deps: ExecutionDeps, plan: PrefillPlan, run: PrefillRun) -> PrefillRun:
    not_attempted = [_receipt(a, "not_attempted") for a in plan.actions]
    pre: list[CurrentnessCheck] = []

    def blocked(reason: str) -> PrefillRun:
        pre.append(CurrentnessCheck(stage="pre_execution", status="stale", detail=reason))
        return _finish(
            deps,
            run,
            outcome="blocked_before_entry",
            reason=reason,
            fields=not_attempted,
            checks=pre,
        )

    problem = grant_problem(run.grant, plan) or _definition_problem(deps, plan)
    if problem is None:
        problem = next(
            (p for a in plan.actions if (p := _approval_problem(deps, plan, a)) is not None), None
        )
    if problem is not None:
        return blocked(problem)
    portal = _portal(plan)
    actions = _browser_actions(plan, portal) if portal is not None else None
    if portal is None or actions is None:
        return blocked("registry_changed")
    pre.append(CurrentnessCheck(stage="pre_execution", status="current", detail="all current"))
    running = deps.repo.append_run(
        plan.organization_id,
        run.model_copy(
            update={"run_version": run.run_version + 1, "status": "running", "checks": pre}
        ),
    )
    hooks = _Hooks(deps, plan, running)
    try:
        run_browser = deps.browser or prefill_browser.execute_actions
        outcome = run_browser(
            prefill_page(portal),
            ready_selector=portal.ready_selector,
            expected_fingerprint=plan.portal.expected_fingerprint,
            expected_page_sha256=plan.portal.page_sha256,
            actions=actions,
            hooks=hooks,
            config=deps.config,
        )
    except Exception:  # never leave a claimed run without a final status
        steps = deps.repo.steps(plan.organization_id, running.run_id, len(plan.actions))
        partial = [steps.get(a.action_index) or not_attempted[a.action_index] for a in plan.actions]
        unknown = any(f.state == "write_in_flight" for f in partial)
        partial = [
            f.model_copy(update={"state": "outcome_unknown"}) if f.state == "write_in_flight" else f
            for f in partial
        ]
        return _finish(
            deps,
            running,
            outcome="outcome_unknown" if unknown or steps else "blocked_before_entry",
            reason="executor_error",
            fields=partial,
            checks=hooks.checks,
        )
    fields: list[FieldReceipt] = []
    for a in plan.actions:
        out = outcome.fields.get(a.action_index)
        fields.append(_receipt(a, out.state, out) if out else not_attempted[a.action_index])  # type: ignore[arg-type]
    for i, f in enumerate(fields):
        stale = next(
            (c for c in hooks.checks if c.stage == f"after:{i}" and c.status != "current"), None
        )
        if f.state == "entered_then_stale" and stale is not None:
            fields[i] = f.model_copy(update={"reason": stale.detail})
    checks = list(hooks.checks)
    final_outcome: RunOutcome
    reason = outcome.reason
    entered = any(f.state not in ("not_attempted", "blocked_before_write") for f in fields)
    if outcome.stage == "unknown":
        final_outcome = "outcome_unknown"
    elif outcome.stage == "blocked_before_entry" or not entered:
        final_outcome = "blocked_before_entry"
    elif outcome.stage == "stopped":
        final_outcome = "stopped_with_partial_entry"
    else:
        completion = next(
            (p for a in plan.actions if (p := _approval_problem(deps, plan, a)) is not None), None
        )
        checks.append(
            CurrentnessCheck(
                stage="completion",
                status="current" if completion is None else "stale",
                detail=completion or "all approvals current at completion",
            )
        )
        all_verified = all(f.state == "entered_verified" for f in fields)
        if completion is None and all_verified and outcome.final_reread == "all_match":
            final_outcome, reason = "selected_fields_verified", None
        else:
            final_outcome = "stopped_with_partial_entry"
            reason = completion or reason or "not_all_fields_verified"
    return _finish(
        deps,
        running,
        outcome=final_outcome,
        reason=reason,
        fields=fields,
        checks=checks,
        browser=outcome,
    )
