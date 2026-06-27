from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from plainweave.wardline_adapter import WardlineAdapter


def _write_snapshot(root: Path, name: str, records: list[dict[str, object]]) -> None:
    wdir = root / ".wardline"
    wdir.mkdir(exist_ok=True)
    (wdir / name).write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")


def _write_raw_snapshot(root: Path, name: str, text: str) -> None:
    wdir = root / ".wardline"
    wdir.mkdir(exist_ok=True)
    (wdir / name).write_text(text, encoding="utf-8")


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
    records = adapter._load_snapshot(tmp_path / ".wardline" / "20260101T000000Z-findings.jsonl")
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
    [record] = adapter._load_snapshot(tmp_path / ".wardline" / "20260101T000000Z-findings.jsonl")
    assert adapter._finding_from_record(record).non_defect is True


def test_load_snapshot_skips_blank_lines(tmp_path: Path) -> None:
    # Blank and whitespace-only lines must be silently skipped; only valid
    # non-blank records must be returned.
    good = _defect("g1")
    text = "\n".join(
        [
            "",
            "   ",
            json.dumps(good),
            "",
            "\t",
        ]
    )
    _write_raw_snapshot(tmp_path, "20260101T000000Z-findings.jsonl", text)
    adapter = WardlineAdapter(tmp_path)
    records = adapter._load_snapshot(tmp_path / ".wardline" / "20260101T000000Z-findings.jsonl")
    assert len(records) == 1
    assert records[0]["fingerprint"] == "g1"


def test_load_snapshot_skips_scan_manifest_records(tmp_path: Path) -> None:
    # scan_manifest records must be silently dropped; surrounding valid records
    # must be returned unaffected.
    manifest: dict[str, object] = {
        "kind": "scan_manifest",
        "fingerprint": "m1",
        "scan_id": "s1",
        "rule_ids": [],
        "scanned_paths": [],
    }
    good = _defect("g2")
    text = "\n".join([json.dumps(manifest), json.dumps(good)])
    _write_raw_snapshot(tmp_path, "20260101T000000Z-findings.jsonl", text)
    adapter = WardlineAdapter(tmp_path)
    records = adapter._load_snapshot(tmp_path / ".wardline" / "20260101T000000Z-findings.jsonl")
    assert len(records) == 1
    assert records[0]["fingerprint"] == "g2"


def test_load_snapshot_tolerates_malformed_lines(tmp_path: Path) -> None:
    # A corrupt / truncated JSONL line must NOT raise; subsequent valid records
    # must still be returned.  This is a reliability guarantee for corrupt files.
    good = _defect("g3")
    text = "\n".join(
        [
            "{not valid json",
            "null",  # valid JSON but not a dict — also skipped
            json.dumps(good),
            "TRUNCATED",
        ]
    )
    _write_raw_snapshot(tmp_path, "20260101T000000Z-findings.jsonl", text)
    adapter = WardlineAdapter(tmp_path)
    records = adapter._load_snapshot(tmp_path / ".wardline" / "20260101T000000Z-findings.jsonl")
    assert len(records) == 1
    assert records[0]["fingerprint"] == "g3"


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


def _manifest(covered: list[str], ruleset: str = "rs@1") -> dict[str, object]:
    return {
        "kind": "scan_manifest",
        "scan_id": "s1",
        "started_at": "2026-01-01T00:00:00Z",
        "commit": "abc",
        "ruleset_id": ruleset,
        "scope": {"selector": "src", "covered_paths": covered},
    }


def test_manifest_primary_resolved_when_path_recovered(tmp_path: Path) -> None:
    prior = [_manifest(["src/a.py"]), _defect("d1", path="src/a.py")]
    latest = [_manifest(["src/a.py"])]  # d1 gone, src/a.py still covered -> resolved
    _write_snapshot(tmp_path, "20260101T000000Z-findings.jsonl", prior)
    _write_snapshot(tmp_path, "20260102T000000Z-findings.jsonl", latest)
    adapter = WardlineAdapter(tmp_path)
    snaps = adapter._snapshots()
    latest_records = adapter._load_snapshot(snaps[-1])
    prior_records = adapter._load_snapshot(snaps[-2])
    covered = adapter._covered_paths(adapter._read_manifest(snaps[-1]))
    assert covered == {"src/a.py"}
    degraded: list[dict[str, object]] = []
    resolved, indeterminate = adapter._resolved_unseen(
        latest_records,
        prior_records,
        covered=covered,
        degraded=degraded,
        prior_manifest=adapter._read_manifest(snaps[-2]),
        latest_manifest=adapter._read_manifest(snaps[-1]),
    )
    assert [item["fingerprint"] for item in resolved] == ["d1"]
    assert indeterminate == 0


def test_manifest_primary_indeterminate_when_path_not_covered(tmp_path: Path) -> None:
    prior = [_manifest(["src/a.py", "src/b.py"]), _defect("d2", path="src/b.py")]
    latest = [_manifest(["src/a.py"])]  # b.py no longer scanned -> indeterminate, NOT resolved
    _write_snapshot(tmp_path, "20260101T000000Z-findings.jsonl", prior)
    _write_snapshot(tmp_path, "20260102T000000Z-findings.jsonl", latest)
    adapter = WardlineAdapter(tmp_path)
    snaps = adapter._snapshots()
    covered = adapter._covered_paths(adapter._read_manifest(snaps[-1]))
    degraded: list[dict[str, object]] = []
    resolved, indeterminate = adapter._resolved_unseen(
        adapter._load_snapshot(snaps[-1]),
        adapter._load_snapshot(snaps[-2]),
        covered=covered,
        degraded=degraded,
        prior_manifest=adapter._read_manifest(snaps[-2]),
        latest_manifest=adapter._read_manifest(snaps[-1]),
    )
    assert resolved == []
    assert indeterminate == 1


