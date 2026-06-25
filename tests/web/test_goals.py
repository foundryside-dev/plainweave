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
