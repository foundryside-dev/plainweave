from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from plainweave.mcp_surface import MCP_RESOURCE_URIS, MCP_TOOL_METADATA, PlainweaveMcpSurface
from plainweave.models import TraceRef
from plainweave.service import PlainweaveService
from plainweave.store import connect, migrate


def service_for(tmp_path: Path) -> PlainweaveService:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")
    return PlainweaveService(db_path)


def approve_requirement(
    service: PlainweaveService,
    *,
    title: str = "Reject expired bearer tokens",
    statement: str = "The API shall reject expired bearer tokens.",
    criterion: str = "Expired tokens return 401.",
    key: str = "approve-1",
) -> str:
    draft = service.create_requirement(title, statement, "human:john")
    service.add_acceptance_criterion(draft.id, criterion, actor="human:john")
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key=key)
    return draft.id


def db_snapshot(db_path: Path) -> dict[str, list[tuple[Any, ...]]]:
    with connect(db_path) as connection:
        tables = [
            str(row["name"])
            for row in connection.execute(
                "select name from sqlite_master where type = 'table' and name not like 'sqlite_%' order by name"
            )
        ]
        snapshot: dict[str, list[tuple[Any, ...]]] = {}
        for table in tables:
            columns = [str(row["name"]) for row in connection.execute(f"pragma table_info({table})")]
            order_by = ", ".join(columns)
            rows = connection.execute(f"select * from {table} order by {order_by}").fetchall()
            snapshot[table] = [tuple(row[column] for column in columns) for row in rows]
        return snapshot


def data(envelope: dict[str, Any]) -> dict[str, Any]:
    assert envelope["ok"] is True
    assert envelope["schema"].startswith("weft.plainweave.")
    assert envelope["warnings"] == []
    assert envelope["meta"]["producer"]["tool"] == "plainweave"
    assert envelope["meta"]["project"] == "AUTH"
    return cast(dict[str, Any], envelope["data"])


def assert_error(envelope: dict[str, Any], code: str) -> None:
    assert envelope["schema"] == "weft.plainweave.error.v1"
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == code
    assert envelope["error"]["recoverable"] is True
    assert envelope["error"]["hint"]


def test_mcp_tool_inventory_is_agent_task_surface() -> None:
    expected_tools = {
        "plainweave_intent_corpus",
        "plainweave_intent_orphans",
        "plainweave_intent_trace",
        "plainweave_project_context_get",
        "plainweave_requirement_search",
        "plainweave_requirement_get",
        "plainweave_requirement_dossier_get",
        "plainweave_trace_link_list",
        "plainweave_baseline_list",
        "plainweave_baseline_get",
        "plainweave_baseline_diff",
        "plainweave_verification_status_get",
        "plainweave_verification_status_list",
    }

    assert set(MCP_TOOL_METADATA) == expected_tools
    for name, metadata in MCP_TOOL_METADATA.items():
        assert metadata["name"] == name
        assert metadata["mutates"] is False
        assert metadata["local_only"] is True
        assert metadata["peer_side_effects"] == []
        assert metadata["authority_boundary"]


def test_mcp_project_context_lists_read_only_capabilities_and_contract_resources(tmp_path: Path) -> None:
    service_for(tmp_path)

    surface = PlainweaveMcpSurface(tmp_path)

    context = data(surface.plainweave_project_context_get(include_contracts=True))

    assert context["initialized"] is True
    assert context["project_key"] == "AUTH"
    assert context["schema_version"] == 2
    assert context["authority_boundary"]["local_only"] is True
    assert context["authority_boundary"]["live_peer_calls"] is False
    assert all(capability["mutates"] is False for capability in context["capabilities"])
    assert "plainweave://contracts/weft.plainweave.requirement_dossier.v1" in context["contract_resources"]


