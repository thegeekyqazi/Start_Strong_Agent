"""Exercise the opt-in managed rehearsal over real HTTP, C approvals, PostgreSQL and Chromium.

Start scripts.int001_managed_rehearsal first; supply its printed replacement ID. This
writes only labelled synthetic rehearsal data and never submits/signs/uploads. Not a
production acceptance or a live-provider test. No approval/content reader overrides.
"""

from __future__ import annotations

import argparse
import secrets
from typing import Any
from urllib.parse import quote

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--replacement", required=True)
    args = parser.parse_args()
    with httpx.Client(base_url=f"http://127.0.0.1:{args.port}", timeout=45) as client:

        def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
            response = client.post(path, json=body)
            assert response.status_code in (200, 201), response.text
            data: dict[str, Any] = response.json()
            return data

        suffix = secrets.token_hex(8)
        source = {"mode": "fixture", "fixture_id": "rep-prefill-definition-v1"}
        sha = post("/api/automation/intake", {"source": source})["input"]["sha256"]
        pub = post(
            "/api/automation/definitions",
            {
                "source": source,
                "expected_input_sha256": sha,
                "idempotency_key": "managed-publish-" + suffix,
            },
        )["publication"]
        workspace = client.get(
            "/api/applications/workspace", params={"question_set_id": pub["question_set_id"]}
        ).json()
        bundle = workspace["evidence_bundle"]
        assert workspace["is_fixture"] and all(
            f["provenance"]["is_simulated"] for f in bundle["facts"]
        )
        selections = []
        for original, fact in zip(("pf-org-name", "pf-summary"), bundle["facts"][:2], strict=True):
            qid = next(
                m["published_question_id"]
                for m in pub["id_mapping"]
                if m["original_question_id"] == original
            )
            version = post(
                "/api/applications/answers/versions",
                {
                    "question_id": qid,
                    "question_version": 1,
                    "question_set_id": pub["question_set_id"],
                    "evidence_bundle_id": bundle["bundle_id"],
                    "text": "Synthetic linked metric: {{fact:" + fact["fact_id"] + "}}.",
                    "expected_answer_version": None,
                },
            )
            decision = post(
                "/api/applications/answers/decisions",
                {
                    "answer_version_id": version["answer_version_id"],
                    "expected_content_sha256": version["content_sha256"],
                    "expected_snapshot_sha256": version["snapshot_sha256"],
                    "decision": "approve",
                    "acknowledge_review_items": True,
                },
            )
            selections.append(
                {"published_question_id": qid, "approval_snapshot_id": decision["approval_id"]}
            )
        request = {
            "question_set_id": pub["question_set_id"],
            "portal_fixture_id": "rep-prefill-v1",
            "selections": selections,
        }
        plan = post("/api/automation/prefill-plans", request)
        assert plan["producers"]["approval_reader"] == "c_reader"
        assert plan["producers"]["dependency_currentness"] == "a4_adapter"

        def execute(record: dict[str, Any], key: str) -> dict[str, Any]:
            return post(
                f"/api/automation/prefill-plans/{record['plan_id']}/execute",
                {"expected_plan_sha256": record["plan_sha256"], "idempotency_key": key},
            )

        completed = execute(plan, "managed-execute-" + suffix)["run"]["run"]
        assert (
            completed["outcome"] == "selected_fields_verified"
            and completed["final_reread"] == "all_match"
        )
        assert completed["browser_version"] and len(completed["fields"]) == 2
        assert completed["activity"]["operations_performed"] == [
            "fill:org-name-field",
            "fill:summary-field",
        ]
        for kind, target_id in [
            ("browser_plan", plan["plan_id"]),
            ("browser_grant", completed["grant"]["grant_id"]),
        ]:
            target = client.get(f"/api/knowledge/dependencies/targets/{kind}/{target_id}").json()
            assert (
                target["state"] == "current"
                and target["projection_sha256"]
                == plan["a4_registration"]["binding"]["projection_sha256"]
            )
        pending = post("/api/automation/prefill-plans", request)
        binding = pending["a4_registration"]["binding"]
        post(
            "/api/knowledge/packs/contexts/"
            + quote(binding["application_context"], safe="")
            + "/activate/"
            + quote(args.replacement, safe=""),
            {"expected_active_pack_version_id": binding["pack_version_id"]},
        )
        view = client.get(f"/api/automation/prefill-plans/{pending['plan_id']}").json()
        assert view["availability"] == "stale" and view["plan"] == pending
        blocked = execute(pending, "managed-blocked-" + suffix)["run"]["run"]
        assert (
            blocked["outcome"] == "blocked_before_entry"
            and blocked["activity"]["operations_performed"] == []
        )
        replay = execute(plan, "managed-execute-" + suffix)
        assert replay["replayed"] and replay["run"]["run"] == completed
        print("PASS: real HTTP C save/approve -> A4 plan/grant -> two-field Chromium/final reread")
        print(
            "PASS: real activation -> stale GET -> zero-write blocked receipt; "
            "historical replay unchanged"
        )
        print(
            "Plan:", plan["plan_id"], "Run:", completed["run_id"], "Blocked run:", blocked["run_id"]
        )


if __name__ == "__main__":
    main()
