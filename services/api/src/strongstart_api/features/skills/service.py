"""C4-SKL-001 practice workflow: source authority, candidate, gates, review, release, preview.

Identity and organization come from the server. Every enabled transition re-derives its gate
state under the scope lock; nothing a client or model sends can mark a candidate screened,
tested, approved or active. Model calls and drafting happen outside any database lock.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter

from strongstart_contracts import Provenance, ProvenanceClass
from strongstart_contracts.answers import CheckRequest, DraftRequest
from strongstart_contracts.skills import (
    AppliedPractice,
    CompiledPracticePackage,
    PracticeActivateRequest,
    PracticeAuditEvent,
    PracticeAuthority,
    PracticeCandidate,
    PracticeContext,
    PracticeOverview,
    PracticePreview,
    PracticePreviewRequest,
    PracticeRelease,
    PracticeReview,
    PracticeReviewRequest,
    PracticeRule,
    PracticeSourceVersion,
    RuleTestReport,
    ScanReport,
    ScreeningReport,
)

from ..applications.public import PracticePreviewPort
from ..applications.rules.policy import WritingPolicy
from .compiler import compile_package, guidance_text
from .demo import ContextDef
from .model_tasks import propose, screen
from .repository import PracticeRepository, Record, Scope, new_id, now
from .rule_tests import compose, conflicts, run_rule_tests
from .scan import package_parts, quarantined, scan_package

RULES = TypeAdapter(list[PracticeRule])


class SkillError(Exception):
    def __init__(self, status: int, reason: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.status, self.reason, self.message, self.details = status, reason, message, details


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Resolved:
    release_id: str
    candidate: PracticeCandidate
    scope_revision: int
    guidance: str


@dataclass
class SkillsService:
    repo: PracticeRepository
    port: PracticePreviewPort
    context: ContextDef
    org: str
    actor: str
    can_decide: bool
    fixture_mode: bool

    # ---- reads ------------------------------------------------------------------------
    def _sources(self, scope: Scope) -> list[PracticeSourceVersion]:
        auth = {
            r.parent_id: r
            for r in self.repo.records(self.org, self.context.context_id, "authority")
        }
        out = []
        for r in self.repo.records(self.org, self.context.context_id, "source"):
            data = json.loads(r.payload)
            a = auth.get(r.record_id)
            out.append(
                PracticeSourceVersion.model_validate(
                    {
                        **data,
                        "authority": json.loads(a.payload) if a else None,
                        "is_current": scope.current_source_version_id == r.record_id,
                    }
                )
            )
        return out

    def source(self, source_version_id: str) -> PracticeSourceVersion:
        scope = self.repo.scope(self.org, self.context.context_id)
        for s in self._sources(scope):
            if s.source_version_id == source_version_id:
                return s
        raise SkillError(404, "unknown_source", "unknown practice source")

    def _latest_screening(self, candidate_id: str) -> ScreeningReport | None:
        rows = [
            r
            for r in self.repo.records(self.org, self.context.context_id, "screening")
            if r.parent_id == candidate_id
        ]
        return ScreeningReport.model_validate_json(rows[-1].payload) if rows else None

    def _latest_review(self, candidate_id: str) -> PracticeReview | None:
        rows = [
            r
            for r in self.repo.records(self.org, self.context.context_id, "review")
            if r.parent_id == candidate_id
        ]
        return PracticeReview.model_validate_json(rows[-1].payload) if rows else None

    def _releases(self, scope: Scope) -> list[PracticeRelease]:
        revoked = {
            r.parent_id: json.loads(r.payload)["reason"]
            for r in self.repo.records(self.org, self.context.context_id, "revocation")
        }
        out = []
        for r in self.repo.records(self.org, self.context.context_id, "release"):
            data = json.loads(r.payload)
            rid = data["release_id"]
            state = (
                "revoked"
                if rid in revoked
                else "superseded"
                if scope.active_release_id != rid
                else "stale_source"
                if scope.current_source_version_id != data["source_version_id"]
                else "active"
            )
            data.pop("idempotency_key", None)
            data.pop("request_sha256", None)
            out.append(
                PracticeRelease.model_validate(
                    {**data, "effective_state": state, "revoked_reason": revoked.get(rid)}
                )
            )
        return out

    def _holds(
        self,
        base: dict[str, Any],
        screening: ScreeningReport | None,
        scope: Scope,
        authority_ok: bool,
    ) -> tuple[list[str], list[str]]:
        scan = ScanReport.model_validate(base["scan"])
        tests = RuleTestReport.model_validate(base["tests"])
        holds: list[str] = []
        for f in scan.findings:
            if f.severity == "block" and f"scan_block:{f.category}" not in holds:
                holds.append(f"scan_block:{f.category}")
        if not tests.passed:
            holds.append("rule_tests_failed")
        if screening is None:
            holds.append("screening_not_run")
        else:
            if screening.package_sha256 != base["package"]["package_sha256"]:
                holds.append("screening_for_other_package")
            if not screening.complete:
                holds.append(screening.hold_reason or "screening_incomplete")
            if screening.signal == "block":
                holds.append("screening_signal_block")
        if scope.current_source_version_id != base["source_version_id"]:
            holds.append("source_not_current")
        if not authority_ok:
            holds.append("source_authority_missing")
        review_ids = [f.finding_id for f in scan.findings if f.severity == "review"]
        if screening is not None and screening.signal == "review":
            review_ids += [f"screen-{n}" for n in range(1, len(screening.findings) + 1)] or [
                "screen-signal"
            ]
        return holds, review_ids

    def _authority_ok(self, source_version_id: str) -> bool:
        return any(
            r.parent_id == source_version_id
            for r in self.repo.records(self.org, self.context.context_id, "authority")
        )

    def _candidate(
        self, rec: Record, scope: Scope, releases: list[PracticeRelease]
    ) -> PracticeCandidate:
        base = json.loads(rec.payload)
        screening = self._latest_screening(rec.record_id)
        review = self._latest_review(rec.record_id)
        holds, _ = self._holds(
            base, screening, scope, self._authority_ok(base["source_version_id"])
        )
        mine = [r for r in releases if r.candidate_id == rec.record_id]
        status: str
        if mine:
            status = mine[-1].effective_state
        elif "source_not_current" in holds:
            status = "stale_source"
        elif holds and holds != ["screening_not_run"]:
            status = "held"
        elif screening is None:
            status = "proposed"
        elif review is not None and review.package_sha256 == base["package"]["package_sha256"]:
            status = "approved"
        else:
            status = "needs_review"
        return PracticeCandidate.model_validate(
            {
                **base,
                "screening": screening,
                "review": review,
                "status": status,
                "hold_reasons": holds,
            }
        )

    def overview(self, screening_live: bool) -> PracticeOverview:
        scope = self.repo.scope(self.org, self.context.context_id)
        releases = self._releases(scope)
        return PracticeOverview(
            context=self.context_model(scope),
            sources=self._sources(scope),
            candidates=[
                self._candidate(r, scope, releases)
                for r in self.repo.records(self.org, self.context.context_id, "candidate")
            ],
            releases=releases,
            audit=[
                PracticeAuditEvent.model_validate_json(r.payload)
                for r in self.repo.records(self.org, self.context.context_id, "audit")
            ][-30:],
            screening_live=screening_live,
        )

    def context_model(self, scope: Scope) -> PracticeContext:
        c = self.context
        return PracticeContext(
            context_id=c.context_id,
            label=c.label,
            program=c.program,
            registered_names=list(c.registered_names),
            is_simulated=c.is_simulated,
            current_source_version_id=scope.current_source_version_id,
            active_release_id=scope.active_release_id,
            revision=scope.revision,
        )

    def candidate(self, candidate_id: str) -> PracticeCandidate:
        rec = self.repo.get(self.org, "candidate", candidate_id)
        if rec is None:
            raise SkillError(404, "unknown_candidate", "unknown practice candidate")
        scope = self.repo.scope(self.org, self.context.context_id)
        return self._candidate(rec, scope, self._releases(scope))

    # ---- commands -----------------------------------------------------------------------
    def _require_staff(self) -> None:
        if not self.can_decide:
            raise SkillError(403, "not_authorized", "only authorized staff can do this")

    def create_source(
        self, title: str, text: str, kind: str, expected_current: str | None, check_cas: bool
    ) -> PracticeSourceVersion:
        self._require_staff()
        simulated = kind == "synthetic_demo"
        with self.repo.locked(self.org, self.context.context_id) as (conn, scope):
            if check_cas and expected_current != scope.current_source_version_id:
                raise SkillError(
                    409, "source_version_changed", "another source version was published"
                )
            versions = self.repo.records(self.org, self.context.context_id, "source")
            sid = new_id("psrc")
            version = PracticeSourceVersion(
                source_version_id=sid,
                source_id=f"practice-source-{self.context.context_id}",
                version=len(versions) + 1,
                context_id=self.context.context_id,
                title=title,
                text=text,
                text_sha256=_sha(text),
                provenance=Provenance(
                    provenance_class=ProvenanceClass.SIMULATED
                    if simulated
                    else ProvenanceClass.SUPPLIED,
                    is_simulated=simulated,
                    note="SYNTHETIC demo practice text (invented; not partner guidance)."
                    if simulated
                    else "Administrator-authored practice text entered by staff.",
                ),
                authority_kind=kind,
                authority=None,
                is_current=True,
                created_by=self.actor,
                created_at=now(),
            )
            payload = version.model_dump(mode="json", exclude={"authority", "is_current"})
            self.repo.add(
                conn,
                self.org,
                self.context.context_id,
                "source",
                sid,
                json.dumps(payload, sort_keys=True),
                self.actor,
                sha256=version.text_sha256,
            )
            self.repo.set_scope(
                conn, self.org, self.context.context_id, scope, current_source_version_id=sid
            )
            self.repo.audit(
                conn,
                self.org,
                self.context.context_id,
                "source_published",
                sid,
                self.actor,
                f"version {version.version}; prior source now noncurrent",
            )
        return self.source(sid)

    def approve_authority(self, source_version_id: str) -> PracticeSourceVersion:
        self._require_staff()
        src = self.source(source_version_id)
        with self.repo.locked(self.org, self.context.context_id) as (conn, scope):
            if scope.current_source_version_id != source_version_id:
                raise SkillError(
                    409, "source_not_current", "this source version is no longer current"
                )
            if src.authority is None:
                auth = PracticeAuthority(
                    kind=src.authority_kind,
                    context_id=self.context.context_id,
                    approved_by=self.actor,
                    approved_at=now(),
                    is_fixture=self.fixture_mode,
                )
                self.repo.add(
                    conn,
                    self.org,
                    self.context.context_id,
                    "authority",
                    new_id("pauth"),
                    auth.model_dump_json(),
                    self.actor,
                    parent_id=source_version_id,
                )
                self.repo.audit(
                    conn,
                    self.org,
                    self.context.context_id,
                    "source_authority_approved",
                    source_version_id,
                    self.actor,
                    f"practice source for {self.context.context_id}",
                )
        return self.source(source_version_id)

    def _preview_target(self) -> tuple[str, int, str]:
        ws = self.port.workspace(self.org, None)
        q = sorted(ws.question_set.questions, key=lambda q: q.order)[0]
        return q.question_id, q.question_version, ws.evidence_bundle.bundle_id

    def _checker(self) -> Any:
        qid, qv, bundle = self._preview_target()

        def check(text: str, policy: WritingPolicy | None) -> Any:
            return self.port.check(
                self.org,
                qid,
                CheckRequest(question_version=qv, evidence_bundle_id=bundle, text=text),
                policy,
            )

        return check

    async def generate(self, source_version_id: str) -> PracticeCandidate:
        self._require_staff()
        src = self.source(source_version_id)
        if src.authority is None:
            raise SkillError(
                422,
                "source_authority_missing",
                "review this source as practice authority before generating",
            )
        if not src.is_current:
            raise SkillError(409, "source_not_current", "this source version is no longer current")
        rules, proposer = await propose(
            self.port.adapter,
            source_text=src.text,
            source_version_id=src.source_version_id,
            text_sha=src.text_sha256,
            data_class=src.provenance.provenance_class,
            program=self.context.program,
            timeout_seconds=self.port.timeout_seconds,
        )
        label = src.provenance.note or src.provenance.provenance_class.value
        package = compile_package(
            self.context, src.source_version_id, src.text_sha256, label, rules
        )
        scan = scan_package(self.context, rules, package)
        conflict = conflicts(self.port.base_policy, rules)
        if conflict:
            scan = scan.model_copy(update={"findings": [*scan.findings, *conflict]})
        tests = run_rule_tests(rules, self.context, self.port.base_policy, self._checker())
        cid = new_id("pcand")
        base = {
            "candidate_id": cid,
            "context_id": self.context.context_id,
            "source_version_id": src.source_version_id,
            "source_text_sha256": src.text_sha256,
            "rules": RULES.dump_python(rules, mode="json"),
            "package": package.model_dump(mode="json"),
            "proposer": proposer.model_dump(mode="json"),
            "scan": scan.model_dump(mode="json"),
            "tests": tests.model_dump(mode="json"),
            "created_at": now().isoformat(),
        }
        with self.repo.locked(self.org, self.context.context_id) as (conn, scope):
            if (
                scope.current_source_version_id != src.source_version_id
            ):  # changed during model work
                raise SkillError(
                    409,
                    "source_changed_during_generation",
                    "the source changed while generating; generate again",
                )
            self.repo.add(
                conn,
                self.org,
                self.context.context_id,
                "candidate",
                cid,
                json.dumps(base, sort_keys=True),
                self.actor,
                parent_id=src.source_version_id,
                sha256=package.package_sha256,
            )
            self.repo.audit(
                conn,
                self.org,
                self.context.context_id,
                "candidate_generated",
                cid,
                self.actor,
                f"package {package.package_sha256[:12]}; "
                f"proposer {proposer.adapter}{' FIXTURE' if proposer.is_fixture else ''}",
            )
        return self.candidate(cid)

    async def run_screening(self, candidate_id: str) -> PracticeCandidate:
        self._require_staff()
        cand = self.candidate(candidate_id)
        src = self.source(cand.source_version_id)
        parts = package_parts(self.context, cand.rules, cand.package)
        if quarantined(cand.scan):
            outcome: dict[str, Any] = {
                "signal": "unknown",
                "complete": False,
                "expected_parts": [p for p, _ in parts],
                "covered_parts": [],
                "findings": [],
                "provider": None,
                "hold_reason": "quarantined_secret_not_sent_to_model",
            }
        else:
            outcome = await screen(
                self.port.adapter,
                candidate_id=candidate_id,
                parts=parts,
                data_class=src.provenance.provenance_class,
                timeout_seconds=self.port.timeout_seconds,
            )
        body = {
            **outcome,
            "candidate_id": candidate_id,
            "package_sha256": cand.package.package_sha256,
        }
        draft = ScreeningReport.model_validate(
            {**body, "screening_id": new_id("pscr"), "report_sha256": "0" * 64, "created_at": now()}
        )
        identity = draft.model_dump_json(exclude={"screening_id", "report_sha256", "created_at"})
        report = draft.model_copy(update={"report_sha256": _sha(identity)})
        with self.repo.locked(self.org, self.context.context_id) as (conn, _):
            self.repo.add(
                conn,
                self.org,
                self.context.context_id,
                "screening",
                report.screening_id,
                report.model_dump_json(),
                self.actor,
                parent_id=candidate_id,
                sha256=report.report_sha256,
            )
            self.repo.audit(
                conn,
                self.org,
                self.context.context_id,
                "candidate_screened",
                candidate_id,
                self.actor,
                f"signal {report.signal}; complete {report.complete}; "
                f"{'FIXTURE ' if report.provider and report.provider.is_fixture else ''}"
                f"{report.hold_reason or ''}",
            )
        return self.candidate(candidate_id)

    def review(self, candidate_id: str, body: PracticeReviewRequest) -> PracticeCandidate:
        self._require_staff()
        rec = self.repo.get(self.org, "candidate", candidate_id)
        if rec is None:
            raise SkillError(404, "unknown_candidate", "unknown practice candidate")
        base = json.loads(rec.payload)
        with self.repo.locked(self.org, self.context.context_id) as (conn, scope):
            if body.package_sha256 != base["package"]["package_sha256"]:
                raise SkillError(
                    409,
                    "package_hash_mismatch",
                    "the package changed; review the exact current hash",
                )
            screening = self._latest_screening(candidate_id)
            holds, review_ids = self._holds(
                base, screening, scope, self._authority_ok(base["source_version_id"])
            )
            if holds:
                raise SkillError(422, "gates_not_passed", "hard gates have not passed", holds=holds)
            if not body.source_supported:
                raise SkillError(
                    422,
                    "source_support_not_confirmed",
                    "confirm that every rule follows from its source excerpt",
                )
            missing = [i for i in review_ids if i not in body.acknowledged_findings]
            if missing:
                raise SkillError(
                    422,
                    "review_items_not_acknowledged",
                    "acknowledge every review finding",
                    missing=missing,
                )
            assert screening is not None
            review = PracticeReview(
                review_id=new_id("prev"),
                candidate_id=candidate_id,
                package_sha256=body.package_sha256,
                scan_sha256=base["scan"]["report_sha256"],
                tests_sha256=base["tests"]["report_sha256"],
                screening_sha256=screening.report_sha256,
                source_supported=True,
                acknowledged=list(body.acknowledged_findings),
                reviewed_by=self.actor,
                reviewed_at=now(),
                is_fixture=self.fixture_mode,
            )
            self.repo.add(
                conn,
                self.org,
                self.context.context_id,
                "review",
                review.review_id,
                review.model_dump_json(),
                self.actor,
                parent_id=candidate_id,
            )
            self.repo.audit(
                conn,
                self.org,
                self.context.context_id,
                "candidate_reviewed",
                candidate_id,
                self.actor,
                f"exact package {body.package_sha256[:12]}; {body.rationale[:120]}",
            )
        return self.candidate(candidate_id)

    def activate(self, candidate_id: str, body: PracticeActivateRequest) -> PracticeRelease:
        self._require_staff()
        rec = self.repo.get(self.org, "candidate", candidate_id)
        if rec is None:
            raise SkillError(404, "unknown_candidate", "unknown practice candidate")
        base = json.loads(rec.payload)
        request_sha = _sha(json.dumps([candidate_id, body.package_sha256]))
        with self.repo.locked(self.org, self.context.context_id) as (conn, scope):
            for r in self.repo.records(self.org, self.context.context_id, "release"):
                prior = json.loads(r.payload)
                if prior.get("idempotency_key") == body.idempotency_key:
                    if prior["request_sha256"] != request_sha:
                        raise SkillError(
                            409,
                            "idempotency_key_reused",
                            "this request key was used for a different activation",
                        )
                    return next(
                        x for x in self._releases(scope) if x.release_id == prior["release_id"]
                    )
            if body.package_sha256 != base["package"]["package_sha256"]:
                raise SkillError(
                    409,
                    "package_hash_mismatch",
                    "activation must name the exact reviewed package hash",
                )
            screening = self._latest_screening(candidate_id)
            holds, _ = self._holds(
                base, screening, scope, self._authority_ok(base["source_version_id"])
            )
            if holds:
                raise SkillError(422, "gates_not_passed", "hard gates have not passed", holds=holds)
            review = self._latest_review(candidate_id)
            assert screening is not None
            if review is None or (
                review.package_sha256,
                review.scan_sha256,
                review.tests_sha256,
                review.screening_sha256,
            ) != (
                body.package_sha256,
                base["scan"]["report_sha256"],
                base["tests"]["report_sha256"],
                screening.report_sha256,
            ):
                raise SkillError(
                    422,
                    "review_missing_or_stale",
                    "an exact-hash staff review of the current gate reports is required",
                )
            if scope.active_release_id is not None:
                self.repo.add(
                    conn,
                    self.org,
                    self.context.context_id,
                    "supersession",
                    new_id("psup"),
                    json.dumps({"by_candidate": candidate_id}),
                    self.actor,
                    parent_id=scope.active_release_id,
                )
            release_id = new_id("prel")
            payload = {
                "release_id": release_id,
                "candidate_id": candidate_id,
                "context_id": self.context.context_id,
                "package_sha256": body.package_sha256,
                "source_version_id": base["source_version_id"],
                "review_id": review.review_id,
                "activated_by": self.actor,
                "activated_at": now().isoformat(),
                "is_fixture": self.fixture_mode or bool(base["proposer"]["is_fixture"]),
                "idempotency_key": body.idempotency_key,
                "request_sha256": request_sha,
            }
            self.repo.add(
                conn,
                self.org,
                self.context.context_id,
                "release",
                release_id,
                json.dumps(payload, sort_keys=True),
                self.actor,
                parent_id=candidate_id,
                sha256=body.package_sha256,
            )
            self.repo.set_scope(
                conn, self.org, self.context.context_id, scope, active_release_id=release_id
            )
            self.repo.audit(
                conn,
                self.org,
                self.context.context_id,
                "release_activated",
                release_id,
                self.actor,
                f"package {body.package_sha256[:12]}",
            )
        return next(
            x
            for x in self._releases(self.repo.scope(self.org, self.context.context_id))
            if x.release_id == release_id
        )

    def revoke(self, release_id: str, reason: str) -> PracticeRelease:
        self._require_staff()
        with self.repo.locked(self.org, self.context.context_id) as (conn, scope):
            releases = {r.release_id: r for r in self._releases(scope)}
            if release_id not in releases:
                raise SkillError(404, "unknown_release", "unknown practice release")
            if releases[release_id].effective_state != "revoked":
                self.repo.add(
                    conn,
                    self.org,
                    self.context.context_id,
                    "revocation",
                    new_id("prvk"),
                    json.dumps({"reason": reason}),
                    self.actor,
                    parent_id=release_id,
                )
                if scope.active_release_id == release_id:
                    self.repo.set_scope(
                        conn, self.org, self.context.context_id, scope, active_release_id=None
                    )
                self.repo.audit(
                    conn,
                    self.org,
                    self.context.context_id,
                    "release_revoked",
                    release_id,
                    self.actor,
                    reason,
                )
        return next(
            x
            for x in self._releases(self.repo.scope(self.org, self.context.context_id))
            if x.release_id == release_id
        )

    # ---- use-time resolution and preview -------------------------------------------------
    def resolve(self) -> tuple[Resolved | None, str | None]:
        """Only a currently active, authorized, hash-verified release for this exact context."""
        scope = self.repo.scope(self.org, self.context.context_id)
        if scope.active_release_id is None:
            return None, "no_active_practice"
        release = next(
            (r for r in self._releases(scope) if r.release_id == scope.active_release_id), None
        )
        if release is None or release.effective_state != "active":
            return None, f"release_{release.effective_state if release else 'missing'}"
        cand = self.candidate(release.candidate_id)
        src = self.source(cand.source_version_id)
        label = src.provenance.note or src.provenance.provenance_class.value
        recompiled = compile_package(
            self.context, src.source_version_id, src.text_sha256, label, cand.rules
        )
        if (
            recompiled.package_sha256 != release.package_sha256
            or cand.package.package_sha256 != release.package_sha256
            or src.text_sha256 != cand.source_text_sha256
            or _sha(src.text) != src.text_sha256
        ):
            return None, "package_hash_verification_failed"
        if src.authority is None or not src.is_current:
            return None, "source_not_current_or_unauthorized"
        return Resolved(release.release_id, cand, scope.revision, guidance_text(cand.rules)), None

    async def preview(self, body: PracticePreviewRequest) -> PracticePreview:
        resolved, reason = self.resolve()
        base_policy = self.port.base_policy
        req = DraftRequest(
            question_version=body.question_version,
            evidence_bundle_id=body.evidence_bundle_id,
            question_set_id=body.question_set_id,
        )
        baseline = await self.port.draft(self.org, body.question_id, req, base_policy, None)
        practice_draft, applied, policy = None, None, None
        if resolved is not None:
            conflict = conflicts(base_policy, resolved.candidate.rules)
            if conflict:
                resolved, reason = None, "practice_conflicts_with_base_policy"
        if resolved is not None:
            policy = compose(
                base_policy, resolved.candidate.rules, self.context, resolved.release_id
            )
            practice_draft = await self.port.draft(
                self.org, body.question_id, req, policy, resolved.guidance
            )
            applied = AppliedPractice(
                release_id=resolved.release_id,
                package_sha256=resolved.candidate.package.package_sha256,
                source_version_id=resolved.candidate.source_version_id,
                source_text_sha256=resolved.candidate.source_text_sha256,
                instruction_sha256=_sha(resolved.guidance),
                instructions=resolved.guidance,
                rule_ids=[r.rule_id for r in resolved.candidate.rules],
                is_fixture=resolved.candidate.proposer.is_fixture or self.fixture_mode,
            )
        sample_base = sample_practice = None
        if body.sample_text:
            check_req = CheckRequest(
                question_version=body.question_version,
                evidence_bundle_id=body.evidence_bundle_id,
                text=body.sample_text,
                question_set_id=body.question_set_id,
            )
            sample_base = self.port.check(self.org, body.question_id, check_req, base_policy)
            if policy is not None:
                sample_practice = self.port.check(self.org, body.question_id, check_req, policy)
        current = resolved is not None
        if resolved is not None:  # re-check after model work, before presenting as current
            again, _ = self.resolve()
            if (
                again is None
                or again.release_id != resolved.release_id
                or again.scope_revision != resolved.scope_revision
            ):
                current, reason = False, "practice_changed_during_preview"
        preview_id = new_id("pprev")
        with self.repo.engine.begin() as conn:
            self.repo.add(
                conn,
                self.org,
                self.context.context_id,
                "preview",
                preview_id,
                json.dumps(
                    {
                        "release_id": applied.release_id if applied else None,
                        "instruction_sha256": applied.instruction_sha256 if applied else None,
                        "baseline_proposal": baseline.proposal_id,
                        "practice_proposal": practice_draft.proposal_id if practice_draft else None,
                        "current": current,
                        "hold_reason": reason,
                    },
                    sort_keys=True,
                ),
                self.actor,
            )
        actions = (
            [
                "Working preview only: it cannot be approved, exported or used for prefill. "
                "Save an answer on the Applications page for the normal review path."
            ]
            if current
            else [
                "No current practice was applied. Activate a reviewed release, or re-run "
                "the preview if the practice changed while it was generating."
            ]
        )
        return PracticePreview(
            preview_id=preview_id,
            context_id=self.context.context_id,
            applied=applied,
            current=current,
            hold_reason=reason if not current else None,
            baseline_draft=baseline,
            practice_draft=practice_draft,
            sample_baseline_check=sample_base,
            sample_practice_check=sample_practice,
            next_actions=actions,
        )

    def package_export(self, candidate_id: str) -> CompiledPracticePackage:
        cand = self.candidate(candidate_id)
        if quarantined(cand.scan):
            raise SkillError(
                422, "package_quarantined", "this package is quarantined and cannot be exported"
            )
        return cand.package
