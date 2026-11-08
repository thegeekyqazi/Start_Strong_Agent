# Dev C: Lane execution plan (C1-C4, I1-I2)

- Revision: 1.0 (accepted by the project owner 2026-11-07 for commit; task specs still need individual "go")
- Lane: Dev C. Draft, review, practice skills, shared shell and integration coordination
- Branch: `dev-c/c0-lane-plan` from `origin/main` `45b4488` (includes B1 PR #1 and B2 PR #2)
- Baseline: `docs/engineering/StrongStart_Engineering_Plan.md` v1.1, s8, 9, 10.5-10.6, 11, 13, 14, 15, 16, 17, 18, 20, 21; `StrongStart_Check_Catalog.json`
- Status: a work allocation and sequence. **Not** an approved feature spec. Each task gets its own spec in `docs/specs/` before code, as was done for B1/B2.

Rule for this document: every item traces to the engineering plan, the catalog or a merged/published teammate handoff. Anything the plan leaves open is listed under open questions, not invented.

## 1. What Dev C owns (engineering s20.2, s20.5, s20.8; ownership.md)

| Area | Source |
| --- | --- |
| Model adapters, answer planning/drafting, claim bindings, application editor | s20.2 Dev C row, s8, s17 |
| Staff approval, DOCX/audit export | s20.2, s9.2, s15, s16 |
| Practice-skill generator, screening, release | s20.2, s11, s13.1 |
| Writing checks (APP, POL) and C's SEC/JOB checks: 37 rules | s20.6, catalog `primary_owner: Dev C` |
| Application shell, navigation, shared finding/evidence components | s20.2, s20.5 ("UI shell, common finding/evidence components and fixture adapters") |
| Real `ApprovedAnswerResolver` | `ports.py`, ownership.md, B2 handoffs |
| Approved-practice extraction from U01 and protected-language examples (A checks locators) | s20.5 |
| Integration coordinator for I1/I2, the feature freeze and the feature matrix | s20.4, s20.8 steps 1 and 8, s21 |

C is the coordinator, not the fixer of other lanes' faults (s20.8).

## 2. Upstream state at plan time (fetched 2026-11-07)

| Producer | Ref | What C consumes | Status |
| --- | --- | --- | --- |
| INIT-001 | `main` | Shell, registry, contracts, `demo-bundle@1` fixtures | merged |
| B1-DISC-001 | PR #1, merged | `/api/capabilities` runtime status; no C action | merged |
| B2-AUTO-001 | PR #2, merged | `AutomationHandoffExport` with embedded `QuestionSet`/`FormMap`, `unresolved`, `limit_conflicts`. Counting conventions are `unknown` (APP-01 is C's). B2-AUTO-002 needs C's real resolver | merged; C acknowledgment pending |
| A1-KNOW-001 | PR #3, draft, `dev-a/a1-know-001-source-fact-foundation` | `GET /api/knowledge/evidence/{pack_version_id}` returns the unchanged `EvidenceBundle`. Simulated `needs_review` facts must not be shown as verified or current | open; C acknowledgment pending |

A and B are working in parallel right now. C stays on fixtures until each seam's real producer is merged (s20.3: "A passing mock is not evidence that the real integration works").

## 3. Task sequence

The order expresses dependencies (s20.4). One active task and one branch/PR per task.

### C1: App shell, editor fixture UI and first model adapter

- Branch: `dev-c/c1-shell-and-adapter`. Spec: `docs/specs/C1-shell-and-adapter.md` rev 1.0 (proposed).
- Plan text (s20.4): starts with EvidenceBundle/QuestionSet fixtures. The adapter test is independent of live search or ingestion.
- Delivers:
  - shared `EvidenceCard`, `FindingRow`, `StatusDot` and `HashChip`;
  - the Application workspace (s18 row "Application", fixture only);
  - the `ModelAdapter` with a capability declaration (s17), the deterministic FakeAdapter and the GeminiAdapter (s23.1 "Gemini first"), disabled without a key;
  - strict validation of model output.
- Checks (boundary coverage only, catalog stays `planned`): SEC-05, SEC-06, SEC-07, SEC-14.
- Gate: G0 UI part ("C UI", s20.7).

### C2: Plan and draft answers with claim bindings and visible findings

- Branch: `dev-c/c2-draft-claims`.
- Plan text (s20.4): the fixture implementation starts after C1. Real completion needs A2 retrieval, the A3 runner and B2 questions.
- Delivers:
  - the answer planner (s7: map all selected questions, select evidence, list missing data, no invented request or spend);
  - bounded writer and reviewer roles (s8.1);
  - fact slots rendered by the server and an unbound-number scan (s8.2);
  - evidence explanations (s8.3);
  - findings in the editor (s18).
- Checks: APP-01 (versioned counter), APP-02, APP-03, POL-01, POL-02, POL-03, POL-04 (P1), SEC-12.
  APP-05 is enforced at C's retrieval boundary using A's primitive (s20.6).
- Real seams: replace the fixture `QuestionSet` with B2's `AutomationHandoffExport`, and the fixture `EvidenceBundle` with A's evidence route once A2 is merged. Rules register in A3's runner.
- Gate: G1 ("Real A evidence reaches C editor/draft; real B questions render with limits/conflicts").

### C3: Exact-version staff approval, invalidation handler, DOCX/audit export

- Branch: `dev-c/c3-approval-export`.
- Plan text (s20.4): needs the C2 state contract and uses fixture check results initially. Done after A3 real checks and an edit-after-approval test. Unblocks B3 real prefill.
- Delivers:
  - the Review view (s18 row "Review");
  - answer states draft → checking → needs_attention → ready_for_review → approved → stale/rejected (s15);
  - the approval snapshot (s15);
  - the approve gate (s9.2);
  - the real `ApprovedAnswerResolver` for B2-AUTO-002;
  - the ChangeSet invalidation consumer;
  - DOCX plus JSON audit export with working/reviewed modes and simulation labels (s16).
- Checks: APP-04, APP-06 (P1), APP-07 (P1), APP-08 (P1), POL-05 (P1), JOB-02, JOB-05, SEC-10.
- Gate: G2 ("staff approval and B form read-back ... B+C prove exact approved transfer").

### C4: Practice proposal, compiler, scans/classifier, test/review/activate/revoke

- Branch: `dev-c/c4-practice-skills`.
- Plan text (s20.4): the schema can start early with U01 fixtures. Real activation needs A2's approved policy provenance and the A/C permission/version gates.
- Delivers:
  - the s11.2 pipeline (steps 1-10);
  - the restricted v1 schema (s11.3);
  - skill states (s11.4);
  - the Skill review panel (s18).
  Generated skills are instructions and finite data only; nothing is executable (AGENTS.md).
- Checks: SKL-01 to SKL-14, plus SKL-15 and SKL-16 (P1).
- Gate: G3 ("Safe practice increment").
- s20.6 allows A to take a bounded compiler/provenance subtask if C4 bottlenecks. Record any such transfer explicitly.

### I1 / I2: Integration (all lanes; C coordinates)

- I1 (s20.4): replace the mock seams and join one full application path. Needs A2/A3, B1/B2/B3 and C2/C3.
- I2 (s20.4): pack swap, skill invalidation, deployment and final rehearsal (G4, G5). Needs A4, C4, B4 and I1.
- C's coordinator duties (s20.8):
  - run the feature freeze;
  - keep the feature matrix of implemented, fixture-only, unavailable and planned items (s21);
  - run the demo script (s21 steps 1-11) and two rehearsals.

## 4. Check allocation summary (catalog, Dev C = 37)

| Task | Rule IDs |
| --- | --- |
| C1 | SEC-05, SEC-06, SEC-07, SEC-14 (boundaries; full enforcement at every later action boundary) |
| C2 | APP-01, APP-02, APP-03, POL-01, POL-02, POL-03, POL-04, SEC-12 |
| C3 | APP-04, APP-06, APP-07, APP-08, POL-05, JOB-02, JOB-05, SEC-10 |
| C4 | SKL-01 to SKL-16 |
| Consumed, not owned | APP-05 (A primitive); SRC/NUM findings (A); DAT/ELG/AUT (B) |

The per-task split is this plan's proposal; the catalog fixes only the owner. A verifies C's fixtures (s20.6 cross-review cycle). Every status stays `planned` until an actual test proves it.

## 5. GitHub practice for every C task (AGENTS.md, coordination/README.md)

1. `git fetch origin --prune`, then read new handoffs/PRs from A and B through `git show <ref>:<path>`, without checking out their branches.
2. Branch from the latest `origin/main` as `dev-c/<task-id>-<slug>`, with no upstream tracking to `main`.
3. Write the spec first (`docs/specs/C<n>-*.md`) and get the owner's "go" before code.
4. Commit small coherent increments, adding files explicitly. Messages follow the AGENTS.md format: Spec, Task-Spec, Checks, Validation, Deviation. No force-push, no direct push to `main`.
5. Run `make contracts` after every contract change or rebase. Never hand-edit the generated files.
6. Run `make check` and `make smoke` (and `make browser-smoke` where UI e2e applies), and report actual output.
7. Before handoff, record deviations in `docs/decisions/C<n>-*.md` and write the handoff in `docs/handoffs/dev-c/c<n>-*-r<k>.md`.
8. Ask the owner before push or PR. Use a draft PR from `.github/PULL_REQUEST_TEMPLATE.md`, and merge only under the owner's policy.
9. Fetch again every 60-90 minutes and at every dependency boundary. Acknowledge consumed producer versions in the PR or Issue.

## 6. UX/UI direction (from a read-only UX design pass, filtered to plan scope)

Users are non-technical grant staff. The stack stays as it is: React, plain `index.css`, hash navigation, no UI library or new dependency.

### 6.1 Principles (s18, s8.3, s9.2)

1. **Separate signals.** Evidence support, time suitability, staff review, simulation provenance and security screening each get their own labelled line. If a signal has no data, it is not drawn. There is never one green badge for everything (s18).
2. **Unknown is a word.** A null value, unit or period, `unit: unknown` or `required: null` shows the word "unknown". It is never guessed or hidden.
3. **A pass names only its own predicate.** For example, "248 of 250 words" (s18).
4. **Every finding answers five things:** what it is, why, the support, the exact value or rule, and the next action (s8.3, s18).
5. **Model output is a suggestion,** never "approved" (s14.2, SEC-14).
6. **Status is never shown by color alone.** Each status has text and a shape.
7. **All content renders as inert text** (SEC-07).

### 6.2 Shared components (C1; reusable by A and B)

- **`StatusDot`**: the states from s15. C1 ships draft, needs_attention, approved and stale; C3 extends it to the full s15 set.
  - Copy: "Draft – not reviewed", "Needs attention", "Approved (this exact version)", "Out of date – approval no longer applies".
  - Approved and stale appear only in tests until C3.
- **`HashChip`**: "Version fingerprint: a1b2c3d4e5f6…". The full hash is reachable by keyboard and screen reader.
  - `null` reads "not computed". Non-hex reads "invalid hash".
- **`EvidenceCard`** (`Fact`): shows the value and unit, scope, population, period (raw), source/version, locator (as text, never a link) and publication date. Then come labelled lines for:
  - staff review (`fact.status`);
  - source verification (`verification_status`);
  - time suitability (quotes `coverage_notes` only; nothing is computed);
  - provenance ("Simulated – synthetic demo data", "Derived from the engineering plan, not the original guide").
- **`FindingRow`**: a presentational shape (origin, outcome, message, observed/expected, affected text, support, next action, href). The shared `ValidationResult` does not yet carry message, span or next-action fields (open question).
  - Badges: "Problem found", "Needs your review", "Passed this check only", "Not applicable", "Note".
  - Question-data notices say "From question data, not a validation check".
  - Only `#/` and relative links are allowed. Any other link is shown as text.

### 6.3 Application workspace (C1; s7, s8.2, s15, s18 "Application")

- **Questions (left):** order, section and text. Tags read "Required" or "Required: not stated", "Limit conflict" and "Unit unknown".
- **Centre:**
  - The original wording, read-only, with its provenance line.
  - The limit exactly as the data states it:
    - partnership-q3 shows **both** 350 and 500 with their sources and does not choose one;
    - pending-q4 says "Max 300; the guide does not say words or characters".
  - The "Your answer" editor.
  - A live counter labelled "placeholder count; counting convention unverified". Going over the limit is shown in text, e.g. "12 over".
  - "Request a draft", then a fact-slot preview. Chips read "120 children · 2025-09/2026-06 · Simulated · Not verified".
  - Draft details: "Drafted by: demo writing assistant (fixed sample output, not an AI model)", a HashChip, the uncertainties and "Draft – not reviewed".
- **Never overwrite staff text (s15).** If the editor has text, the draft appears as a separate "Suggested draft" with an explicit "Replace my text with this suggestion".
- **Evidence (right):** "Evidence for this application. Not yet matched to individual questions."
- **Error states:** each has its own plain-language message and says "Your text is unchanged". Technical codes go under "Technical details". The states are 401, 503 workspace, 503 draft ("we don't switch to another assistant automatically"), 502 rejected output, 504 timeout, 409 version conflict, 403 data class, 429 and 404. The exact copy goes in the C1 spec.
- **Layout:** three columns when wide. At medium width, evidence moves below the editor. On narrow screens the panes stack in reading order.
- **Accessibility (implementation quality, not a feature):** labels, `aria-live` counter, `aria-busy` while requesting, visible focus, ≥ 4.5:1 contrast.

### 6.4 Later views (outline only; plan text)

- **Review (C3, s18):** source excerpt, exact answer changes, checks, review controls and export/prefill readiness. Approval is bound to the exact hash, and an edit makes it stale (APP-04). Working and reviewed export are separate modes with labels.
- **Skill review panel (C4, s18, s11.2 step 8):** source-to-rule map, scopes, flags, tests, version diff and activate/revoke by exact hash, plus the s11.4 states. This is the only place the security-screening signal appears.

### 6.5 Excluded from the UX pass (not in the plan, or it would break a shared contract)

- Changing the fixture banner from `role="alert"`: this would break `App.test.tsx:57`, and A/B pages use the same pattern.
- Styling B1's page classes from the shared CSS: that is B1's page, so offer it to B1 instead.
- Clicking a chip to highlight its evidence card: an extra interaction the plan does not specify.
- Rewording the nav or capability labels (e.g. "(C)", "Fixture only"): these are shared strings and need agreement across lanes. Listed as an open question.
- New color tokens (`--c-info`, `--c-simulated`) are allowed only as additions to `:root`. Existing colors stay as they are.

### 6.6 UX questions: owner decisions (2026-11-07)

The owner said "do this as well" to the recommended answers below.

1. **FindingRow** keeps its presentational shape for now. Adding message, span and next-action fields to `ValidationResult` (s9.1) is proposed to A3/C2 as a shared-contract change. C does not make it alone.
2. **The s16 yellow/green/blue scheme** stays export-only (C3). The editor uses the s6.1 separate-signal labels.
3. **pending-q4 (unit unknown):** the counter shows **both** a word count and a character count, and does not choose a limit unit.
4. **Staff-friendly nav wording** is proposed to A and B and is not changed by C alone, because the strings are shared. The current labels stay until the lanes acknowledge.

## 7. Open questions and blockers

- Tooling on this machine: `uv` and `gh` are not installed. Without `uv` no `make` target runs; without `gh` C cannot read or post PRs/Issues (git fetch works).
- Gemini model ID and quota are unconfirmed (s23.1: "confirm actual model IDs/endpoints"). The model name must be configured, not assumed.
- Counter convention for the representative form is unconfirmed (s23.1). B2 reports conventions as `unknown`, which affects APP-01 in C2.
- s17 defines a separate `AgentRuntimeAdapter` and a later Featherless adapter. No s20.4 ticket schedules them, so they are **not** in C1-C4 unless the owner adds them.
- U01 (writing guide) is not in the repo (INIT report s7). C4 and the s20.5 practice extraction need it, or they stay on labelled fixtures.
- C has not yet acknowledged B2-AUTO-001 or A1-KNOW-001. Acknowledge in their PRs once `gh` access exists.
