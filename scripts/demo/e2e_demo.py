"""E2E-DEMO: one labelled Strong Start journey over the existing APIs (no new endpoints).

Subcommands
-----------
prepare   Steps 1-3: FIXTURE funding search (context), explicit selection of a labelled
          saved source, intake preview, save its questions, verify that exact question set
          opens in Applications. Prints the IDs/selections for the UI walkthrough. Drafting,
          review, approval, export and portal execution stay with the human operator.
rehearse  Verification only: steps 1-8 over real HTTP against the real C store/approval,
          B planner/runner and Chromium. Browser entry (step 8) happens only with the
          explicit ``--execute-portal`` flag. Approvals are made by the LOCAL fixture
          reviewer identity; that is a rehearsal, not meaningful human review.
status    Read-back of a manifest (answer history, plan availability, stored receipt).

``--source prefill`` (default) is the executable journey; ``--source capture`` is the
labelled capture variant whose representative portal holds every field (zero-write plan).

Everything is LOCAL and SYNTHETIC: fixture identity, FIXTURE sources, synthetic evidence
bundle (demo-bundle@1, not partner records), deterministic fake model, registered
representative portal (not a funder site). Nothing submits, signs or uploads. A non-2xx
response stops with the exact request; nothing is fabricated. Manifests under
.local-data/e2e-demo/manifests hold IDs/hashes/synthetic demo text only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

import httpx

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = ROOT / ".local-data" / "e2e-demo" / "manifests"
LABEL = "E2E-DEMO (LOCAL, SYNTHETIC, FIXTURE)"

# Explicitly selected, labelled saved sources (live search keys are not configured):
#  * "prefill" (default, executable): registered saved definition rep-prefill-definition-v1,
#    bound by the server registry to the positive representative portal rep-prefill-v1.
#  * "capture": B2's FIXTURE capture of representative portal rep-portal-v1 (bytes identical
#    to that portal). B's planner deliberately holds every field of that portal, so this
#    variant ends at a zero-write plan that shows the gating, not a fill.
# B1's fixture funding pages are not registered prefill targets: search is context only.
SOURCES: dict[str, dict[str, Any]] = {
    "prefill": {
        "source": {"mode": "fixture", "fixture_id": "rep-prefill-definition-v1"},
        "catalog_id": "rep-prefill-definition-v1",
        "portal": "rep-prefill-v1",
        "answers": {
            "pf-org-name": "Riverside Youth Collective",
            "pf-summary": "[E2E-DEMO SYNTHETIC] Historical synthetic metric: {{fact:%(fact)s}}.",
        },
    },
    "capture": {
        "source": {
            "mode": "capture",
            "capture_id": "cap-fixture-portal-html",
            "artifact_id": "art-portal-raw-html",
        },
        "catalog_id": "cap-fixture-portal-html:art-portal-raw-html",
        "portal": "rep-portal-v1",
        "answers": {
            "rp-mission": "[E2E-DEMO SYNTHETIC] Riverside Youth Collective supports early "
            "learning in Demo Region.",
            "rp-services": "[E2E-DEMO SYNTHETIC] Historical synthetic metric: {{fact:%(fact)s}}.",
            "rp-other-funding": "[E2E-DEMO SYNTHETIC] No other funding is recorded here.",
        },
    },
}
SEARCH_PROFILE = {"interests": ["early learning", "family literacy"], "geography": "Demo Region"}


def fail(msg: str) -> NoReturn:
    print(f"\nE2E-DEMO BLOCKER: {msg}", file=sys.stderr)
    raise SystemExit(1)


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.c = httpx.Client(base_url=self.base, timeout=120)

    def _check(self, r: httpx.Response, method: str, path: str, body: Any) -> Any:
        if r.status_code not in (200, 201):
            shown = json.dumps(body)[:600] if body is not None else ""
            fail(
                f"{method} {self.base}{path} -> HTTP {r.status_code}\n"
                f"  request: {shown}\n  response: {r.text[:1500]}"
            )
        return r.json() if r.content else None

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._check(self.c.get(path, params=params), "GET", path, params)

    def post(self, path: str, body: Any) -> Any:
        return self._check(self.c.post(path, json=body), "POST", path, body)

    def raw(self, path: str) -> bytes:
        r = self.c.get(path)
        if r.status_code != 200:
            fail(f"GET {self.base}{path} -> HTTP {r.status_code}: {r.text[:800]}")
        return r.content


def step(n: str, title: str) -> None:
    print(f"\n== Step {n}: {title}")


def preflight(api: Api, src: dict[str, Any]) -> dict[str, Any]:
    ready = api.c.get("/health/ready")
    if ready.status_code != 200:
        fail(
            f"GET {api.base}/health/ready -> {ready.status_code}: {ready.text[:600]}\n"
            "  Not migrating/resetting. Start via scripts/demo/start_stack.sh or ask the DB owner."
        )
    funding = api.get("/api/funding/availability")
    if not funding.get("identity_is_fixture"):
        fail("session is not the labelled LOCAL fixture identity; refusing to write demo records")
    avail = api.get("/api/automation/availability")
    if src["catalog_id"] not in {f["fixture_id"] for f in avail["fixtures"]}:
        fail(f"labelled source {src['catalog_id']} is not offered (fixture mode disabled?)")
    return {"browser_status": avail["browser_status"], "environment": funding["environment"]}


def prepare(api: Api, suffix: str, source_key: str) -> dict[str, Any]:
    src = SOURCES[source_key]
    m: dict[str, Any] = {
        "label": LABEL,
        "api": api.base,
        "suffix": suffix,
        "source_key": source_key,
        "portal": src["portal"],
        "started_at": datetime.now(UTC).isoformat(),
    }
    m["preflight"] = preflight(api, src)
    print(f"{LABEL}\nAPI {api.base} ready; Chromium: {m['preflight']['browser_status']}")

    step("1", "funding search (FIXTURE provider), then explicit labelled saved source")
    fa = api.get("/api/funding/availability")
    print(
        "  providers:", {p["operation"]: f"{p['provider']}/{p['status']}" for p in fa["providers"]}
    )
    search = api.post("/api/funding/search", {"profile": SEARCH_PROFILE, "max_results": 5})
    m["funding_search"] = {
        "search_id": search["search_id"],
        "provider_mode": search["query"]["mode"],
        "candidates": [c.get("title") for c in search["candidates"]],
        "omitted": len(search["omitted"]),
    }
    print(
        f"  search {search['search_id']} ({search['query']['mode']}): "
        f"{len(search['candidates'])} candidates, {len(search['omitted'])} omitted as unsafe"
    )
    for c in search["candidates"]:
        print(f"    - {c.get('title')}")
    print(
        "  Live search is unavailable (no provider keys) and FIXTURE funding pages are not\n"
        f"  registered portals. Explicitly selected labelled saved source: {src['catalog_id']}"
    )

    step("2", "import + save its application questions")
    preview = api.post("/api/automation/intake", {"source": src["source"]})
    sha = preview["input"]["sha256"]
    print(f"  {preview['mode_label']}")
    print(
        f"  input sha256 {sha}; {preview['coverage']['questions_extracted']} questions; "
        f"authority={preview['authority_status']}"
    )
    pub = api.post(
        "/api/automation/definitions",
        {
            "source": src["source"],
            "expected_input_sha256": sha,
            "idempotency_key": f"e2e-demo-publish-{suffix}",
        },
    )["publication"]
    m["definition"] = {
        "definition_id": pub["definition_id"],
        "version": pub["version"],
        "question_set_id": pub["question_set_id"],
        "input_sha256": sha,
        "id_mapping": pub["id_mapping"],
    }
    print(
        f"  saved definition {pub['definition_id']} v{pub['version']} -> question set "
        f"{pub['question_set_id']} (saved, not reviewed)"
    )

    step("3", "open those exact questions in Applications")
    ws = api.get("/api/applications/workspace", {"question_set_id": pub["question_set_id"]})
    if ws["question_set_ref"]["question_set_id"] != pub["question_set_id"]:
        fail("workspace returned a different question set")
    bundle = ws["evidence_bundle"]
    if not ws["is_fixture"] or not all(f["provenance"]["is_simulated"] for f in bundle["facts"]):
        fail("evidence bundle is not labelled synthetic; refusing to present it as demo evidence")
    m["workspace"] = {
        "data_label": ws["data_label"],
        "evidence_bundle_id": bundle["bundle_id"],
        "pack_version_id": bundle["pack_version_id"],
        "fact_ids": [f["fact_id"] for f in bundle["facts"]],
        "questions": [q["question_id"] for q in ws["question_set"]["questions"]],
        "unresolved": [(u["question_id"], u["kind"]) for u in ws["unresolved"]],
    }
    print(f"  {ws['data_label']}")
    print(
        f"  {len(m['workspace']['questions'])} questions; evidence {bundle['bundle_id']} "
        f"facts {m['workspace']['fact_ids']}; {len(ws['unresolved'])} unresolved notes"
    )
    return m


def published(m: dict[str, Any], original: str) -> str:
    for row in m["definition"]["id_mapping"]:
        if row["original_question_id"] == original:
            return str(row["published_question_id"])
    fail(f"{original} is not a question of the saved definition")


def rehearse(api: Api, m: dict[str, Any], execute_portal: bool) -> None:
    src = SOURCES[m["source_key"]]
    qs = m["definition"]["question_set_id"]
    bundle_id = m["workspace"]["evidence_bundle_id"]
    fact = m["workspace"]["fact_ids"][0]
    texts = {o: t % {"fact": fact} if "%(" in t else t for o, t in src["answers"].items()}
    m["answers"] = {o: {"question_id": published(m, o), "text": t} for o, t in texts.items()}

    step("4", "draft with the supported evidence source (synthetic bundle, fake model)")
    for orig, a in m["answers"].items():
        d = api.post(
            f"/api/applications/questions/{a['question_id']}/draft",
            {"question_version": 1, "evidence_bundle_id": bundle_id, "question_set_id": qs},
        )
        a["draft"] = {
            "proposal_id": d["proposal_id"],
            "model": f"{d['provider']['adapter']}/{d['provider']['model']}",
            "is_fixture_model": d["provider"]["is_fixture"],
            "template_text": d["template_text"],
            "fact_ids": d["fact_ids"],
            "uncertainties": d["uncertainties"],
        }
        print(
            f"  {orig}: {d['proposal_id']} ({a['draft']['model']}, fixture model) facts "
            f"{d['fact_ids']}; {len(d['uncertainties'])} uncertainties"
        )

    step("5", "sources, uncertainty and deterministic findings for the exact final text")
    for orig, a in m["answers"].items():
        rep = api.post(
            f"/api/applications/questions/{a['question_id']}/check",
            {
                "question_version": 1,
                "evidence_bundle_id": bundle_id,
                "text": a["text"],
                "mode": "working",
                "question_set_id": qs,
            },
        )
        a["findings"] = [
            {
                "rule_id": f["result"]["rule_id"],
                "outcome": f["result"]["outcome"],
                "message": f["message"],
            }
            for f in rep["findings"]
        ]
        print(f"  {orig}: " + ", ".join(f"{f['rule_id']}={f['outcome']}" for f in a["findings"]))

    step("6", "save the exact versions; review + approve (LOCAL fixture reviewer identity)")
    for orig, a in m["answers"].items():
        v = api.post(
            "/api/applications/answers/versions",
            {
                "question_id": a["question_id"],
                "question_version": 1,
                "question_set_id": qs,
                "evidence_bundle_id": bundle_id,
                "text": a["text"],
                "expected_answer_version": None,
            },
        )
        dec = api.post(
            "/api/applications/answers/decisions",
            {
                "answer_version_id": v["answer_version_id"],
                "expected_content_sha256": v["content_sha256"],
                "expected_snapshot_sha256": v["snapshot_sha256"],
                "decision": "approve",
                "acknowledge_review_items": True,
            },
        )
        a.update(
            answer_version_id=v["answer_version_id"],
            content_sha256=v["content_sha256"],
            snapshot_sha256=v["snapshot_sha256"],
            approval_id=dec["approval_id"],
        )
        print(
            f"  {orig}: version {v['answer_version_id']} content {v['content_sha256'][:12]} "
            f"-> approval {dec['approval_id']}"
        )

    step("7", "download reviewed export (existing gates)")
    qids = [a["question_id"] for a in m["answers"].values()]
    exp = api.post(
        "/api/applications/exports",
        {"mode": "reviewed", "question_ids": qids, "question_set_id": qs},
    )
    if exp["blocked"]:
        print(f"  reviewed export blocked by gates: {exp['blocked_by']}")
        exp = api.post(
            "/api/applications/exports",
            {"mode": "working", "question_ids": qids, "question_set_id": qs},
        )
        print("  FALLBACK: working export (labelled working, not reviewed)")
    docx = api.raw(f"/api/applications/exports/{exp['export_id']}/docx")
    digest = hashlib.sha256(docx).hexdigest()
    if digest != exp["docx_sha256"]:
        fail(f"downloaded DOCX sha256 {digest} != export record {exp['docx_sha256']}")
    out = MANIFEST_DIR / f"{m['suffix']}-{exp['mode']}.docx"
    out.write_bytes(docx)
    m["export"] = {
        "export_id": exp["export_id"],
        "mode": exp["mode"],
        "labels": exp["labels"],
        "docx_sha256": digest,
        "bytes": len(docx),
        "saved_to": str(out),
    }
    print(f"  {exp['export_id']} mode={exp['mode']} {len(docx)} B sha256 {digest[:16]}…")
    print(f"  labels: {exp['labels']}")

    step("8", f"prepare selected-field plan on registered representative portal {src['portal']}")
    selections = [
        {"published_question_id": a["question_id"], "approval_snapshot_id": a["approval_id"]}
        for a in m["answers"].values()
    ]
    plan = api.post(
        "/api/automation/prefill-plans",
        {"question_set_id": qs, "portal_fixture_id": src["portal"], "selections": selections},
    )
    m["plan"] = {
        "plan_id": plan["plan_id"],
        "plan_sha256": plan["plan_sha256"],
        "executable": plan["executable"],
        "not_executable_reasons": plan["not_executable_reasons"],
        "producers": plan["producers"],
        "actions": [
            {k: x.get(k) for k in ("original_question_id", "field_id", "rendered_sha256")}
            for x in plan["actions"]
        ],
        "held": [(h["original_question_id"], h["reason"], h["detail"]) for h in plan["held"]],
        "forbidden_operations": plan["forbidden_operations"],
    }
    print(
        f"  plan {plan['plan_id']}; executable={plan['executable']} producers={plan['producers']}"
    )
    for x in m["plan"]["actions"]:
        print(f"    ELIGIBLE {x['original_question_id']} -> {x['field_id']}")
    for h in m["plan"]["held"]:
        print(f"    HELD     {h[0]}: {h[1]} ({h[2]})")
    if not plan["executable"]:
        print(f"  Not executable: {plan['not_executable_reasons']} — no browser entry attempted.")
        return
    if not execute_portal:
        print("  Prepared only. Pass --execute-portal to fill these approved selected fields.")
        return
    res = api.post(
        f"/api/automation/prefill-plans/{plan['plan_id']}/execute",
        {
            "expected_plan_sha256": plan["plan_sha256"],
            "idempotency_key": f"e2e-demo-exec-{m['suffix']}",
        },
    )
    run = res["run"]["run"]
    stored = api.get(f"/api/automation/prefill-runs/{run['run_id']}")
    m["run"] = {
        "run_id": run["run_id"],
        "outcome": run["outcome"],
        "final_reread": run["final_reread"],
        "browser_version": run.get("browser_version"),
        "operations": run["activity"]["operations_performed"],
        "fields": run["fields"],
        "stored_receipt_equal": stored.get("run") == run or stored == res["run"],
    }
    print(f"  run {run['run_id']}: outcome={run['outcome']} final_reread={run['final_reread']}")
    print(
        f"  operations: {m['run']['operations']}; "
        f"stored receipt equal: {m['run']['stored_receipt_equal']}"
    )
    if run["outcome"] != "selected_fields_verified" or run["final_reread"] != "all_match":
        fail(f"read-back did not verify: {run['outcome']}/{run['final_reread']} (see manifest)")


def write_manifest(m: dict[str, Any]) -> Path:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    path = MANIFEST_DIR / f"{m['suffix']}.json"
    path.write_text(json.dumps(m, indent=2, sort_keys=True, default=str) + "\n")
    return path


def print_walkthrough(m: dict[str, Any], web: str) -> None:
    d = m["definition"]
    src = SOURCES[m["source_key"]]
    rows = "\n".join(
        f"      {r['original_question_id']:<24} -> {r['published_question_id']}"
        for r in d["id_mapping"]
        if r["original_question_id"] in src["answers"]
    )
    print(f"""
