from __future__ import annotations

from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from plainweave.web.app import create_app
from plainweave.web.context import RequestContext


@pytest.fixture
def client(project_root: Path) -> TestClient:
    return TestClient(create_app(actor="human:alice", root=project_root))


def test_base_has_live_region_and_skip_link(client: TestClient) -> None:
    """§4.1 / §12: base.html must carry the SR status live region and skip-link."""
    html = client.get("/").text
    assert 'id="sr-status"' in html
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    assert 'class="skip-link"' in html


def test_search_has_visible_label(client: TestClient) -> None:
    """§4.1: corpus filter must have a visible <label> associated with the search input."""
    html = client.get("/").text
    assert '<label for="req-search"' in html


def test_review_buttons_have_unique_aria_labels(client: TestClient) -> None:
    """§4.1 / §12: each Approve button must carry a per-item aria-label with the title
    interpolated so screen readers announce unambiguous, distinct action names."""
    app: Starlette = client.app  # type: ignore[assignment]
    ctx: RequestContext = app.state.ctx_factory()
    ctx.service.create_requirement("Aria draft one", "body one", actor="human:alice")
    ctx.service.create_requirement("Aria draft two", "body two", actor="human:alice")
    html = client.get("/review").text
    assert "Approve draft: Aria draft one" in html
    assert "Approve draft: Aria draft two" in html
