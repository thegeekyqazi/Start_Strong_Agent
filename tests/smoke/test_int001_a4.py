"""INT-13 through INT-22: actual PostgreSQL/A4 registration and replacement."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, event, text

from strongstart_api.features.knowledge.packs import (
    PackConflictError,
    PackManifestError,
    PackNotFoundError,
    PackService,
)
from strongstart_contracts import DependencyRegistrationRequest
from strongstart_contracts.answers import DependencyRef

pytest_plugins = ["tests.integration.a4_support"]

pytestmark = pytest.mark.db


def test_exact_projection_and_guarded_registration(managed):
    binding, refs = managed.binding(include_policy=True)
    projected = {(d.kind, d.ref_id, d.version) for d in binding.dependencies}
    assert ("pack_version", binding.pack_version_id, binding.pack_version_id) in projected
    fact = next(d for d in binding.dependencies if d.kind == "fact_version")
    assert fact.version in ("1", "2")
    assert next(d for d in refs if d.kind == "fact").version != fact.version
    for kind in ("browser_plan", "browser_grant"):
        reg = managed.facade.register("demo-org", kind, managed.prefix + kind, binding)
        target = managed.service.get_target("demo-org", kind, reg.target_id)
        assert target.organization_id == "demo-org"
        assert target.application_context == managed.context
        assert target.active_revision == binding.active_revision
        assert target.projection_sha256 == binding.projection_sha256
        assert (
            target.dependencies == binding.dependencies
            and target.revision == reg.target_revision == 1
        )
        assert managed.facade.check_registration("demo-org", reg).status == "current"
        assert managed.facade.register("demo-org", kind, reg.target_id, binding, 1) == reg
        assert managed.facade.check_registration("other-org", reg).status == "stale"
        with pytest.raises(PackManifestError):
            managed.facade.register("other-org", kind, reg.target_id, binding)
        with pytest.raises(PackConflictError):
            managed.facade.register("demo-org", kind, reg.target_id, binding, 0)


@pytest.mark.parametrize(
    "bad", ["fact_digest", "fact_missing", "policy_version", "requirement_set", "pack", "context"]
)
def test_mapping_never_drops_or_reinterprets_dependencies(managed, bad):
    bundle = managed.facade.resolve_active("demo-org", managed.context)
    _, refs = managed.binding(include_policy=True)
    if bad == "fact_digest":
        refs = [r.model_copy(update={"version": "999"}) if r.kind == "fact" else r for r in refs]
    elif bad == "fact_missing":
        refs.append(DependencyRef(kind="fact", ref_id="foreign-fact", version="1"))
    elif bad == "policy_version":
        refs = [r.model_copy(update={"version": "01"}) if r.kind == "policy" else r for r in refs]
    elif bad == "requirement_set":
        refs.append(DependencyRef(kind="requirement_set", ref_id="unverified", version="1"))
    elif bad == "pack":
        refs = [r for r in refs if r.kind != "pack"]
    with pytest.raises((PackManifestError, PackNotFoundError)):
        managed.facade.project(
            "demo-org", "other-context" if bad == "context" else managed.context, bundle, refs
        )


@pytest.mark.parametrize("replacement", [1, 2, 3])
def test_fact_policy_and_same_content_new_version_stale_without_revival(managed, replacement):
    binding, _ = managed.binding(include_policy=True)
    reg = managed.facade.register("demo-org", "browser_plan", managed.prefix + "plan", binding)
    managed.replace(replacement)
    assert managed.facade.check_registration("demo-org", reg).status == "stale"
    with pytest.raises(PackConflictError):
        managed.facade.register("demo-org", "browser_plan", reg.target_id, binding, 1)
    with pytest.raises(PackConflictError):
        managed.service.register_target(
            "demo-org",
            DependencyRegistrationRequest(
                target_kind="browser_plan",
                target_id=reg.target_id,
                expected_revision=1,
                dependencies=binding.dependencies,
            ),
        )
    assert managed.service.get_target("demo-org", "browser_plan", reg.target_id).state == "stale"


def test_replacement_wins_before_old_registration(managed):
    binding, _ = managed.binding()
    managed.replace()
    with pytest.raises(PackConflictError):
        managed.facade.register("demo-org", "browser_plan", managed.prefix + "late", binding)


def test_registration_lock_serializes_replacement_and_prevents_stale_registration(managed):
    """The mutation audit removes both registration locks, never activation's locks.

    pg_blocking_pids proves the competing writer reached the protected operation.
    If guards are absent, replacement completes before insertion; target stays wrongly
    current and the stale_registration assertion below fails for that exact reason.
    """
    engine = managed.service.engine
    replacement_engine = create_engine(managed.url, connect_args={"connect_timeout": 3})
    captured, release, attempted = threading.Event(), threading.Event(), threading.Event()
    replacement_pid: list[int] = []
    binding, _ = managed.binding()
    target_id = managed.prefix + "race-plan"

    def pause_after_context(conn, cursor, statement, parameters, context, many):
        if "FROM active_pack_contexts" in statement and "FOR UPDATE" in statement:
            captured.set()
            assert release.wait(10)
        elif "FROM active_pack_contexts" in statement and not captured.is_set():
            # Mutant also pauses at exactly the same read boundary.
            captured.set()
            assert release.wait(10)

    def reached_activation_lock(conn, cursor, statement, parameters, context, many):
        if "FROM organizations" in statement and "FOR UPDATE" in statement:
            replacement_pid.append(conn.connection.driver_connection.info.backend_pid)
            attempted.set()

    event.listen(engine, "after_cursor_execute", pause_after_context)
    event.listen(replacement_engine, "before_cursor_execute", reached_activation_lock)
    observed_wait = False
    try:
        with ThreadPoolExecutor(2) as pool:
            registration = pool.submit(
                managed.facade.register, "demo-org", "browser_plan", target_id, binding
            )
            try:
                assert captured.wait(5)
                replacement = pool.submit(
                    PackService(replacement_engine).activate,
                    "demo-org",
                    "fixture-staff",
                    managed.context,
                    managed.manifests[1].pack_version_id,
                    binding.pack_version_id,
                )
                assert attempted.wait(5)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    with replacement_engine.connect() as observer:
                        observed_wait = bool(
                            observer.execute(
                                text(
                                    "SELECT cardinality(pg_blocking_pids(:pid)) > 0 "
                                    "AND wait_event_type = 'Lock' "
                                    "FROM pg_stat_activity WHERE pid = :pid"
                                ),
                                {"pid": replacement_pid[0]},
                            ).scalar()
                        )
                    if observed_wait or replacement.done():
                        break
                    attempted.wait(0.01)
            finally:
                release.set()
            reg = registration.result(timeout=10)
            replacement.result(timeout=10)
        assert managed.service.get_target("demo-org", "browser_plan", target_id).state == "stale", (
            "stale_registration: replacement missed the new target"
        )
        assert observed_wait, "competing activation never observed waiting on registration lock"
        assert managed.facade.check_registration("demo-org", reg).status == "stale"
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause_after_context)
        event.remove(replacement_engine, "before_cursor_execute", reached_activation_lock)
        replacement_engine.dispose()


def test_unrelated_context_replacement_keeps_this_plan_current(managed):
    binding, _ = managed.binding()
    reg = managed.facade.register("demo-org", "browser_plan", managed.prefix + "isolated", binding)
    context = managed.prefix + "other-context"
    packs = []
    for i in (1, 2):
        request = managed.manifests[0].model_copy(
            update={
                "pack_id": managed.prefix + "other-pack",
                "pack_version_id": managed.prefix + f"other-v{i}",
                "bundle_id": managed.prefix + f"other-bundle-{i}",
                "application_context": context,
            }
        )
        managed.service.create_manifest("demo-org", "fixture-staff", request)
        packs.append(request.pack_version_id)
    managed.service.activate("demo-org", "fixture-staff", context, packs[0], None)
    managed.service.activate("demo-org", "fixture-staff", context, packs[1], packs[0])
    assert managed.facade.check_registration("demo-org", reg).status == "current"
