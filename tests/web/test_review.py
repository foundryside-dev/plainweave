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


def test_approve_non_integer_expected_version_returns_400(client: TestClient) -> None:
    """POST /req/{id}/approve with a non-integer expected_version must return 400, not 500."""
    app: Starlette = client.app  # type: ignore[assignment]
    ctx = app.state.ctx_factory()
    req = ctx.service.create_requirement("Bad int req", "body", actor="human:alice")
    client.get("/review")
    token = client.cookies.get("pw_csrf")
    resp = client.post(
        f"/req/{req.requirement_id}/approve",
        data={"expected_version": "not-a-number", "_csrf": token},
    )
    assert resp.status_code == 400, f"expected 400 for non-integer expected_version, got {resp.status_code}"


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
    assert 'hx-swap-oob="innerHTML:#sr-status"' in resp.text  # SR announcement preserved
    assert 'hx-swap-oob="innerHTML:#toast"' in resp.text  # M9: visible toast mirrors it
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


def test_drifted_link_renders_warning_and_requires_extra_confirm(client: TestClient) -> None:
    """GET /trace/{lid}/accept-drifted-confirm returns 200 with all five required confirm elements."""
    app: Starlette = client.app  # type: ignore[assignment]
    ctx: RequestContext = app.state.ctx_factory()
    link = _propose(ctx)
    confirm = client.get(f"/trace/{link.id}/accept-drifted-confirm")
    assert confirm.status_code == 200
    # 1. Real drift warning text — badge and alert paragraph (not just the CSS class)
    assert "CODE DRIFTED" in confirm.text
    assert "the code changed since it was proposed" in confirm.text
    # 2. Hidden acknowledgement field
    assert 'name="drift_acknowledged"' in confirm.text
    # 3. Accept POST target (hx-post ends in /accept)
    assert f'hx-post="/trace/{link.id}/accept"' in confirm.text
    # 4. Cancel / card-restore target
    assert f'hx-get="/trace/{link.id}/card"' in confirm.text
    # 5. CSRF hidden input
    assert 'name="_csrf"' in confirm.text


def test_approve_attributes_operator_as_approver(client: TestClient) -> None:
    """Human authority claim: approving via the UI route records the operator as approver.

    This is the product's core invariant — a human operator's identity must appear
    in the approved version record, not an agent or anonymous actor.
    """
    app: Starlette = client.app  # type: ignore[assignment]
    ctx: RequestContext = app.state.ctx_factory()
    req = ctx.service.create_requirement("Authority req", "body", actor="human:alice")

    # Warm the cookie jar, then get a fresh CSRF token.
    client.get("/review")
    token = client.cookies.get("pw_csrf")

    resp = client.post(
        f"/req/{req.requirement_id}/approve",
        data={"expected_version": "0", "_csrf": token},
    )
    assert resp.status_code == 200

    # The approved version record must attribute the human operator, not an agent.
    version_rec = ctx.service.get_requirement(req.requirement_id).current_version_record
    assert version_rec is not None, "requirement has no approved version record after approve"
    assert version_rec.approved_by == "human:alice", (
        f"approved_by is {version_rec.approved_by!r}, expected 'human:alice' — human authority attribution is broken"
    )


def test_accept_link_attributes_operator(client: TestClient) -> None:
    """Human authority claim: accepting a trace link via the UI records the operator as acceptor."""
    app: Starlette = client.app  # type: ignore[assignment]
    ctx: RequestContext = app.state.ctx_factory()
    link = _propose(ctx)

    client.get("/review")
    token = client.cookies.get("pw_csrf")
    resp = client.post(f"/trace/{link.id}/accept", data={"_csrf": token})
    assert resp.status_code == 200

    # Accepted link must carry the human operator's id.
    accepted_links = ctx.service.trace_for(state="accepted")
    assert accepted_links, "no accepted links found after accept"
    accepted = accepted_links[0]
    assert accepted.accepted_by == "human:alice", (
        f"accepted_by is {accepted.accepted_by!r}, expected 'human:alice' — "
        "human authority attribution is broken for trace-link accept"
    )


def _req_stub() -> object:
    from types import SimpleNamespace

    return SimpleNamespace(state=SimpleNamespace(csrf_token="test-token"))


@pytest.mark.parametrize(
    ("confidence", "band"),
    [(0.3, "low"), (0.5, "med"), (0.79, "med"), (0.8, "high"), (0.95, "high")],
)
def test_conf_chip_band(project_root: Path, confidence: float, band: str) -> None:
    """Fold-in: link confidence renders a .conf chip banded low/med/high alongside the raw value
    so an operator can read calibration risk at a glance."""
    app = create_app(actor="human:alice", root=project_root)
    item = LinkItem(
        kind="link",
        link_id="LINK-1",
        from_label="a",
        relation="rel",
        to_label="b",
        proposing_actor="agent:claude",
        confidence=confidence,
        drifted=False,
    )
    rendered = app.state.templates.get_template("_partials/queue_item_link.html").render(
        {"item": item, "request": _req_stub()}
    )
    assert f"conf {confidence}" in rendered  # raw value preserved
    assert f'class="conf conf--{band}"' in rendered
    assert f">{band}</span>" in rendered


def test_conf_chip_absent_when_no_confidence(project_root: Path) -> None:
    app = create_app(actor="human:alice", root=project_root)
    item = LinkItem(
        kind="link",
        link_id="LINK-2",
        from_label="a",
        relation="rel",
        to_label="b",
        proposing_actor="agent:claude",
        confidence=None,
        drifted=False,
    )
    rendered = app.state.templates.get_template("_partials/queue_item_link.html").render(
        {"item": item, "request": _req_stub()}
    )
    assert 'class="conf' not in rendered


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
