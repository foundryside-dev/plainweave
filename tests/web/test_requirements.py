from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from plainweave.intent_graph import CorpusEntry, IntentLevel, IntentNode
from plainweave.models import RequirementRecord, RequirementVersion
from plainweave.web import views
from plainweave.web.app import create_app
from plainweave.web.views import CorpusRow


@pytest.fixture
def client(project_root: Path) -> TestClient:
    return TestClient(create_app(actor="human:alice", root=project_root))


def _mint(client: TestClient, title: str, statement: str) -> Any:
    # Author a draft requirement through the (later) new-req route; for this test
    # seed via the service directly to keep the test focused on rendering.
    app: Starlette = client.app  # type: ignore[assignment]
    ctx = app.state.ctx_factory()
    return ctx.service.create_requirement(title, statement, actor="human:alice")


def test_corpus_lists_requirements(client: TestClient) -> None:
    _mint(client, "Coverage is self-computable", "answers why this exists")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Coverage is self-computable" in resp.text


def test_corpus_orphan_filter_no_goal(client: TestClient) -> None:
    _mint(client, "Orphan req", "no goal yet")
    resp = client.get("/", params={"orphan": "no-goal"})
    assert "Orphan req" in resp.text
    # status filter excludes it
    resp2 = client.get("/", params={"status": "approved"})
    assert "Orphan req" not in resp2.text


def test_corpus_status_filter(client: TestClient) -> None:
    _mint(client, "Draft only req", "a draft")
    resp = client.get("/", params={"status": "draft"})
    assert resp.status_code == 200
    assert "Draft only req" in resp.text


def test_corpus_search_query(client: TestClient) -> None:
    _mint(client, "Unique title XYZ", "some statement")
    _mint(client, "Another req", "different")
    resp = client.get("/", params={"q": "XYZ"})
    assert "Unique title XYZ" in resp.text
    assert "Another req" not in resp.text


