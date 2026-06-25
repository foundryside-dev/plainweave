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


def test_plainweave_error_renders_error_partial(project_root: Path) -> None:
    """A route that raises PlainweaveError(NOT_FOUND) must render the error partial at 404."""

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

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 404
    assert "NOT_FOUND" in resp.text
    assert "thing not found" in resp.text
    assert "check the id" in resp.text


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
    # POST /healthz is not a defined route so it will 405; but the CSRF check
    # must pass first (status != 403 means gate was not tripped).
    resp = client.post(
        "/healthz",
        data={"_csrf": token},
        cookies={"pw_csrf": token},
    )
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
