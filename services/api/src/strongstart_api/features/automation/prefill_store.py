"""Plans, single-use claims and per-field progress in the Dev B local store (B2-AUTO-002 s7).

Development/test only; production has no repository (503). Layout per organization:

- ``prefill-plans/<plan_id>/v000001.json``: the exact hashed plan (immutable);
- ``prefill-runs/<run_id>/vN``: v1 = the atomic claim (with its grant), later versions =
  run status. ``run_id`` is derived from ``plan_id``, so a plan has at most one run;
- ``prefill-steps/<run_id>.aNN/vN``: v1 = intent recorded *before* the DOM mutation,
  v2 = the read-back result. No step object means not started.

The claim is ``commit(expected_version=0)`` on the derived run ID: the no-clobber create
under the collection lock lets exactly one of several racing threads/processes create
v1. No store lock is held while C is called or Chromium runs (each commit is short).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from strongstart_contracts.automation_prefill import FieldReceipt, PrefillPlan, PrefillRun

from ..dev_b_store.core import (
    IntegrityFailure,
    LocalVersionStore,
    NotFound,
    VersionConflict,
    canonical_json,
    sha256_hex,
)
from .prefill_plan import plan_hash

PLANS = "prefill-plans"
RUNS = "prefill-runs"
STEPS = "prefill-steps"


class AlreadyClaimed(Exception):
    def __init__(self, run_id: str) -> None:
        super().__init__(run_id)
        self.run_id = run_id


def run_id_for(plan_id: str) -> str:
    return "pfr-" + plan_id.removeprefix("pfp-")


def _record_hash(record: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(record))


class PrefillRepository:
    def __init__(self, store: LocalVersionStore) -> None:
        self.store = store

    # -- plans ------------------------------------------------------------------

    def save_plan(self, organization_id: str, plan: PrefillPlan) -> None:
        record = plan.model_dump(mode="json")
        self.store.collection(organization_id, PLANS).commit(
            idempotency_key=f"plan:{plan.plan_id}",
            command_hash=plan.plan_sha256,
            object_id=plan.plan_id,
            expected_version=0,
            build=lambda _oid, _v, _prev: record,
        )

    def get_plan(self, organization_id: str, plan_id: str) -> PrefillPlan:
        record = self.store.collection(organization_id, PLANS).read(plan_id, 1)
        try:
            plan = PrefillPlan.model_validate(record)
        except ValueError:
            raise IntegrityFailure("stored plan failed validation") from None
        if (
            plan.plan_id != plan_id
            or plan.organization_id != organization_id
            or plan_hash(record) != plan.plan_sha256
        ):
            raise IntegrityFailure("stored plan failed integrity verification")
        return plan

    # -- runs -------------------------------------------------------------------

    def claim(
        self,
        organization_id: str,
        plan_id: str,
        idempotency_key: str,
        command_hash: str,
        build: Callable[[], PrefillRun],
    ) -> tuple[PrefillRun, bool]:
        """Create run v1 atomically, or replay this exact command's run.

        Raises ``AlreadyClaimed`` when another command already claimed the plan and
        ``IdempotencyReused`` when the key was used for a different command.
        """
        runs = self.store.collection(organization_id, RUNS)
        run_id = run_id_for(plan_id)
        if runs.replay(idempotency_key, command_hash) is not None:
            return self.latest_run(organization_id, run_id), True
        try:
            result = runs.commit(
                idempotency_key=idempotency_key,
                command_hash=command_hash,
                object_id=run_id,
                expected_version=0,
                build=lambda _oid, _v, _prev: build().model_dump(mode="json"),
            )
        except VersionConflict:
            raise AlreadyClaimed(run_id) from None
        run = self._validate_run(organization_id, run_id, result.version, result.record)
        return (self.latest_run(organization_id, run_id), True) if result.replayed else (run, False)

    def append_run(self, organization_id: str, run: PrefillRun) -> PrefillRun:
        record = run.model_dump(mode="json")
        self.store.collection(organization_id, RUNS).commit(
            idempotency_key=f"{run.run_id}:v{run.run_version}",
            command_hash=_record_hash(record),
            object_id=run.run_id,
            expected_version=run.run_version - 1,
            build=lambda _oid, _v, _prev: record,
        )
        return run

    def _validate_run(
        self, organization_id: str, run_id: str, version: int, record: dict[str, Any]
    ) -> PrefillRun:
        try:
            run = PrefillRun.model_validate(record)
        except ValueError:
            raise IntegrityFailure("stored run failed validation") from None
        if (
            run.run_id != run_id
            or run.run_version != version
            or run.organization_id != organization_id
        ):
            raise IntegrityFailure("stored run failed integrity verification")
        return run

    def latest_run(self, organization_id: str, run_id: str) -> PrefillRun:
        version, record = self.store.collection(organization_id, RUNS).read_current(run_id)
        return self._validate_run(organization_id, run_id, version, record)

    def run_for_plan(self, organization_id: str, plan_id: str) -> PrefillRun | None:
        try:
            return self.latest_run(organization_id, run_id_for(plan_id))
        except NotFound:
            return None

    # -- per-field steps --------------------------------------------------------

    def _step_id(self, run_id: str, index: int) -> str:
        return f"{run_id}.a{index:02d}"

    def record_step(self, organization_id: str, run_id: str, receipt: FieldReceipt) -> None:
        """v1 before the mutation (write_in_flight), v2 after read-back."""
        steps = self.store.collection(organization_id, STEPS)
        oid = self._step_id(run_id, receipt.action_index)
        record = receipt.model_dump(mode="json")
        expected = steps.current_version(oid)
        steps.commit(
            idempotency_key=f"{oid}:v{expected + 1}",
            command_hash=_record_hash(record),
            object_id=oid,
            expected_version=expected,
            build=lambda _oid, _v, _prev: record,
        )

    def steps(self, organization_id: str, run_id: str, count: int) -> dict[int, FieldReceipt]:
        steps = self.store.collection(organization_id, STEPS)
        out: dict[int, FieldReceipt] = {}
        for i in range(count):
            oid = self._step_id(run_id, i)
            if steps.current_version(oid) == 0:
                continue
            _, record = steps.read_current(oid)
            try:
                out[i] = FieldReceipt.model_validate(record)
            except ValueError:
                raise IntegrityFailure("stored step failed validation") from None
        return out