def test_manifest_ruleset_mismatch_is_flagged(tmp_path: Path) -> None:
    prior = [_manifest(["src/a.py"], ruleset="rs@1"), _defect("d1", path="src/a.py")]
    latest = [_manifest(["src/a.py"], ruleset="rs@2")]
    _write_snapshot(tmp_path, "20260101T000000Z-findings.jsonl", prior)
    _write_snapshot(tmp_path, "20260102T000000Z-findings.jsonl", latest)
    adapter = WardlineAdapter(tmp_path)
    snaps = adapter._snapshots()
    degraded: list[dict[str, object]] = []
    adapter._resolved_unseen(
        adapter._load_snapshot(snaps[-1]),
        adapter._load_snapshot(snaps[-2]),
        covered={"src/a.py"},
        degraded=degraded,
        prior_manifest=adapter._read_manifest(snaps[-2]),
        latest_manifest=adapter._read_manifest(snaps[-1]),
    )
    assert any(d["code"] == "wardline_ruleset_mismatch" for d in degraded)


def test_fallback_flags_scan_identity_absent_when_no_manifest(tmp_path: Path) -> None:
    _write_snapshot(tmp_path, "20260101T000000Z-findings.jsonl", [_defect("d1", path="src/a.py")])
    _write_snapshot(tmp_path, "20260102T000000Z-findings.jsonl", [])  # d1 gone, no manifest
    # latest has no findings -> latest_path_set empty -> d1 path not covered -> indeterminate + scope_mismatch
    adapter = WardlineAdapter(tmp_path)
    snaps = adapter._snapshots()
    degraded: list[dict[str, object]] = []
    covered = adapter._scope_for_diff(
        adapter._load_snapshot(snaps[-1]),
        adapter._load_snapshot(snaps[-2]),
        latest_manifest=None,
        prior_manifest=None,
        degraded=degraded,
    )
    assert covered == set()
    assert any(d["code"] == "wardline_scan_identity_absent" for d in degraded)
    assert any(d["code"] == "wardline_scope_mismatch" for d in degraded)
    mismatch = next(d for d in degraded if d["code"] == "wardline_scope_mismatch")
    assert isinstance(cast(dict[str, object], mismatch["detail"])["jaccard"], float)


def test_list_peer_facts_single_snapshot_marks_resolved_unavailable(tmp_path: Path) -> None:
    _write_snapshot(
        tmp_path,
        "20260101T000000Z-findings.jsonl",
        [_defect("d1", state="active"), _defect("w1", state="waived"), _engine()],
    )
    data = WardlineAdapter(tmp_path).list_peer_facts()
    source = cast(dict[str, Any], data["source"])
    assert source["snapshot"] == "20260101T000000Z-findings.jsonl"
    assert source["prior"] is None
    assert "/" not in str(source["snapshot"])
    summary = cast(dict[str, Any], data["summary"])
    by_state = cast(dict[str, Any], summary["by_suppression_state"])
    assert by_state == {"active": 1, "waived": 1, "baselined": 0, "judged": 0}
    assert summary["defect"] == 2 and summary["non_defect"] == 0
    assert data["resolved_or_unseen"] == []
    degraded = cast(list[dict[str, Any]], data["degraded"])
    assert any(d["code"] == "wardline_single_snapshot" for d in degraded)
    engine_metrics = cast(list[Any], data["engine_metrics"])
    assert len(engine_metrics) == 1
    authority = cast(dict[str, Any], data["authority_boundary"])
    assert authority["trust_policy_owner"] == "wardline"


def test_list_peer_facts_unavailable_when_absent(tmp_path: Path) -> None:
    data = WardlineAdapter(tmp_path).list_peer_facts()
    assert data["freshness"] == "unavailable"
    assert data["facts"] == []
    degraded = cast(list[dict[str, Any]], data["degraded"])
    assert any(d["code"] == "wardline_findings_absent" for d in degraded)


def test_fallback_resolved_when_same_path_set(tmp_path: Path) -> None:
    _write_snapshot(
        tmp_path, "20260101T000000Z-findings.jsonl", [_defect("d1", path="src/a.py"), _defect("keep", path="src/a.py")]
    )
    _write_snapshot(tmp_path, "20260102T000000Z-findings.jsonl", [_defect("keep", path="src/a.py")])
    adapter = WardlineAdapter(tmp_path)
    snaps = adapter._snapshots()
    degraded: list[dict[str, object]] = []
    covered = adapter._scope_for_diff(
        adapter._load_snapshot(snaps[-1]),
        adapter._load_snapshot(snaps[-2]),
        latest_manifest=None,
        prior_manifest=None,
        degraded=degraded,
    )
    assert covered == {"src/a.py"}
    assert not any(d["code"] == "wardline_scope_mismatch" for d in degraded)
    assert any(d["code"] == "wardline_scan_identity_absent" for d in degraded)
