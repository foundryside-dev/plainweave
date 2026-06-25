from __future__ import annotations

import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from plainweave.web import server
from plainweave.web.app import create_app


def test_forged_post_without_csrf_rejected(project_root: Path) -> None:
    """A POST with a bogus CSRF token (no matching cookie) must return 403."""
    fresh = TestClient(create_app(actor="human:alice", root=project_root))
    resp = fresh.post("/req/new", data={"title": "x", "statement": "y", "_csrf": "bogus"})
    assert resp.status_code == 403


def test_csrf_cold_start_first_render_embeds_real_token(project_root: Path) -> None:
    """COLD-FLOW: the very first GET (no prior cookie) must embed a non-empty _csrf token.

    Before the fix, csrf.html read request.cookies.get('pw_csrf', ''), which was
    empty on the first request because the cookie is set on the *response*, not
    available in the request yet.  After the fix, the middleware mints a token
    and stores it in request.state.csrf_token BEFORE calling the handler, so the
    template can embed it and the immediately-following POST succeeds.
    """
    # Fresh client — no cookies at all in the jar yet.
    client = TestClient(create_app(actor="human:alice", root=project_root))

    # First ever GET: cookie is NOT pre-seeded; the form must still embed a real token.
    get_resp = client.get("/req/new")
    assert get_resp.status_code == 200

    # Parse the hidden _csrf value from the rendered HTML.
    match = re.search(r'<input[^>]+name="_csrf"[^>]+value="([^"]*)"', get_resp.text)
    assert match is not None, "_csrf hidden input not found in rendered form"
    embedded_token = match.group(1)
    assert embedded_token != "", "CSRF token is EMPTY on cold render — the cold-start bug is present"

    # The GET response sets the cookie; the TestClient jar now holds it.
    # A POST with the embedded token must NOT be rejected with 403.
    post_resp = client.post(
        "/req/new",
        data={"title": "Cold start req", "statement": "body text", "_csrf": embedded_token},
    )
    assert post_resp.status_code != 403, (
        f"POST after cold-start GET returned {post_resp.status_code} (CSRF rejected); the cold-start fix is not working"
    )


def test_wrong_csrf_token_still_403(project_root: Path) -> None:
    """After a cold GET (cookie now set), a POST with a WRONG token must still 403."""
    client = TestClient(create_app(actor="human:alice", root=project_root))
    # Warm the cookie jar.
    client.get("/req/new")
    # POST with a deliberately wrong token.
    resp = client.post(
        "/req/new",
        data={"title": "Smuggled", "statement": "should be blocked", "_csrf": "wrong-token"},
    )
    assert resp.status_code == 403


def test_missing_extra_prints_hint(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """run_web must print the installation hint and return 1 when starlette is absent."""

    def boom(**_kwargs: object) -> None:
        raise ModuleNotFoundError("starlette")

    monkeypatch.setattr(server, "_serve", boom)
    assert server.run_web(host="127.0.0.1", port=1, actor=None, open_browser=False) == 1
    assert "plainweave[web]" in capsys.readouterr().out
