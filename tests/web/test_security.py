from __future__ import annotations

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


def test_missing_extra_prints_hint(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """run_web must print the installation hint and return 1 when starlette is absent."""

    def boom(**_kwargs: object) -> None:
        raise ModuleNotFoundError("starlette")

    monkeypatch.setattr(server, "_serve", boom)
    assert server.run_web(host="127.0.0.1", port=1, actor=None, open_browser=False) == 1
    assert "plainweave[web]" in capsys.readouterr().out
