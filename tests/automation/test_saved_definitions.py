"""DEV-B-BUNDLE-002 M1: saved definitions and the public ApplicationDefinitionReader.

Acceptance cases BND-01..BND-16 (task-local; not catalog rules). Every client uses a
per-test temporary Dev B store and capture store; nothing touches .local-data.
"""

from __future__ import annotations

import json
import multiprocessing
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.automation.public import (
    build_application_definition_reader,
    get_application_definition_reader,
)
from strongstart_api.features.dev_b_store import core as store_core
from strongstart_api.features.dev_b_store.core import LocalVersionStore, VersionConflict
from strongstart_api.identity import require_identity
from strongstart_contracts import SessionIdentity
from strongstart_contracts.application_publication import (
    ApplicationDefinitionNotFound,
    ApplicationDefinitionReader,
    PublishedApplicationVersion,
    UnconfiguredApplicationDefinitionReader,
)
from strongstart_contracts.ports import CapabilityUnavailable

from .conftest import definition

FIXTURE_SRC = {"mode": "fixture", "fixture_id": "rep-portal-definition-v1"}
OTHER_ORG = SessionIdentity(
    actor_id="other-staff",
    organization_id="other-org",
    roles=["fixture-staff"],
    is_fixture=True,
    label="TEST other organization",
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        auth_mode="fixture",
        funding_capture_store_dir=tmp_path / "captures",
        dev_b_store_dir=tmp_path / "dev-b",
    )


ClientFactory = Callable[..., TestClient]


@pytest.fixture
def make(settings: Settings) -> ClientFactory:
    def factory(identity: SessionIdentity | None = None, **overrides: Any) -> TestClient:
        s = settings.model_copy(update=overrides) if overrides else settings
        app = create_app(s)
        if identity is not None:
            app.dependency_overrides[require_identity] = lambda: identity
        return TestClient(app)

    return factory


@pytest.fixture
def client(make: ClientFactory) -> TestClient:
    return make()


def preview(c: TestClient, source: dict[str, Any]) -> dict[str, Any]:
    r = c.post("/api/automation/intake", json={"source": source})
    assert r.status_code == 200, r.text
    data: dict[str, Any] = r.json()
    return data


def save(c: TestClient, source: dict[str, Any], key: str = "key-00000001", **extra: Any) -> Any:
    sha = extra.pop("expected_input_sha256", None) or preview(c, source)["input"]["sha256"]
    body = {"source": source, "expected_input_sha256": sha, "idempotency_key": key, **extra}
    return c.post("/api/automation/definitions", json=body)


def saved(c: TestClient, source: dict[str, Any] = FIXTURE_SRC, key: str = "key-00000001") -> Any:
    r = save(c, source, key)
    assert r.status_code == 201, r.text
    return r.json()["publication"]


def structured(n_questions: int | None = None, **changes: Any) -> dict[str, Any]:
    d = definition()
    if n_questions is not None:
        template = d["questions"][0]
        d["questions"] = [
            {**template, "question_id": f"q-{i:03d}", "number": str(i + 1)}
            for i in range(n_questions)
        ]
    d.update(changes)
    return {"mode": "structured_json", "content": json.dumps(d)}


# ----------------------------------------------------------------------- BND-01/02/03/04


