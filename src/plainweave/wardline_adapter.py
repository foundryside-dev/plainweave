from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]

WARDLINE_DEGRADE_FINDINGS_ABSENT = "wardline_findings_absent"
WARDLINE_DEGRADE_RULESET_MISMATCH = "wardline_ruleset_mismatch"
WARDLINE_DEGRADE_SINGLE_SNAPSHOT = "wardline_single_snapshot"
WARDLINE_DEGRADE_SCOPE_MISMATCH = "wardline_scope_mismatch"
WARDLINE_DEGRADE_SCAN_IDENTITY_ABSENT = "wardline_scan_identity_absent"
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

    def _latest_path_set(self, records: list[JsonObject]) -> set[str]:
        paths: set[str] = set()
        for record in records:
            if self._is_engine_record(record):
                continue
            path = self._record_path(record)
            if path is not None:
                paths.add(path)
        return paths

    def _jaccard(self, a: set[str], b: set[str]) -> float:
        union = a | b
        if not union:
            return 1.0
        return round(len(a & b) / len(union), 4)

    def _scope_for_diff(
        self,
        latest: list[JsonObject],
        prior: list[JsonObject],
        *,
        latest_manifest: JsonObject | None,
        prior_manifest: JsonObject | None,
        degraded: list[JsonObject],
    ) -> set[str]:
        latest_covered = self._covered_paths(latest_manifest)
        prior_covered = self._covered_paths(prior_manifest)
        if latest_covered is not None and prior_covered is not None:
            covered = latest_covered
        else:
            covered = self._latest_path_set(latest)
            degraded.append(
                self._degraded(
                    WARDLINE_DEGRADE_SCAN_IDENTITY_ABSENT,
                    "Scan-identity metadata absent; resolved/unseen bounded by the latest path-set heuristic.",
                )
            )
        prior_paths = self._latest_path_set(prior)
        if prior_paths - covered:
            degraded.append(
                {
                    "code": WARDLINE_DEGRADE_SCOPE_MISMATCH,
                    "message": "Some prior findings lie outside the latest scanned scope; they are indeterminate.",
                    "detail": {"jaccard": self._jaccard(prior_paths, covered)},
                }
            )
        return covered

    def list_peer_facts(self, *, limit: int = 50, offset: int = 0) -> JsonObject:
        snapshots = self._snapshots()
        authority = {
            "local_only": True,
            "live_peer_calls": False,
            "governance_verdicts": False,
            "trust_policy_owner": "wardline",
        }
        if not snapshots:
            return {
                "source": {"snapshot": None, "snapshot_count": 0, "prior": None},
                "freshness": "unavailable",
                "facts": [],
                "resolved_or_unseen": [],
                "engine_metrics": [],
                "summary": self._summary([], [], resolved=0, indeterminate=0),
                "degraded": [
                    self._degraded(
                        WARDLINE_DEGRADE_FINDINGS_ABSENT,
                        "No .wardline findings snapshot is present; peer facts are unavailable.",
                    )
                ],
                "authority_boundary": authority,
                "notes": ["No .wardline findings snapshot present; result is unavailable, not clean."],
            }
        latest_path = snapshots[-1]
        latest_records = self._load_snapshot(latest_path)
        entity_records = [r for r in latest_records if not self._is_engine_record(r)]
        engine_metrics = [r for r in latest_records if self._is_engine_record(r)]
        findings = [self._finding_from_record(r) for r in entity_records]
        degraded: list[JsonObject] = []
        notes: list[str] = []
        resolved: list[JsonObject] = []
        indeterminate = 0
        prior_path: Path | None = None
        if len(snapshots) < 2:
            degraded.append(
                self._degraded(
                    WARDLINE_DEGRADE_SINGLE_SNAPSHOT,
                    "Only one snapshot present; resolved/unseen cannot be computed.",
                )
            )
            notes.append("resolved/unseen unavailable: a single snapshot cannot diff.")
        else:
            prior_path = snapshots[-2]
            prior_records = self._load_snapshot(prior_path)
            latest_manifest = self._read_manifest(latest_path)
            prior_manifest = self._read_manifest(prior_path)
            covered = self._scope_for_diff(
                latest_records,
                prior_records,
                latest_manifest=latest_manifest,
                prior_manifest=prior_manifest,
                degraded=degraded,
            )
            resolved, indeterminate = self._resolved_unseen(
                latest_records,
                prior_records,
                covered=covered,
                degraded=degraded,
                prior_manifest=prior_manifest,
                latest_manifest=latest_manifest,
            )
            if not self._read_manifest(latest_path):
                notes.append("scan-identity metadata absent; resolved/unseen bounded by latest path-set.")
        summary = self._summary(findings, engine_metrics, resolved=len(resolved), indeterminate=indeterminate)
        fact_dicts = [f.to_dict() for f in findings]
        page = fact_dicts[offset : offset + limit]
        if len(page) < len(fact_dicts):
            notes.append(f"facts truncated to page; {len(fact_dicts)} total")
        return {
            "source": {
                "snapshot": latest_path.name,
                "snapshot_count": len(snapshots),
                "prior": prior_path.name if prior_path is not None else None,
            },
            "freshness": "current",
            "facts": page,
            "resolved_or_unseen": resolved,
            "engine_metrics": engine_metrics,
            "summary": summary,
            "degraded": degraded,
            "authority_boundary": authority,
            "notes": notes,
        }

    def _summary(
        self,
        findings: list[WardlineFinding],
        engine_metrics: list[JsonObject],
        *,
        resolved: int,
        indeterminate: int,
    ) -> JsonObject:
        by_state = {"active": 0, "waived": 0, "baselined": 0, "judged": 0}
        by_kind: dict[str, int] = {}
        defect = 0
        for finding in findings:
            if not finding.non_defect and finding.suppression_state in by_state:
                by_state[finding.suppression_state] += 1
            by_kind[finding.kind] = by_kind.get(finding.kind, 0) + 1
            if not finding.non_defect:
                defect += 1
        return {
            "by_suppression_state": by_state,
            "by_kind": dict(sorted(by_kind.items())),
            "defect": defect,
            "non_defect": len(findings) - defect,
            "resolved_or_unseen": resolved,
            "indeterminate": indeterminate,
        }

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
