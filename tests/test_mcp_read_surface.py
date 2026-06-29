from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from plainweave import __version__
from plainweave.mcp_surface import MCP_RESOURCE_URIS, MCP_TOOL_METADATA, PlainweaveMcpSurface
from plainweave.models import TraceRef
from plainweave.service import PlainweaveService
from plainweave.store import connect, migrate
from tests.loomweave_test_utils import seed_loomweave_catalog
from tests.preflight_contract import validate_preflight_facts


def service_for(tmp_path: Path) -> PlainweaveService:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")
    return PlainweaveService(db_path, root=tmp_path)


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


_VERDICT_KEYS = {"allow", "allowed", "block", "blocked", "verdict", "decision", "gate", "enforcement"}
_VERDICT_VALUE_TOKENS = {
    "allow",
    "allowed",
    "block",
    "blocked",
    "block_candidate",
    "deny",
    "denied",
    "approved",
    "rejected",
    "pass_fail",
    "verdict",
}
_NEUTRAL_FACT_SEVERITIES = {"info", "warn", "critical"}


def assert_no_verdict_keys(value: object) -> None:
    """Reject gate/verdict semantics by key, by severity value, and by string value.

    Key-only checks miss a verdict smuggled into a *value* (e.g. severity
    "block_candidate"), so this also asserts severities use the neutral fact
    vocabulary and that no string anywhere is a verdict token.
    """
    if isinstance(value, dict):
        assert _VERDICT_KEYS.isdisjoint(value)
        severity = value.get("severity")
        if isinstance(severity, str):
            assert severity in _NEUTRAL_FACT_SEVERITIES, f"non-neutral severity value: {severity}"
        for item in value.values():
            assert_no_verdict_keys(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_verdict_keys(item)
    elif isinstance(value, str):
        assert value.strip().lower() not in _VERDICT_VALUE_TOKENS, f"verdict-like value: {value}"


def test_mcp_tool_inventory_is_agent_task_surface() -> None:
    expected_tools = {
        "plainweave_intent_corpus",
        "plainweave_intent_coverage",
        "plainweave_intent_orphans",
        "plainweave_intent_trace",
        "plainweave_project_context_get",
        "plainweave_loomweave_catalog_list",
        "plainweave_requirement_search",
        "plainweave_requirement_get",
        "plainweave_requirement_dossier_get",
        "plainweave_trace_link_list",
        "plainweave_baseline_list",
        "plainweave_baseline_get",
        "plainweave_baseline_diff",
        "plainweave_entity_intent_context_get",
        "plainweave_preflight_facts_get",
        "plainweave_verification_status_get",
        "plainweave_verification_status_list",
        "plainweave_wardline_peer_facts_list",
        "plainweave_requirements_enrichment_get",
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
    seed_loomweave_catalog(tmp_path)

    surface = PlainweaveMcpSurface(tmp_path)

    context = data(surface.plainweave_project_context_get(include_contracts=True))

    assert context["initialized"] is True
    assert context["project_key"] == "AUTH"
    assert context["schema_version"] == 2
    assert context["authority_boundary"]["local_only"] is True
    assert context["authority_boundary"]["live_peer_calls"] is False
    assert all(capability["mutates"] is False for capability in context["capabilities"])
    assert "plainweave://contracts/weft.plainweave.requirement_dossier.v1" in context["contract_resources"]
    assert "plainweave://contracts/weft.plainweave.entity_intent_context.v1" in context["contract_resources"]
    assert "plainweave://contracts/weft.plainweave.preflight_facts.v1" in context["contract_resources"]
    assert context["peer_read_capabilities"]["loomweave"]["adapter_status"]["status"] == "available"
    assert context["peer_read_capabilities"]["loomweave"]["degraded"] == []


def test_mcp_read_tools_return_envelopes_and_do_not_mutate_state(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    seed_loomweave_catalog(tmp_path)
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
    assert data(surface.plainweave_loomweave_catalog_list())["items"]
    assert data(surface.plainweave_baseline_list())["items"][0]["id"] == baseline.id
    assert data(surface.plainweave_baseline_get(baseline.id))["id"] == baseline.id
    assert data(surface.plainweave_baseline_diff(baseline.id))["summary"]["unchanged"] == 1
    assert data(surface.plainweave_entity_intent_context_get(entity_refs=["src/auth.py"]))["summary"]["resolved"] == 1
    assert data(surface.plainweave_preflight_facts_get(requirement_ids=[requirement_id]))["summary"]["info"] >= 1
    assert data(surface.plainweave_verification_status_get(requirement_id))["status"] == "satisfied"
    assert data(surface.plainweave_verification_status_list(status_filter="unverified"))["items"] == []

    assert db_snapshot(service.db_path) == before


def test_mcp_preflight_facts_returns_scoped_advisory_facts_without_verdicts(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    seed = seed_loomweave_catalog(tmp_path)
    stale_requirement = approve_requirement(service, title="Rotate signing keys", key="approve-stale")
    method = service.add_verification_method(
        stale_requirement,
        method="test",
        target="tests/test_keys.py::test_rotation",
        actor="human:john",
    )
    service.record_verification_evidence(
        method.id,
        status="passing",
        evidence_ref="pytest:tests/test_keys.py::test_rotation",
        actor="agent:codex",
    )
    service.create_trace_link(
        TraceRef("loomweave_entity", seed["public_locator"]),
        "satisfies",
        TraceRef("requirement_version", f"{stale_requirement}@1"),
        actor="human:john",
        authority="accepted",
    )
    baseline = service.create_baseline("Release 1.0", actor="human:john")
    service.supersede_requirement(
        stale_requirement,
        title="Rotate signing keys promptly",
        statement="The API shall rotate signing keys within the configured window.",
        actor="human:john",
        expected_version=1,
        idempotency_key="supersede-stale",
    )
    missing_requirement = approve_requirement(service, title="Audit password resets", key="approve-missing")
    surface = PlainweaveMcpSurface(tmp_path)

    envelope = surface.plainweave_preflight_facts_get(
        scope_kind="pending_diff",
        base="main",
        head="WORKTREE",
        requirement_ids=[stale_requirement, missing_requirement],
        entity_refs=[seed["public_sei"], "loomweave:eid:untraced"],
        baseline_id=baseline.id,
    )

    assert envelope["schema"] == "weft.plainweave.preflight_facts.v1"
    preflight = data(envelope)
    # Live output runs through the SAME validator as the golden fixture (no drift).
    validate_preflight_facts(preflight)
    assert set(preflight) == {
        "producer",
        "scope",
        "generated_at",
        "freshness",
        "facts",
        "summary",
        "warnings",
        "provenance",
        "authority_boundary",
    }
    assert preflight["producer"] == {"tool": "plainweave", "version": __version__, "project": "AUTH"}
    assert preflight["scope"] == {
        "kind": "pending_diff",
        "base": "main",
        "head": "WORKTREE",
        "requirement_ids": [stale_requirement, missing_requirement],
        "entity_refs": [seed["public_sei"], "loomweave:eid:untraced"],
        "baseline_id": baseline.id,
    }
    assert preflight["freshness"] == "partial"
    assert preflight["authority_boundary"] == {
        "local_only": True,
        "live_peer_calls": False,
        "governance_verdicts": False,
        "legis_policy_cells": "external",
    }
    assert_no_verdict_keys(preflight)

    facts = cast(list[dict[str, Any]], preflight["facts"])
    fact_kinds = {fact["kind"] for fact in facts}
    assert {
        "requirement_touched",
        "requirement_verification_stale",
        "requirement_verification_missing",
        "baseline_drift",
        "trace_gap",
        "untraced_change",
    }.issubset(fact_kinds)
    for fact in facts:
        assert set(fact) == {
            "id",
            "kind",
            "severity",
            "requirement",
            "message",
            "evidence_refs",
            "source",
            "freshness",
            "provenance",
        }
        assert fact["severity"] in {"info", "warn", "critical"}
        assert fact["freshness"] in {"current", "partial", "unavailable"}
        assert fact["provenance"]["producer"] == "plainweave"
        assert fact["source"]["kind"]

    summary = cast(dict[str, Any], preflight["summary"])
    assert summary["info"] == sum(1 for fact in facts if fact["severity"] == "info")
    assert summary["warn"] == sum(1 for fact in facts if fact["severity"] == "warn")
    assert summary["critical"] == sum(1 for fact in facts if fact["severity"] == "critical")
    assert summary["facts"] == len(facts)
    assert summary["by_kind"]["untraced_change"] == 1
    assert summary["by_freshness"]["partial"] >= 1

    warnings = cast(list[dict[str, Any]], preflight["warnings"])
    assert {warning["code"] for warning in warnings} == {
        "live_diff_resolution_unavailable",
        "goal_trail_unavailable",
        "linked_work_facts_unavailable",
        "finding_facts_unavailable",
    }


def test_mcp_preflight_freshness_is_current_for_fully_resolved_explicit_scope(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    seed = seed_loomweave_catalog(tmp_path)
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
    service.create_trace_link(
        TraceRef("loomweave_entity", seed["public_locator"]),
        "satisfies",
        TraceRef("requirement_version", f"{requirement_id}@1"),
        actor="human:john",
        authority="accepted",
    )
    surface = PlainweaveMcpSurface(tmp_path)

    preflight = data(
        surface.plainweave_preflight_facts_get(scope_kind="explicit_requirements", requirement_ids=[requirement_id])
    )

    # Non-diff scope, every fact current -> "current" is reachable (was a dead constant).
    assert preflight["freshness"] == "current"
    assert {fact["kind"] for fact in preflight["facts"]} == {"requirement_touched"}


def test_mcp_preflight_freshness_is_unavailable_for_empty_project_scope(tmp_path: Path) -> None:
    service_for(tmp_path)
    surface = PlainweaveMcpSurface(tmp_path)

    preflight = data(surface.plainweave_preflight_facts_get(scope_kind="project"))

    assert preflight["facts"] == []
    assert preflight["freshness"] == "unavailable"

    # Filigree seam, scope-independent no-silent-clean (production blocker #5, paired with
    # tests/contracts/test_filigree_contract.py): even on an EMPTY scope, linked-work absence
    # is reported in-band as `linked_work_facts_unavailable`, never an empty-but-ok result.
    warnings = cast(list[dict[str, Any]], preflight["warnings"])
    linked_work = next(w for w in warnings if w["code"] == "linked_work_facts_unavailable")
    assert "Filigree" in linked_work["message"]
    assert linked_work["severity"] == "info"
    assert linked_work["freshness"] == "unavailable"
    assert linked_work["provenance"]["inputs"] == []


def test_mcp_preflight_soft_degrades_an_unresolvable_requirement_id(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    surface = PlainweaveMcpSurface(tmp_path)

    envelope = surface.plainweave_preflight_facts_get(
        scope_kind="explicit_requirements",
        requirement_ids=[requirement_id, "REQ-AUTH-9999"],
    )

    # One missing id must NOT hard-fail the whole report (was a NOT_FOUND abort).
    assert envelope["ok"] is True
    preflight = data(envelope)
    assert any(fact["requirement"]["id"] == requirement_id for fact in preflight["facts"])
    warning_codes = {warning["code"] for warning in preflight["warnings"]}
    assert "requirement_unresolved" in warning_codes


def test_mcp_preflight_labels_corpus_fallback_requirements_nearby_not_touched(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    approve_requirement(service)
    surface = PlainweaveMcpSurface(tmp_path)

    # Default pending_diff with no explicit ids falls back to the whole corpus; with the
    # diff unresolved, those requirements are "nearby", not proven "touched".
    preflight = data(surface.plainweave_preflight_facts_get(scope_kind="pending_diff"))

    fact_kinds = {fact["kind"] for fact in preflight["facts"]}
    assert "requirement_nearby" in fact_kinds
    assert "requirement_touched" not in fact_kinds


def test_mcp_preflight_emits_orphaned_entity_link_for_a_stale_entity_trace(tmp_path: Path) -> None:
    """Production blocker #4 test-hardening: orphaned_entity_link emits but had zero
    behavioral coverage. A scoped requirement whose entity trace went stale/orphaned must
    surface an orphaned_entity_link warn fact citing the offending trace."""
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    stale = service.create_trace_link(
        TraceRef("file_ref", "src/legacy_auth.py"),
        "fragile_satisfies",
        TraceRef("requirement_version", f"{requirement_id}@1"),
        actor="human:john",
        authority="accepted",
    )
    service.mark_trace_stale(stale.id, actor="agent:codex", reason="content changed")
    surface = PlainweaveMcpSurface(tmp_path)

    preflight = data(
        surface.plainweave_preflight_facts_get(scope_kind="explicit_requirements", requirement_ids=[requirement_id])
    )

    orphaned = [fact for fact in preflight["facts"] if fact["kind"] == "orphaned_entity_link"]
    assert len(orphaned) == 1
    assert orphaned[0]["severity"] == "warn"
    assert stale.id in orphaned[0]["evidence_refs"]


def test_mcp_entity_intent_context_returns_peer_ready_entity_facts(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    seed = seed_loomweave_catalog(tmp_path)
    satisfied_requirement = approve_requirement(
        service,
        title="Reject expired bearer tokens",
        key="approve-satisfied",
    )
    method = service.add_verification_method(
        satisfied_requirement,
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
    stale_requirement = approve_requirement(
        service,
        title="Rotate signing keys",
        statement="The API shall rotate signing keys.",
        criterion="Rotated keys are accepted.",
        key="approve-stale",
    )
    sei_ref = seed["public_sei"]
    service.create_trace_link(
        TraceRef("loomweave_entity", seed["public_locator"]),
        "satisfies",
        TraceRef("requirement_version", f"{satisfied_requirement}@1"),
        actor="human:john",
        authority="accepted",
    )
    stale_link = service.create_trace_link(
        TraceRef("file_ref", "src/auth.py"),
        "fragile_satisfies",
        TraceRef("requirement_version", f"{stale_requirement}@1"),
        actor="human:john",
        authority="accepted",
    )
    service.mark_trace_stale(stale_link.id, actor="agent:codex", reason="content changed")
    goal = service.create_goal(
        "Bearer tokens are trustworthy",
        "Every accepted bearer token is provably unexpired.",
        actor="human:john",
    )
    service.link_goal_to_requirement(goal.id, satisfied_requirement, actor="human:john")
    surface = PlainweaveMcpSurface(tmp_path)

    context = data(
        surface.plainweave_entity_intent_context_get(
            entity_refs=[sei_ref, "src/auth.py", "loomweave:eid:missing"],
        )
    )

    assert context["authority_boundary"] == {
        "local_only": True,
        "live_peer_calls": False,
        "identity_authority": "loomweave",
        "drift_source": "local_trace_freshness",
    }
    assert context["summary"] == {
        "requested": 3,
        "resolved": 2,
        "resolved_no_binding": 0,
        "unresolved": 1,
        "peer_resolution_unavailable": 3,
        "orphaned": 1,
    }
    items = {item["input_ref"]: item for item in context["items"]}

    resolved = items[sei_ref]
    assert resolved["resolution"]["state"] == "resolved"
    assert resolved["resolution"]["matched_refs"] == [
        {"kind": "loomweave_entity", "id": sei_ref, "match": "exact_local_trace"}
    ]
    assert resolved["resolution"]["local_catalog"]["state"] == "resolved"
    assert resolved["resolution"]["local_catalog"]["sei"] == sei_ref
    assert resolved["resolution"]["peer_resolution"]["state"] == "unavailable"
    assert resolved["bindings"][0]["trace"]["from"]["id"] == sei_ref
    assert resolved["bindings"][0]["requirement"]["id"] == "REQ-AUTH-0001"
    assert resolved["bindings"][0]["verification"]["status"] == "satisfied"
    satisfied_goal_trail = resolved["requirement_trail"][0]["goal_trail"]
    assert satisfied_goal_trail["state"] == "resolved"
    assert satisfied_goal_trail["goals"][0]["id"] == goal.id
    assert satisfied_goal_trail["goals"][0]["title"] == "Bearer tokens are trustworthy"
    assert satisfied_goal_trail["goals"][0]["edge_freshness"] == "current"
    assert resolved["orphan"] == {
        "state": "bound",
        "is_orphan": False,
        "accepted_bindings": 1,
        "nonaccepted_bindings": 0,
    }
    assert resolved["freshness"]["state"] == "current"
    assert resolved["drift"]["state"] == "not_detected"

    stale = items["src/auth.py"]
    assert stale["resolution"]["state"] == "resolved"
    assert stale["orphan"]["state"] == "stale_binding"
    assert stale["orphan"]["is_orphan"] is True
    assert stale["freshness"]["state"] == "stale"
    assert stale["drift"]["state"] == "stale"
    stale_goal_trail = stale["requirement_trail"][0]["goal_trail"]
    assert stale_goal_trail["state"] == "no_goal"
    assert stale_goal_trail["goals"] == []

    missing = items["loomweave:eid:missing"]
    assert missing["resolution"]["state"] == "unresolved"
    assert missing["resolution"]["local_catalog"]["state"] == "unresolved"
    assert missing["resolution"]["peer_resolution"]["state"] == "unavailable"
    assert missing["bindings"] == []
    assert missing["requirement_trail"] == []
    # A ref Plainweave cannot resolve is NOT asserted to be a known orphan, and must
    # not inflate summary.orphaned — that count is for genuine unbound/stale bindings.
    assert missing["orphan"]["state"] == "unavailable"
    assert missing["orphan"]["is_orphan"] is False
    assert missing["freshness"]["state"] == "unavailable"
    assert missing["drift"]["state"] == "unavailable"


def test_mcp_entity_intent_context_resolves_loomweave_locator_inputs(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    seed = seed_loomweave_catalog(tmp_path)
    requirement_id = approve_requirement(service, key="approve-locator")
    # The trace is stored under the canonical SEI (writes canonicalize locator -> SEI).
    service.create_trace_link(
        TraceRef("loomweave_entity", seed["public_locator"]),
        "satisfies",
        TraceRef("requirement_version", f"{requirement_id}@1"),
        actor="human:john",
        authority="accepted",
    )
    surface = PlainweaveMcpSurface(tmp_path)

    # A peer (e.g. Warpline) holding the legacy locator form must still resolve the
    # binding, not be told the entity is unresolved + an unbound orphan.
    context = data(surface.plainweave_entity_intent_context_get(entity_refs=[seed["public_locator"]]))

    item = context["items"][0]
    assert item["resolution"]["state"] == "resolved"
    assert item["resolution"]["local_catalog"]["state"] == "resolved"
    assert item["resolution"]["local_catalog"]["sei"] == seed["public_sei"]
    assert item["resolution"]["matched_refs"] == [
        {"kind": "loomweave_entity", "id": seed["public_sei"], "match": "canonical_identity"}
    ]
    assert item["bindings"][0]["requirement"]["id"] == requirement_id
    assert item["orphan"]["state"] == "bound"
    assert item["orphan"]["is_orphan"] is False
    assert context["summary"]["resolved"] == 1
    assert context["summary"]["orphaned"] == 0


def test_mcp_entity_intent_context_distinguishes_resolved_no_binding_from_unresolved(tmp_path: Path) -> None:
    service_for(tmp_path)
    seed = seed_loomweave_catalog(tmp_path)
    surface = PlainweaveMcpSurface(tmp_path)

    context = data(
        surface.plainweave_entity_intent_context_get(
            entity_refs=[seed["public_sei"], "loomweave:eid:unknown"],
        )
    )
    items = {item["input_ref"]: item for item in context["items"]}

    # Known to Loomweave's local catalog but bound to no requirement: a real orphan.
    known = items[seed["public_sei"]]
    assert known["resolution"]["state"] == "resolved_no_binding"
    assert known["resolution"]["local_catalog"]["state"] == "resolved"
    assert known["orphan"]["state"] == "unbound"
    assert known["orphan"]["is_orphan"] is True

    # Not known to Loomweave at all: cannot be resolved, and not a claimed orphan.
    unknown = items["loomweave:eid:unknown"]
    assert unknown["resolution"]["state"] == "unresolved"
    assert unknown["resolution"]["local_catalog"]["state"] == "unresolved"
    assert unknown["orphan"]["state"] == "unavailable"
    assert unknown["orphan"]["is_orphan"] is False

    assert context["summary"] == {
        "requested": 2,
        "resolved": 0,
        "resolved_no_binding": 1,
        "unresolved": 1,
        "peer_resolution_unavailable": 2,
        "orphaned": 1,
    }


def test_mcp_entity_intent_context_reports_unresolved_binding_for_vanished_requirement(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    seed = seed_loomweave_catalog(tmp_path)
    # A proposed trace whose requirement_version target does not (or no longer) resolves
    # to a requirement: the entity itself is resolved (it has a matching trace), but the
    # binding's requirement_resolution must report "unresolved" rather than crash or fake
    # a requirement.
    service.create_trace_link(
        TraceRef("loomweave_entity", seed["public_locator"]),
        "satisfies",
        TraceRef("requirement_version", "REQ-AUTH-9999@1"),
        actor="agent:codex",
        authority="agent_proposed",
    )
    surface = PlainweaveMcpSurface(tmp_path)

    context = data(surface.plainweave_entity_intent_context_get(entity_refs=[seed["public_sei"]]))

    item = context["items"][0]
    assert item["resolution"]["state"] == "resolved"
    binding = item["bindings"][0]
    assert binding["requirement_resolution"]["state"] == "unresolved"
    assert binding["requirement"] is None
    assert binding["verification"]["state"] == "unavailable"
    # No requirement resolved, so the trail is empty (nothing to ladder to a goal).
    assert item["requirement_trail"] == []


def test_mcp_entity_intent_context_distinguishes_unavailable_catalog_from_unresolved(tmp_path: Path) -> None:
    # No Loomweave catalog seeded: the local catalog cannot be consulted at all.
    service_for(tmp_path)
    surface = PlainweaveMcpSurface(tmp_path)

    context = data(surface.plainweave_entity_intent_context_get(entity_refs=["loomweave:eid:anything"]))

    item = context["items"][0]
    # "unavailable" (catalog absent) must be distinguishable from "unresolved" (catalog
    # present, ref not found) so a peer can tell an outage from a genuine miss.
    assert item["resolution"]["local_catalog"]["state"] == "unavailable"
    assert item["resolution"]["state"] == "unresolved"
    assert item["orphan"]["state"] == "unavailable"
    assert item["orphan"]["is_orphan"] is False


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


def test_mcp_intent_trace_from_goal_lists_downstream_requirements_and_code(tmp_path: Path) -> None:
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
    service.bind_sei_to_requirement(sei, requirement_id, actor="agent:codex", content_hash_at_attach="sha256:old")
    before = db_snapshot(service.db_path)

    surface = PlainweaveMcpSurface(tmp_path)
    trace = data(surface.plainweave_intent_trace(level="goal", node_id=goal.id))

    assert trace["node"]["level"] == "goal"
    assert trace["up"] == []
    down_by_level = {(item["level"], item["node_id"]) for item in trace["down"]}
    assert ("requirement", canonical_requirement_id) in down_by_level
    assert ("code", sei) in down_by_level
    assert db_snapshot(service.db_path) == before


def test_mcp_loomweave_catalog_list_is_paginated_and_reports_adapter_status(tmp_path: Path) -> None:
    service_for(tmp_path)
    seed = seed_loomweave_catalog(tmp_path)
    surface = PlainweaveMcpSurface(tmp_path)

    first_page = data(surface.plainweave_loomweave_catalog_list(limit=1, offset=0))
    second_page = data(surface.plainweave_loomweave_catalog_list(limit=10, offset=1))

    assert first_page["limit"] == 1
    assert first_page["offset"] == 0
    assert first_page["adapter_status"]["status"] == "available"
    assert first_page["coverage"]["complete"] is False
    assert set(first_page["coverage"]["absent_tags"]) == {"http-route", "cli-command"}
    assert any(item["code"] == "public_surface_tags_incomplete" for item in first_page["degraded"])
    assert first_page["has_more"] is True
    assert second_page["has_more"] is False
    all_items = first_page["items"] + second_page["items"]
    assert [item["locator"] for item in all_items] == [
        "python:function:pkg.main",
        seed["public_locator"],
        "python:module:pkg",
    ]
    assert all_items[1]["sei"] == seed["public_sei"]
    assert all_items[1]["source"]["line_start"] == 10


def test_mcp_dossier_peer_facts_report_loomweave_trace_sources(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    seed = seed_loomweave_catalog(tmp_path)
    requirement_id = approve_requirement(service)
    service.create_trace_link(
        TraceRef("loomweave_entity", seed["public_locator"]),
        "satisfies",
        TraceRef("requirement_version", f"{requirement_id}@1"),
        actor="human:john",
        authority="accepted",
    )
    surface = PlainweaveMcpSurface(tmp_path)

    dossier = data(surface.plainweave_requirement_dossier_get(requirement_id))

    assert "loomweave" in dossier["peer_facts"]["sources"]
    assert any("Loomweave" in note for note in dossier["peer_facts"]["notes"])
    assert dossier["traces"]["items"][0]["target_snapshot"]["sei"] == seed["public_sei"]


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
    assert_error(surface.plainweave_entity_intent_context_get(entity_refs=[]), "VALIDATION")
    assert_error(surface.plainweave_preflight_facts_get(scope_kind="release_verdict"), "VALIDATION")
    assert_error(surface.plainweave_verification_status_list(status_filter="satisfied"), "VALIDATION")


def test_mcp_wardline_peer_facts_returns_advisory_envelope_without_verdicts(tmp_path: Path) -> None:
    service_for(tmp_path)  # initialize the plainweave store
    wdir = tmp_path / ".wardline"
    wdir.mkdir()
    record: dict[str, object] = {
        "fingerprint": "d1",
        "kind": "defect",
        "rule_id": "WLN-1",
        "location": {"path": "src/a.py", "line_start": 1, "line_end": 1, "col_start": 0, "col_end": 1},
        "maturity": "stable",
        "message": "m",
        "properties": {},
        "qualname": "a.f",
        "related_entities": [],
        "severity": "CRITICAL",
        "suggestion": None,
        "suppression_reason": None,
        "suppression_state": "active",
    }
    (wdir / "20260101T000000Z-findings.jsonl").write_text(json.dumps(record), encoding="utf-8")
    envelope = PlainweaveMcpSurface(tmp_path).plainweave_wardline_peer_facts_list()
    assert envelope["schema"] == "weft.plainweave.wardline_peer_facts.v1"
    assert envelope["ok"] is True
    from tests.wardline_contract import validate_wardline_peer_facts

    validate_wardline_peer_facts(cast(dict[str, Any], envelope["data"]))


def test_mcp_contract_resources_are_readable(tmp_path: Path) -> None:
    service_for(tmp_path)

    surface = PlainweaveMcpSurface(tmp_path)

    assert "plainweave://project/context" in MCP_RESOURCE_URIS
    for uri in MCP_RESOURCE_URIS:
        resource = surface.read_resource(uri)
        assert resource["ok"] is True
        assert isinstance(resource["schema"], str)
        assert resource["schema"].startswith("weft.plainweave.")


def test_mcp_requirements_enrichment_tool_is_advertised_and_callable(tmp_path: Path) -> None:
    service_for(tmp_path)
    seed_loomweave_catalog(tmp_path)
    envelope = PlainweaveMcpSurface(tmp_path).plainweave_requirements_enrichment_get(
        entity_refs=["loomweave:eid:public00000000000000000000000000"]
    )
    assert envelope["schema"] == "weft.plainweave.requirements_enrichment.v1"
    assert "plainweave_requirements_enrichment_get" in MCP_TOOL_METADATA
