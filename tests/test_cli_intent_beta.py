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


def approve_requirement(capsys: pytest.CaptureFixture[str]) -> str:
    added = run_json(
        [
            "req",
            "add",
            "--title",
            "Explain authentication verifier",
            "--statement",
            "Authentication verifier code shall have explicit intent.",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    requirement_id = str(added["data"]["id"])
    run_json(
        [
            "criterion",
            "add",
            requirement_id,
            "--text",
            "Verifier intent is traceable to a goal.",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    run_json(
        [
            "req",
            "approve",
            requirement_id,
            "--actor",
            "human:john",
            "--expected-version",
            "0",
            "--idempotency-key",
            "approve-auth",
        ],
        capsys,
    )
    return requirement_id


def test_cli_exposes_intent_bind_and_read_primitives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    requirement_id = approve_requirement(capsys)
    sei = "loomweave:eid:auth.verify-token"

    recorded = run_json(
        [
            "catalog",
            "record",
            sei,
            "--entity-kind",
            "loomweave_entity",
            "--display-name",
            "auth.verify_token",
            "--content-hash",
            "sha256:old",
            "--actor",
            "agent:loomweave",
        ],
        capsys,
    )
    assert recorded["schema"] == "weft.plainweave.code_entity.v1"

    code_orphans = run_json(["intent", "orphans", "code"], capsys)
    assert code_orphans["schema"] == "weft.plainweave.intent_orphans.v1"
    assert [item["node_id"] for item in code_orphans["data"]["items"]] == [sei]

    goal = run_json(
        [
            "goal",
            "add",
            "--title",
            "Make authentication intent explainable",
            "--statement",
            "Every public authentication surface can answer why it exists.",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    goal_id = str(goal["data"]["id"])
    run_json(["goal", "link", goal_id, requirement_id, "--actor", "human:john"], capsys)
    bind = run_json(
        [
            "bind",
            "sei",
            sei,
            requirement_id,
            "--content-hash",
            "sha256:old",
            "--actor",
            "agent:codex",
        ],
        capsys,
    )
    assert bind["schema"] == "weft.plainweave.sei_binding.v1"
    assert bind["data"]["entity_id"] == sei

    assert run_json(["intent", "orphans", "code"], capsys)["data"]["items"] == []
    trace = run_json(["intent", "trace", "code", sei], capsys)
    assert trace["schema"] == "weft.plainweave.intent_trace.v1"
    assert [node["level"] for node in trace["data"]["up"]] == ["requirement", "goal"]

    corpus = run_json(["intent", "corpus"], capsys)
    assert corpus["schema"] == "weft.plainweave.intent_corpus.v1"
    assert corpus["data"]["items"][0]["requirement"]["node_id"] == "req-1"