def test_mcp_read_tools_return_envelopes_and_do_not_mutate_state(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method = service.add_verification_method(
        requirement_id,
        method="test",
        target="tests/test_auth.py::test_expired",
        actor="human:john",
    )
    service.record_verification_evidence(
        method.id,
        status="passing",
        evidence_ref="pytest:tests/test_auth.py::test_expired",
        actor="agent:codex",
    )
    baseline = service.create_baseline("Release 1.0", actor="human:john")
    service.create_trace_link(
        TraceRef("file_ref", "src/auth.py"),
        "fragile_satisfies",
        TraceRef("requirement_version", f"{requirement_id}@1"),
        actor="human:john",
        authority="accepted",
    )
    surface = PlainweaveMcpSurface(tmp_path)
    before = db_snapshot(service.db_path)

    assert data(surface.plainweave_requirement_search(query="tokens"))["items"][0]["id"] == requirement_id
    assert data(surface.plainweave_requirement_get(requirement_id))["id"] == requirement_id
    assert data(surface.plainweave_requirement_dossier_get(requirement_id))["peer_facts"]["live_peer_calls"] is False
    assert data(surface.plainweave_trace_link_list(requirement_id=requirement_id))["items"][0]["state"] == "accepted"
    assert data(surface.plainweave_baseline_list())["items"][0]["id"] == baseline.id
    assert data(surface.plainweave_baseline_get(baseline.id))["id"] == baseline.id
    assert data(surface.plainweave_baseline_diff(baseline.id))["summary"]["unchanged"] == 1
    assert data(surface.plainweave_verification_status_get(requirement_id))["status"] == "satisfied"
    assert data(surface.plainweave_verification_status_list(status_filter="unverified"))["items"] == []

    assert db_snapshot(service.db_path) == before


def test_mcp_intent_graph_read_tools_are_paginated_and_do_not_mutate_state(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    canonical_requirement_id = service.get_requirement(requirement_id).requirement_id
    sei = "loomweave:eid:auth.verify-token"
    service.record_code_entity(
        sei,
        entity_kind="loomweave_entity",
        display_name="auth.verify_token",
        content_hash="sha256:old",
        actor="agent:loomweave",
    )
    goal = service.create_goal(
        "Make authentication intent explainable",
        "Every public authentication surface can answer why it exists.",
        actor="human:john",
    )
    service.link_goal_to_requirement(goal.id, requirement_id, actor="human:john")
    before = db_snapshot(service.db_path)

    surface = PlainweaveMcpSurface(tmp_path)

    code_orphans = data(surface.plainweave_intent_orphans(level="code", limit=1, offset=0))
    assert code_orphans["items"][0]["node_id"] == sei

    service.bind_sei_to_requirement(sei, requirement_id, actor="agent:codex", content_hash_at_attach="sha256:old")
    after_bind = db_snapshot(service.db_path)
    trace = data(surface.plainweave_intent_trace(level="code", node_id=sei))
    corpus = data(surface.plainweave_intent_corpus(limit=10, offset=0))

    assert [item["level"] for item in trace["up"]] == ["requirement", "goal"]
    assert corpus["items"][0]["requirement"]["node_id"] == canonical_requirement_id
    assert db_snapshot(service.db_path) == after_bind
    assert before != after_bind


def test_mcp_list_tools_are_paginated_and_filterable(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    first = approve_requirement(service, title="Reject expired bearer tokens", key="approve-1")
    second = approve_requirement(service, title="Rotate signing keys", key="approve-2")
    method = service.add_verification_method(first, method="test", target="tests/test_auth.py", actor="human:john")
    service.record_verification_evidence(
        method.id,
        status="passing",
        evidence_ref="pytest:tests/test_auth.py",
        actor="agent:codex",
    )
    surface = PlainweaveMcpSurface(tmp_path)

    first_page = data(surface.plainweave_requirement_search(status_filter="approved", limit=1, offset=0))
    second_page = data(surface.plainweave_requirement_search(status_filter="approved", limit=1, offset=1))
    unverified = data(surface.plainweave_verification_status_list(status_filter="unverified", limit=10, offset=0))

    assert first_page["has_more"] is True
    assert first_page["next_offset"] == 1
    assert [item["id"] for item in first_page["items"]] == [first]
    assert second_page["has_more"] is False
    assert [item["id"] for item in second_page["items"]] == [second]
    assert [item["id"] for item in unverified["items"]] == [second]


def test_mcp_errors_use_plainweave_error_envelope(tmp_path: Path) -> None:
    service_for(tmp_path)

    surface = PlainweaveMcpSurface(tmp_path)

    assert_error(surface.plainweave_requirement_get("REQ-AUTH-4040"), "NOT_FOUND")
    assert_error(surface.plainweave_requirement_search(status_filter="done"), "VALIDATION")
    assert_error(surface.plainweave_trace_link_list(state_filter="missing"), "VALIDATION")
    assert_error(surface.plainweave_verification_status_list(status_filter="satisfied"), "VALIDATION")


def test_mcp_contract_resources_are_readable(tmp_path: Path) -> None:
    service_for(tmp_path)

    surface = PlainweaveMcpSurface(tmp_path)

    assert "plainweave://project/context" in MCP_RESOURCE_URIS
    for uri in MCP_RESOURCE_URIS:
        resource = surface.read_resource(uri)
        assert resource["ok"] is True
        assert isinstance(resource["schema"], str)
        assert resource["schema"].startswith("weft.plainweave.")
