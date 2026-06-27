from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

JsonObject = dict[str, object]

WARDLINE_DEGRADE_FINDINGS_ABSENT = "wardline_findings_absent"
ENGINE_PATH_SENTINEL = "<engine>"

NON_DEFECT_KINDS = frozenset({"metric", "fact", "classification", "suggestion"})


@dataclass(frozen=True)
class WardlineFinding:
    fingerprint: str
    rule_id: str
    kind: str
    non_defect: bool
    severity: str
    suppression_state: str
    suppression_reason: str | None
    location: JsonObject
    qualname: str | None
    message: str

    def to_dict(self) -> JsonObject:
        return {
            "fingerprint": self.fingerprint,
            "rule_id": self.rule_id,
            "kind": self.kind,
            "non_defect": self.non_defect,
            "severity": self.severity,
            "suppression_state": self.suppression_state,
            "suppression_reason": self.suppression_reason,
            "location": dict(self.location),
            "qualname": self.qualname,
            "message": self.message,
        }


class WardlineAdapter:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.wardline_dir = self.root / ".wardline"

    def health(self) -> dict[str, object]:
        state = self._findings_state()
        return {"adapter_status": self._adapter_status(state), "degraded": self._state_degraded(state)}

    def _snapshots(self) -> list[Path]:
        if not self.wardline_dir.is_dir():
            return []
        return sorted(self.wardline_dir.glob("*-findings.jsonl"))

    def _findings_state(self) -> dict[str, object]:
        snapshots = self._snapshots()
        if not snapshots:
            return {
                "status": "unavailable",
                "snapshot_count": 0,
                "degraded": [
                    self._degraded(
                        WARDLINE_DEGRADE_FINDINGS_ABSENT,
                        "No .wardline findings snapshot is present; peer facts are unavailable.",
                    )
                ],
            }
        status = "available" if len(snapshots) >= 2 else "degraded"
        return {"status": status, "snapshot_count": len(snapshots), "degraded": []}

    def _adapter_status(self, state: dict[str, object]) -> JsonObject:
        return {
            "status": state["status"],
            "wardline_dir": ".wardline",
            "snapshot_count": state["snapshot_count"],
        }

    def _state_degraded(self, state: dict[str, object]) -> list[JsonObject]:
        degraded = state.get("degraded")
        return [dict(item) for item in degraded] if isinstance(degraded, list) else []

    def _degraded(self, code: str, message: str) -> JsonObject:
        return {"code": code, "message": message}

    def _load_snapshot(self, path: Path) -> list[JsonObject]:
        records: list[JsonObject] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                continue
            if parsed.get("kind") == "scan_manifest":
                continue
            records.append(parsed)
        return records

    def _is_engine_record(self, record: JsonObject) -> bool:
        location = record.get("location")
        path = location.get("path") if isinstance(location, dict) else None
        return path == ENGINE_PATH_SENTINEL

    def _finding_from_record(self, record: JsonObject) -> WardlineFinding:
        location = record.get("location")
        kind = str(record.get("kind"))
        reason = record.get("suppression_reason")
        qualname = record.get("qualname")
        return WardlineFinding(
            fingerprint=str(record.get("fingerprint")),
            rule_id=str(record.get("rule_id")),
            kind=kind,
            non_defect=kind not in {"defect"},
            severity=str(record.get("severity")),
            suppression_state=str(record.get("suppression_state")),
            suppression_reason=reason if isinstance(reason, str) else None,
            location=dict(location) if isinstance(location, dict) else {"path": None},
            qualname=qualname if isinstance(qualname, str) else None,
            message=str(record.get("message")),
        )
