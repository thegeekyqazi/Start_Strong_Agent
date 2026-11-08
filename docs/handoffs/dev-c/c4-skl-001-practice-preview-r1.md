# C4-SKL-001 thin practice generator and draft preview — revision 1.0 handoff

**Status:** thin working slice implemented; lean checkpoint verification (owner time-budget update
2026-11-08, decision `C4-SKL-001-thin-practice-preview`). Not full C4/G3/G4, not all SKL-01…16,
not production-ready. Broader regression is left for the integrated release check.

- Branch `dev-c/c4-skl-001-practice-preview`, **stacked on** `data/data-001-tigerdata-application-state`
  (PR #20, head `068f5aa`). Integration order: PR #20 first, then this PR retargeted to `main`.
- Spec: [C4-SKL-001 r1.0](../../specs/C4-SKL-001_Thin_Practice_Generator_and_Draft_Preview.md);
  engineering v1.1 §§4–5, 8.2–8.3, 9, 12, 13, 15–18. Migration `0010_practice_skills` (after `0009`).
- Owners: project owner (engineering); Sawaab (UI/UX) — see [UI contract](c4-skl-001-ui-contract.md).
  Demo steps: [demo guide](c4-skl-001-demo-guide.md).

## What works

Synthetic or administrator-authored source → explicit authority review for one server-owned scope
→ candidate from the configured ModelAdapter (`propose_practice`, strict JSON, exact code-point
citations verified against the stored text) → deterministic compiler (fixed `SKILL.md`,
`rules.json`, `references/policy-excerpts.md`; canonical package hash) → static raw+normalized scans
(override, exfiltration/URL, executable, path, hidden/format characters, secret canary with
quarantine and redaction, unregistered name, numeric constants) + base-policy conflict detection →
finite rule tests through the real POL-01/POL-02 engine via the public Applications check port →
`screen_practice` signal requiring complete part coverage → exact-hash staff review (source support
confirmation, acknowledgments for review items; hard gates cannot be acknowledged) → guarded
idempotent activation (one active release per scope, supersession recorded) → use-time resolver
(re-verifies package/source hashes, authority, currentness) → working-only preview: baseline vs
practice draft through C's real draft/render/check pipeline, applied-instruction trace, and the
same sample checked with base policy vs composed policy → revoke / new source version blocks the
next use.

Storage: `skl_scope_state` (row locked `FOR UPDATE`; currentness check, writes and audit in one
transaction) and append-only `skl_records`, on the DATA-001 PostgreSQL engine. No memory fallback
(503 `practice_store_unavailable`). Previews always carry `working_preview_only=true`,
`approval_permitted=false`; no approve/export/prefill path exists from them.

Normal Applications drafting is unchanged: `draft_answer(practice_guidance=None)` sends byte-identical
instructions/payload (existing tests pass unchanged).

## Exactly what ran (2026-11-08)

| Command | Result | Kind |
| --- | --- | --- |
| `uv run pytest -m db tests/skills` | 4 passed | Real API + local PostgreSQL 17 (disposable DB) + real C pipeline; FakeAdapter fixture and explicit test-only adapter overrides |
| `make check` (once, at checkpoint) | exit 0: ruff/format, strict mypy 248 files, TS, 819 pytest, 103 Vitest, contract drift, builds | Unit/static |
| `make contracts` | regenerated schema + TS with `strongstart_contracts.skills` | Static |
| `uv run python scripts/c4_walkthrough.py` | passed in Chromium (Python Playwright), 0 console errors, 0 external requests | Actual API (uvicorn, fixture mode, local PostgreSQL DB `strongstart_c4_demo` at 0010) + actual Chromium UI |

The four essential checks from the owner's update, by test:

1. Source → candidate → review/activate → draft preview:
   `test_source_to_candidate_to_activation_to_draft_preview` (also: guidance reaches the draft
   model payload, baseline call does not get it; sample flagged `kids`→`children` and the
   protected-name variant; core APP/POL checks still present; forged `approved` field → 422;
   deterministic recompilation hash).
2. Tampered hash or incomplete screening cannot activate:
   `test_tampered_hash_incomplete_screening_and_hostile_candidate_cannot_activate` (trailing-part
   omission → held; reversed hash → 409/422; activation without review → `review_missing_or_stale`;
   hostile candidate held, never sent to the screening model, package export 422, no secret prefix
   in any response; conflicting source → `scan_block:policy_conflict`).
3. Revocation/source change prevents subsequent use:
   `test_revocation_and_source_change_prevent_subsequent_use` (revoke → `no_active_practice`;
   new source version → `release_stale_source`; fresh app instance reads the same durable state).
4. Missing identity / other organization: `test_missing_identity_and_other_organization_cannot_bypass_access`
   (401 without identity; other org's candidate IDs → 404 and empty overview; non-staff → 403).

Walkthrough finding fixed during verification: planted secret text reached clients through the
source text, citation quotes and package files, and scan excerpt windows could expose a truncated
secret prefix. Client read models now pass through `skills/display.py` redaction; excerpts are
windowed from fully redacted text. Covered by test assertion and the walkthrough.

## Not run / unverified at this checkpoint (honest gaps)

- Full `make smoke` and `make browser-smoke` were **not** rerun (lean scope). `make smoke` now
  includes `tests/skills`; CI will run it. No automated Chromium test was added to the suite.
- C4-14/C4-20 races (event-controlled source revision vs activation; revoke during a model call):
  implemented as guarded single-transaction checks and a post-model resolver recheck, **not**
  tested with process barriers.
- C4-23 audit-failure rollback and unknown-commit behaviour: relies on single-transaction design;
  **not** fault-injected.
- Migration 0010 downgrade: not exercised. Restart persistence: covered only by a fresh app
  instance in-process, not a uvicorn restart.
- Live provider: no Gemini key configured; **all proposal/screening evidence is FIXTURE**
  (labelled in UI and records). No live-provider rehearsal ran. The fixture proposer follows fixed
  sentence patterns and the fixture screener reports `no_flags` for exactly the parts it was sent.
- Hosted TigerData: not run for C4 (DATA-001 hosted gate is separate).
- C4-21 managed A4 identity: no managed A4 binding exists for the synthetic source; not
  A4-integrated and not labelled so.

## C4-01…30 status

Verified = executed test or walkthrough above. Implemented = code path exists, not separately
tested now. Deferred = out of the thin scope.

| ID | Status |
| --- | --- |
| C4-01 | Implemented (strict contracts/extra=forbid; C's strict JSON stage rejects duplicates/depth/size/forbidden keys); forged-field 422 verified |
| C4-02 | Implemented (span/quote/hash check); org scoping verified |
| C4-03 | Verified (authority required before generation; labels) |
| C4-04 | Implemented (two operators only; scans for code/paths/URLs) |
| C4-05 | Verified (recompile → identical hash); metadata-change invalidation implemented |
| C4-06 | Verified (fixed file map; quarantined export 422) |
| C4-07 | Verified (hostile fixture; redaction) |
| C4-08 | Verified (missing trailing part holds activation) |
| C4-09 | Implemented (data-class check before calls) |
| C4-10 | Implemented (server-derived status; forbidden keys) |
| C4-11 | Verified via rule tests in candidate + preview sample |
| C4-12 | Verified (review binds package/scan/tests/screening hashes; holds not acknowledgeable) |
| C4-13 | Idempotent repeat verified; concurrent conflict not tested |
| C4-14 | Implemented, not tested |
| C4-15 | Server-owned single context; unknown context has no fallback (implemented) |
| C4-16 | Verified with FIXTURE adapter |
| C4-17 | Verified |
| C4-18 | Verified (forged field; no approve/export path) |
| C4-19 | Verified (revoke, source change, fresh app instance) |
| C4-20 | Implemented (post-model recheck), not tested |
| C4-21 | Not applicable to the unmanaged synthetic demo; deferred |
| C4-22 | Partially verified (fresh app instance); outage behaviour not tested |
| C4-23 | Implemented by design, not tested |
| C4-24 | Verified (Chromium walkthrough) |
| C4-25 | Implemented (screening unavailable → held with reason), not tested live |
| C4-26 | Verified labelling of FIXTURE evidence |
| C4-27 | Verified (cross-org 404, redaction); production fixture denial inherited |
| C4-28 | `make check` unit regression passed; DB/browser regression deferred to CI/release |
| C4-29 | Chromium walkthrough script (manual run), not a suite test; live rehearsal not run |
| C4-30 | This handoff + feature-status row |

## Next actions

- Owner: review stacked draft PR; merge PR #20 first, then retarget this PR to `main`.
- Release check: run full `make smoke` / `make browser-smoke`, add the race/rollback tests above,
  and a bounded live-provider rehearsal if a key is configured.
- Sawaab: presentation pass on the Skills page per the UI contract.
