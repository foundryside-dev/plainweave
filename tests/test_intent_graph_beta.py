from __future__ import annotations

from pathlib import Path

from plainweave.intent_graph import IntentLevel, IntentNode
from plainweave.service import PlainweaveService
from plainweave.store import connect, migrate


def service_for(tmp_path: Path) -> PlainweaveService:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")
    return PlainweaveService(db_path)


def approved_requirement(service: PlainweaveService) -> str:
    draft = service.create_requirement(
        "Explain authentication verifier",
        "Authentication verifier code shall have explicit intent.",
        actor="human:john",
    )
    service.add_acceptance_criterion(draft.id, "Verifier intent is traceable to a goal.", actor="human:john")
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-auth")
    return draft.requirement_id


def test_schema_v2_adds_intent_tables_without_rewriting_precursor_rows(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approved_requirement(service)
    before = service.get_requirement(requirement_id)

    migrate(service.db_path, project_key="AUTH")

    after = service.get_requirement(requirement_id)
    assert after == before
    with connect(service.db_path) as connection:
        metadata = dict(connection.execute("select key, value from schema_meta").fetchall())
        assert metadata["schema_version"] == "2"
        tables = {
            str(row["name"])
            for row in connection.execute("select name from sqlite_master where type = 'table'").fetchall()
        }
    assert {"intent_goals", "intent_edges", "code_entities", "entity_associations"} <= tables


def test_goal_to_requirement_to_sei_golden_vector(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approved_requirement(service)
    sei = "loomweave:eid:auth.verify-token"

    service.record_code_entity(
        sei,
        entity_kind="loomweave_entity",
        display_name="auth.verify_token",
        content_hash="sha256:old",
        actor="agent:loomweave",
    )

    assert service.intent_orphans(IntentLevel.CODE) == [IntentNode(IntentLevel.CODE, sei)]
    assert service.intent_orphans(IntentLevel.REQUIREMENT) == [IntentNode(IntentLevel.REQUIREMENT, requirement_id)]

    goal = service.create_goal(
        "Make authentication intent explainable",
        "Every public authentication surface can answer why it exists.",
        actor="human:john",
    )
    edge = service.link_goal_to_requirement(goal.id, requirement_id, actor="human:john")
    binding = service.bind_sei_to_requirement(
        sei,
        requirement_id,
        actor="agent:codex",
        content_hash_at_attach="sha256:old",
        provenance={"source": "authoring-time-bind"},
    )

    assert edge.goal_id == goal.goal_id
    assert binding.entity_id == sei
    assert service.intent_orphans(IntentLevel.CODE) == []
    assert service.intent_orphans(IntentLevel.REQUIREMENT) == []
    assert service.is_binding_drifted(binding, "sha256:old") is False
    assert service.is_binding_drifted(binding, "sha256:new") is True

    trace = service.intent_trace(IntentNode(IntentLevel.CODE, sei))
    assert trace.up == (
        IntentNode(IntentLevel.REQUIREMENT, requirement_id),
        IntentNode(IntentLevel.GOAL, goal.goal_id),
    )
    assert trace.down == ()

    requirement_trace = service.intent_trace(IntentNode(IntentLevel.REQUIREMENT, requirement_id))
    assert requirement_trace.up == (IntentNode(IntentLevel.GOAL, goal.goal_id),)
    assert requirement_trace.down == (IntentNode(IntentLevel.CODE, sei),)

    corpus = service.intent_corpus()
    assert len(corpus) == 1
    assert corpus[0].requirement == IntentNode(IntentLevel.REQUIREMENT, requirement_id)
    assert corpus[0].goals == (IntentNode(IntentLevel.GOAL, goal.goal_id),)
    assert corpus[0].code == (IntentNode(IntentLevel.CODE, sei),)


def test_binding_is_idempotent_for_same_requirement_and_sei(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approved_requirement(service)
    sei = "loomweave:eid:auth.rotate-keys"

    first = service.bind_sei_to_requirement(
        sei,
        requirement_id,
        actor="agent:codex",
        content_hash_at_attach="sha256:first",
    )
    second = service.bind_sei_to_requirement(
        sei,
        requirement_id,
        actor="agent:codex",
        content_hash_at_attach="sha256:ignored",
    )

    assert second == first
    assert [binding.entity_id for binding in service.list_sei_bindings(requirement_id=requirement_id)] == [sei]
