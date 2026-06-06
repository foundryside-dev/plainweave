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


def approve_requirement(capsys: pytest.CaptureFixture[str], title: str, statement: str, key: str) -> None:
    run_json(
        [
            "req",
            "add",
            "--title",
            title,
            "--statement",
            statement,
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
            key,
        ],
        capsys,
    )


def test_baseline_cli_create_show_list_and_diff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    approve_requirement(
        capsys,
        "Reject expired bearer tokens",
        "The API shall reject expired bearer tokens.",
        "approve-1",
    )

    created = run_json(
        [
            "baseline",
            "create",
            "--name",
            "Release 1.0 requirements",
            "--description",
            "Approved requirements for release 1.0.",
            "--actor",
            "human:john",
        ],
        capsys,
    )

    assert created["schema"] == "weft.charter.baseline.v1"
    assert created["data"]["id"] == "BASELINE-0001"
    assert created["data"]["locked"] is True
    assert [member["id"] for member in created["data"]["members"]] == ["REQ-AUTH-0001"]

    shown = run_json(["baseline", "show", "BASELINE-0001"], capsys)
    assert shown["data"] == created["data"]

    listed = run_json(["baseline", "list"], capsys)
    assert listed["schema"] == "weft.charter.baseline_list.v1"
    assert listed["data"]["items"] == [created["data"]]

    run_json(
        [
            "req",
            "supersede",
            "REQ-AUTH-0001",
            "--title",
            "Reject invalid bearer tokens",
            "--statement",
            "The API shall reject expired or malformed bearer tokens.",
            "--actor",
            "human:john",
            "--expected-version",
            "1",
            "--idempotency-key",
            "supersede-1",
        ],
        capsys,
    )
    run_json(
        [
            "req",
            "add",
            "--title",
            "Log token failures",
            "--statement",
            "The API shall log token failures.",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    run_json(
        [
            "req",
            "approve",
            "REQ-AUTH-0002",
            "--actor",
            "human:john",
            "--expected-version",
            "0",
            "--idempotency-key",
            "approve-2",
        ],
        capsys,
    )

    diff = run_json(["baseline", "diff", "BASELINE-0001"], capsys)
    assert diff["schema"] == "weft.charter.baseline_diff.v1"
    assert diff["data"]["summary"] == {
        "unchanged": 0,
        "changed": 0,
        "missing_current": 0,
        "new_since_baseline": 1,
        "superseded_since_baseline": 1,
    }
    assert [item["status"] for item in diff["data"]["items"]] == [
        "superseded_since_baseline",
        "new_since_baseline",
    ]


def test_baseline_cli_requires_actor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)

    error = run_json(
        ["baseline", "create", "--name", "Release 1.0 requirements"],
        capsys,
        expected_status=2,
    )

    assert error["schema"] == "weft.charter.error.v1"
    assert error["error"]["code"] == "VALIDATION"


def test_baseline_cli_missing_baseline_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)

    error = run_json(["baseline", "show", "BASELINE-9999"], capsys, expected_status=2)

    assert error["schema"] == "weft.charter.error.v1"
    assert error["error"]["code"] == "NOT_FOUND"
