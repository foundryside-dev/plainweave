from __future__ import annotations

import argparse

import pytest

from plainweave.web import server


def test_web_subcommand_parses_defaults() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    server.add_web_subcommand(sub)
    args = parser.parse_args(["web"])
    assert args.command == "web"
    assert args.host == "127.0.0.1"
    assert args.port == 8765
    assert args.open_browser is True
    assert callable(args.handler)


def test_run_web_without_starlette_prints_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Simulate the optional extra being absent.
    def boom(**_kwargs: object) -> None:
        raise ModuleNotFoundError("No module named 'starlette'")

    monkeypatch.setattr(server, "_serve", boom)
    rc = server.run_web(host="127.0.0.1", port=8765, actor=None, open_browser=False)
    out = capsys.readouterr().out
    assert rc == 1
    assert "pip install plainweave[web]" in out
