"""Saved public searches, staff-triggered reruns and source rechecks (DEV-B-BUNDLE-002 M5).

No scheduler, cron, notification or durable job exists here: every run/recheck is one
explicit staff request that uses the existing bounded search/capture operation once (one
provider request, no automatic retry). Results are versioned records:

- a run that fails or is unavailable is stored as such (never back-filled with fixtures);
- comparisons only cover successful runs of the *same* profile version, by normalized URL,
  and "not seen in this result set" never means removed or closed;
- a recheck creates a new capture (old bytes untouched) and a ChangeObservation comparing
  like representations; a linked funding case then requires re-review.
"""

from __future__ import annotations

import difflib
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from strongstart_contracts.discovery import (
    CapturedDocument,
    CaptureIntegrityError,
    CaptureNotFoundError,
    CaptureRequest,
    FundingErrorReason,
    SearchRequest,
)
from strongstart_contracts.funding_review import (
    ChangeObservation,
    ChangeObservationList,
    RecheckCommand,
    RepresentationComparison,
    RunComparison,
    RunSearchCommand,
    SearchProfileCommand,
    SearchProfileList,
    SearchProfileVersion,
    SearchRunList,
    SearchRunRecord,
)

from ..dev_b_store import (
    IntegrityFailure,
    LocalVersionStore,
    NotFound,
    canonical_json,
    new_object_id,
    sha256_hex,
)
from .cases import CaseCommandError, FundingCaseRepository
from .normalize import build_query, normalize_url
from .providers import CaptureProvider, SearchProvider
from .service import FundingError, SeedEntry, run_capture, run_search
from .store import LocalCaptureStore
from .url_policy import Resolver

PROFILES = "search-profiles"
RUNS = "search-runs"
OBSERVATIONS = "observations"
MAX_DIFF_LINES = 200
MAX_DIFF_CHARS = 20_000

DOWNSTREAM_NOTE = (
    "Local Dev B handling only: Dev A's pack-change graph (A4) and Dev C's answer/approval "
    "invalidation (C3) are not implemented here; no answers, approvals or rules were changed."
)


def _load[M: BaseModel](model: type[M], record: dict[str, Any]) -> M:
    return model.model_validate_json(canonical_json(record))


def _cmd_hash(cmd: BaseModel, **extra: Any) -> str:
    body = cmd.model_dump(mode="json", exclude={"idempotency_key"}) | extra
    return sha256_hex(canonical_json(body))


