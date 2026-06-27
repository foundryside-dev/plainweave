from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from plainweave.wardline_adapter import WardlineAdapter


def _write_snapshot(root: Path, name: str, records: list[dict[str, object]]) -> None:
    wdir = root / ".wardline"
    wdir.mkdir(exist_ok=True)
    (wdir / name).write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")


def _defect(
    fp: str,
    path: str = "src/a.py",
    state: str = "active",
    severity: str = "ERROR",
    reason: str | None = None,
) -> dict[str, object]:
    return {
        "fingerprint": fp,
        "kind": "defect",
        "rule_id": "WLN-TAINT-1",
        "location": {"path": path, "line_start": 1, "line_end": 1, "col_start": 0, "col_end": 1},
        "maturity": "stable",
        "message": "tainted sink",
        "properties": {},
        "qualname": "a.f",
        "related_entities": [],
        "severity": severity,
        "suggestion": None,
        "suppression_reason": reason,
        "suppression_state": state,
    }


def _engine() -> dict[str, object]:
    return {
        "fingerprint": "eng1",
        "kind": "metric",
        "rule_id": "WLN-ENGINE-METRICS",
        "location": {
            "path": "<engine>",
            "line_start": None,
            "line_end": None,
            "col_start": None,
            "col_end": None,
        },
        "maturity": "stable",
        "message": "L3 resolver run metrics",
        "properties": {"cache_hit_rate": 0.0},
        "qualname": None,
        "related_entities": [],
        "severity": "NONE",
        "suggestion": None,
        "suppression_reason": None,
        "suppression_state": "active",
    }


def test_engine_record_is_separated_from_entity_findings(tmp_path: Path) -> None:
    _write_snapshot(tmp_path, "20260101T000000Z-findings.jsonl", [_defect("d1"), _engine()])
    adapter = WardlineAdapter(tmp_path)
    records = adapter._load_snapshot((tmp_path / ".wardline" / "20260101T000000Z-findings.jsonl"))
    entity = [r for r in records if not adapter._is_engine_record(r)]
    engine = [r for r in records if adapter._is_engine_record(r)]
    assert len(entity) == 1 and len(engine) == 1
    finding = adapter._finding_from_record(entity[0])
    assert finding.non_defect is False
    assert finding.suppression_state == "active"


def test_non_defect_kinds_are_tagged_non_defect(tmp_path: Path) -> None:
    rec = _defect("c1")
    rec["kind"] = "classification"
    _write_snapshot(tmp_path, "20260101T000000Z-findings.jsonl", [rec])
    adapter = WardlineAdapter(tmp_path)
    [record] = adapter._load_snapshot((tmp_path / ".wardline" / "20260101T000000Z-findings.jsonl"))
    assert adapter._finding_from_record(record).non_defect is True


def test_health_reports_unavailable_when_no_wardline_dir(tmp_path: Path) -> None:
    health = WardlineAdapter(tmp_path).health()
    adapter_status = cast(dict[str, Any], health["adapter_status"])
    assert adapter_status["status"] == "unavailable"
    degraded = cast(list[dict[str, Any]], health["degraded"])
    codes = [d["code"] for d in degraded]
    assert "wardline_findings_absent" in codes
    # no-silent-clean: a missing source is reported, never an empty-but-ok health
    for entry in degraded:
        assert set(entry) == {"code", "message"}
        assert ".wardline" not in entry["message"] or "/" not in entry["message"]


def test_health_reports_available_with_one_snapshot(tmp_path: Path) -> None:
    wdir = tmp_path / ".wardline"
    wdir.mkdir()
    (wdir / "20260101T000000Z-findings.jsonl").write_text("", encoding="utf-8")
    health = WardlineAdapter(tmp_path).health()
    adapter_status = cast(dict[str, Any], health["adapter_status"])
    assert adapter_status["status"] in {"available", "degraded"}
    assert adapter_status["snapshot_count"] == 1
