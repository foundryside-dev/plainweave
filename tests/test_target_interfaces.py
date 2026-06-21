from __future__ import annotations

from plainweave.bindings import (
    bind_sei_to_requirement,
    is_drifted,
)
from plainweave.intent_graph import (
    CorpusEntry,
    IntentGraphReads,
    IntentLevel,
    IntentNode,
    Trace,
)


def test_intent_levels_span_code_to_goal() -> None:
    assert {level.value for level in IntentLevel} == {"code", "requirement", "goal"}


def test_intent_graph_dataclasses_are_constructible() -> None:
    code = IntentNode(IntentLevel.CODE, "loomweave:eid:abc123")
    req = IntentNode(IntentLevel.REQUIREMENT, "REQ-AUTH-017")
    goal = IntentNode(IntentLevel.GOAL, "GOAL-SECURE-ACCESS")
    assert Trace(node=req, up=(goal,), down=(code,)).node is req
    assert CorpusEntry(requirement=req, goals=(goal,), code=(code,)).requirement is req


def test_intent_graph_facade_delegates_to_readers() -> None:
    code = IntentNode(IntentLevel.CODE, "loomweave:eid:abc123")
    req = IntentNode(IntentLevel.REQUIREMENT, "req-1")
    goal = IntentNode(IntentLevel.GOAL, "goal-1")
    reads = IntentGraphReads(
        orphans_reader=lambda level: [code] if level == IntentLevel.CODE else [],
        trace_reader=lambda node: Trace(node, (req, goal), ()) if node == code else Trace(node, (), (code,)),
        corpus_reader=lambda: [CorpusEntry(req, (goal,), (code,))],
    )

    assert reads.orphans(IntentLevel.CODE) == [code]
    assert reads.trace(code).up == (req, goal)
    assert reads.corpus()[0].code == (code,)


def test_sei_binding_helper_constructs_driftable_value_object() -> None:
    binding = bind_sei_to_requirement(
        "loomweave:eid:abc123",
        "req-1",
        bound_by="agent:opus",
        content_hash_at_attach="deadbeef",
        provenance={"source": "unit-test"},
    )

    assert binding.sei == "loomweave:eid:abc123"
    assert binding.entity_kind == "loomweave_entity"
    assert binding.requirement_id == "req-1"
    assert binding.provenance == {"source": "unit-test"}
    assert is_drifted(binding, "deadbeef") is False
    assert is_drifted(binding, "cafef00d") is True