class MonitoringRepository:
    def __init__(self, store: LocalVersionStore, cases: FundingCaseRepository) -> None:
        self.store = store
        self.cases = cases

    # -- profiles ---------------------------------------------------------------

    def save_profile(
        self,
        org: str,
        actor: str,
        profile_id: str | None,
        cmd: SearchProfileCommand,
        allowed_fields: list[str],
    ) -> tuple[SearchProfileVersion, bool]:
        if (profile_id is None) != (cmd.expected_version is None):
            raise CaseCommandError(422, "invalid_input", "revisions name the profile and version")
        query, used = build_query(cmd.profile, allowed_fields)
        now = datetime.now(UTC)

        def build(object_id: str, version: int, prev: dict[str, Any] | None) -> dict[str, Any]:
            dumped: dict[str, Any] = SearchProfileVersion(
                organization_id=org,
                profile_id=object_id,
                version=version,
                label=cmd.label,
                profile=cmd.profile,
                query_preview=query,
                public_fields_used=used,
                created_by=actor,
                created_at=now,
            ).model_dump(mode="json")
            return dumped

        result = self.store.collection(org, PROFILES).commit(
            idempotency_key=cmd.idempotency_key,
            command_hash=_cmd_hash(cmd, profile_id=profile_id),
            object_id=profile_id,
            expected_version=cmd.expected_version or 0,
            build=build,
            id_prefix="prof",
        )
        return _load(SearchProfileVersion, result.record), result.replayed

    def get_profile(
        self, org: str, profile_id: str, version: int | None = None
    ) -> SearchProfileVersion:
        coll = self.store.collection(org, PROFILES)
        v = version or coll.current_version(profile_id)
        if v == 0:
            raise NotFound(profile_id)
        try:
            return _load(SearchProfileVersion, coll.read(profile_id, v))
        except ValidationError:
            raise IntegrityFailure("search profile does not match its schema") from None

    def list_profiles(self, org: str, cursor: str | None, limit: int) -> SearchProfileList:
        page = self.store.collection(org, PROFILES).list_ids(cursor, limit)
        items = []
        for pid in page.object_ids:
            try:
                items.append(self.get_profile(org, pid))
            except (NotFound, IntegrityFailure):
                continue
        return SearchProfileList(
            items=items,
            next_cursor=page.next_cursor,
            more=page.more,
            incomplete=page.incomplete,
            limit=limit,
        )

    # -- runs -------------------------------------------------------------------

    def run(
        self,
        org: str,
        actor: str,
        profile_id: str,
        cmd: RunSearchCommand,
        provider: SearchProvider | None,
        *,
        max_results: int,
        timeout_s: float,
        allowed_fields: list[str],
        seed: list[SeedEntry],
        capture_check: CaptureProvider | None,
    ) -> tuple[SearchRunRecord, bool]:
        profile = self.get_profile(org, profile_id, cmd.profile_version)
        current = self.store.collection(org, PROFILES).current_version(profile_id)
        if cmd.profile_version != current:
            raise CaseCommandError(
                409,
                "version_conflict",
                "run the current profile version (or revise explicitly)",
                current_version=current,
            )
        coll = self.store.collection(org, RUNS, scope=profile_id)
        command_hash = _cmd_hash(cmd, profile_id=profile_id)
        done = coll.replay(cmd.idempotency_key, command_hash)
        if done is not None:  # a replay never calls the provider again
            return _load(SearchRunRecord, done.record), True
        started = datetime.now(UTC)
        outcome: Any = "success"
        error_reason = error_message = None
        result = None
        try:
            result = run_search(
                SearchRequest(profile=profile.profile, max_results=max_results),
                provider,
                max_results_limit=max_results,
                timeout_s=timeout_s,
                allowed_fields=allowed_fields,
                seed=seed,
                fixture_capture_check=capture_check,
            )
        except FundingError as exc:
            outcome = (
                "unavailable" if exc.reason == FundingErrorReason.PROVIDER_UNAVAILABLE else "failed"
            )
            error_reason, error_message = exc.reason.value, exc.message
        completed = datetime.now(UTC)

        def build(object_id: str, version: int, prev: dict[str, Any] | None) -> dict[str, Any]:
            dumped: dict[str, Any] = SearchRunRecord(
                organization_id=org,
                run_id=object_id,
                profile_id=profile_id,
                profile_version=cmd.profile_version,
                started_at=started,
                completed_at=completed,
                outcome=outcome,
                error_reason=error_reason,
                error_message=error_message,
                provider=result.query.provider if result else getattr(provider, "name", None),
                provider_mode=result.query.mode if result else getattr(provider, "mode", None),
                result=result,
                normalized_urls=[c.normalized_url for c in result.candidates] if result else [],
                created_by=actor,
            ).model_dump(mode="json")
            return dumped

        committed = coll.commit(
            idempotency_key=cmd.idempotency_key,
            command_hash=command_hash,
            object_id=None,
            expected_version=0,
            build=build,
            id_prefix="run",
        )
        return _load(SearchRunRecord, committed.record), committed.replayed

    def get_run(self, org: str, profile_id: str, run_id: str) -> SearchRunRecord:
        coll = self.store.collection(org, RUNS, scope=profile_id)
        try:
            return _load(SearchRunRecord, coll.read(run_id, 1))
        except ValidationError:
            raise IntegrityFailure("search run does not match its schema") from None

    def list_runs(self, org: str, profile_id: str, cursor: str | None, limit: int) -> SearchRunList:
        self.get_profile(org, profile_id)  # unknown/other-org profile -> NotFound
        coll = self.store.collection(org, RUNS, scope=profile_id)
        page = coll.list_ids(cursor, limit)
        items = []
        for rid in page.object_ids:
            try:
                items.append(self.get_run(org, profile_id, rid))
            except (NotFound, IntegrityFailure):
                continue
        return SearchRunList(
            items=items,
            next_cursor=page.next_cursor,
            more=page.more,
            incomplete=page.incomplete,
            limit=limit,
        )

    def compare(self, org: str, profile_id: str, base_id: str, run_id: str) -> RunComparison:
        base, run = self.get_run(org, profile_id, base_id), self.get_run(org, profile_id, run_id)
        if base.outcome != "success" or run.outcome != "success":
            raise CaseCommandError(
                409,
                "not_comparable",
                "only successful runs can be compared; failures stay failures",
            )
        if base.profile_version != run.profile_version:
            raise CaseCommandError(
                409,
                "not_comparable",
                "different profile versions are not automatically comparable",
                base_version=base.profile_version,
                run_version=run.profile_version,
            )
        old, new = set(base.normalized_urls), set(run.normalized_urls)
        return RunComparison(
            profile_id=profile_id,
            profile_version=run.profile_version,
            base_run_id=base_id,
            run_id=run_id,
            newly_seen=sorted(new - old),
            seen_again=sorted(new & old),
            not_seen_in_this_result_set=sorted(old - new),
            note=(
                "Result sets are bounded and provider-ranked. A URL not seen in this result set "
                "is not a removed opportunity or a closed grant."
            ),
        )

    # -- recheck ----------------------------------------------------------------

    def recheck(
        self,
        org: str,
        actor: str,
        capture_id: str,
        cmd: RecheckCommand,
        *,
        provider: CaptureProvider | None,
        capture_store: LocalCaptureStore | None,
        resolver: Resolver,
        timeout_s: float,
        max_bytes: int,
        seed: list[SeedEntry],
    ) -> tuple[ChangeObservation, bool]:
        if capture_store is None:
            raise CaseCommandError(503, "store_unavailable", "no capture store is available")
        try:
            old = capture_store.get_record(org, capture_id)
        except CaptureNotFoundError:
            raise CaseCommandError(404, "capture_not_found", "capture not found") from None
        except CaptureIntegrityError:
            raise CaseCommandError(
                409, "integrity_failure", "capture failed verification"
            ) from None
        if cmd.funding_case_id is not None and cmd.funding_case_version is not None:
            env = self.cases.get_version(org, cmd.funding_case_id, cmd.funding_case_version)
            linked = {x.capture_id for x in env.version.capture_links} | {
                a.capture_id for a in env.version.anchors
            }
            if capture_id not in linked:
                raise CaseCommandError(
                    422, "invalid_input", "this capture is not linked to the selected case"
                )
        coll = self.store.collection(org, OBSERVATIONS, scope=capture_id)
        command_hash = _cmd_hash(cmd, capture_id=capture_id)
        done = coll.replay(cmd.idempotency_key, command_hash)
        if done is not None:  # never repeat the provider request on a replay
            return _load(ChangeObservation, done.record), True
        new: CapturedDocument | None = None
        failure = None
        try:
            new = run_capture(
                CaptureRequest(
                    url=old.requested_url,
                    candidate_id=old.candidate_id,
                    search_id=old.search_id,
                    opportunity_id=old.opportunity_id,
                    stream_id=old.stream_id,
                    cycle_id=old.cycle_id,
                ),
                org,
                provider,
                capture_store,
                resolver,
                timeout_s=timeout_s,
                max_bytes=max_bytes,
                seed=seed,
            )
        except FundingError as exc:
            failure = exc.reason.value
            recorded = exc.details.get("capture_id")
            if isinstance(recorded, str):  # an empty capture was recorded for inspection
                try:
                    new = capture_store.get_record(org, recorded)
                except (CaptureNotFoundError, CaptureIntegrityError):
                    new = None
        observation_id = new_object_id("obs")
        observed = observe(old, new, failure, capture_store, org)
        linked_effects = []
        if cmd.funding_case_id and observed["overall"] != "unchanged":
            linked_effects.append(
                f"Funding case {cmd.funding_case_id} now requires re-review of this source; its "
                "historical evaluations stay unchanged and are marked stale."
            )
        record = ChangeObservation(
            organization_id=org,
            observation_id=observation_id,
            old_capture_id=old.capture_id,
            new_capture_id=new.capture_id if new else None,
            requested_url=old.requested_url,
            observed_at=datetime.now(UTC),
            linked_case_id=cmd.funding_case_id,
            linked_case_version=cmd.funding_case_version,
            downstream_effects=[*linked_effects, DOWNSTREAM_NOTE],
            created_by=actor,
            failure_reason=failure,
            **observed,
        )
        committed = coll.commit(
            idempotency_key=cmd.idempotency_key,
            command_hash=command_hash,
            object_id=observation_id,
            expected_version=0,
            build=lambda o, v, p: record.model_dump(mode="json"),
        )
        stored = _load(ChangeObservation, committed.record)
        self.cases.record_observation(org, stored)  # makes a linked case require re-review
        return stored, committed.replayed

    def list_observations(
        self, org: str, capture_id: str, cursor: str | None, limit: int
    ) -> ChangeObservationList:
        coll = self.store.collection(org, OBSERVATIONS, scope=capture_id)
        page = coll.list_ids(cursor, limit)
        items = []
        for oid in page.object_ids:
            try:
                items.append(_load(ChangeObservation, coll.read(oid, 1)))
            except (NotFound, IntegrityFailure, ValidationError):
                continue
        return ChangeObservationList(
            items=items,
            next_cursor=page.next_cursor,
            more=page.more,
            incomplete=page.incomplete,
            limit=limit,
        )


