from __future__ import annotations

from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from plainweave.models import TraceRef
from plainweave.web.app import create_app
from plainweave.web.views import LinkItem


@pytest.fixture
def client(project_root: Path) -> TestClient:
    return TestClient(create_app(actor="human:alice", root=project_root))


def test_empty_queue_state(client: TestClient) -> None:
    resp = client.get("/review")
    assert resp.status_code == 200
    assert "All caught up" in resp.text


def test_queue_shows_pending_draft_and_proposed_link(client: TestClient) -> None:
    app: Starlette = client.app  # type: ignore[assignment]
    ctx = app.state.ctx_factory()
    ctx.service.create_requirement("Pending draft", "body", actor="human:alice")
    ctx.service.propose_trace_link(
        TraceRef("test_selector", "tests/test_auth.py::test_expired"),
        "provides_evidence_for",
        TraceRef("verification_method", "VERM-0001"),
        actor="agent:claude",
        confidence=0.8,
    )
    resp = client.get("/review")
    assert resp.status_code == 200
    assert "Pending draft" in resp.text  # the draft card
    assert "DRAFT" in resp.text and "LINK" in resp.text
    assert "agent:claude" in resp.text  # proposing agent shown


def test_drift_card_branch_renders(project_root: Path) -> None:
    """Unit test: LinkItem(drifted=True) renders CODE DRIFTED + aria-describedby.

    The drift branch in queue_item_link.html is unreachable from real proposed-queue
    data (proposed links always have freshness == 'current'). This direct template
    render ensures the branch is exercised without fabricating service state.
    """
    app = create_app(actor="human:alice", root=project_root)
    drifted_item = LinkItem(
        kind="link",
        link_id="LINK-9999",
        from_label="tests/test_auth.py::test_expired",
        relation="provides_evidence_for",
        to_label="VERM-0001",
        proposing_actor="agent:claude",
        confidence=0.9,
        drifted=True,
    )
    templates = app.state.templates
    rendered = templates.get_template("_partials/queue_item_link.html").render({"item": drifted_item})
    assert "CODE DRIFTED" in rendered
    assert "aria-describedby" in rendered
