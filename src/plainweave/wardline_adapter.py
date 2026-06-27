from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

JsonObject = dict[str, object]

WARDLINE_DEGRADE_FINDINGS_ABSENT = "wardline_findings_absent"
ENGINE_PATH_SENTINEL = "<engine>"


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