== UI walkthrough selections — {LABEL}. Full guide: docs/demo/e2e-demo-guide.md
  Web {web}
  Funding       {web}/#/funding       FIXTURE search
                (prepared search {m["funding_search"]["search_id"]})
  Automation    {web}/#/automation    saved definition {d["definition_id"]} v{d["version"]}
  Applications  {web}/#/applications  "Questions from": {d["question_set_id"]}
  Review        {web}/#/review        same question set; you approve each exact version
  Automation    portal {src["portal"]}: prepare plan (no entry), then click fill explicitly
  Questions to answer:
{rows}
  Evidence {m["workspace"]["evidence_bundle_id"]}: synthetic demo-bundle@1, not partner records
""")


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("command", choices=["prepare", "rehearse", "status"])
    p.add_argument("--api", default="http://127.0.0.1:18120")
    p.add_argument("--web", default="http://127.0.0.1:15190")
    p.add_argument("--source", choices=sorted(SOURCES), default="prefill")
    p.add_argument(
        "--execute-portal",
        action="store_true",
        help="rehearse: explicitly run browser entry on the representative portal",
    )
    p.add_argument("--manifest", help="status: manifest written by prepare/rehearse")
    a = p.parse_args()
    api = Api(a.api)
    if a.command == "status":
        if not a.manifest:
            fail("status needs --manifest")
        m = json.loads(Path(a.manifest).read_text())
        qs = m["definition"]["question_set_id"]
        for orig, ans in m.get("answers", {}).items():
            h = api.get(f"/api/applications/answers/{ans['question_id']}", {"question_set_id": qs})
            print(
                f"{orig}: prefill_ready={h.get('prefill_ready')} "
                f"versions={len(h.get('versions', []))}"
            )
        if "plan" in m:
            view = api.get(f"/api/automation/prefill-plans/{m['plan']['plan_id']}")
            print(
                f"plan {m['plan']['plan_id']}: {view['availability']} "
                f"({view.get('availability_reason')})"
            )
        if "run" in m:
            r = api.get(f"/api/automation/prefill-runs/{m['run']['run_id']}")
            run = r.get("run", r)
            print(
                f"stored run {m['run']['run_id']}: {run.get('outcome')} {run.get('final_reread')}"
            )
        return
    suffix = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    m = prepare(api, suffix, a.source)
    path = write_manifest(m)
    if a.command == "rehearse":
        try:
            rehearse(api, m, a.execute_portal)
        finally:
            write_manifest(m)
        print(f"\nREHEARSAL COMPLETE ({LABEL}, source={a.source}).")
    else:
        print_walkthrough(m, a.web)
    print(f"Manifest (IDs/hashes only): {path}")


if __name__ == "__main__":
    main()
