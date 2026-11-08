# C2: Non-blocking request to Dev A for a fact version field

- Author/lane: Dev C agent (Claude Code, claude-opus-5-5)
- Intended consumers: Dev A (EvidenceBundle/Fact producer); project owner
- UTC timestamp: 2026-11-08
- Status: proposed (request only; **not blocking** C2)
- Task spec: `docs/specs/C2-draft-claims.md` rev 1.1, s3 and s11 #3 (owner decision)
- Engineering: v1.1 s4.1 ("unique version numbers within each object"), s8.2 (claim bindings), s15 (approval snapshot "selected source/fact versions")

## Request

`Fact` (in `strongstart_contracts/evidence.py`, owned by A) has no version or `updated_at` field. C2 claim bindings therefore reference a fact as `pack_version_id` plus `fact_id`.

C3's approval snapshot must bind "selected source/fact versions" (s15) and stale on a fact change (APP-04/APP-06). A per-fact version makes that binding exact rather than pack-wide.

**Ask:** an additive, optional field on `Fact`, e.g. `fact_version: int | None` (or `updated_at`), in a release that suits A2/A4. Name and shape are A's choice. Existing consumers keep working while it is optional.

## C behaviour until then

- `ClaimBinding.pack_version_id` plus `fact_id` is the binding key, so a pack version change invalidates all bindings from that pack. This is coarser but safe.
- C does not edit `evidence.py`.

## Acknowledgments

None yet. Please acknowledge in the C2 PR thread or reply with the planned version.
