from __future__ import annotations

from pathlib import Path

import pytest
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.web.app import create_app


@pytest.fixture
def client(project_root: Path) -> TestClient:
    app = create_app(actor="human:alice", root=project_root)
    return TestClient(app, raise_server_exceptions=False)


def test_app_boots_and_sets_csrf_cookie(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert "pw_csrf" in resp.cookies


def test_unknown_path_404(client: TestClient) -> None:
    assert client.get("/no-such-page").status_code == 404


def _boom_app(project_root: Path) -> TestClient:
    async def boom(request: Request) -> Response:
        raise PlainweaveError(
            ErrorCode.NOT_FOUND,
            "thing not found",
            recoverable=False,
            hint="check the id",
        )

    app = create_app(actor="human:alice", root=project_root)
    # Splice in a test-only route at the front of the router.
    app.routes.insert(0, Route("/boom", boom))
    return TestClient(app, raise_server_exceptions=False)


def test_plainweave_error_renders_full_page_on_navigation(project_root: Path) -> None:
    """A normal navigation that raises PlainweaveError must render a full, navigable page:
    base chrome (nav + stylesheet + <html lang>) PLUS the error detail (M2)."""
    resp = _boom_app(project_root).get("/boom")
    assert resp.status_code == 404
    # Error detail
    assert "NOT_FOUND" in resp.text
    assert "thing not found" in resp.text
    assert "check the id" in resp.text
    # Full-page chrome
    assert "<html lang=" in resp.text
    assert '<link rel="stylesheet" href="/static/app.css">' in resp.text
    assert 'class="topnav"' in resp.text
    assert 'class="skip-link"' in resp.text
    # Global pending badge mechanism reaches the error page too (M6)
    assert 'id="review-badge"' in resp.text


def test_plainweave_error_renders_bare_fragment_on_hx(project_root: Path) -> None:
    """An HTMX swap that raises PlainweaveError must render a bare fragment — no base chrome (M2)."""
    resp = _boom_app(project_root).get("/boom", headers={"HX-Request": "true"})
    assert resp.status_code == 404
    assert "thing not found" in resp.text
    # No full-page chrome in the fragment
    assert "<html" not in resp.text
    assert 'class="topnav"' not in resp.text


def test_error_page_survives_context_construction_failure(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If the error itself was raised while building the per-request context (e.g. a
    launch-time POLICY_REQUIRED operator / DB-open failure), the full-page error must
    still render with chrome — the global context processor must not raise a second
    time and collapse the actionable page into an opaque 500."""

    def explode(_request: Request) -> object:
        raise PlainweaveError(
            ErrorCode.POLICY_REQUIRED, "operator cannot self-register", recoverable=False, hint="register first"
        )

    # Both the route and the context processor resolve ctx via request_ctx; make it fail.
    monkeypatch.setattr("plainweave.web.app.request_ctx", explode)
    monkeypatch.setattr("plainweave.web.routes.requirements.request_ctx", explode, raising=False)

    resp = _boom_app(project_root).get("/boom")
    assert resp.status_code == 404
    # Helpful detail preserved (not an opaque 500)
    assert "thing not found" in resp.text
    # Chrome still renders despite the degraded context...
    assert 'class="topnav"' in resp.text
    assert 'id="review-badge"' in resp.text
    # ...and the operator span is gracefully omitted rather than raising UndefinedError.
    assert "operator:" not in resp.text


def test_csrf_blocks_mutation_without_token(project_root: Path) -> None:
    """POST without a valid CSRF token returns 403."""
    app = create_app(actor="human:alice", root=project_root)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/healthz", data={"field": "value"})
    assert resp.status_code == 403


def test_csrf_passes_mutation_with_valid_token(project_root: Path) -> None:
    """POST with a matching CSRF cookie+form token passes the CSRF gate."""
    from plainweave.web.context import new_csrf_token

    app = create_app(actor="human:alice", root=project_root)
    client = TestClient(app, raise_server_exceptions=False)
    token = new_csrf_token()
    # Set the cookie on the client instance (not per-request) to avoid the
    # Starlette per-request cookies deprecation warning.
    client.cookies.set("pw_csrf", token)
    # POST /healthz is not a defined route so it will 405; but the CSRF check
    # must pass first (status != 403 means gate was not tripped).
    resp = client.post("/healthz", data={"_csrf": token})
    assert resp.status_code != 403


def test_csrf_middleware_does_not_consume_form_body(project_root: Path) -> None:
    """CSRF middleware must not consume the request body.

    Downstream POST handlers that call request.form() must receive the submitted
    form fields, not an empty form. This locks the fix for the body-stream bug
    where ``await request.form()`` in BaseHTTPMiddleware consumed the body before
    the downstream handler could read it.
    """
    from plainweave.web.context import new_csrf_token

    async def echo_field(request: Request) -> Response:
        form = await request.form()
        value = form.get("field") or ""
        return PlainTextResponse(str(value))

    app = create_app(actor="human:alice", root=project_root)
    app.routes.insert(0, Route("/echo", echo_field, methods=["POST"]))

    token = new_csrf_token()
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("pw_csrf", token)
    resp = client.post("/echo", data={"_csrf": token, "field": "hello"})
    # CSRF must pass (not 403) AND downstream form data must be intact (not empty).
    assert resp.status_code == 200
    assert resp.text == "hello"
