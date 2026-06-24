from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from plainweave.cli import main
from plainweave.service import PlainweaveService
from tests.intent_coverage_contract import validate_intent_coverage
from tests.loomweave_test_utils import create_loomweave_db
from tests.test_intent_coverage import add_surface, justify


def run_json(args: list[str], capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    assert main([*args, "--json"]) == 0
    return cast(dict[str, Any], json.loads(capsys.readouterr().out))


def setup_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> PlainweaveService:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--project-key", "AUTH", "--json"]) == 0
    capsys.readouterr()
    return PlainweaveService(tmp_path / ".plainweave" / "plainweave.db", root=tmp_path)


def test_cli_intent_coverage_scopes_namespaces_and_matches_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    service = setup_project(tmp_path, monkeypatch, capsys)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:function:pkg.real", tags=["exported-api"], sei="loomweave:eid:real")
    add_surface(db, "python:function:tests.perf.harness", tags=["entry-point"], sei="loomweave:eid:tperf")
    justify(service, "loomweave:eid:real", key="real")

    envelope = run_json(["intent", "coverage"], capsys)

    assert envelope["schema"] == "weft.plainweave.intent_coverage.v1"
    data = envelope["data"]
    validate_intent_coverage(data)
    assert data["north_star"] == {"numerator": 1, "denominator": 1, "ratio": 1.0}
    assert data["scoping"]["excluded_count"] == 1
    assert data["scoping"]["excluded_namespaces"] == ["scripts.", "tests."]
    assert [surface["locator"] for surface in data["justified"]] == ["python:function:pkg.real"]


def test_cli_intent_coverage_override_namespace_changes_denominator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    setup_project(tmp_path, monkeypatch, capsys)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:function:pkg.real", tags=["exported-api"], sei="loomweave:eid:real")
    add_surface(db, "python:function:tests.perf.harness", tags=["entry-point"], sei="loomweave:eid:tperf")

    envelope = run_json(["intent", "coverage", "--exclude-namespace", "pkg."], capsys)

    data = envelope["data"]
    validate_intent_coverage(data)
    assert data["scoping"]["excluded_namespaces"] == ["pkg."]
    assert data["north_star"]["denominator"] == 1
    assert [surface["locator"] for surface in data["unjustified"]] == ["python:function:tests.perf.harness"]


def test_cli_intent_coverage_surface_class_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    setup_project(tmp_path, monkeypatch, capsys)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:function:pkg.api", tags=["exported-api"], sei="loomweave:eid:api")
    add_surface(db, "python:function:pkg.cli", tags=["cli-command"], sei="loomweave:eid:cli")

    envelope = run_json(["intent", "coverage", "--surface-class", "exported-api"], capsys)

    data = envelope["data"]
    validate_intent_coverage(data)
    assert data["scoping"]["surface_classes"] == ["exported-api"]
    assert [surface["locator"] for surface in data["unjustified"]] == ["python:function:pkg.api"]
