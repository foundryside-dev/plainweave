from __future__ import annotations

from pathlib import Path

from plainweave.wardline_adapter import WardlineAdapter


def test_health_reports_unavailable_when_no_wardline_dir(tmp_path: Path) -> None:
    health = WardlineAdapter(tmp_path).health()
    assert health["adapter_status"]["status"] == "unavailable"
    codes = [d["code"] for d in health["degraded"]]
    assert "wardline_findings_absent" in codes
    # no-silent-clean: a missing source is reported, never an empty-but-ok health
    for entry in health["degraded"]:
        assert set(entry) == {"code", "message"}
        assert ".wardline" not in entry["message"] or "/" not in entry["message"]


def test_health_reports_available_with_one_snapshot(tmp_path: Path) -> None:
    wdir = tmp_path / ".wardline"
    wdir.mkdir()
    (wdir / "20260101T000000Z-findings.jsonl").write_text("", encoding="utf-8")
    health = WardlineAdapter(tmp_path).health()
    assert health["adapter_status"]["status"] in {"available", "degraded"}
    assert health["adapter_status"]["snapshot_count"] == 1