def observe(
    old: CapturedDocument,
    new: CapturedDocument | None,
    failure: str | None,
    store: LocalCaptureStore,
    org: str,
) -> dict[str, Any]:
    """Compare like representations; hash equality is byte equality, nothing more."""
    if new is None:
        return {
            "options_comparable": False,
            "old_options": dict(old.provider_request_params),
            "overall": "failed",
            "explanation": f"The recheck did not produce a new capture ({failure}). The old "
            "capture is unchanged; nothing about the funder's policy is inferred.",
        }
    comparable = (
        old.provider == new.provider
        and old.provider_mode == new.provider_mode
        and old.provider_request_params == new.provider_request_params
    )
    base = {
        "options_comparable": comparable,
        "old_options": dict(old.provider_request_params),
        "new_options": dict(new.provider_request_params),
    }
    if not comparable:
        return {
            **base,
            "overall": "not_comparable",
            "explanation": "The provider or extraction options differ, so representations are "
            "not comparable; no semantic difference is claimed.",
        }
    old_reps = {a.representation: a for a in old.artifacts}
    new_reps = {a.representation: a for a in new.artifacts}
    comparisons = []
    for rep in sorted(set(old_reps) | set(new_reps)):
        o, n = old_reps.get(rep), new_reps.get(rep)
        if o and n:
            outcome = "match" if o.sha256 == n.sha256 else "changed"
        else:
            outcome = "missing_in_new" if o else "missing_in_old"
        comparisons.append(
            RepresentationComparison(
                representation=rep,
                old_sha256=o.sha256 if o else None,
                new_sha256=n.sha256 if n else None,
                outcome=outcome,
            )
        )
    outcomes = {c.outcome for c in comparisons}
    if new.coverage != "complete" or failure or outcomes & {"missing_in_new", "missing_in_old"}:
        overall = "partial"
    elif "changed" in outcomes:
        overall = "changed"
    else:
        overall = "unchanged"
    explanation = {
        "unchanged": "Every stored representation has the same bytes (hash match). This does not "
        "prove the extraction is complete or that the funder's terms are unchanged elsewhere.",
        "changed": "At least one representation's bytes changed (hash differs). That shows a "
        "change in the captured text, not by itself a policy change; staff must re-review.",
        "partial": "The new capture is partial or a representation is missing, so it cannot be "
        "fully compared; staff must re-review the source.",
    }[overall]
    diff, truncated = _bounded_diff(old, new, comparisons, store, org)
    return {
        **base,
        "comparisons": comparisons,
        "overall": overall,
        "explanation": explanation,
        "text_diff": diff,
        "text_diff_truncated": truncated,
    }


