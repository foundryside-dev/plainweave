from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from charter.cli import main


def json_output(output: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(output))


def run_json(args: list[str], capsys: pytest.CaptureFixture[str], expected_status: int = 0) -> dict[str, Any]:
    assert main([*args, "--json"]) == expected_status
    return json_output(capsys.readouterr().out)


def init_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--project-key", "AUTH", "--json"]) == 0
    capsys.readouterr()


def approve_requirement_with_criterion(capsys: pytest.CaptureFixture[str]) -> None:
    run_json(
        [
            "req",
            "add",
            "--title",
            "Reject expired bearer tokens",
            "--statement",
            "The API shall reject expired bearer tokens.",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    run_json(
        [
            "criterion",
            "add",
            "REQ-AUTH-0001",
            "--text",
            "Expired tokens return 401.",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    run_json(
        [
            "req",
            "approve",
            "REQ-AUTH-0001",
            "--actor",
            "human:john",
            "--expected-version",
            "0",
            "--idempotency-key",
            "approve-1",
        ],
        capsys,
    )


def test_dossier_cli_json_includes_sections_and_peer_facts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    approve_requirement_with_criterion(capsys)

    dossier = run_json(["dossier", "REQ-AUTH-0001"], capsys)

    assert dossier["schema"] == "weft.charter.requirement_dossier.v1"
    assert dossier["ok"] is True
    data = dossier["data"]
    assert set(data) == {
        "identity",
        "authority_summary",
        "requirement",
        "acceptance_criteria",
        "traces",
        "verification",
        "baseline_exposure",
        "computed_gaps",
        "peer_facts",
        "next_actions",
    }
    assert set(data["identity"]) == {"requirement_id", "id", "stable_id", "current_version"}
    assert data["identity"]["id"] == "REQ-AUTH-0001"
    assert data["identity"]["current_version"] == 1
    assert data["authority_summary"]["status"] == "approved"
    assert set(data["verification"]) == {"status", "reasons", "current_evidence", "stale_evidence"}
    assert [item["text"] for item in data["acceptance_criteria"]["current_version"]] == ["Expired tokens return 401."]
    assert set(data["peer_facts"]) == {"live_peer_calls", "sources", "notes"}
    assert data["peer_facts"]["live_peer_calls"] is False
    assert all(set(item) == {"action", "priority", "reason", "command", "blocked_by"} for item in data["next_actions"])


def test_dossier_cli_human_output_is_compact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    approve_requirement_with_criterion(capsys)

    assert main(["dossier", "REQ-AUTH-0001"]) == 0
    output = capsys.readouterr().out

    assert "REQ-AUTH-0001 v1 approved" in output
    assert "Verification: unverified" in output
    assert "Gaps:" in output
    assert "Next actions:" in output


def test_dossier_cli_missing_requirement_json_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)

    error = run_json(["dossier", "REQ-AUTH-9999"], capsys, expected_status=2)

    assert error["schema"] == "weft.charter.error.v1"
    assert error["error"]["code"] == "NOT_FOUND"
