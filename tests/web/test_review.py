from __future__ import annotations

from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from plainweave.models import TraceLink, TraceRef
from plainweave.web.app import create_app
from plainweave.web.context import RequestContext
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


def test_approve_two_step(client: TestClient) -> None:
    app: Starlette = client.app  # type: ignore[assignment]
    ctx = app.state.ctx_factory()
    req = ctx.service.create_requirement("To approve", "body", actor="human:alice")
    confirm = client.get(f"/req/{req.requirement_id}/approve-confirm")
    assert confirm.status_code == 200
    assert "version 1" in confirm.text.lower() or "approves version 1" in confirm.text.lower()
    # Cookie is set on the first request; subsequent responses won't repeat Set-Cookie.
    # Use client.cookies (the jar) rather than a specific response's cookies.
    client.get("/review")
    token = client.cookies.get("pw_csrf")
    done = client.post(
        f"/req/{req.requirement_id}/approve",
        data={"expected_version": "0", "_csrf": token},
    )
    assert done.status_code == 200
    assert 'hx-swap-oob="innerHTML:#sr-status"' in done.text  # announces outcome
    # the requirement is now approved
    assert ctx.service.get_requirement(req.requirement_id).status == "approved"


def test_approve_conflict_returns_confirm_with_error(client: TestClient) -> None:
    """Stale expected_version → 200 + confirm partial with error banner."""
    app: Starlette = client.app  # type: ignore[assignment]
    ctx = app.state.ctx_factory()
    req = ctx.service.create_requirement("Conflict req", "body", actor="human:alice")
    # Ensure CSRF cookie is set in the jar before posting.
    client.get("/review")
    token = client.cookies.get("pw_csrf")
    # Send wrong expected_version (e.g. 999) → CONFLICT from service
    done = client.post(
        f"/req/{req.requirement_id}/approve",
        data={"expected_version": "999", "_csrf": token},
    )
    assert done.status_code == 200
    # Should re-render confirm partial with error, not OOB result
    assert 'hx-swap-oob="innerHTML:#sr-status"' not in done.text
    assert "queue-item" in done.text  # confirm card was rendered


def test_draft_card_restore(client: TestClient) -> None:
    """GET /req/{id}/draft-card renders the original queue card (Cancel restore)."""
    app: Starlette = client.app  # type: ignore[assignment]
    ctx = app.state.ctx_factory()
    req = ctx.service.create_requirement("Restore me", "body", actor="human:alice")
    resp = client.get(f"/req/{req.requirement_id}/draft-card")
    assert resp.status_code == 200
    assert "Restore me" in resp.text
    assert "queue-item" in resp.text


def _propose(ctx: RequestContext) -> TraceLink:
    return ctx.service.propose_trace_link(
        TraceRef("test_selector", "tests/test_auth.py::test_expired"),
        "provides_evidence_for",
        TraceRef("verification_method", "VERM-0001"),
        actor="agent:claude",
        confidence=0.7,
    )


def test_reject_requires_reason(client: TestClient) -> None:
    app: Starlette = client.app  # type: ignore[assignment]
    ctx: RequestContext = app.state.ctx_factory()
    link = _propose(ctx)
    client.get("/review")
    token = client.cookies.get("pw_csrf")
    # empty reason → 200 with inline error, link NOT rejected
    resp = client.post(f"/trace/{link.id}/reject", data={"reason": "", "_csrf": token})
    assert resp.status_code == 200
    assert "reason is required" in resp.text.lower()
    assert ctx.service.trace_for(state="proposed")  # still proposed


def test_accept_link(client: TestClient) -> None:
    app: Starlette = client.app  # type: ignore[assignment]
    ctx: RequestContext = app.state.ctx_factory()
    link = _propose(ctx)
    client.get("/review")
    token = client.cookies.get("pw_csrf")
    resp = client.post(f"/trace/{link.id}/accept", data={"_csrf": token})
    assert resp.status_code == 200
    assert 'hx-swap-oob="innerHTML:#sr-status"' in resp.text
    assert not ctx.service.trace_for(state="proposed")  # no longer pending


def test_reject_link(client: TestClient) -> None:
    app: Starlette = client.app  # type: ignore[assignment]
    ctx: RequestContext = app.state.ctx_factory()
    link = _propose(ctx)
    client.get("/review")
    token = client.cookies.get("pw_csrf")
    resp = client.post(f"/trace/{link.id}/reject", data={"reason": "stale evidence", "_csrf": token})
    assert resp.status_code == 200
    assert 'hx-swap-oob="innerHTML:#sr-status"' in resp.text
    assert "Rejected" in resp.text
    assert not ctx.service.trace_for(state="proposed")  # actually rejected


def test_link_card_restore(client: TestClient) -> None:
    """GET /trace/{id}/card renders the original queue card (Cancel restore)."""
    app: Starlette = client.app  # type: ignore[assignment]
    ctx: RequestContext = app.state.ctx_factory()
    link = _propose(ctx)
    resp = client.get(f"/trace/{link.id}/card")
    assert resp.status_code == 200
    assert "queue-item" in resp.text
    assert "VERM-0001" in resp.text


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
