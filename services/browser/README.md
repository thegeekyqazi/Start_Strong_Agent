# services/browser (extension point - owner B2)

Planned restricted browser worker (FormAdapter: inspect, validate_mapping, plan_prefill,
execute_approved_prefill, read_back; engineering v1.1 s16). Not implemented.

INIT-001 provides only a readiness smoke test (`make browser-smoke`,
`tests/browser/test_browser_smoke.py`) that opens a local static fixture in Chromium
and reads a value back. That is not approved prefill and has no submit/sign capability.