def test_corpus_htmx_partial(client: TestClient) -> None:
    _mint(client, "HTMX req", "for htmx test")
    resp = client.get("/", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    # Should not include the full page chrome
    assert "<html" not in resp.text


def test_corpus_approved_req_shows_version_title(client: TestClient) -> None:
    """Approved requirements must show the approved version title, not the display-id."""
    app: Starlette = client.app  # type: ignore[assignment]
    ctx = app.state.ctx_factory()
    draft = ctx.service.create_requirement("Approved title", "statement", actor="human:alice")
    ctx.service.approve_requirement(
        draft.requirement_id,
        actor="human:alice",
        expected_version=0,
    )
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Approved title" in resp.text


# --- Unit tests for filter_rows ---


def _row(
    title: str = "Test",
    display_id: str = "REQ-001",
    status: str = "draft",
    goal_count: int = 0,
    code_count: int = 0,
) -> CorpusRow:
    return CorpusRow(
        req_id="req-1",
        display_id=display_id,
        title=title,
        status=status,
        goal_count=goal_count,
        code_count=code_count,
    )


def test_filter_rows_empty_filters() -> None:
    rows = [_row("A"), _row("B")]
    assert views.filter_rows(rows, q="", status="", orphan="") == rows


def test_filter_rows_q_by_title() -> None:
    rows = [_row("Coverage metric"), _row("Other req")]
    result = views.filter_rows(rows, q="coverage", status="", orphan="")
    assert len(result) == 1
    assert result[0].title == "Coverage metric"


def test_filter_rows_q_by_display_id() -> None:
    rows = [
        CorpusRow("req-1", "REQ-PROJ-0001", "Some title", "draft", 0, 0),
        CorpusRow("req-2", "REQ-PROJ-0002", "Another", "draft", 0, 0),
    ]
    result = views.filter_rows(rows, q="0001", status="", orphan="")
    assert len(result) == 1
    assert result[0].display_id == "REQ-PROJ-0001"


def test_filter_rows_status() -> None:
    rows = [_row(status="draft"), _row(status="approved")]
    result = views.filter_rows(rows, q="", status="approved", orphan="")
    assert len(result) == 1
    assert result[0].status == "approved"


def test_filter_rows_orphan_no_goal() -> None:
    rows = [_row(goal_count=0, code_count=1), _row(goal_count=2, code_count=0)]
    result = views.filter_rows(rows, q="", status="", orphan="no-goal")
    assert len(result) == 1
    assert result[0].goal_count == 0


def test_filter_rows_orphan_no_code() -> None:
    rows = [_row(goal_count=1, code_count=0), _row(goal_count=0, code_count=2)]
    result = views.filter_rows(rows, q="", status="", orphan="no-code")
    assert len(result) == 1
    assert result[0].code_count == 0


def test_filter_rows_orphan_both() -> None:
    rows = [
        _row(goal_count=0, code_count=0),
        _row(goal_count=1, code_count=0),
        _row(goal_count=0, code_count=1),
    ]
    result = views.filter_rows(rows, q="", status="", orphan="both")
    assert len(result) == 1
    assert result[0].goal_count == 0
    assert result[0].code_count == 0


def test_filter_rows_combined() -> None:
    rows = [
        _row(title="Target", status="draft", goal_count=0),
        _row(title="Target", status="approved", goal_count=0),
        _row(title="Other", status="draft", goal_count=0),
    ]
    result = views.filter_rows(rows, q="target", status="draft", orphan="no-goal")
    assert len(result) == 1
    assert result[0].title == "Target"
    assert result[0].status == "draft"


def test_inline_expand_independent_targets(client: TestClient) -> None:
    a = _mint(client, "Alpha req", "alpha statement body")
    b = _mint(client, "Beta req", "beta statement body")
    ra = client.get(f"/req/{a.requirement_id}/inline")
    assert ra.status_code == 200
    assert "alpha statement body" in ra.text
    assert f'id="req-detail-{a.requirement_id}"' not in ra.text  # partial targets the existing row div, not nested
    rb = client.get(f"/req/{b.requirement_id}/inline")
    assert "beta statement body" in rb.text
    # collapse returns empty
    rc = client.get(f"/req/{a.requirement_id}/inline/collapsed")
    assert rc.status_code == 200
    assert rc.text.strip() == ""


# --- Unit tests for build_corpus_rows ---


def test_build_corpus_rows_draft_uses_provided_title() -> None:
    """Draft-only requirement uses the title from the resolved titles dict."""
    entry = CorpusEntry(
        requirement=IntentNode(IntentLevel.REQUIREMENT, "req-1"),
        goals=(),
        code=(),
    )
    record = RequirementRecord(
        requirement_id="req-1",
        id="REQ-TEST-0001",
        stable_id="plainweave:req:test:0001",
        current_version=0,
        active_draft_id="DRAFT-0001",
        status="draft",
        current_version_record=None,
    )
    titles = {"req-1": "My Draft Title"}
    rows = views.build_corpus_rows([entry], [record], titles)
    assert len(rows) == 1
    assert rows[0].title == "My Draft Title"
    assert rows[0].goal_count == 0
    assert rows[0].code_count == 0


def test_build_corpus_rows_approved_uses_version_title() -> None:
    """Approved requirement uses the title from the titles dict (resolved from version)."""
    version = RequirementVersion(
        requirement_id="req-2",
        id="REQ-TEST-0002",
        stable_id="plainweave:req:test:0002",
        version=1,
        title="Approved Title",
        statement="approved statement",
        statement_hash="abc",
        status="approved",
        approved_by="human:alice",
        approved_at="2026-01-01T00:00:00",
    )
    entry = CorpusEntry(
        requirement=IntentNode(IntentLevel.REQUIREMENT, "req-2"),
        goals=(IntentNode(IntentLevel.GOAL, "goal-1"),),
        code=(IntentNode(IntentLevel.CODE, "code-1"), IntentNode(IntentLevel.CODE, "code-2")),
    )
    record = RequirementRecord(
        requirement_id="req-2",
        id="REQ-TEST-0002",
        stable_id="plainweave:req:test:0002",
        current_version=1,
        active_draft_id=None,
        status="approved",
        current_version_record=version,
    )
    titles = {"req-2": "Approved Title"}
    rows = views.build_corpus_rows([entry], [record], titles)
    assert len(rows) == 1
    assert rows[0].title == "Approved Title"
    assert rows[0].goal_count == 1
    assert rows[0].code_count == 2


def test_requirement_detail_renders_statement(client: TestClient) -> None:
    r = _mint(client, "Detail req", "the full detail statement")
    resp = client.get(f"/req/{r.requirement_id}")
    assert resp.status_code == 200
    assert "Detail req" in resp.text
    assert "the full detail statement" in resp.text


def test_requirement_detail_approved_version_block(client: TestClient) -> None:
    """Approved requirement: current-version block present, draft block absent."""
    app: Starlette = client.app  # type: ignore[assignment]
    ctx = app.state.ctx_factory()
    draft = ctx.service.create_requirement(
        "Approved version title",
        "approved version statement",
        actor="human:alice",
    )
    req_id = draft.requirement_id
    ctx.service.approve_requirement(req_id, actor="human:alice", expected_version=0)
    resp = client.get(f"/req/{req_id}")
    assert resp.status_code == 200
    # Approved block heading present (template: "Current approved — v1")
    assert "Current approved" in resp.text
    # Approved statement carried through
    assert "approved version statement" in resp.text
    # Draft block absent (class="draft" is the discriminator for that section)
    # Note: the both-blocks case (approved + active draft simultaneously) is not
    # reachable via the public PlainweaveService API.  approve_requirement sets
    # active_draft_id=null, and supersede_requirement likewise creates a new
    # approved version directly without a draft step — there is no verb that opens
    # a fresh draft on a requirement that already has a current_version.
    assert 'class="draft"' not in resp.text


# --- New/Edit requirement routes ---


def test_new_req_form_renders(client: TestClient) -> None:
    """GET /req/new must return 200 with the form — not 404 from req_detail collision."""
    resp = client.get("/req/new")
    assert resp.status_code == 200
    assert 'name="title"' in resp.text
    assert "New requirement" in resp.text


def test_create_requirement(client: TestClient) -> None:
    token = client.get("/").cookies.get("pw_csrf")  # ensure cookie set
    resp = client.post("/req/new", data={"title": "Newborn", "statement": "fresh shell", "_csrf": token})
    assert resp.status_code in (200, 303)
    assert "Newborn" in client.get("/").text


def test_edit_form_renders(client: TestClient) -> None:
    """GET /req/{req_id}/edit must render the form pre-populated with the current draft."""
    r = _mint(client, "Editable Req", "initial body")
    # Warm the cookie jar (cookie is already persisted on the client after _mint's GET).
    client.get("/")
    resp = client.get(f"/req/{r.requirement_id}/edit")
    assert resp.status_code == 200
    assert "Editable Req" in resp.text
    assert "initial body" in resp.text
    assert "Edit draft" in resp.text


def test_edit_success_redirects(client: TestClient) -> None:
    """POST /req/{req_id}/edit with correct revision redirects and update is persisted."""
    r = _mint(client, "Success Req", "original body")
    token = client.get("/").cookies.get("pw_csrf")
    resp = client.post(
        f"/req/{r.requirement_id}/edit",
        data={
            "title": "Success Req",
            "statement": "updated body",
            "expected_draft_revision": "1",
            "_csrf": token,
        },
    )
    assert resp.status_code in (200, 303)
    # Verify the update was persisted (TestClient follows redirects by default)
    assert "updated body" in resp.text


def test_edit_conflict_preserves_text(client: TestClient) -> None:
    r = _mint(client, "Editable", "v1 body")
    token = client.get("/").cookies.get("pw_csrf")
    # submit a stale revision (0 when the real draft_revision is 1)
    resp = client.post(
        f"/req/{r.requirement_id}/edit",
        data={"title": "Editable", "statement": "MY UNSAVED EDIT", "expected_draft_revision": "0", "_csrf": token},
    )
    assert resp.status_code == 200  # NOT 409 — HTMX must be able to swap
    assert "MY UNSAVED EDIT" in resp.text  # operator's text echoed back
    assert "v1 body" in resp.text  # current draft shown alongside
