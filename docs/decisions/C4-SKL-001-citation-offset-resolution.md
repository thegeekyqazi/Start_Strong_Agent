# C4-SKL-001-citation-offset-resolution: server-derived offsets for exact, unique model quotes

- Author/developer: Claude (coding agent) for the project owner, live demo launch task `demo/live-launch-001`
- Date: 2026-11-08
- Status: developer-decision (needs maintainer acceptance before it is treated as the C4 contract)
- Decided/accepted by and evidence: developer decision during the live launch; real Gemini evidence below
- Engineering path/version/sections: `docs/engineering/StrongStart_Engineering_Plan.md` (practice-skill source mapping)
- Feature spec path/revision: `docs/specs/C4-SKL-001_Thin_Practice_Generator_and_Draft_Preview.md` r1.0
- PR / Issue: demo/live-launch-001 PR
- Supersedes / superseded by: none

## Original requirement

Every proposed practice rule must cite exact source text. `verify_span` rejected a citation
unless the model-reported Unicode code-point offsets `[start, end)` sliced exactly to its
`quote` (`citation_not_exact_source_text`).

## Decision / deviation and reason

First real Gemini run (`gemini-3.5-flash-lite`, synthetic `demo` source) was rejected with
`citation_not_exact_source_text`. The previous C4 evidence used only the fixture adapter, which
emits computed offsets. Language models count code-point offsets unreliably, while quoting
exact text is a task they do well. The raw model output is deliberately not logged, so the
diagnosis is an inference: the quotes were exact but the offsets were wrong. A rerun on the
same source after this change passed, and every resulting span satisfies `text[start:end] == quote`.

New rule: if the reported offsets do not slice to the quote, the server searches for the exact
quote. Only if it occurs exactly once does the server use that occurrence's offsets. An absent,
case-different or ambiguous (repeated) quote is still rejected. Offsets that already match
are kept unchanged, as before.

Alternatives considered: asking the model to retry, which costs more paid calls and is no more
reliable; dropping offsets from the schema, which is a larger contract change; disabling the
check, which is rejected outright.

## Impact and coordination

- Stored `SourceSpan` records keep the same shape and invariant (`quote` is exact source text).
- An ambiguous quote is never guessed, so the citation still identifies one exact location.
- The C owner/maintainer should review; no other lane consumes this function.

## Validation and rollback

- `tests/skills/test_citation_spans.py`: exact offsets kept; wrong offsets with a unique exact
  quote resolved; non-exact, case-different and ambiguous quotes rejected (5 passed).
- `pytest -m db tests/skills` (4 passed, local disposable PostgreSQL).
- Live: candidate `pcand-5eb94918feea73f0107fb214` (TigerData TEST) with exact spans.
- Rollback: revert the `verify_span` change; live Gemini proposals then fail closed again.
