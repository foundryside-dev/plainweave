from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, cast

import pytest

from plainweave.cli import main


def read_json_output(output: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(output))


def schema_meta(db_path: Path) -> dict[str, str]:
    with closing(sqlite3.connect(db_path)) as connection:
        return dict(connection.execute("select key, value from schema_meta").fetchall())


def test_init_json_creates_project_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["init", "--project-key", "AUTH", "--json"]) == 0

    db_path = tmp_path / ".plainweave" / "plainweave.db"
    assert db_path.is_file()
    envelope = read_json_output(capsys.readouterr().out)
    assert envelope["schema"] == "weft.plainweave.init.v1"
    assert envelope["ok"] is True
    assert envelope["data"] == {
        "created": True,
        "project_key": "AUTH",
        "schema_version": 2,
        "db_path": str(db_path),
    }
    assert schema_meta(db_path) == {"project_key": "AUTH", "schema_version": "2"}


def test_init_json_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["init", "--project-key", "AUTH", "--json"]) == 0
    capsys.readouterr()
    assert main(["init", "--project-key", "AUTH", "--json"]) == 0

    envelope = read_json_output(capsys.readouterr().out)
    data = cast(dict[str, Any], envelope["data"])
    assert data["created"] is False
    assert schema_meta(tmp_path / ".plainweave" / "plainweave.db") == {"project_key": "AUTH", "schema_version": "2"}
