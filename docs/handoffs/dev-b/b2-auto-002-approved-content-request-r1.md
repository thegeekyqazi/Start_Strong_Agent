> INT-001 adoption (2026-11-08): engineering ownership and current producer/consumer
> integration are recorded in the [integration handoff](../integration/int-001-approved-content-currentness-r1.md).
> This historical note retains its original status, evidence and limitations below.

# B2-AUTO-002: Request to Dev C for an approved-content reader for prefill (r1)

- Author/lane: Dev B agent (Claude Code, claude-opus-5-5) for the project owner (Dev B)
- Intended consumers: **Dev C** (producer of the requested reader); owner; Dev A (FYI, s5)
- UTC timestamp: 2026-11-08
- Status: proposed (contract request). Nothing here is accepted until Dev C replies.
- Task spec path/revision: `docs/specs/B2-AUTO-002_Approved_Prefill_and_Read_Back.md` rev 1.0, s5, s7, s11
- Engineering version/sections and rule IDs: v1.1 s9.2, s10.5, s13.2-13.3, s20; APP-04 (C), SEC-14, AUT-02/03 (B)
- Branch and exact implementation commit: `dev-b/b2-auto-002-approved-prefill`, P0 commit (see PR)
- PR / Issue links: the B2-AUTO-002 draft PR. Also announced on C3 PR #10.
- Supersedes / superseded by: none

## The gap

Prefill must enter the exact approved text. On `main` (`c490dba`), C3's `StoreApprovedAnswerResolver.resolve(org, approval_id)` returns an `ApprovalSnapshot`: IDs, `content_sha256` of the **editor/template** text, and dependencies. It contains **no text**. The rendered text, the version funders would read with `{{fact:…}}` slots resolved, is in C's private `StoredVersion.rendered`.

B will **not**:

- read `AnswerStore`, `StoredVersion` or the resolver's private `_find`;
- call C's HTTP routes through loopback;
- accept answer text from the browser and compare only a claimed hash.

## Request: one narrow C-owned reader

B has declared the port it consumes in the B-owned contract module `strongstart_contracts.automation_prefill`. C may adopt these names, or publish its own and tell B. B will adapt.

```python
class ApprovedPrefillReader(Protocol):
    is_fixture: bool

    def resolve_for_prefill(
        self, organization_id: str, approval_snapshot_id: str
    ) -> ApprovedPrefillContent: ...
```

The reader raises `strongstart_contracts.fixture_adapters.ApprovalNotUsable(approval_id, reason)` for missing, other-organization, rejected and stale approvals. Missing and other-org must be indistinguishable. Unconfigured raises `CapabilityUnavailable`.

`ApprovedPrefillContent` must be **one consistent envelope** read under C's own consistency rules, not several unrelated reads:

| Field                                                       | Meaning C must guarantee                                                                                                                                                               |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `approval: ApprovalSnapshot`                                | Exactly what `resolve()` returns now, live                                                                                                                                             |
| `organization_id`                                           | Server-derived organization, which B checks against its own                                                                                                                            |
| `answer_version_id`, `answer_version`                       | Equals `approval.answer_snapshot_id`; the immutable version that was approved                                                                                                          |
| `question_set_id`, `question_id`, `question_version`        | The question identity the approval names. For B these must be B's **published** IDs (`qs-def-…-vN`, `def-…:<original>`). `mission-q1` is a different question and cannot be relabelled |
| `template_text`, `template_sha256`                          | Exact editor text; `sha256(template_text) == approval.content_sha256`                                                                                                                  |
| `rendered_text`, `rendered_sha256`, `renderer_version`      | Exact saved `RenderedAnswer.text` of **that** version and its own hash. `unresolved_marker_count` is 0 for a fillable answer                                                           |
| `dependency_snapshot_sha256`, `dependencies`                | C's approved snapshot hash. A fresh recomputation still matches (`stale_reason` is `None`)                                                                                             |
| `currentness`, `currentness_checked_at`                     | `"current"` and the time of this check                                                                                                                                                 |
| `typed_value` (optional)                                    | A C-authorized typed choice (`kind="choice"`, `values=[…]`) for select/radio/checkbox questions. Null means text only; B then holds choice controls                                    |
| `provenance`, `is_fixture`, `producer_id`, `producer_epoch` | Fixture/simulation labels. `producer_epoch` changes when the process-local fixture store restarts                                                                                      |

B independently recomputes both hashes and refuses any mismatch, any token left in the rendered text, any identity mismatch and any epoch change. B never re-renders facts or substitutes values.

### How B calls it

- Once at planning.
- Again immediately before **each** field action.
- Once after the action, and once at run completion.

B does not hold a lock while calling C. This gives pre/post-check detection, **not** a zero-race guarantee against a C edit during an in-flight browser operation. Such a run is labelled stale/partial. A stronger guarantee would need a C/A action permit, which is not requested now.

### Wiring

- Expose it through a C-owned public factory, for example `strongstart_api.features.applications.public.get_approved_prefill_reader`.
- B's dependency provider `strongstart_api.features.automation.prefill_deps.get_approved_prefill_reader` currently returns the unconfigured reader. Once C publishes the factory, B will point that provider at it.
- Shared `ports.get_approved_answer_resolver` stays as is unless the owner decides otherwise.

## Second need: question identities (C2b)

C's workspace is the `demo-bundle@1` fixture. For a real save → approve → resolve → entry test, C needs to answer B's saved question set, through `ApplicationDefinitionReader` (C2b) or a C-owned test workspace adapter. Until then, B's P2 joined test stays pending. B will not rename approval IDs.

## Choice values

If C cannot yet authorize typed choice values, B enables text fields only and reports choice controls as `held_choice_value_unavailable` in the integrated capability. B's P1 test provider exercises choices and conditions only as a harness.

## FYI Dev A (A4)

A4's currentness is HTTP-only on `main`. B will not call it through loopback. B asks for an in-process consumer factory that does two things:

- registers a target with exact `(kind, ref_id, version)` tuples;
- reads its current state.

B would register `prefill-plan` and `prefill-grant` targets. Until that factory exists, the B2-AUTO-002 A4 adapter stays disabled and is reported as not integrated.

## Consumer action / blockers

- **Dev C:**
  1. Accept, adjust or reject the DTO and protocol above.
  2. Publish the reader and factory.
  3. Say whether typed choice values are in scope.
  4. Name the C2b or test-workspace route to B question IDs.
- **Dev A:** say whether an in-process currentness factory is planned.
- **B continues** P1 on an explicitly injected test provider. Its results are labelled fixture/harness-complete.

## Acknowledgments

None yet.
