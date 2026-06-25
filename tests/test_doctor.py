from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from plainweave.cli import main


def read_json_output(output: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(output))


def _check(data: dict[str, Any], check_id: str) -> dict[str, Any]:
    return next(c for c in data["checks"] if c["id"] == check_id)


def test_doctor_reports_uninitialized_store_as_a_problem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    # An uninitialized store is a fixable problem -> non-zero exit (federation standard).
    assert main(["doctor", "--json"]) == 1

    envelope = read_json_output(capsys.readouterr().out)
    assert envelope["schema"] == "weft.plainweave.doctor.v2"
    assert envelope["ok"] is True  # the doctor command itself ran fine
    data = envelope["data"]
    assert data["ok"] is False
    assert data["initialized"] is False
    store = _check(data, "store")
    assert store["status"] == "error"
    assert store["fixable"] is True
    assert "doctor --fix" in store["next_action"]


def test_doctor_initialized_store_passes_catalog_warns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--project-key", "AUTH", "--json"]) == 0
    capsys.readouterr()

    # Store is healthy; there is no Loomweave catalog in a bare dir -> warn (advisory),
    # so overall is still ok (exit 0).
    assert main(["doctor", "--json"]) == 0

    envelope = read_json_output(capsys.readouterr().out)
    assert envelope["schema"] == "weft.plainweave.doctor.v2"
    data = envelope["data"]
    assert data["ok"] is True
    assert data["initialized"] is True and data["project_key"] == "AUTH"
    assert _check(data, "store")["status"] == "ok"
    catalog = _check(data, "loomweave_catalog")
    assert catalog["status"] == "warn"
    assert "loomweave analyze" in catalog["next_action"]
    assert _check(data, "mcp_surface")["status"] == "ok"


def test_doctor_fix_initializes_the_store_idempotently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["doctor", "--fix", "--json"]) == 0  # --fix repairs the store -> no error
    data = read_json_output(capsys.readouterr().out)["data"]
    assert data["fix_applied"] is True
    assert data["initialized"] is True
    store = _check(data, "store")
    assert store["status"] == "ok" and store["fixed"] is True
    assert (tmp_path / ".plainweave" / "plainweave.db").exists()

    # Idempotent: a second --fix is a no-op repair and still passes.
    capsys.readouterr()
    assert main(["doctor", "--fix", "--json"]) == 0


def test_doctor_root_inspects_and_fixes_an_external_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.chdir(tmp_path)  # cwd is NOT the project root

    assert main(["doctor", "--root", str(proj), "--fix", "--json"]) == 0
    data = read_json_output(capsys.readouterr().out)["data"]
    assert data["root"] == str(proj.resolve())
    assert (proj / ".plainweave" / "plainweave.db").exists()
    # cwd remained untouched.
    assert not (tmp_path / ".plainweave").exists()
