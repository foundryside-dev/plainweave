from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.wardline_contract import assert_no_wardline_verdicts, validate_wardline_peer_facts

from plainweave.wardline_adapter import WardlineAdapter


def test_validator_accepts_live_payload(tmp_path: Path) -> None:
    wdir = tmp_path / ".wardline"
    wdir.mkdir()
    record: dict[str, object] = {
        "fingerprint": "d1",
        "kind": "defect",
        "rule_id": "WLN-1",
        "location": {"path": "src/a.py", "line_start": 1, "line_end": 1, "col_start": 0, "col_end": 1},
        "maturity": "stable",
        "message": "m",
        "properties": {},
        "qualname": "a.f",
        "related_entities": [],
        "severity": "CRITICAL",
        "suggestion": None,
        "suppression_reason": None,
        "suppression_state": "active",
    }
    (wdir / "20260101T000000Z-findings.jsonl").write_text(json.dumps(record), encoding="utf-8")
    data = WardlineAdapter(tmp_path).list_peer_facts()
    validate_wardline_peer_facts(data)  # must not raise; CRITICAL is a valid wardline severity


def test_validator_rejects_verdict_token() -> None:
    with pytest.raises(AssertionError):
        assert_no_wardline_verdicts({"facts": [{"severity": "blocked"}]})
