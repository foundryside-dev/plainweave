from __future__ import annotations

from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from plainweave.intent_graph import IntentLevel, IntentNode
from plainweave.web import views
from plainweave.web.app import create_app


@pytest.fixture
def client(project_root: Path) -> TestClient:
    return TestClient(create_app(actor="human:alice", root=project_root))


def test_intent_dashboard_renders(client: TestClient) -> None:
    resp = client.get("/intent")
    assert resp.status_code == 200
    assert "Coverage" in resp.text


def test_intent_orphans_render_titles_and_links(client: TestClient) -> None:
    """M7: requirement orphans show their human title linked to /req/{id}; goal orphans
    show their title linked to /goals; zero-count altitudes are hidden."""
    app: Starlette = client.app  # type: ignore[assignment]
    ctx = app.state.ctx_factory()
    req = ctx.service.create_requirement("Unladdered requirement", "body", actor="human:alice")
    # An approved-but-unladdered requirement is also an orphan; its title resolves from
    # the approved version record rather than a draft dossier lookup.
    approved = ctx.service.create_requirement("Approved orphan title", "body", actor="human:alice")
    ctx.service.approve_requirement(approved.requirement_id, actor="human:alice", expected_version=0)
    ctx.service.create_goal("Unladdered goal", "north-star", actor="human:alice")
    html = client.get("/intent").text
    # Requirement orphan (draft-only): human title, linked to its detail page (not the raw node id).
    assert "Unladdered requirement" in html
    assert f'href="/req/{req.requirement_id}"' in html
    # Approved orphan: version-record title, also linked.
    assert "Approved orphan title" in html
    assert f'href="/req/{approved.requirement_id}"' in html
    # Goal orphan: human title, linked to the goals page.
    assert "Unladdered goal" in html
    assert 'href="/goals"' in html
    # No code entities indexed → the code orphan section must be hidden, not shown as (0).
    assert "Orphans — code" not in html


def test_build_orphan_sections_resolves_and_drops_empty() -> None:
    orphans = {
        IntentLevel.CODE.value: [IntentNode(IntentLevel.CODE, "loomweave:eid:abc")],
        IntentLevel.REQUIREMENT.value: [IntentNode(IntentLevel.REQUIREMENT, "req-1")],
        IntentLevel.GOAL.value: [],
    }
    sections = views.build_orphan_sections(orphans, {"req-1": "Req Title"}, {})
    # Empty GOAL altitude dropped; CODE + REQUIREMENT kept in altitude order.
    assert [s.level for s in sections] == [IntentLevel.CODE.value, IntentLevel.REQUIREMENT.value]
    code_item = sections[0].items[0]
    assert code_item.label == "loomweave:eid:abc"
    assert code_item.href is None
    req_item = sections[1].items[0]
    assert req_item.label == "Req Title"
    assert req_item.href == "/req/req-1"


def test_build_orphan_sections_falls_back_to_node_id() -> None:
    """Unknown title → label falls back to the raw node id rather than crashing."""
    orphans = {IntentLevel.GOAL.value: [IntentNode(IntentLevel.GOAL, "goal-9")]}
    sections = views.build_orphan_sections(orphans, {}, {})
    assert sections[0].items[0].label == "goal-9"
    assert sections[0].items[0].href == "/goals"


def test_degraded_banner_when_denominator_incomplete() -> None:
    class _Cov:
        denominator_complete = False
        adapter_degraded = ({"reason": "loomweave catalog stale"},)

    assert views.coverage_banner(_Cov()) is not None

    class _Ok:
        denominator_complete = True
        adapter_degraded = ()

    assert views.coverage_banner(_Ok()) is None
