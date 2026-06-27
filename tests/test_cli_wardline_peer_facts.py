from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from plainweave.cli import main
from tests.wardline_contract import assert_no_wardline_verdicts, validate_wardline_peer_facts


def _active_defect() -> dict[str, Any]:
    return {
        "fingerprint": "fp-active",
        "rule_id": "PY-WL-101",
        "kind": "defect",
        "severity": "ERROR",
        "suppression_state": "active",
        "suppression_reason": None,
        "location": {"path": "src/a.py", "line_start": 1, "line_end": 1, "col_start": 0, "col_end": 1},
        "qualname": "a.unsafe",
        "message": "untrusted reaches a trusted producer",
    }


def _write(wdir: Path, name: str, records: list[dict[str, Any]]) -> None:
    wdir.mkdir(parents=True, exist_ok=True)
    (wdir / name).write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def test_wardline_peer_facts_emits_v1_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / ".wardline", "20260101T000000Z-findings.jsonl", [_active_defect()])
    assert main(["wardline-peer-facts", "--json"]) == 0
    envelope = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    assert envelope["schema"] == "weft.plainweave.wardline_peer_facts.v1"
    assert envelope["ok"] is True
    data = cast(dict[str, Any], envelope["data"])
    validate_wardline_peer_facts(data)
    assert_no_wardline_verdicts(envelope)
    assert data["freshness"] == "current"


def test_wardline_peer_facts_absent_is_unavailable_not_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)  # no .wardline/
    assert main(["wardline-peer-facts", "--json"]) == 0
    envelope = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    data = cast(dict[str, Any], envelope["data"])
    assert data["freshness"] == "unavailable"
    assert any(d["code"] == "wardline_findings_absent" for d in data["degraded"])
    validate_wardline_peer_facts(data)
    assert_no_wardline_verdicts(envelope)


def test_wardline_peer_facts_invalid_limit_is_validation_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / ".wardline", "20260101T000000Z-findings.jsonl", [_active_defect()])
    assert main(["wardline-peer-facts", "--limit", "0", "--json"]) == 2
    envelope = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "VALIDATION"


def test_wardline_peer_facts_human_output_prints_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / ".wardline", "20260101T000000Z-findings.jsonl", [_active_defect()])
    assert main(["wardline-peer-facts"]) == 0
    data = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    assert data["freshness"] == "current"  # human path prints data (still JSON)
