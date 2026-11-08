# services/worker (extension point - not a running service)

Planned home for durable job handlers (ingestion, discovery, model and export jobs;
engineering v1.1 s2, s15). Nothing runs here yet. The shared `JobContext`/`JobResult`
schemas and the `JobStore` port live in `packages/contracts/python`; the default
`UnconfiguredJobStore` fails explicitly. Add a uv workspace member here only when a
feature spec implements a real worker.
