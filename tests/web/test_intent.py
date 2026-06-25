from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from plainweave.web import views
from plainweave.web.app import create_app


@pytest.fixture
def client(project_root: Path) -> TestClient:
    return TestClient(create_app(actor="human:alice", root=project_root))


def test_intent_dashboard_renders(client: TestClient) -> None:
    resp = client.get("/intent")
    assert resp.status_code == 200
    assert "Coverage" in resp.text


def test_degraded_banner_when_denominator_incomplete() -> None:
    class _Cov:
        denominator_complete = False
        adapter_degraded = ({"reason": "loomweave catalog stale"},)

    assert views.coverage_banner(_Cov()) is not None

    class _Ok:
        denominator_complete = True
        adapter_degraded = ()

    assert views.coverage_banner(_Ok()) is None