def test_bnd01_missing_identity_denies_every_new_route_before_store_access(
    make: ClientFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    touched: list[str] = []
    monkeypatch.setattr(
        LocalVersionStore, "collection", lambda *a, **k: touched.append("collection")
    )
    monkeypatch.setattr(LocalVersionStore, "put_blob", lambda *a, **k: touched.append("blob"))
    c = make(auth_mode="none")
    body = {"source": FIXTURE_SRC, "expected_input_sha256": "0" * 64, "idempotency_key": "k" * 8}
    responses = [
        c.post("/api/automation/definitions", json=body),
        c.post("/api/automation/definitions", content=b"{not json"),
        c.get("/api/automation/definitions"),
        c.get("/api/automation/definitions/def-" + "0" * 26),
        c.get("/api/automation/question-sets/qs-def-" + "0" * 26 + "-v1"),
    ]
    assert [r.status_code for r in responses] == [401] * 5
    assert all(r.json()["code"] == "unauthenticated" for r in responses)
    assert touched == []


def test_bnd02_other_org_and_unknown_fail_identically_and_lists_do_not_leak(
    make: ClientFactory,
) -> None:
    mine = make()
    pub = saved(mine)
    other = make(identity=OTHER_ORG)
    unknown_def = "def-" + "f" * 26
    a = other.get(f"/api/automation/definitions/{pub['definition_id']}")
    b = other.get(f"/api/automation/definitions/{unknown_def}")
    c = other.get(f"/api/automation/question-sets/{pub['question_set_id']}")
    assert a.status_code == b.status_code == c.status_code == 404

    def strip(r: Any) -> dict[str, Any]:
        return {k: v for k, v in r.json().items() if k != "request_id"}

    assert strip(a) == strip(b) == strip(c)
    assert other.get("/api/automation/definitions").json()["items"] == []
    # A revision of another org's lineage looks exactly like an unknown lineage.
    rev = save(other, FIXTURE_SRC, "key-other-01", definition_id=pub["definition_id"],
               expected_version=1)  # fmt: skip
    rev_unknown = save(other, FIXTURE_SRC, "key-other-02", definition_id=unknown_def,
                       expected_version=1)  # fmt: skip
    assert rev.status_code == rev_unknown.status_code == 409
    assert (
        rev.json()["details"]
        == rev_unknown.json()["details"]
        == {
            "reason": "version_conflict",
            "current_version": 0,
        }
    )


@pytest.mark.parametrize(
    ("patch", "loc"),
    [
        ({"expected_version": "1"}, "expected_version"),
        ({"expected_version": 1.0}, "expected_version"),
        ({"expected_version": True}, "expected_version"),
        ({"organization_id": "demo-org"}, "organization_id"),
        ({"approved": True}, "approved"),
        ({"actor_id": "someone"}, "actor_id"),
        ({"provenance": {"provenance_class": "public"}}, "provenance"),
        ({"path": "../../etc"}, "path"),
        ({"question_set": {"questions": []}}, "question_set"),
        ({"verification_status": "verified"}, "verification_status"),
    ],
)
def test_bnd03_strict_command_rejects_coercion_and_authority_extras(
    client: TestClient, patch: dict[str, Any], loc: str
) -> None:
    body = {
        "source": FIXTURE_SRC,
        "expected_input_sha256": "0" * 64,
        "idempotency_key": "key-00000001",
        "definition_id": "def-" + "0" * 26,
        "expected_version": 1,
        **patch,
    }
    r = client.post("/api/automation/definitions", json=body)
    assert r.status_code == 422
    assert r.json()["details"]["reason"] == "malformed_request"
    assert any(loc in i["loc"] for i in r.json()["details"]["issues"])


@pytest.mark.parametrize(
    "path",
    [
        "/api/automation/definitions/..%2F..%2Fetc%2Fpasswd",
        "/api/automation/definitions/def-..%2F" + "0" * 22,
        "/api/automation/definitions/%2e%2e",
        "/api/automation/definitions/DEF-" + "0" * 26,
        "/api/automation/question-sets/qs-def-" + "0" * 26 + "-v99",
        "/api/automation/question-sets/qs-def-" + "0" * 26 + "-v1%2F..",
        "/api/automation/question-sets/..%5c..%5cwindows",
    ],
)
def test_bnd04_malicious_ids_fail_before_outside_io(
    client: TestClient, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    real_scandir = os.scandir

    def spy(p: Any = ".") -> Any:
        opened.append(str(p))
        return real_scandir(p)

    monkeypatch.setattr(os, "scandir", spy)
    r = client.get(path)
    assert r.status_code == 404
    assert all("dev-b" in p for p in opened)


def test_bnd04_symlink_escape_is_not_followed(client: TestClient, settings: Settings) -> None:
    pub = saved(client)
    org_dir = next((settings.dev_b_store_dir / "").resolve().glob("org-*"))
    outside = settings.dev_b_store_dir.parent / "outside"
    outside.mkdir()
    (outside / "v000001.json").write_text("{}")
    link = org_dir / "definitions" / ("def-" + "e" * 26)
    link.symlink_to(outside, target_is_directory=True)
    assert client.get(f"/api/automation/definitions/{link.name}").status_code == 404
    ids = [i["definition_id"] for i in client.get("/api/automation/definitions").json()["items"]]
    assert ids == [pub["definition_id"]]


# ----------------------------------------------------------------------------- BND-05


def test_bnd05_question_bound_at_n_and_n_plus_one(client: TestClient) -> None:
    assert save(client, structured(100), "key-q-100").status_code == 201
    r = save(client, structured(101), "key-q-101")
    assert r.status_code == 413
    assert r.json()["details"]["reason"] == "too_many_questions"
    assert client.get("/api/automation/definitions").json()["items"].__len__() == 1


def test_bnd05_huge_deep_and_duplicate_key_requests_rejected_without_commit(
    client: TestClient,
) -> None:
    huge = client.post(
        "/api/automation/definitions",
        content=b'{"x":"' + b"a" * (2 * 1024 * 1024 + 10) + b'"}',
        headers={"content-type": "application/json"},
    )
    assert huge.status_code == 413
    deep = client.post(
        "/api/automation/definitions",
        content=b'{"a":' * 40 + b"1" + b"}" * 40,
        headers={"content-type": "application/json"},
    )
    assert deep.status_code == 422
    dup = client.post(
        "/api/automation/definitions",
        content=b'{"idempotency_key":"key-00000001","idempotency_key":"key-00000002"}',
        headers={"content-type": "application/json"},
    )
    assert dup.status_code == 422
    nan = client.post(
        "/api/automation/definitions",
        content=b'{"expected_version": NaN}',
        headers={"content-type": "application/json"},
    )
    assert nan.status_code == 422
    assert client.get("/api/automation/definitions").json()["items"] == []


# ----------------------------------------------------------------------------- BND-06/07


def test_bnd06_nine_question_fixture_saves_and_reloads_in_original_order(
    client: TestClient,
) -> None:
    pub = saved(client)
    again = client.get(f"/api/automation/question-sets/{pub['question_set_id']}").json()
    assert again == pub
    originals = [q["question_id"] for q in definition()["questions"]]
    assert [m["original_question_id"] for m in pub["id_mapping"]] == originals
    assert [q["question_id"] for q in pub["question_set"]["questions"]] == [
        f"{pub['definition_id']}:{o}" for o in originals
    ]
    for src, rich, shared in zip(
        definition()["questions"],
        pub["intake"]["questions"],
        pub["question_set"]["questions"],
        strict=True,
    ):
        assert rich["text"]["text"] == src["text"] == shared["original_text"]
        assert rich["text"]["locator"]["kind"] == "json_pointer"
        assert shared["source_refs"][0]["locator"] == rich["source_ref"]["locator"]
    assert pub["approval_status"] == "not_approved"
    assert pub["prefill_permitted"] is False
    assert pub["review_status"] == "saved_not_reviewed"
    assert pub["context"]["opportunity_basis"] == "fixture_registry"


def test_bnd07_conflicts_unknowns_conditions_streams_and_files_survive(
    client: TestClient,
) -> None:
    pub = saved(client)
    d = pub["definition_id"]
    shared = {q["question_id"]: q for q in pub["question_set"]["questions"]}
    rich = {q["question_id"]: q for q in pub["intake"]["questions"]}
    partnership = shared[f"{d}:rp-partnership"]
    assert partnership["limit"] is None
    assert {c["maximum"] for c in partnership["conflicts"][0]["candidate_limits"]} == {350, 500}
    assert partnership["conflicts"][0]["resolution"] == "unresolved"
    max300 = rich["rp-other-funding"]
    assert any(x["unit"] == "unknown" and x["maximum"] == "300" for x in max300["limits"])
    assert shared[f"{d}:rp-other-funding"]["limit"]["unit"] == "unknown"
    cond = rich["rp-partnership"]["conditions"][0]
    assert cond["depends_on_question_id"] == "rp-has-partners"  # rich intake keeps originals
    assert any(q["required"] is None for q in shared.values())
    assert shared[f"{d}:rp-partnership"]["conditions"]
    amounts = [x for x in rich["rp-request-amount"]["limits"] if x["unit"] == "amount"]
    assert {(x["applies_to_stream"], x["maximum"]) for x in amounts} >= {("network", "250000")}
    attachment = rich["rp-financial-statement"]["attachment"]
    assert attachment["max_size_bytes"] == 5242880
    kinds = {(u["question_id"], u["kind"]) for u in pub["unresolved"]}
    assert (f"{d}:rp-partnership", "limit_conflict") in kinds
    assert (f"{d}:rp-other-funding", "unknown_limit_unit") in kinds
    assert all(u["question_id"].startswith(f"{d}:") for u in pub["unresolved"])


# ----------------------------------------------------------------------------- BND-08/09/10


def test_bnd08_changed_preview_hash_is_409_with_no_side_effects(
    client: TestClient, settings: Settings
) -> None:
    r = save(client, FIXTURE_SRC, expected_input_sha256="1" * 64)
    assert r.status_code == 409
    assert r.json()["details"]["reason"] == "input_changed"
    assert not list(settings.dev_b_store_dir.glob("org-*/definitions/*"))
    assert not list(settings.dev_b_store_dir.glob("org-*/idempotency/**/*.json"))


def test_bnd09_fresh_app_and_repository_read_same_ids_and_hashes(
    make: ClientFactory, settings: Settings
) -> None:
    pub = saved(make())
    fresh = make()  # new app instance over the same directory (restart)
    again = fresh.get(f"/api/automation/definitions/{pub['definition_id']}").json()
    assert again["question_set_id"] == pub["question_set_id"]
    assert again["integrity"] == pub["integrity"]
    reader = build_application_definition_reader(settings)
    assert reader.get_version("demo-org", pub["question_set_id"]).model_dump(mode="json") == pub
    assert list(settings.dev_b_store_dir.glob("org-*/blobs/*"))  # bytes on disk, not memory


def test_bnd10_idempotent_replay_and_key_reuse(client: TestClient) -> None:
    first = save(client, FIXTURE_SRC, "key-replay-1")
    replay = save(client, FIXTURE_SRC, "key-replay-1")
    assert (first.status_code, replay.status_code) == (201, 200)
    assert replay.json()["replayed"] is True
    assert replay.json()["publication"] == first.json()["publication"]
    reused = save(client, structured(), "key-replay-1")
    assert reused.status_code == 409
    assert reused.json()["details"]["reason"] == "idempotency_key_reused"
    pub = first.json()["publication"]
    rev = save(client, FIXTURE_SRC, "key-rev-1", definition_id=pub["definition_id"],
               expected_version=1)  # fmt: skip
    assert rev.status_code == 201
    # Lost response: the completed revision replays even though v1 is no longer current.
    again = save(client, FIXTURE_SRC, "key-rev-1", definition_id=pub["definition_id"],
                 expected_version=1)  # fmt: skip
    assert again.status_code == 200
    assert again.json()["publication"]["version"] == 2


# ----------------------------------------------------------------------------- BND-11


def test_bnd11_revision_keeps_old_version_and_namespaced_stable_ids(
    client: TestClient,
) -> None:
    d = definition()
    v1 = saved(client, structured(), "key-lineage-1")
    d2 = definition()
    d2["questions"] = [q for q in d["questions"] if q["question_id"] != "rp-other-funding"]
    d2["questions"].append({**d["questions"][0], "question_id": "rp-new-question", "number": "10"})
    r = save(client, {"mode": "structured_json", "content": json.dumps(d2)}, "key-lineage-2",
             definition_id=v1["definition_id"], expected_version=1)  # fmt: skip
    assert r.status_code == 201, r.text
    v2 = r.json()["publication"]
    assert v2["version"] == 2 and v2["revision_of_version"] == 1
    assert v2["question_set_id"] != v1["question_set_id"]
    assert v2["added_original_ids"] == ["rp-new-question"]
    assert v2["removed_original_ids"] == ["rp-other-funding"]
    ids_v1 = {m["original_question_id"]: m["published_question_id"] for m in v1["id_mapping"]}
    ids_v2 = {m["original_question_id"]: m["published_question_id"] for m in v2["id_mapping"]}
    assert all(ids_v2[k] == ids_v1[k] for k in ids_v1 if k in ids_v2)
    assert {q["question_version"] for q in v2["question_set"]["questions"]} == {2}
    old = client.get(f"/api/automation/question-sets/{v1['question_set_id']}").json()
    assert old == v1  # exact version, not a substituted latest
    current = client.get(f"/api/automation/definitions/{v1['definition_id']}").json()
    assert current["version"] == 2
    # A different lineage with identical rp-* IDs cannot collide.
    other = saved(client, structured(), "key-lineage-3")
    assert not set(ids_v1.values()) & {m["published_question_id"] for m in other["id_mapping"]}


# ----------------------------------------------------------------------------- BND-12


def _writer(root: str, barrier: Any, key: str, out: Any) -> None:
    store = LocalVersionStore(Path(root))
    coll = store.collection("demo-org", "definitions")
    barrier.wait()
    try:
        r = coll.commit(
            idempotency_key=key,
            command_hash=key,
            object_id="def-" + "a" * 26,
            expected_version=1,
            build=lambda oid, v, prev: {"writer": key, "version": v},
        )
        out.put(("ok", r.version))
    except VersionConflict as exc:
        out.put(("conflict", exc.current_version))


def test_bnd12_two_cross_process_writers_one_commit_one_conflict(tmp_path: Path) -> None:
    store = LocalVersionStore(tmp_path)
    coll = store.collection("demo-org", "definitions")
    coll.commit(idempotency_key="seed-key", command_hash="seed", object_id="def-" + "a" * 26,
                expected_version=0, build=lambda o, v, p: {"seed": True})  # fmt: skip
    ctx = multiprocessing.get_context("spawn")
    barrier, out = ctx.Barrier(2), ctx.Queue()
    procs = [
        ctx.Process(target=_writer, args=(str(tmp_path), barrier, f"writer-{i}", out))
        for i in range(2)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(30)
    results = sorted(out.get(timeout=5) for _ in procs)
    assert results == [("conflict", 2), ("ok", 2)]
    assert coll.current_version("def-" + "a" * 26) == 2


def test_bnd12_api_concurrent_revisions_one_wins(client: TestClient) -> None:
    from concurrent.futures import ThreadPoolExecutor

    pub = saved(client)
    sha = preview(client, FIXTURE_SRC)["input"]["sha256"]

    def revise(key: str) -> int:
        r = save(client, FIXTURE_SRC, key, expected_input_sha256=sha,
                 definition_id=pub["definition_id"], expected_version=1)  # fmt: skip
        return int(r.status_code)

    with ThreadPoolExecutor(2) as pool:
        codes = sorted(pool.map(revise, ["key-conc-01", "key-conc-02"]))
    assert codes == [201, 409]


# ----------------------------------------------------------------------------- BND-13/14


def _version_file(settings: Settings, definition_id: str, version: int = 1) -> Path:
    return next(settings.dev_b_store_dir.glob(f"org-*/definitions/{definition_id}"))  / (
        f"v{version:06d}.json"
    )  # fmt: skip


def _rewrite(path: Path, mutate: Callable[[dict[str, Any]], None], *, redigest: bool) -> None:
    env = json.loads(path.read_text("utf-8"))
    mutate(env["record"])
    if redigest:
        env["digest"] = store_core.sha256_hex(store_core.canonical_json(env["record"]))
    path.chmod(0o600)
    path.write_bytes(store_core.canonical_json(env))


@pytest.mark.parametrize("redigest", [False, True])
def test_bnd13_altered_limit_withholds_content(
    client: TestClient, settings: Settings, redigest: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uuid

    pub = saved(client)
    # The raw-response leak assertion must not match an unrelated random correlation
    # ID (a real run generated one containing "5000"). Preserve the assertion itself.
    monkeypatch.setattr("strongstart_api.errors.uuid.uuid4", lambda: uuid.UUID(int=1))

    def change_limit(rec: dict[str, Any]) -> None:
        rec["question_set"]["questions"][0]["limit"]["maximum"] = 5000

    _rewrite(_version_file(settings, pub["definition_id"]), change_limit, redigest=redigest)
    for path in (
        f"/api/automation/definitions/{pub['definition_id']}",
        f"/api/automation/question-sets/{pub['question_set_id']}",
    ):
        r = client.get(path)
        assert r.status_code == 409
        assert r.json()["details"]["reason"] == "integrity_failure"
        assert "5000" not in r.text and "mission" not in r.text
    item = client.get("/api/automation/definitions").json()["items"][0]
    assert item["status"] == "integrity_failure" and item["question_count"] is None


@pytest.mark.parametrize("target", ["raw_blob", "hash", "mapping"])
def test_bnd13_altered_input_hash_or_mapping_withholds_content(
    client: TestClient, settings: Settings, target: str
) -> None:
    pub = saved(client)
    if target == "raw_blob":
        blob = next(settings.dev_b_store_dir.glob("org-*/blobs/*"))
        blob.chmod(0o600)
        blob.write_bytes(blob.read_bytes() + b" ")
    else:

        def mutate(rec: dict[str, Any]) -> None:
            if target == "hash":
                rec["integrity"]["raw_input_sha256"] = "0" * 64
            else:
                rec["id_mapping"][0]["published_question_id"] = rec["id_mapping"][1][
                    "published_question_id"
                ]

        _rewrite(_version_file(settings, pub["definition_id"]), mutate, redigest=True)
    r = client.get(f"/api/automation/question-sets/{pub['question_set_id']}")
    assert r.status_code == 409
    assert r.json()["details"]["reason"] == "integrity_failure"


def test_bnd13_redirected_idempotency_index_never_returns_other_content(
    client: TestClient, settings: Settings
) -> None:
    a = saved(client, FIXTURE_SRC, "key-index-a")
    saved(client, structured(), "key-index-b")
    intents = list(settings.dev_b_store_dir.glob("org-*/idempotency/definitions/*.json"))
    target = next(
        p for p in intents if json.loads(p.read_text())["object_id"] != a["definition_id"]
    )
    index_a = next(p for p in intents if p != target)
    data = json.loads(index_a.read_text())
    data["object_id"] = json.loads(target.read_text())["object_id"]
    index_a.chmod(0o600)
    index_a.write_text(json.dumps(data))
    r = save(client, FIXTURE_SRC, "key-index-a")
    assert r.status_code == 409


def test_bnd14_mid_commit_failure_leaves_nothing_visible_and_retry_is_consistent(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = store_core.atomic_create

    def failing(path: Path, data: bytes, durability: Any) -> bool:
        if path.name.startswith("v0"):
            raise OSError("injected disk failure")
        return real(path, data, durability)

    monkeypatch.setattr(store_core, "atomic_create", failing)
    failed = save(client, FIXTURE_SRC, "key-crash-01")
    assert failed.status_code == 503
    assert failed.json()["details"]["reason"] == "store_write_failed"
    assert "injected" not in failed.text
    assert client.get("/api/automation/definitions").json()["items"] == []
    monkeypatch.setattr(store_core, "atomic_create", real)
    retry = save(client, FIXTURE_SRC, "key-crash-01")
    assert retry.status_code == 201
    assert retry.json()["publication"]["version"] == 1
    assert len(client.get("/api/automation/definitions").json()["items"]) == 1


# ----------------------------------------------------------------------------- BND-15/16


def test_bnd15_unsupported_and_contextless_imports_are_not_published(
    client: TestClient,
) -> None:
    prose = {"mode": "html", "content": "<main><h1>Grant</h1><p>Apply by email.</p></main>"}
    r = save(client, prose, "key-prose-1")
    assert r.status_code == 422
    assert r.json()["details"]["reason"] == "publication_blocked"
    form = {"mode": "html", "content": '<form><label for="m">Mission</label>'
            '<textarea id="m" name="m"></textarea></form>'}  # fmt: skip
    r = save(client, form, "key-form-1")
    assert r.status_code == 422
    assert r.json()["details"] == {
        "reason": "publication_blocked",
        "missing": ["opportunity_id"],
    }
    assert client.get("/api/automation/definitions").json()["items"] == []


def test_bnd16_public_reader_returns_real_questions_with_labels(
    client: TestClient, settings: Settings
) -> None:
    fixture_pub = saved(client, FIXTURE_SRC, "key-label-1")
    upload_pub = saved(client, structured(), "key-label-2")
    reader = get_application_definition_reader(settings)
    assert isinstance(reader, ApplicationDefinitionReader)
    assert reader.is_fixture is False  # adapter: a real local repository
    f = reader.get_version("demo-org", fixture_pub["question_set_id"])
    u = reader.get_current("demo-org", upload_pub["definition_id"])
    assert isinstance(f, PublishedApplicationVersion)
    assert f.is_fixture is True and f.provenance.is_simulated is True
    assert u.is_fixture is False and u.provenance.provenance_class == "supplied"
    assert u.context.opportunity_basis == "source_declared_claim"
    assert len(f.question_set.questions) == 9 and f.unresolved
    with pytest.raises(ApplicationDefinitionNotFound):
        reader.get_version("other-org", fixture_pub["question_set_id"])
    prod = Settings(_env_file=None, environment="production")
    unconfigured = build_application_definition_reader(prod)
    assert isinstance(unconfigured, UnconfiguredApplicationDefinitionReader)
    with pytest.raises(CapabilityUnavailable):
        unconfigured.get_version("demo-org", fixture_pub["question_set_id"])
