"""Pins the reframe's target interfaces as *intentionally pending*.

These stubs (the code-up intent-graph reads and the ADR-029 SEI binding) were
laid down at repo standup to mark the shape Plainweave is being built toward
(see docs/MODULE-MAP.md and docs/design/). Each must remain importable and must
fail loudly as not-yet-implemented until its backlog item lands — that is the
contract this test guards. When a primitive is implemented, replace its
assertion here with real behaviour tests.
"""

from __future__ import annotations

import pytest

from plainweave.bindings import (
    SeiBinding,
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


@pytest.mark.parametrize("level", list(IntentLevel))
def test_orphans_is_pending(level: IntentLevel) -> None:
    with pytest.raises(NotImplementedError):
        IntentGraphReads().orphans(level)


def test_trace_is_pending() -> None:
    node = IntentNode(IntentLevel.REQUIREMENT, "REQ-AUTH-017")
    with pytest.raises(NotImplementedError):
        IntentGraphReads().trace(node)


def test_corpus_is_pending() -> None:
    with pytest.raises(NotImplementedError):
        IntentGraphReads().corpus()


def test_sei_binding_is_constructible() -> None:
    binding = SeiBinding(
        sei="loomweave:eid:abc123",
        requirement_id="REQ-AUTH-017",
        content_hash_at_attach="deadbeef",
        bound_by="agent:opus",
        bound_at="2026-06-18T00:00:00+10:00",
    )
    assert binding.sei.startswith("loomweave:eid:")


def test_bind_sei_to_requirement_is_pending() -> None:
    with pytest.raises(NotImplementedError):
        bind_sei_to_requirement("loomweave:eid:abc123", "REQ-AUTH-017", bound_by="agent:opus")


def test_is_drifted_is_pending() -> None:
    binding = SeiBinding(
        sei="loomweave:eid:abc123",
        requirement_id="REQ-AUTH-017",
        content_hash_at_attach="deadbeef",
        bound_by="agent:opus",
        bound_at="2026-06-18T00:00:00+10:00",
    )
    with pytest.raises(NotImplementedError):
        is_drifted(binding, "cafef00d")
