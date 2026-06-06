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


def approve_requirement(capsys: pytest.CaptureFixture[str], *, title: str = "Reject expired bearer tokens") -> None:
    run_json(
        [
            "req",
            "add",
            "--title",
            title,
            "--statement",
            "The API shall reject expired bearer tokens.",
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
            "approve-verification",
        ],
        capsys,
    )


def test_verify_cli_method_evidence_and_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    approve_requirement(capsys)

    method = run_json(
        [
            "verify",
            "method",
            "add",
            "REQ-AUTH-0001",
            "--method",
            "test",
            "--target",
            "tests/test_auth.py::test_expired",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    assert method["schema"] == "weft.charter.verification_method.v1"
    assert method["data"]["id"] == "VERM-0001"
    assert method["data"]["method"] == "test"

    evidence = run_json(
        [
            "verify",
            "evidence",
            "record",
            "VERM-0001",
            "--status",
            "passing",
            "--evidence-ref",
            "pytest:tests/test_auth.py::test_expired",
            "--actor",
            "agent:codex",
        ],
        capsys,
    )
    assert evidence["schema"] == "weft.charter.verification_evidence.v1"
    assert evidence["data"]["id"] == "EVID-0001"
    assert evidence["data"]["authority"] == "test_derived"

    status = run_json(["verify", "status", "REQ-AUTH-0001"], capsys)
    assert status["schema"] == "weft.charter.requirement_verification_status.v1"
    assert status["data"]["status"] == "satisfied"
    assert [item["id"] for item in status["data"]["current_evidence"]] == ["EVID-0001"]


def test_status_cli_lists_unverified_and_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    approve_requirement(capsys, title="Reject expired bearer tokens")
    run_json(
        [
            "verify",
            "method",
            "add",
            "REQ-AUTH-0001",
            "--method",
            "test",
            "--target",
            "tests/test_auth.py::test_expired",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    run_json(
        [
            "verify",
            "evidence",
            "record",
            "VERM-0001",
            "--status",
            "passing",
            "--evidence-ref",
            "pytest:tests/test_auth.py::test_expired",
            "--actor",
            "agent:codex",
        ],
        capsys,
    )
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
            "supersede-verification",
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
            "approve-verification-2",
        ],
        capsys,
    )

    requirement = run_json(["status", "requirement", "REQ-AUTH-0001"], capsys)
    stale = run_json(["status", "stale"], capsys)
    unverified = run_json(["status", "unverified"], capsys)

    assert requirement["data"]["status"] == "stale"
    assert [item["id"] for item in stale["data"]["items"]] == ["REQ-AUTH-0001"]
    assert [item["id"] for item in unverified["data"]["items"]] == ["REQ-AUTH-0002"]


def test_cli_unregistered_human_prefix_cannot_waive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    approve_requirement(capsys)
    run_json(
        [
            "verify",
            "method",
            "add",
            "REQ-AUTH-0001",
            "--method",
            "manual",
            "--target",
            "manual:operator",
            "--actor",
            "human:john",
        ],
        capsys,
    )

    spoofed = run_json(
        [
            "verify",
            "evidence",
            "record",
            "VERM-0001",
            "--status",
            "waived",
            "--evidence-ref",
            "waiver:spoofed",
            "--actor",
            "human:fake",
        ],
        capsys,
        expected_status=2,
    )
    assert spoofed["error"]["code"] == "POLICY_REQUIRED"


def test_cli_actor_register_enables_waiver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    approve_requirement(capsys)
    run_json(
        [
            "verify",
            "method",
            "add",
            "REQ-AUTH-0001",
            "--method",
            "manual",
            "--target",
            "manual:operator",
            "--actor",
            "human:john",
        ],
        capsys,
    )

    registered = run_json(
        [
            "actor",
            "register",
            "human:john",
            "--kind",
            "human",
            "--display-name",
            "John",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    assert registered["schema"] == "weft.charter.actor.v1"
    assert registered["data"]["kind"] == "human"

    evidence = run_json(
        [
            "verify",
            "evidence",
            "record",
            "VERM-0001",
            "--status",
            "waived",
            "--evidence-ref",
            "waiver:release-manager",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    assert evidence["data"]["authority"] == "waiver"


def test_cli_agent_cannot_register_attester_after_genesis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    # Genesis attester established at setup.
    run_json(["actor", "register", "human:john", "--kind", "human", "--actor", "human:john"], capsys)

    # An agent cannot then mint a fake human via the shipped CLI.
    blocked = run_json(
        ["actor", "register", "human:fake", "--kind", "human", "--actor", "agent:codex"],
        capsys,
        expected_status=2,
    )
    assert blocked["error"]["code"] == "POLICY_REQUIRED"


def test_verify_cli_policy_and_not_found_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    approve_requirement(capsys)
    run_json(
        [
            "verify",
            "method",
            "add",
            "REQ-AUTH-0001",
            "--method",
            "manual",
            "--target",
            "manual:operator",
            "--actor",
            "human:john",
        ],
        capsys,
    )

    policy_error = run_json(
        [
            "verify",
            "evidence",
            "record",
            "VERM-0001",
            "--status",
            "passing",
            "--evidence-ref",
            "manual:agent-claim",
            "--actor",
            "agent:codex",
        ],
        capsys,
        expected_status=2,
    )
    not_found = run_json(["verify", "status", "REQ-AUTH-9999"], capsys, expected_status=2)

    assert policy_error["error"]["code"] == "POLICY_REQUIRED"
    assert not_found["error"]["code"] == "NOT_FOUND"
