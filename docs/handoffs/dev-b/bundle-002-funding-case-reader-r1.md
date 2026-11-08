# DEV-B-BUNDLE-002 M3/M4: funding-case reader and evaluation report contract (r1)

- Author/lane: Dev B agent (Claude Code, claude-opus-5-5) for the project owner (Dev B)
- Intended consumers: Dev C (future requirement/answer dependencies), Dev A (A3 runner registration), owner
- UTC timestamp: 2026-11-08 (M3/M4 checkpoint)
- Status: ready-for-review (producer). No consumer integration is claimed.
- Task spec: `docs/specs/DEV-B-BUNDLE-002_Saved_Grant_Workspace_and_Reviewed_Research.md` rev 1.0, s7-s8, s13
- Engineering: v1.1 s9, s10.3-10.4, s14-15, s20.3, s20.6
- Branch/PR: `dev-b/dev-b-bundle-002`, https://github.com/thegeekyqazi/Start_Strong_Agent/pull/12 (draft), commit "feat(funding): reviewed funding cases and deterministic evaluations (M3, M4)"

## Public imports

```python
from strongstart_contracts.funding_review import (
    FundingCaseReader,  # Protocol: is_fixture, get_version(org, case_id, version), get_current(org, case_id)
    FundingCaseEnvelope,  # version + version_digest + review + source_status + readiness + projections
    FundingCaseNotFound,  # unknown and other-org IDs (indistinguishable)
    FundingCaseIntegrityError,  # stored version/review failed verification; withhold
    EvaluationReport,
    RequirementEvaluation,
    DeadlineSpec,
    resolve_local_deadline,
)
from strongstart_api.features.funding.public import (
    get_funding_case_reader,
    build_funding_case_reader,
)
```

Production returns `UnconfiguredFundingCaseReader`, which raises `CapabilityUnavailable`. The repository is the development/test Dev B local store.

## Envelope semantics (`b1-funding-case/1`)

- `version` is immutable. `version_digest` is the SHA-256 of its canonical JSON. A `review` exists only for that exact digest (server reviewer/time), and an edit creates a new, unreviewed version.
- `readiness` takes one of these values: `no_rules`, `not_reviewed`, `requires_re_review` (a linked recheck after review was changed, partial, failed or not comparable), or `ready_for_evaluation`.
- `opportunity` is the shared `Opportunity`, emitted only when funder, stream, cycle and a source are established. Its `deadline` is a **date only**. Use the reviewed `DeadlineSpec` (time, zone, offset, fold, boundary) for any cutoff logic.
- `requirement_set` is the shared `RequirementSet`, emitted only when reviewed. Every `evaluation` is `unknown`, because no verified organizational facts exist (no A `EvidenceProvider` mapping). Never treat a scenario report as a pass.
- Anchors carry capture/artifact/source-version IDs, the artifact SHA-256, exact code-point offsets and the quote. `verification` means "quote matched hash-verified bytes"; it does not mean the interpretation is correct.

## Evaluation reports (M4)

`POST /api/funding/cases/{id}/evaluations` stores an `EvaluationReport`. The report contains:
- exact case version/digest and review digest;
- the clock (`request` or `server`);
- scope;
- typed inputs with `staff_asserted`/`simulated` provenance;
- `inputs_digest`;
- per-rule results: what was compared, support excerpt, inputs used, what was found, uncertainty, next action, and a shared `ValidationResult`;
- excluded rules with reasons;
- the all-of group outcome;
- `reliance_status: not_confirmed` (always).

Mapping to `ValidationResult`: met→pass, not_met→fail, unknown/at-cutoff→needs_review, n/a→not_applicable. Primary rule IDs: deadline DAT-02, window DAT-04, amount ELG-03, membership/activity ELG-02, invitation ELG-04.

**For A3:** the pure predicates are `strongstart_api.features.funding.rules.evaluate_one/evaluate_case/all_of`. They take typed inputs and do no I/O, so they can be registered behind A3's runner without a competing engine. Registration is pending; no runner exists on main.

## Validation

`make check` exit 0: 539 pytest, 68 Vitest. `tests/funding/test_cases.py` has 35 tests (BND-22..27, 39, 40 plus boundaries) and `tests/funding/test_rules.py` has 30 (BND-28..38).

## Limitations

- Scenario inputs are per evaluation only. Evidence-backed inputs stay missing until A publishes an authorized fact mapping.
- DAT-05 (claim-time suitability) is not addressed.

## Acknowledgments

None yet.
