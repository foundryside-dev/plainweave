from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

JsonObject = dict[str, object]

WARDLINE_DEGRADE_FINDINGS_ABSENT = "wardline_findings_absent"
WARDLINE_DEGRADE_RULESET_MISMATCH = "wardline_ruleset_mismatch"
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

    def _read_manifest(self, path: Path) -> JsonObject | None:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and parsed.get("kind") == "scan_manifest":
                return parsed
        return None

    def _covered_paths(self, manifest: JsonObject | None) -> set[str] | None:
        if manifest is None:
            return None
        scope = manifest.get("scope")
        paths = scope.get("covered_paths") if isinstance(scope, dict) else None
        if not isinstance(paths, list):
            return None
        return {str(p) for p in paths}

    def _record_path(self, record: JsonObject) -> str | None:
        location = record.get("location")
        path = location.get("path") if isinstance(location, dict) else None
        return path if isinstance(path, str) else None

    def _resolved_unseen(
        self,
        latest: list[JsonObject],
        prior: list[JsonObject],
        *,
        covered: set[str] | None,
        degraded: list[JsonObject],
        prior_manifest: JsonObject | None,
        latest_manifest: JsonObject | None,
    ) -> tuple[list[JsonObject], int]:
        latest_fps = {str(r.get("fingerprint")) for r in latest if not self._is_engine_record(r)}
        resolved: list[JsonObject] = []
        indeterminate = 0
        effective_covered: set[str] = covered if covered is not None else set()
        for record in prior:
            if self._is_engine_record(record):
                continue
            if str(record.get("fingerprint")) in latest_fps:
                continue
            path = self._record_path(record)
            if path is not None and path in effective_covered:
                loc = record.get("location")
                resolved.append(
                    {
                        "fingerprint": str(record.get("fingerprint")),
                        "rule_id": str(record.get("rule_id")),
                        "location": dict(loc) if isinstance(loc, dict) else {},
                    }
                )
            else:
                indeterminate += 1
        if self._ruleset_id(prior_manifest) != self._ruleset_id(latest_manifest):
            degraded.append(
                self._degraded(
                    WARDLINE_DEGRADE_RULESET_MISMATCH,
                    "Ruleset id differs between snapshots; resolved/unseen is lower-trust.",
                )
            )
        return resolved, indeterminate

    def _ruleset_id(self, manifest: JsonObject | None) -> str | None:
        if manifest is None:
            return None
        value = manifest.get("ruleset_id")
        return value if isinstance(value, str) else None

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
