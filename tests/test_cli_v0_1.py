from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from plainweave.cli import main


def json_output(output: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(output))


def run_json(args: list[str], capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    assert main([*args, "--json"]) == 0
    return json_output(capsys.readouterr().out)


def init_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--project-key", "AUTH", "--json"]) == 0
    capsys.readouterr()


def test_requirement_cli_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)

    added = run_json(
        [
            "req",
            "add",
            "--title",
            "Reject expired tokens",
            "--statement",
            "Expired tokens return 401.",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    assert added["schema"] == "weft.plainweave.requirement_draft.v1"
    assert added["data"]["id"] == "REQ-AUTH-0001"

    edited = run_json(
        ["req", "edit", "REQ-AUTH-0001", "--statement", "Expired bearer tokens return 401.", "--actor", "human:john"],
        capsys,
    )
    assert edited["data"]["draft_revision"] == 2

    approved = run_json(
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
    assert approved["schema"] == "weft.plainweave.requirement_version.v1"
    assert approved["data"]["version"] == 1

    shown = run_json(["req", "show", "REQ-AUTH-0001"], capsys)
    assert shown["schema"] == "weft.plainweave.requirement.v1"
    assert shown["data"]["current_version"] == 1

    searched = run_json(["req", "search", "bearer"], capsys)
    assert searched["schema"] == "weft.plainweave.requirement_list.v1"
    assert [item["id"] for item in searched["data"]["items"]] == ["REQ-AUTH-0001"]


def test_requirement_supersede_and_deprecate_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    run_json(
        [
            "req",
            "add",
            "--title",
            "Reject expired tokens",
            "--statement",
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
            "a",
        ],
        capsys,
    )

    superseded = run_json(
        [
            "req",
            "supersede",
            "REQ-AUTH-0001",
            "--title",
            "Reject invalid tokens",
            "--statement",
            "Expired or malformed tokens return 401.",
            "--actor",
            "human:john",
            "--expected-version",
            "1",
            "--idempotency-key",
            "s",
        ],
        capsys,
    )
    assert superseded["data"]["version"] == 2

    deprecated = run_json(
        [
            "req",
            "deprecate",
            "REQ-AUTH-0001",
            "--actor",
            "human:john",
            "--expected-version",
            "2",
            "--idempotency-key",
            "d",
        ],
        capsys,
    )
    assert deprecated["data"]["status"] == "deprecated"


def test_requirement_reject_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    run_json(
        [
            "req",
            "add",
            "--title",
            "Draft only",
            "--statement",
            "This draft will be rejected.",
            "--actor",
            "human:john",
        ],
        capsys,
    )

    rejected = run_json(
        [
            "req",
            "reject",
            "REQ-AUTH-0001",
            "--actor",
            "human:john",
            "--expected-version",
            "0",
            "--reason",
            "out of scope",
        ],
        capsys,
    )

    assert rejected["schema"] == "weft.plainweave.requirement.v1"
    assert rejected["data"]["status"] == "rejected"


def test_criteria_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    run_json(
        [
            "req",
            "add",
            "--title",
            "Reject expired tokens",
            "--statement",
            "Expired tokens return 401.",
            "--actor",
            "human:john",
        ],
        capsys,
    )

    added = run_json(
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
    assert added["schema"] == "weft.plainweave.acceptance_criterion.v1"
    assert added["data"]["id"] == "AC-0001"
    assert added["data"]["created_at"]

    listed = run_json(["criterion", "list", "REQ-AUTH-0001"], capsys)
    assert listed["schema"] == "weft.plainweave.acceptance_criterion_list.v1"
    assert [item["id"] for item in listed["data"]["items"]] == ["AC-0001"]


def test_trace_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    init_project(tmp_path, monkeypatch, capsys)

    proposed = run_json(
        [
            "trace",
            "propose",
            "--from-kind",
            "test_selector",
            "--from-id",
            "tests/test_auth.py::test_expired",
            "--relation",
            "provides_evidence_for",
            "--to-kind",
            "verification_method",
            "--to-id",
            "VERM-0001",
            "--actor",
            "agent:codex",
            "--confidence",
            "0.82",
        ],
        capsys,
    )
    assert proposed["schema"] == "weft.plainweave.trace_link.v1"
    assert proposed["data"]["state"] == "proposed"

    accepted = run_json(["trace", "accept", "LINK-0001", "--actor", "human:john"], capsys)
    assert accepted["data"]["state"] == "accepted"

    listed = run_json(["trace", "list", "--state", "accepted"], capsys)
    assert [item["id"] for item in listed["data"]["items"]] == ["LINK-0001"]

    rejected_source = run_json(
        [
            "trace",
            "propose",
            "--from-kind",
            "file_ref",
            "--from-id",
            "src/auth.py",
            "--relation",
            "fragile_satisfies",
            "--to-kind",
            "requirement_version",
            "--to-id",
            "REQ-AUTH-0001@1",
            "--actor",
            "agent:codex",
        ],
        capsys,
    )
    assert rejected_source["data"]["id"] == "LINK-0002"

    rejected = run_json(["trace", "reject", "LINK-0002", "--actor", "human:john", "--reason", "not relevant"], capsys)
    assert rejected["data"]["state"] == "rejected"


def test_cli_json_validation_error_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)

    assert main(["req", "add", "--title", "Missing actor", "--statement", "No actor.", "--json"]) == 2
    envelope = json_output(capsys.readouterr().out)
    assert envelope["schema"] == "weft.plainweave.error.v1"
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "VALIDATION"


def test_cli_json_error_envelope_when_project_is_not_initialized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    assert (
        main(
            [
                "req",
                "add",
                "--title",
                "Missing project",
                "--statement",
                "Project has not been initialized.",
                "--actor",
                "human:john",
                "--json",
            ]
        )
        == 2
    )
    envelope = json_output(capsys.readouterr().out)
    assert envelope["schema"] == "weft.plainweave.error.v1"
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "NOT_FOUND"
