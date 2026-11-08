# Funding fixtures (owner B1)

`sample-capture-v1/` is a **synthetic** capture record for B2 (B1-DISC-001 s9, launch agreement s3). It was produced by the real B1 capture code in **fixture mode**: the fixture capture provider plus `LocalCaptureStore`, against the registered synthetic page `https://demo-funder.example/programs/community-grants` (reserved `.example` domain).

- `record.json`: a `CapturedDocument` (semantic v1). `provider_mode = fixture`, `provenance.is_simulated = true`, and authority comes from the FIXTURE discovery seed.
- `artifacts/<artifact_id>`: the exact stored bytes of each representation. Each file's SHA-256 equals `artifacts[].sha256` in the record.
  - `...-markdown`: `provider_markdown`, for read-only context.
  - `...-html`: `provider_html`, the main-content HTML. It is importable by B2 and contains a `<form>` with `mission` and `services` textareas.
  - `...-raw-html`: `provider_raw_html`. It is importable by B2 and deliberately contains a `<script>`, a tracking `<img>` and hidden instruction text, to test inert handling.

These files are not a live capture and not partner material. No secrets are included. To load the sample into a store, use `LocalCaptureStore.save(record, {sha256: bytes})` (see `tests/funding/test_store.py`). Live code paths serve the same shape via `GET /api/funding/captures/{capture_id}` and `.../artifacts/{artifact_id}/content`.
