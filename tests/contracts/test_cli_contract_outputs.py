from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from charter.cli import main

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "contracts"


def load_fixture(path: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURE_ROOT / path).read_text(encoding="utf-8")))


def json_output(output: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(output))


def run_json(args: list[str], capsys: pytest.CaptureFixture[str], expected_status: int = 0) -> dict[str, Any]:
    assert main([*args, "--json"]) == expected_status
    return json_output(capsys.readouterr().out)


def init_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--project-key", "AUTH", "--json"]) == 0
    capsys.readouterr()


def assert_matches_fixture(actual: dict[str, Any], fixture: dict[str, Any]) -> None:
    assert set(actual) == set(fixture)
    for key, expected in fixture.items():
        assert_value_matches(actual[key], expected, key)


def assert_value_matches(actual: Any, expected: Any, field_name: str) -> None:
    if field_name in {"generated_at", "approved_at", "created_at", "recorded_at"}:
        assert isinstance(actual, str)
        assert actual
        return
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        assert set(actual) == set(expected)
        for key, nested_expected in expected.items():
            assert_value_matches(actual[key], nested_expected, key)
        return
    if isinstance(expected, list):
        assert isinstance(actual, list)
        assert len(actual) == len(expected)
        for actual_item, expected_item in zip(actual, expected, strict=True):
            assert_value_matches(actual_item, expected_item, field_name)
        return
    assert actual == expected


def test_requirement_cli_outputs_match_contract_fixtures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)

    draft = run_json(
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
    assert_matches_fixture(draft, load_fixture("cli/req-add-json.json"))

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
            "approve-contract",
        ],
        capsys,
    )
    assert_matches_fixture(approved, load_fixture("cli/req-approve-json.json"))

    shown = run_json(["req", "show", "REQ-AUTH-0001"], capsys)
    assert_matches_fixture(shown, load_fixture("cli/req-show-json.json"))


def test_cli_error_output_matches_contract_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)

    error = run_json(
        ["req", "add", "--title", "Missing actor", "--statement", "No actor."],
        capsys,
        expected_status=2,
    )
    assert_matches_fixture(error, load_fixture("cli/error-validation-json.json"))


def test_cli_conflict_error_output_matches_contract_fixture(
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
            "req",
            "approve",
            "REQ-AUTH-0001",
            "--actor",
            "human:john",
            "--expected-version",
            "0",
            "--idempotency-key",
            "approve-contract",
        ],
        capsys,
    )

    error = run_json(
        [
            "req",
            "deprecate",
            "REQ-AUTH-0001",
            "--actor",
            "human:john",
            "--expected-version",
            "0",
            "--idempotency-key",
            "deprecate-conflict",
        ],
        capsys,
        expected_status=2,
    )
    assert_matches_fixture(error, load_fixture("cli/error-conflict-json.json"))


def test_criterion_cli_output_matches_contract_fixture(
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
            "Reject expired bearer tokens",
            "--statement",
            "The API shall reject expired bearer tokens.",
            "--actor",
            "human:john",
        ],
        capsys,
    )

    criterion = run_json(
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
    assert_matches_fixture(criterion, load_fixture("cli/criterion-add-json.json"))


def test_dossier_cli_output_matches_contract_fixture(
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
            "approve-dossier-contract",
        ],
        capsys,
    )

    dossier = run_json(["dossier", "REQ-AUTH-0001"], capsys)
    assert_matches_fixture(dossier, load_fixture("cli/dossier-json.json"))


def test_trace_cli_outputs_match_contract_fixtures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
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
    assert_matches_fixture(proposed, load_fixture("cli/trace-propose-json.json"))

    accepted = run_json(["trace", "accept", "LINK-0001", "--actor", "human:john"], capsys)
    assert_matches_fixture(accepted, load_fixture("cli/trace-accept-json.json"))

    second = run_json(
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
    assert second["data"]["id"] == "LINK-0002"

    rejected = run_json(["trace", "reject", "LINK-0002", "--actor", "human:john", "--reason", "not relevant"], capsys)
    assert_matches_fixture(rejected, load_fixture("cli/trace-reject-json.json"))

    listed = run_json(["trace", "list", "--state", "accepted"], capsys)
    assert_matches_fixture(listed, load_fixture("cli/trace-list-json.json"))


def test_baseline_cli_outputs_match_contract_fixtures(
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
            "req",
            "approve",
            "REQ-AUTH-0001",
            "--actor",
            "human:john",
            "--expected-version",
            "0",
            "--idempotency-key",
            "approve-baseline-contract",
        ],
        capsys,
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
    assert_matches_fixture(created, load_fixture("cli/baseline-create-json.json"))

    shown = run_json(["baseline", "show", "BASELINE-0001"], capsys)
    assert_matches_fixture(shown, load_fixture("cli/baseline-show-json.json"))

    listed = run_json(["baseline", "list"], capsys)
    assert_matches_fixture(listed, load_fixture("cli/baseline-list-json.json"))

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
            "supersede-baseline-contract",
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
            "approve-baseline-new-contract",
        ],
        capsys,
    )

    diff = run_json(["baseline", "diff", "BASELINE-0001"], capsys)
    assert_matches_fixture(diff, load_fixture("cli/baseline-diff-json.json"))


def test_verification_cli_outputs_match_contract_fixtures(
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
            "req",
            "approve",
            "REQ-AUTH-0001",
            "--actor",
            "human:john",
            "--expected-version",
            "0",
            "--idempotency-key",
            "approve-verification-contract",
        ],
        capsys,
    )

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
    assert_matches_fixture(method, load_fixture("cli/verify-method-add-json.json"))

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
    assert_matches_fixture(evidence, load_fixture("cli/verify-evidence-record-json.json"))

    status = run_json(["verify", "status", "REQ-AUTH-0001"], capsys)
    assert_matches_fixture(status, load_fixture("cli/verify-status-json.json"))

    requirement_status = run_json(["status", "requirement", "REQ-AUTH-0001"], capsys)
    assert_matches_fixture(requirement_status, load_fixture("cli/status-requirement-json.json"))

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
            "approve-unverified-contract",
        ],
        capsys,
    )
    unverified = run_json(["status", "unverified"], capsys)
    assert_matches_fixture(unverified, load_fixture("cli/status-unverified-json.json"))

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
            "supersede-verification-contract",
        ],
        capsys,
    )
    stale = run_json(["status", "stale"], capsys)
    assert_matches_fixture(stale, load_fixture("cli/status-stale-json.json"))
