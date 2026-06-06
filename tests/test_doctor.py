from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from charter.cli import main


def read_json_output(output: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(output))


def test_doctor_json_reports_uninitialized_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["doctor", "--json"]) == 0

    envelope = read_json_output(capsys.readouterr().out)
    assert envelope["schema"] == "weft.charter.doctor.v1"
    assert envelope["ok"] is True
    assert envelope["data"] == {
        "initialized": False,
        "project_key": None,
        "schema_version": None,
        "db_path": str(tmp_path / ".charter" / "charter.db"),
    }


def test_doctor_json_reports_initialized_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--project-key", "AUTH", "--json"]) == 0
    capsys.readouterr()

    assert main(["doctor", "--json"]) == 0

    envelope = read_json_output(capsys.readouterr().out)
    assert envelope["data"] == {
        "initialized": True,
        "project_key": "AUTH",
        "schema_version": 1,
        "db_path": str(tmp_path / ".charter" / "charter.db"),
    }
