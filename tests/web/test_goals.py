from __future__ import annotations

from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from plainweave.web.app import create_app


@pytest.fixture
def client(project_root: Path) -> TestClient:
    return TestClient(create_app(actor="human:alice", root=project_root))


def test_goals_page_lists_created_goal(client: TestClient) -> None:
    app: Starlette = client.app  # type: ignore[assignment]
    ctx = app.state.ctx_factory()
    ctx.service.create_goal("Be self-computable", "the north-star goal", actor="human:alice")
    resp = client.get("/goals")
    assert resp.status_code == 200
    assert "Be self-computable" in resp.text


def test_create_goal_and_ladder(client: TestClient) -> None:
    token = client.get("/goals").cookies.get("pw_csrf")
    client.post("/goals/new", data={"title": "Ladder target", "statement": "g", "_csrf": token})
    app: Starlette = client.app  # type: ignore[assignment]
    ctx = app.state.ctx_factory()
    req = ctx.service.create_requirement("Ladders up", "body", actor="human:alice")
    goals = ctx.service.list_goals()
    gid = goals[0].goal_id
    resp = client.post(f"/req/{req.requirement_id}/ladder", data={"goal_id": gid, "_csrf": token})
    assert resp.status_code in (200, 303)
    # the requirement now ladders to a goal → no longer a requirement-orphan
    from plainweave.intent_graph import IntentLevel

    orphan_ids = {n.node_id for n in ctx.service.intent_orphans(IntentLevel.REQUIREMENT)}
    assert req.requirement_id not in orphan_ids
