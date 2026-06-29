from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from tests.loomweave_test_utils import seed_loomweave_catalog

from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.loomweave_adapter import LoomweaveAdapter
from plainweave.models import TraceRef
from plainweave.service import PlainweaveService
from plainweave.store import connect, migrate


def service_for(tmp_path: Path) -> PlainweaveService:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")
    return PlainweaveService(db_path, root=tmp_path)


def approved_requirement_ref(service: PlainweaveService) -> str:
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )
    version = service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")
    return f"{version.id}@{version.version}"


def test_propose_trace_link_creates_agent_proposed_current_link(tmp_path: Path) -> None:
    service = service_for(tmp_path)

    link = service.propose_trace_link(
        TraceRef("test_selector", "tests/test_auth.py::test_expired"),
        "provides_evidence_for",
        TraceRef("verification_method", "VERM-0001"),
        actor="agent:codex",
        confidence=0.82,
    )

    assert link.id == "LINK-0001"
    assert link.state == "proposed"
    assert link.authority == "agent_proposed"
    assert link.freshness == "current"
    assert link.accepted_by is None
    assert service.trace_for(state="proposed") == [link]


def test_accept_and_reject_trace_links_preserve_actor_attribution(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    accepted = service.propose_trace_link(
        TraceRef("test_selector", "tests/test_auth.py::test_expired"),
        "provides_evidence_for",
        TraceRef("verification_method", "VERM-0001"),
        actor="agent:codex",
    )
    rejected = service.propose_trace_link(
        TraceRef("file_ref", "src/auth.py"),
        "fragile_satisfies",
        TraceRef("requirement_version", "REQ-AUTH-0001@1"),
        actor="agent:codex",
    )

    accepted_link = service.accept_trace_link(accepted.id, actor="human:john")
    rejected_link = service.reject_trace_link(rejected.id, actor="human:john", reason="not relevant")

    assert accepted_link.state == "accepted"
    assert accepted_link.authority == "accepted"
    assert accepted_link.accepted_by == "human:john"
    assert rejected_link.state == "rejected"
    assert rejected_link.authority == "agent_proposed"
    assert rejected_link.accepted_by is None


def test_stale_and_orphaned_states_remain_distinct(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    seed = seed_loomweave_catalog(tmp_path)
    requirement_version_ref = approved_requirement_ref(service)
    stale = service.create_trace_link(
        TraceRef("file_ref", "src/auth.py"),
        "fragile_satisfies",
        TraceRef("requirement_version", requirement_version_ref),
        actor="human:john",
        authority="accepted",
    )
    orphaned = service.create_trace_link(
        TraceRef("loomweave_entity", seed["public_locator"]),
        "satisfies",
        TraceRef("requirement_version", requirement_version_ref),
        actor="human:john",
        authority="accepted",
    )

    stale_link = service.mark_trace_stale(stale.id, actor="agent:codex", reason="content changed")
    orphaned_link = service.mark_trace_orphaned(orphaned.id, actor="agent:codex", reason="entity removed")

    assert stale_link.state == "stale"
    assert stale_link.freshness == "stale"
    assert orphaned_link.state == "orphaned"
    assert orphaned_link.freshness == "orphaned"


def test_inverted_canonical_relation_returns_validation(tmp_path: Path) -> None:
    service = service_for(tmp_path)

    with pytest.raises(PlainweaveError) as exc_info:
        service.propose_trace_link(
            TraceRef("requirement_version", "REQ-AUTH-0001@1"),
            "satisfies",
            TraceRef("loomweave_entity", "sei:abc123"),
            actor="agent:codex",
        )

    assert exc_info.value.code == ErrorCode.VALIDATION


def test_high_risk_code_links_remain_proposed_until_accepted(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    seed = seed_loomweave_catalog(tmp_path)

    link = service.propose_trace_link(
        TraceRef("loomweave_entity", seed["public_locator"]),
        "satisfies",
        TraceRef("requirement_version", "REQ-AUTH-0001@1"),
        actor="agent:codex",
        confidence=0.99,
    )

    assert link.state == "proposed"
    assert link.authority == "agent_proposed"


def test_accepting_local_requirement_version_trace_requires_existing_version(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    link = service.propose_trace_link(
        TraceRef("file_ref", "src/auth.py"),
        "fragile_satisfies",
        TraceRef("requirement_version", "REQ-AUTH-9999@1"),
        actor="agent:codex",
    )

    with pytest.raises(PlainweaveError) as exc_info:
        service.accept_trace_link(link.id, actor="human:john")

    assert exc_info.value.code == ErrorCode.NOT_FOUND


def test_invented_loomweave_entity_ids_cannot_create_trace_links(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    approved = approved_requirement_ref(service)
    seed_loomweave_catalog(tmp_path)

    with pytest.raises(PlainweaveError) as exc_info:
        service.create_trace_link(
            TraceRef("loomweave_entity", "python:function:pkg.invented"),
            "satisfies",
            TraceRef("requirement_version", approved),
            actor="human:john",
            authority="accepted",
        )

    assert exc_info.value.code == ErrorCode.NOT_FOUND
    assert service.trace_for() == []


def test_valid_loomweave_locator_creates_trace_link_snapshot_and_normalizes_to_sei(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    approved = approved_requirement_ref(service)
    seed = seed_loomweave_catalog(tmp_path)

    link = service.create_trace_link(
        TraceRef("loomweave_entity", seed["public_locator"]),
        "satisfies",
        TraceRef("requirement_version", approved),
        actor="human:john",
        authority="accepted",
    )

    assert link.from_ref.id == seed["public_sei"]
    assert link.target_snapshot["sei"] == seed["public_sei"]
    assert link.target_snapshot["locator"] == seed["public_locator"]
    assert link.target_snapshot["content_hash"] == "hash-public-v1"
    assert link.target_snapshot["content_hash_at_attach"] == "hash-public-v1"
    assert link.target_snapshot["public_signal"]["state"] == "explicit_public_tag"
    assert link.target_snapshot["lineage_status"] == "alive"
    assert link.target_snapshot["freshness"] == "current"
    assert link.target_snapshot["source"]["line_start"] == 10


def test_read_time_hash_drift_marks_loomweave_trace_stale_without_mutating_storage(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    approved = approved_requirement_ref(service)
    seed = seed_loomweave_catalog(tmp_path)
    link = service.create_trace_link(
        TraceRef("loomweave_entity", seed["public_locator"]),
        "satisfies",
        TraceRef("requirement_version", approved),
        actor="human:john",
        authority="accepted",
    )
    with connect(service.db_path) as connection:
        stored_before = str(
            connection.execute(
                "select target_snapshot_json from trace_links where link_id = ?",
                (link.id,),
            ).fetchone()["target_snapshot_json"]
        )
    with sqlite3.connect(seed["db_path"]) as connection:
        connection.execute(
            "update entities set content_hash = 'hash-public-v2' where id = ?",
            (seed["public_locator"],),
        )
        connection.execute(
            "update sei_bindings set body_hash = 'hash-public-v2' where sei = ?",
            (seed["public_sei"],),
        )

    returned = service.trace_for()[0]

    assert returned.freshness == "stale"
    assert returned.target_snapshot["freshness"] == "stale"
    assert returned.target_snapshot["content_hash"] == "hash-public-v2"
    assert returned.target_snapshot["content_hash_at_attach"] == "hash-public-v1"
    with connect(service.db_path) as connection:
        stored_after = str(
            connection.execute(
                "select target_snapshot_json from trace_links where link_id = ?",
                (link.id,),
            ).fetchone()["target_snapshot_json"]
        )
    assert stored_after == stored_before


def test_read_time_orphaned_loomweave_identity_returns_degraded_trace_without_deleting_row(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    approved = approved_requirement_ref(service)
    seed = seed_loomweave_catalog(tmp_path)
    link = service.create_trace_link(
        TraceRef("loomweave_entity", seed["public_locator"]),
        "satisfies",
        TraceRef("requirement_version", approved),
        actor="human:john",
        authority="accepted",
    )
    with sqlite3.connect(seed["db_path"]) as connection:
        connection.execute(
            "update sei_bindings set status = 'orphaned', current_locator = null where sei = ?",
            (seed["public_sei"],),
        )

    returned = service.trace_for()[0]

    assert returned.id == link.id
    assert returned.state == "accepted"
    assert returned.freshness == "orphaned"
    assert returned.target_snapshot["freshness"] == "orphaned"
    assert any(item["code"] == "identity_orphaned" for item in returned.target_snapshot["degraded"])
    with connect(service.db_path) as connection:
        assert connection.execute("select count(*) from trace_links").fetchone()[0] == 1


def test_read_path_honors_local_only_boundary_when_loomweave_endpoint_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RED-2 (weft-d5091cba12): Plainweave's trace read tools advertise
    ``local_only: True`` / ``live_peer_calls: False``. With a Loomweave HTTP
    endpoint CONFIGURED, the read-time enrich path (``trace_for`` ->
    ``_enrich_loomweave_trace``, which backs ``plainweave_trace_link_list`` and
    the dossier) must resolve identity from the local catalog only and make NO
    live peer call — otherwise the advertised boundary is a lie."""
    service = service_for(tmp_path)
    approved = approved_requirement_ref(service)
    seed = seed_loomweave_catalog(tmp_path)
    # Create the accepted link BEFORE an endpoint is configured: write-time
    # normalization is a separate (non-local_only) path and is not what we test.
    link = service.create_trace_link(
        TraceRef("loomweave_entity", seed["public_locator"]),
        "satisfies",
        TraceRef("requirement_version", approved),
        actor="human:john",
        authority="accepted",
    )

    # Now a Loomweave HTTP endpoint IS configured, and ANY live peer call made
    # from the read path must fail the test instead of reaching the wire.
    monkeypatch.setenv("WEFT_LOOMWEAVE_URL", "http://127.0.0.1:9")

    def fail_http(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("advertised local_only read path must not make a live peer call")

    monkeypatch.setattr(LoomweaveAdapter, "_http_json", fail_http)
    # Guard the guard: the endpoint really is configured, so a route to HTTP
    # would happen if the read path used the HTTP-capable resolver.
    assert LoomweaveAdapter(tmp_path).http_url == "http://127.0.0.1:9"

    returned = service.trace_for()[0]

    assert returned.id == link.id
    assert returned.target_snapshot["sei"] == seed["public_sei"]
    assert returned.target_snapshot["content_hash"] == "hash-public-v1"
    assert returned.freshness == "current"
