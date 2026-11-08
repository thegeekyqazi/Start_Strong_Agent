# Feature development specs

The project owner supplies one feature development spec at a time after selecting the work to implement. Store each here with a stable task ID and revision. No placeholder in this kit represents an approved feature spec.

Each spec should identify goal/scope, repo context, contracts/dependencies/fixtures, implementation requirements, applicable deterministic rule IDs and tests, acceptance criteria, integration/handoff and permitted discretion. Link its engineering baseline and any explicit superseding decisions. Update by reviewed revision when scope changes; do not rewrite requirements simply to make a faulty implementation pass.

## Dev A validation

- `A3-VAL-003_Deterministic_Validation_Runner.md` rev 1.0: repository-native deterministic source/numeric validation, immutable receipts and A4 dependency output. Implementation status: A3a/A3b implemented on `dev-a/a3ab-val-003-source-validation`; A3c numeric/C2 integration remains separate.

## Dev A pack replacement

- `A4-PKG-004_Pack_Replacement_and_Invalidation.md` rev 1.0: strict immutable manifests, per-context active packs, structured A/B diffs, exact reverse-dependency invalidation and inactive-pack gates. Implementation status: implemented on `dev-a/a4-pack-replacement`; real C approval/export and B browser-grant consumers must register when their durable producers land.