def _bounded_diff(
    old: CapturedDocument,
    new: CapturedDocument,
    comparisons: list[RepresentationComparison],
    store: LocalCaptureStore,
    org: str,
) -> tuple[str | None, bool]:
    changed = [c.representation for c in comparisons if c.outcome == "changed"]
    if not changed:
        return None, False
    rep = "provider_markdown" if "provider_markdown" in changed else changed[0]
    try:
        a = next(x for x in old.artifacts if x.representation == rep)
        b = next(x for x in new.artifacts if x.representation == rep)
        old_text = store.read_artifact(org, old.capture_id, a.artifact_id).content.decode("utf-8")
        new_text = store.read_artifact(org, new.capture_id, b.artifact_id).content.decode("utf-8")
    except (CaptureNotFoundError, CaptureIntegrityError, UnicodeDecodeError, StopIteration):
        return None, False
    lines = list(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile=f"{old.capture_id}/{rep}",
            tofile=f"{new.capture_id}/{rep}",
            lineterm="",
        )
    )
    text = "\n".join(lines[:MAX_DIFF_LINES])
    truncated = len(lines) > MAX_DIFF_LINES or len(text) > MAX_DIFF_CHARS
    return text[:MAX_DIFF_CHARS], truncated


__all__ = ["MonitoringRepository", "normalize_url"]
