# Plainweave Peer Facts (Wardline + Warpline) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship two local-first, advisory peer producers and their frozen `.v1` contracts inside the Plainweave repo: (1) `weft.plainweave.wardline_peer_facts.v1` — surfaces the most-recent `.wardline/*-findings.jsonl` findings (active/waived/baselined/judged, defect/non-defect, resolved-or-unseen) as advisory context; (2) `weft.plainweave.requirements_enrichment.v1` — the Plainweave-owned producer for Warpline's reserved `enrichment.requirements` slot, mapping local entity→requirement resolution into the closed `present|absent|unavailable` vocab. Both are local-only, emit zero verdict vocabulary, and are explicit about degraded state (no silent-clean).

**Architecture:** A new `WardlineAdapter(root)` mirrors `LoomweaveAdapter`: read-only `.wardline/` snapshot load, `health()`, a `_findings_state()` status model, and frozen dataclass returns. It computes resolved/unseen with a scan-identity-manifest PRIMARY path and a path-set heuristic FALLBACK, with every degraded condition reported in-band. The Warpline producer is a `PlainweaveMcpSurface` method that REUSES the existing `_entity_intent_context_item` resolution and maps it to the closed Warpline status vocab. Both are surfaced via the service accessor pattern, two new MCP tools, contract resources, and a `plainweave doctor` health line. Each contract gets a structural no-verdict validator (mirroring `tests/preflight_contract.py`) and a two-layer wire-golden test: the Wardline envelope is byte-pinned (blob-pin + non-circular producer recheck); the Warpline envelope is STRUCTURE-pinned only (producer recheck through the validator, no byte-pin) until the item schema is ratified.

**Tech Stack:** Python 3, dataclasses, Starlette-free (pure service/MCP), pytest, mypy --strict, ruff.

## Global Constraints
- local-first, no live peer calls (live_peer_calls:false); advisory only; NO verdict vocabulary (validator-enforced)
- mypy --strict + ruff clean; `make ci` green; `wardline scan . --fail-on ERROR` clean
- Wardline envelope byte-pinned; Warpline producer structure-pinned until item-schema ratified
- schema strings exactly `weft.plainweave.wardline_peer_facts.v1` / `weft.plainweave.requirements_enrichment.v1`
---

## File Structure

| Path | Create/Modify | Single responsibility |
|---|---|---|
| `src/plainweave/wardline_adapter.py` | Create | Read-only `.wardline/` snapshot load, `health()`, finding classification, resolved/unseen (manifest-primary + heuristic-fallback), and `list_peer_facts()` returning the `weft.plainweave.wardline_peer_facts.v1` *data* dict. |
| `src/plainweave/mcp_surface.py` | Modify | Add `_wardline_adapter()`, `plainweave_wardline_peer_facts_list()`, `plainweave_requirements_enrichment_get()` + `_requirements_enrichment_item()`; register two `MCP_TOOL_METADATA` entries, two `MCP_RESOURCE_URIS`, two `CONTRACT_RESOURCES`. |
| `src/plainweave/mcp_server.py` | Modify | Wrap the two new surface methods as `@mcp.tool()` functions. |
| `src/plainweave/service.py` | Modify | Add `_wardline_adapter()` accessor mirroring `_loomweave_adapter()`. |
| `src/plainweave/cli_commands.py` | Modify | Add `_doctor_wardline_check(root)` and wire it into `run_doctor`'s `checks` list. |
| `tests/wardline_contract.py` | Create | `validate_wardline_peer_facts()` + `assert_no_wardline_verdicts()` (Wardline severity allowlist; no-verdict scan). |
| `tests/warpline_contract.py` | Create | `validate_requirements_enrichment()` + `assert_no_warpline_verdicts()` (no `severity` field; no-verdict scan). |
| `tests/test_wardline_adapter.py` | Create | Unit tests for adapter load/health/classification/resolved-unseen/degrade-codes over fixture scenarios A–D. |
| `tests/test_warpline_requirements_enrichment.py` | Create | Unit tests for the producer status mapping + item shape over a seeded project. |
| `tests/fixtures/wardline/` | Create | Crafted snapshot sets A–D (`.jsonl`) — INPUT to adapter unit tests + the Wardline wire-golden seeding. |
| `tests/fixtures/contracts/wardline/peer-facts.json` | Create | Byte-pinned `schema + data` golden for `weft.plainweave.wardline_peer_facts.v1`. |
| `tests/fixtures/contracts/warpline/requirements-enrichment.json` | Create | Structure-only golden for `weft.plainweave.requirements_enrichment.v1` (NOT byte-pinned). |
| `tests/contracts/test_wardline_peer_facts_wire_golden.py` | Create | Two-layer wire-golden (blob byte-pin + non-circular producer recheck). |
| `tests/contracts/test_requirements_enrichment_wire_golden.py` | Create | Structure-only wire-golden (producer recheck through validator; comment explaining no byte-pin per §11). |
| `tests/contracts/test_contract_fixtures.py` | Modify | Register both contract goldens in `REQUIRED_FIXTURES`; update tool/resource inventory expectations; add fixture-contract tests for both new goldens. |
| `tests/test_mcp_read_surface.py` | Modify | Add the two new tool names to the hardcoded `expected_tools` set (~L108-126). |
| `tests/fixtures/contracts/mcp/tool-inventory.json` | Modify | Add the two new tool entries (sorted). |
| `tests/fixtures/contracts/mcp/resource-inventory.json` | Modify | Add the two new resource URIs. |

> **Note on `tests/test_mcp_server.py:17-18`:** it asserts `{tool.name for tool in tools} == set(MCP_TOOL_METADATA)` and `{resource.uri} == set(MCP_RESOURCE_URIS)`. These AUTO-SYNC and need NO edit, *provided* the `@mcp.tool()` wrapper, the `MCP_TOOL_METADATA` entry, and the `MCP_RESOURCE_URIS` URI all land in the same task. Do not edit that test.

---

## Task A1 — `WardlineAdapter` scaffolding: snapshot discovery + `health()`

**Files**
- Create `src/plainweave/wardline_adapter.py` (new).
- Create `tests/test_wardline_adapter.py` (new).

**Interfaces**

Mirror `LoomweaveAdapter` (real signatures from `src/plainweave/loomweave_adapter.py`):
- `LoomweaveAdapter.__init__(self, root: Path) -> None` sets `self.root = root.resolve()`.
- `LoomweaveAdapter.health(self) -> dict[str, object]` returns `{"adapter_status": {...}, "degraded": [ {code,message}, ... ]}`.
- `LoomweaveAdapter._schema_state(self) -> dict[str, object]` returns `{"status": "available|degraded|unavailable", ...}` and a `degraded` list; `_degraded(self, code, message) -> {"code":code,"message":message}`.

Produces (this task):
- `class WardlineAdapter` with `__init__(self, root: Path) -> None` → `self.root = root.resolve()`, `self.wardline_dir = self.root / ".wardline"`.
- `WardlineAdapter._snapshots(self) -> list[Path]` — timestamp-sorted (ascending) `*-findings.jsonl` under `.wardline/`; sort by filename (the `YYYYMMDDThhmmssZ-findings.jsonl` prefix sorts lexically == chronologically).
- `WardlineAdapter.health(self) -> dict[str, object]` → `{"adapter_status": {...}, "degraded": [...]}`.
- `WardlineAdapter._findings_state(self) -> dict[str, object]` → status model.
- module constant `WARDLINE_DEGRADE_FINDINGS_ABSENT = "wardline_findings_absent"`.

Discipline (byte-pin safety — see A8): degrade messages and `adapter_status` MUST NOT embed absolute paths. Report the relative dir name `".wardline"` only; never `str(self.wardline_dir)`.

**Steps**

- [ ] Write failing test `tests/test_wardline_adapter.py::test_health_reports_unavailable_when_no_wardline_dir`:
  ```python
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
  ```
- [ ] Run it, expect FAIL (module does not exist):
  `uv run pytest tests/test_wardline_adapter.py -q`
- [ ] Minimal impl — create `src/plainweave/wardline_adapter.py`:
  ```python
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
  ```
- [ ] Run it, expect PASS:
  `uv run pytest tests/test_wardline_adapter.py -q`
- [ ] Commit:
  `git add src/plainweave/wardline_adapter.py tests/test_wardline_adapter.py`
  `git commit -m "feat(wardline): WardlineAdapter snapshot discovery + health()"`

---

## Task A2 — Finding load, classification (suppression/kind/non_defect) + engine-record separation

**Files**
- Modify `src/plainweave/wardline_adapter.py` (add `_load_snapshot`, `_classify`, the engine split).
- Modify `tests/test_wardline_adapter.py` (add classification tests).

**Interfaces**

Consumes a real `.wardline` record (observed shape — `.wardline/20260626T054106Z-findings.jsonl`): keys `fingerprint`, `kind` (`defect|metric|fact|classification|suggestion`), `location {path,line_start,line_end,col_start,col_end}`, `maturity`, `message`, `properties`, `qualname`, `related_entities`, `rule_id`, `severity` (`CRITICAL|ERROR|WARN|INFO|NONE`), `suggestion`, `suppression_reason`, `suppression_state` (`active|waived|baselined|judged`). The engine/run-metric record has `location.path == "<engine>"` (observed: many such records, `rule_id` `WLN-ENGINE-METRICS` and `WLN-L3-LOW-RESOLUTION`, all `kind: "metric"`).

Produces:
- `WardlineAdapter._load_snapshot(self, path: Path) -> list[JsonObject]` — parse JSONL, skip blank lines, skip `scan_manifest` records (handled in A3), tolerate a malformed line by skipping it.
- `WardlineAdapter._is_engine_record(self, record: JsonObject) -> bool` — True iff `location.path == "<engine>"`. (Path sentinel is the reliable signal; `rule_id` prefix `WLN-ENGINE-METRICS` is corroborating but real data also tags `WLN-L3-LOW-RESOLUTION` engine records, so the path sentinel governs.)
- `WardlineAdapter._finding_from_record(self, record: JsonObject) -> WardlineFinding` — `non_defect = record["kind"] != "defect"`.

**Steps**

- [ ] Write failing test in `tests/test_wardline_adapter.py`:
  ```python
  import json

  from plainweave.wardline_adapter import WardlineAdapter


  def _write_snapshot(root, name, records):
      wdir = root / ".wardline"
      wdir.mkdir(exist_ok=True)
      (wdir / name).write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")


  def _defect(fp, path="src/a.py", state="active", severity="ERROR", reason=None):
      return {
          "fingerprint": fp, "kind": "defect", "rule_id": "WLN-TAINT-1",
          "location": {"path": path, "line_start": 1, "line_end": 1, "col_start": 0, "col_end": 1},
          "maturity": "stable", "message": "tainted sink", "properties": {}, "qualname": "a.f",
          "related_entities": [], "severity": severity, "suggestion": None,
          "suppression_reason": reason, "suppression_state": state,
      }


  def _engine():
      return {
          "fingerprint": "eng1", "kind": "metric", "rule_id": "WLN-ENGINE-METRICS",
          "location": {"path": "<engine>", "line_start": None, "line_end": None, "col_start": None, "col_end": None},
          "maturity": "stable", "message": "L3 resolver run metrics", "properties": {"cache_hit_rate": 0.0},
          "qualname": None, "related_entities": [], "severity": "NONE", "suggestion": None,
          "suppression_reason": None, "suppression_state": "active",
      }


  def test_engine_record_is_separated_from_entity_findings(tmp_path):
      _write_snapshot(tmp_path, "20260101T000000Z-findings.jsonl", [_defect("d1"), _engine()])
      adapter = WardlineAdapter(tmp_path)
      records = adapter._load_snapshot((tmp_path / ".wardline" / "20260101T000000Z-findings.jsonl"))
      entity = [r for r in records if not adapter._is_engine_record(r)]
      engine = [r for r in records if adapter._is_engine_record(r)]
      assert len(entity) == 1 and len(engine) == 1
      finding = adapter._finding_from_record(entity[0])
      assert finding.non_defect is False
      assert finding.suppression_state == "active"


  def test_non_defect_kinds_are_tagged_non_defect(tmp_path):
      rec = _defect("c1")
      rec["kind"] = "classification"
      _write_snapshot(tmp_path, "20260101T000000Z-findings.jsonl", [rec])
      adapter = WardlineAdapter(tmp_path)
      [record] = adapter._load_snapshot((tmp_path / ".wardline" / "20260101T000000Z-findings.jsonl"))
      assert adapter._finding_from_record(record).non_defect is True
  ```
- [ ] Run it, expect FAIL (`_load_snapshot` / `_is_engine_record` / `_finding_from_record` absent):
  `uv run pytest tests/test_wardline_adapter.py -k "engine_record or non_defect" -q`
- [ ] Minimal impl — add to `src/plainweave/wardline_adapter.py`:
  ```python
  import json

  NON_DEFECT_KINDS = frozenset({"metric", "fact", "classification", "suggestion"})

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
              non_defect=kind != "defect",
              severity=str(record.get("severity")),
              suppression_state=str(record.get("suppression_state")),
              suppression_reason=reason if isinstance(reason, str) else None,
              location=dict(location) if isinstance(location, dict) else {"path": None},
              qualname=qualname if isinstance(qualname, str) else None,
              message=str(record.get("message")),
          )
  ```
- [ ] Run it, expect PASS:
  `uv run pytest tests/test_wardline_adapter.py -k "engine_record or non_defect" -q`
- [ ] Commit:
  `git add src/plainweave/wardline_adapter.py tests/test_wardline_adapter.py`
  `git commit -m "feat(wardline): finding classification + engine-record separation"`

---

## Task A3 — Resolved/unseen: scan-identity manifest PRIMARY (exact scope)

**Files**
- Modify `src/plainweave/wardline_adapter.py` (add manifest read + the primary diff).
- Modify `tests/test_wardline_adapter.py`.

**Interfaces**

Consumes the `scan_manifest` record (agreed contract — `docs/handoffs/2026-06-27-wardline-scan-identity-metadata.md` §"What to build"): `{"kind":"scan_manifest","scan_id":...,"started_at":...,"commit":...,"ruleset_id":...,"scope":{"selector":...,"covered_paths":[...]}}`.

Spec §5.3 PRIMARY algorithm:
```
covered = latest.scan_manifest.scope.covered_paths
for prior record p with p.fingerprint not in latest_fps:
    if p.location.path in covered: -> resolved_or_unseen
    else:                          -> indeterminate
if latest.ruleset_id != prior.ruleset_id: degraded += wardline_ruleset_mismatch
```

Produces:
- `WardlineAdapter._read_manifest(self, path: Path) -> JsonObject | None` — first `scan_manifest` record in the file, else None.
- `WardlineAdapter._covered_paths(self, manifest: JsonObject | None) -> set[str] | None` — `manifest["scope"]["covered_paths"]` as a set, else None (None == "no manifest", routes to A4 fallback).
- `WardlineAdapter._resolved_unseen(self, latest, prior, *, covered, degraded) -> tuple[list[JsonObject], int]` — returns `(resolved_or_unseen_items, indeterminate_count)`; appends `wardline_ruleset_mismatch` to `degraded` when ruleset ids differ. Each item is `{"fingerprint","rule_id","location"}`.

Module constants: `WARDLINE_DEGRADE_RULESET_MISMATCH = "wardline_ruleset_mismatch"`.

**Steps**

- [ ] Write failing test in `tests/test_wardline_adapter.py`:
  ```python
  def _manifest(covered, ruleset="rs@1"):
      return {
          "kind": "scan_manifest", "scan_id": "s1", "started_at": "2026-01-01T00:00:00Z",
          "commit": "abc", "ruleset_id": ruleset, "scope": {"selector": "src", "covered_paths": covered},
      }


  def test_manifest_primary_resolved_when_path_recovered(tmp_path):
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
      degraded = []
      resolved, indeterminate = adapter._resolved_unseen(
          latest_records, prior_records, covered=covered, degraded=degraded,
          prior_manifest=adapter._read_manifest(snaps[-2]), latest_manifest=adapter._read_manifest(snaps[-1]),
      )
      assert [item["fingerprint"] for item in resolved] == ["d1"]
      assert indeterminate == 0


  def test_manifest_primary_indeterminate_when_path_not_covered(tmp_path):
      prior = [_manifest(["src/a.py", "src/b.py"]), _defect("d2", path="src/b.py")]
      latest = [_manifest(["src/a.py"])]  # b.py no longer scanned -> indeterminate, NOT resolved
      _write_snapshot(tmp_path, "20260101T000000Z-findings.jsonl", prior)
      _write_snapshot(tmp_path, "20260102T000000Z-findings.jsonl", latest)
      adapter = WardlineAdapter(tmp_path)
      snaps = adapter._snapshots()
      covered = adapter._covered_paths(adapter._read_manifest(snaps[-1]))
      degraded = []
      resolved, indeterminate = adapter._resolved_unseen(
          adapter._load_snapshot(snaps[-1]), adapter._load_snapshot(snaps[-2]),
          covered=covered, degraded=degraded,
          prior_manifest=adapter._read_manifest(snaps[-2]), latest_manifest=adapter._read_manifest(snaps[-1]),
      )
      assert resolved == []
      assert indeterminate == 1


  def test_manifest_ruleset_mismatch_is_flagged(tmp_path):
      prior = [_manifest(["src/a.py"], ruleset="rs@1"), _defect("d1", path="src/a.py")]
      latest = [_manifest(["src/a.py"], ruleset="rs@2")]
      _write_snapshot(tmp_path, "20260101T000000Z-findings.jsonl", prior)
      _write_snapshot(tmp_path, "20260102T000000Z-findings.jsonl", latest)
      adapter = WardlineAdapter(tmp_path)
      snaps = adapter._snapshots()
      degraded = []
      adapter._resolved_unseen(
          adapter._load_snapshot(snaps[-1]), adapter._load_snapshot(snaps[-2]),
          covered={"src/a.py"}, degraded=degraded,
          prior_manifest=adapter._read_manifest(snaps[-2]), latest_manifest=adapter._read_manifest(snaps[-1]),
      )
      assert any(d["code"] == "wardline_ruleset_mismatch" for d in degraded)
  ```
- [ ] Run it, expect FAIL:
  `uv run pytest tests/test_wardline_adapter.py -k "manifest" -q`
- [ ] Minimal impl — add to `src/plainweave/wardline_adapter.py`:
  ```python
  WARDLINE_DEGRADE_RULESET_MISMATCH = "wardline_ruleset_mismatch"

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
          covered: set[str],
          degraded: list[JsonObject],
          prior_manifest: JsonObject | None,
          latest_manifest: JsonObject | None,
      ) -> tuple[list[JsonObject], int]:
          latest_fps = {str(r.get("fingerprint")) for r in latest if not self._is_engine_record(r)}
          resolved: list[JsonObject] = []
          indeterminate = 0
          for record in prior:
              if self._is_engine_record(record):
                  continue
              if str(record.get("fingerprint")) in latest_fps:
                  continue
              path = self._record_path(record)
              if path is not None and path in covered:
                  resolved.append(
                      {
                          "fingerprint": str(record.get("fingerprint")),
                          "rule_id": str(record.get("rule_id")),
                          "location": dict(record.get("location")) if isinstance(record.get("location"), dict) else {},
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
  ```
  (The ruleset-mismatch check only fires when both manifests are present and differ; when either is None it is the A4 heuristic path, which sets a different degrade code.)
- [ ] Run it, expect PASS:
  `uv run pytest tests/test_wardline_adapter.py -k "manifest" -q`
- [ ] Commit:
  `git add src/plainweave/wardline_adapter.py tests/test_wardline_adapter.py`
  `git commit -m "feat(wardline): resolved/unseen manifest-primary exact-scope diff"`

---

## Task A4 — Resolved/unseen: path-set heuristic FALLBACK + all degrade codes

**Files**
- Modify `src/plainweave/wardline_adapter.py` (add `_scope_for_diff`, jaccard, single-snapshot/scope-mismatch/scan-identity-absent degrade codes).
- Modify `tests/test_wardline_adapter.py`.

**Interfaces**

Spec §5.3 FALLBACK (manifest absent on either snapshot):
```
covered ≈ latest_paths = { r.location.path for r in latest if path not in (None, "<engine>") }
... same resolved/indeterminate split ...
degraded += wardline_scan_identity_absent
```
Degrade rules (in-band, both paths):
- `< 2 snapshots` → resolved/unseen unavailable; `wardline_single_snapshot`.
- prior fingerprint path outside `covered` → counted indeterminate; `wardline_scope_mismatch` carrying `detail.jaccard` (overlap of the two scopes).
- no `.wardline` dir / no findings file → `freshness: unavailable`; `wardline_findings_absent`.

Produces:
- module constants `WARDLINE_DEGRADE_SINGLE_SNAPSHOT = "wardline_single_snapshot"`, `WARDLINE_DEGRADE_SCOPE_MISMATCH = "wardline_scope_mismatch"`, `WARDLINE_DEGRADE_SCAN_IDENTITY_ABSENT = "wardline_scan_identity_absent"`.
- `WardlineAdapter._latest_path_set(self, records) -> set[str]` — non-None, non-`<engine>` `location.path` values.
- `WardlineAdapter._jaccard(self, a: set[str], b: set[str]) -> float`.
- `WardlineAdapter._scope_for_diff(self, latest, prior, latest_manifest, prior_manifest, degraded) -> set[str]` — returns `covered` (manifest paths if BOTH manifests present, else heuristic `_latest_path_set(latest)` + appends `wardline_scan_identity_absent`); also appends `wardline_scope_mismatch` (with jaccard) when any prior path falls outside `covered`.

Byte-pin safety: `wardline_scope_mismatch.detail.jaccard` is a FLOAT. The A8 byte-golden scenario MUST NOT trigger it (scenario A is same-scope, jaccard absent). Float-bearing degrades are exercised here in A4 unit tests only.

**Steps**

- [ ] Write failing test in `tests/test_wardline_adapter.py`:
  ```python
  def test_fallback_flags_scan_identity_absent_when_no_manifest(tmp_path):
      _write_snapshot(tmp_path, "20260101T000000Z-findings.jsonl", [_defect("d1", path="src/a.py")])
      _write_snapshot(tmp_path, "20260102T000000Z-findings.jsonl", [])  # d1 gone, no manifest
      # latest has no findings -> latest_path_set empty -> d1 path not covered -> indeterminate + scope_mismatch
      adapter = WardlineAdapter(tmp_path)
      snaps = adapter._snapshots()
      degraded = []
      covered = adapter._scope_for_diff(
          adapter._load_snapshot(snaps[-1]), adapter._load_snapshot(snaps[-2]),
          latest_manifest=None, prior_manifest=None, degraded=degraded,
      )
      assert covered == set()
      assert any(d["code"] == "wardline_scan_identity_absent" for d in degraded)
      assert any(d["code"] == "wardline_scope_mismatch" for d in degraded)
      mismatch = next(d for d in degraded if d["code"] == "wardline_scope_mismatch")
      assert isinstance(mismatch["detail"]["jaccard"], float)


  def test_fallback_resolved_when_same_path_set(tmp_path):
      _write_snapshot(tmp_path, "20260101T000000Z-findings.jsonl",
                      [_defect("d1", path="src/a.py"), _defect("keep", path="src/a.py")])
      _write_snapshot(tmp_path, "20260102T000000Z-findings.jsonl", [_defect("keep", path="src/a.py")])
      adapter = WardlineAdapter(tmp_path)
      snaps = adapter._snapshots()
      degraded = []
      covered = adapter._scope_for_diff(
          adapter._load_snapshot(snaps[-1]), adapter._load_snapshot(snaps[-2]),
          latest_manifest=None, prior_manifest=None, degraded=degraded,
      )
      assert covered == {"src/a.py"}
      assert not any(d["code"] == "wardline_scope_mismatch" for d in degraded)
      assert any(d["code"] == "wardline_scan_identity_absent" for d in degraded)
  ```
- [ ] Run it, expect FAIL:
  `uv run pytest tests/test_wardline_adapter.py -k "fallback" -q`
- [ ] Minimal impl — add to `src/plainweave/wardline_adapter.py`:
  ```python
  WARDLINE_DEGRADE_SINGLE_SNAPSHOT = "wardline_single_snapshot"
  WARDLINE_DEGRADE_SCOPE_MISMATCH = "wardline_scope_mismatch"
  WARDLINE_DEGRADE_SCAN_IDENTITY_ABSENT = "wardline_scan_identity_absent"

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
  ```
- [ ] Run it, expect PASS:
  `uv run pytest tests/test_wardline_adapter.py -k "fallback" -q`
- [ ] Commit:
  `git add src/plainweave/wardline_adapter.py tests/test_wardline_adapter.py`
  `git commit -m "feat(wardline): resolved/unseen heuristic fallback + degrade codes"`

---

## Task A5 — `weft.plainweave.wardline_peer_facts.v1` data assembly (`list_peer_facts`)

**Files**
- Modify `src/plainweave/wardline_adapter.py` (add `list_peer_facts`, `_summary`, freshness, single-snapshot wiring).
- Modify `tests/test_wardline_adapter.py`.

**Interfaces**

Produces the §5.4 `data` dict (NOT the envelope — the surface in A9 wraps via `success_envelope`):
- `WardlineAdapter.list_peer_facts(self, *, limit: int = 50, offset: int = 0) -> JsonObject` returning:
  ```
  {
    "source": {"snapshot": "<basename|null>", "snapshot_count": N, "prior": "<basename|null>"},
    "freshness": "current|stale|unavailable",
    "facts": [ {fingerprint,rule_id,kind,non_defect,severity,suppression_state,suppression_reason,location,qualname,message} ],
    "resolved_or_unseen": [ {fingerprint,rule_id,location} ],
    "engine_metrics": [ {<verbatim engine record>} ],
    "summary": {"by_suppression_state": {active,waived,baselined,judged}, "by_kind": {...},
                "defect": N, "non_defect": N, "resolved_or_unseen": N, "indeterminate": N},
    "degraded": [ {code,message[,detail]} ],
    "authority_boundary": {"local_only": true, "live_peer_calls": false,
                           "governance_verdicts": false, "trust_policy_owner": "wardline"},
    "notes": [ "..." ]
  }
  ```

Byte-pin / no-silent-clean discipline:
- `source.snapshot` / `source.prior` are **basenames** (`path.name`), never absolute paths.
- `< 2 snapshots`: `resolved_or_unseen = []`, `summary.resolved_or_unseen = 0`, `summary.indeterminate = 0`, append `wardline_single_snapshot` degrade, and a `notes` entry "resolved/unseen unavailable: a single snapshot cannot diff." `freshness` stays `current` for the present snapshot's facts (facts ARE present); resolved/unseen is the unavailable axis, reported via degraded — never an empty-as-clean.
- `0 snapshots`: `freshness = "unavailable"`, empty facts, `wardline_findings_absent` degrade, `notes` entry. Empty-as-unavailable, never empty-as-clean.
- `summary.by_suppression_state` always carries all four keys `{active,waived,baselined,judged}` (0 when absent) so "nothing waived" reads as an explicit 0, not a missing key.
- `limit`/`offset` slice `facts` for transport; `summary` always reflects the FULL finding set. If `facts` is truncated, append a `notes` entry "facts truncated to page; N total". (A8's golden scenario keeps facts under the default limit so no truncation note appears and bytes stay stable.)

**Steps**

- [ ] Write failing test in `tests/test_wardline_adapter.py`:
  ```python
  def test_list_peer_facts_single_snapshot_marks_resolved_unavailable(tmp_path):
      _write_snapshot(tmp_path, "20260101T000000Z-findings.jsonl",
                      [_defect("d1", state="active"), _defect("w1", state="waived"), _engine()])
      data = WardlineAdapter(tmp_path).list_peer_facts()
      assert data["source"]["snapshot"] == "20260101T000000Z-findings.jsonl"
      assert data["source"]["prior"] is None
      assert "/" not in data["source"]["snapshot"]
      assert data["summary"]["by_suppression_state"] == {"active": 1, "waived": 1, "baselined": 0, "judged": 0}
      assert data["summary"]["defect"] == 2 and data["summary"]["non_defect"] == 0
      assert data["resolved_or_unseen"] == []
      assert any(d["code"] == "wardline_single_snapshot" for d in data["degraded"])
      assert len(data["engine_metrics"]) == 1
      assert data["authority_boundary"]["trust_policy_owner"] == "wardline"


  def test_list_peer_facts_unavailable_when_absent(tmp_path):
      data = WardlineAdapter(tmp_path).list_peer_facts()
      assert data["freshness"] == "unavailable"
      assert data["facts"] == []
      assert any(d["code"] == "wardline_findings_absent" for d in data["degraded"])
  ```
- [ ] Run it, expect FAIL:
  `uv run pytest tests/test_wardline_adapter.py -k "list_peer_facts" -q`
- [ ] Minimal impl — add to `src/plainweave/wardline_adapter.py`:
  ```python
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
                  latest_records, prior_records,
                  latest_manifest=latest_manifest, prior_manifest=prior_manifest, degraded=degraded,
              )
              resolved, indeterminate = self._resolved_unseen(
                  latest_records, prior_records, covered=covered, degraded=degraded,
                  prior_manifest=prior_manifest, latest_manifest=latest_manifest,
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
              if finding.suppression_state in by_state:
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
  ```
- [ ] Run it, expect PASS:
  `uv run pytest tests/test_wardline_adapter.py -k "list_peer_facts" -q`
- [ ] Commit:
  `git add src/plainweave/wardline_adapter.py tests/test_wardline_adapter.py`
  `git commit -m "feat(wardline): assemble wardline_peer_facts.v1 data payload"`

---

## Task A6 — `tests/wardline_contract.py` validator + no-verdict

**Files**
- Create `tests/wardline_contract.py` (new).
- Create test `tests/contracts/test_wardline_contract.py` (new) OR add a test to `tests/test_wardline_adapter.py` that runs the validator over a live payload.

**Interfaces**

Mirror `tests/preflight_contract.py` (`validate_preflight_facts`, `assert_no_preflight_verdicts` — verdict key/value scan). KEY DIFFERENCE from preflight: Wardline `severity` is `CRITICAL|ERROR|WARN|INFO|NONE`, so the no-verdict scan MUST use a Wardline severity allowlist; reusing `PREFLIGHT_SEVERITIES` would reject the legitimate `CRITICAL`/`ERROR` values.

Produces:
```python
WARDLINE_SEVERITIES = {"CRITICAL", "ERROR", "WARN", "INFO", "NONE"}
WARDLINE_SUPPRESSION_STATES = {"active", "waived", "baselined", "judged"}
WARDLINE_KINDS = {"defect", "metric", "fact", "classification", "suggestion"}
WARDLINE_FRESHNESS = {"current", "stale", "unavailable"}
WARDLINE_DATA_KEYS = {"source", "freshness", "facts", "resolved_or_unseen",
                      "engine_metrics", "summary", "degraded", "authority_boundary", "notes"}
def assert_no_wardline_verdicts(value: object) -> None: ...
def validate_wardline_peer_facts(payload: dict[str, Any]) -> None: ...
```

**Steps**

- [ ] Write failing test `tests/contracts/test_wardline_contract.py`:
  ```python
  from __future__ import annotations

  import json
  from pathlib import Path

  import pytest

  from plainweave.wardline_adapter import WardlineAdapter
  from tests.wardline_contract import assert_no_wardline_verdicts, validate_wardline_peer_facts


  def test_validator_accepts_live_payload(tmp_path: Path) -> None:
      wdir = tmp_path / ".wardline"
      wdir.mkdir()
      record = {
          "fingerprint": "d1", "kind": "defect", "rule_id": "WLN-1",
          "location": {"path": "src/a.py", "line_start": 1, "line_end": 1, "col_start": 0, "col_end": 1},
          "maturity": "stable", "message": "m", "properties": {}, "qualname": "a.f",
          "related_entities": [], "severity": "CRITICAL", "suggestion": None,
          "suppression_reason": None, "suppression_state": "active",
      }
      (wdir / "20260101T000000Z-findings.jsonl").write_text(json.dumps(record), encoding="utf-8")
      data = WardlineAdapter(tmp_path).list_peer_facts()
      validate_wardline_peer_facts(data)  # must not raise; CRITICAL is a valid wardline severity


  def test_validator_rejects_verdict_token() -> None:
      with pytest.raises(AssertionError):
          assert_no_wardline_verdicts({"facts": [{"severity": "blocked"}]})
  ```
- [ ] Run it, expect FAIL (module absent):
  `uv run pytest tests/contracts/test_wardline_contract.py -q`
- [ ] Minimal impl — create `tests/wardline_contract.py`:
  ```python
  """Single source of truth for the ``weft.plainweave.wardline_peer_facts.v1`` shape.

  Mirrors ``tests/preflight_contract.py`` so the committed golden and the live
  producer cannot drift. Wardline severity is CRITICAL|ERROR|WARN|INFO|NONE, so the
  no-verdict scan uses a Wardline-specific severity allowlist (NOT the preflight one).
  """

  from __future__ import annotations

  from typing import Any

  WARDLINE_SEVERITIES = {"CRITICAL", "ERROR", "WARN", "INFO", "NONE"}
  WARDLINE_SUPPRESSION_STATES = {"active", "waived", "baselined", "judged"}
  WARDLINE_KINDS = {"defect", "metric", "fact", "classification", "suggestion"}
  WARDLINE_FRESHNESS = {"current", "stale", "unavailable"}
  WARDLINE_DATA_KEYS = {
      "source", "freshness", "facts", "resolved_or_unseen",
      "engine_metrics", "summary", "degraded", "authority_boundary", "notes",
  }
  WARDLINE_FACT_KEYS = {
      "fingerprint", "rule_id", "kind", "non_defect", "severity",
      "suppression_state", "suppression_reason", "location", "qualname", "message",
  }
  WARDLINE_SUMMARY_KEYS = {
      "by_suppression_state", "by_kind", "defect", "non_defect", "resolved_or_unseen", "indeterminate",
  }
  WARDLINE_AUTHORITY_KEYS = {"local_only", "live_peer_calls", "governance_verdicts", "trust_policy_owner"}

  _VERDICT_KEYS = {"allow", "allowed", "block", "blocked", "verdict", "decision", "gate", "enforcement"}
  _VERDICT_VALUE_TOKENS = {
      "allow", "allowed", "block", "blocked", "block_candidate", "deny", "denied",
      "approved", "rejected", "pass_fail", "verdict",
  }


  def assert_no_wardline_verdicts(value: object) -> None:
      """Reject gate semantics by key, by severity value, and by string value."""
      if isinstance(value, dict):
          assert _VERDICT_KEYS.isdisjoint(value), f"verdict-like key in {sorted(value)}"
          severity = value.get("severity")
          if isinstance(severity, str):
              assert severity in WARDLINE_SEVERITIES, f"non-wardline severity value: {severity}"
          for item in value.values():
              assert_no_wardline_verdicts(item)
      elif isinstance(value, list):
          for item in value:
              assert_no_wardline_verdicts(item)
      elif isinstance(value, str):
          assert value.strip().lower() not in _VERDICT_VALUE_TOKENS, f"verdict-like value: {value}"


  def validate_wardline_peer_facts(payload: dict[str, Any]) -> None:
      """Structurally validate a wardline-peer-facts *data* payload (no envelope wrapper)."""
      assert set(payload) == WARDLINE_DATA_KEYS, f"section drift: {sorted(payload)}"
      assert payload["freshness"] in WARDLINE_FRESHNESS
      assert set(payload["source"]) == {"snapshot", "snapshot_count", "prior"}
      snapshot = payload["source"]["snapshot"]
      assert snapshot is None or "/" not in snapshot, "source.snapshot must be a basename, not a path"

      facts = payload["facts"]
      assert isinstance(facts, list)
      for fact in facts:
          assert set(fact) == WARDLINE_FACT_KEYS, f"fact key drift: {sorted(fact)}"
          assert fact["kind"] in WARDLINE_KINDS
          assert fact["severity"] in WARDLINE_SEVERITIES
          assert fact["suppression_state"] in WARDLINE_SUPPRESSION_STATES
          assert fact["non_defect"] == (fact["kind"] != "defect")
          assert "path" in fact["location"]

      for item in payload["resolved_or_unseen"]:
          assert set(item) == {"fingerprint", "rule_id", "location"}

      summary = payload["summary"]
      assert set(summary) == WARDLINE_SUMMARY_KEYS
      assert set(summary["by_suppression_state"]) == WARDLINE_SUPPRESSION_STATES
      assert summary["defect"] + summary["non_defect"] >= 0

      for entry in payload["degraded"]:
          assert {"code", "message"}.issubset(entry)

      authority = payload["authority_boundary"]
      assert set(authority) == WARDLINE_AUTHORITY_KEYS
      assert authority["governance_verdicts"] is False
      assert authority["live_peer_calls"] is False
      assert authority["local_only"] is True
      assert authority["trust_policy_owner"] == "wardline"

      assert isinstance(payload["notes"], list)
      assert isinstance(payload["engine_metrics"], list)

      assert_no_wardline_verdicts(payload)
  ```
- [ ] Run it, expect PASS:
  `uv run pytest tests/contracts/test_wardline_contract.py -q`
- [ ] Also wire it into the adapter unit tests: add `validate_wardline_peer_facts(WardlineAdapter(tmp_path).list_peer_facts())` to the A5 happy-path tests so the validator runs over live output. Run `uv run pytest tests/test_wardline_adapter.py -q`, expect PASS.
- [ ] Commit:
  `git add tests/wardline_contract.py tests/contracts/test_wardline_contract.py tests/test_wardline_adapter.py`
  `git commit -m "test(wardline): wardline_peer_facts.v1 structural validator + no-verdict scan"`

---

## Task A7 — Fixture snapshot sets A–D under `tests/fixtures/wardline/`

**Files**
- Create `tests/fixtures/wardline/scenario_a/` (≥2 snapshots, same-scope, manifest present, one resolution).
- Create `tests/fixtures/wardline/scenario_b/` (scope mismatch — prior path absent from latest).
- Create `tests/fixtures/wardline/scenario_c/` (single snapshot).
- Create `tests/fixtures/wardline/scenario_d/` (full state matrix: waived/baselined/judged + defect + non-defect).
- Modify `tests/test_wardline_adapter.py` (add scenario-driven tests + a `_seed_scenario(tmp_path, name)` helper that copies a fixture dir into `tmp_path/.wardline`).

**Interfaces**

Each scenario dir holds `*-findings.jsonl` files named with sortable `YYYYMMDDThhmmssZ-findings.jsonl` prefixes. Scenario A additionally carries a `scan_manifest` record in each snapshot (manifest-primary path). Scenarios B/D are crafted to exercise the FALLBACK (no manifest) so the `wardline_scan_identity_absent` degrade is asserted. Real snapshots carry NO manifest (verified), so the fallback scenarios model today's data; A models the post-integration data.

**Steps**

- [ ] Create `tests/fixtures/wardline/scenario_a/20260101T000000Z-findings.jsonl` (prior):
  ```
  {"kind": "scan_manifest", "scan_id": "a-1", "started_at": "2026-01-01T00:00:00Z", "commit": "c1", "ruleset_id": "rs@1", "scope": {"selector": "src", "covered_paths": ["src/a.py", "src/b.py"]}}
  {"fingerprint": "fa-resolved", "kind": "defect", "rule_id": "WLN-TAINT", "location": {"path": "src/a.py", "line_start": 4, "line_end": 4, "col_start": 0, "col_end": 3}, "maturity": "stable", "message": "tainted", "properties": {}, "qualname": "a.f", "related_entities": [], "severity": "ERROR", "suggestion": null, "suppression_reason": null, "suppression_state": "active"}
  {"fingerprint": "fa-keep", "kind": "defect", "rule_id": "WLN-TAINT", "location": {"path": "src/b.py", "line_start": 9, "line_end": 9, "col_start": 0, "col_end": 3}, "maturity": "stable", "message": "tainted b", "properties": {}, "qualname": "b.g", "related_entities": [], "severity": "WARN", "suggestion": null, "suppression_reason": null, "suppression_state": "active"}
  ```
- [ ] Create `tests/fixtures/wardline/scenario_a/20260102T000000Z-findings.jsonl` (latest — `fa-resolved` gone, same covered scope):
  ```
  {"kind": "scan_manifest", "scan_id": "a-2", "started_at": "2026-01-02T00:00:00Z", "commit": "c2", "ruleset_id": "rs@1", "scope": {"selector": "src", "covered_paths": ["src/a.py", "src/b.py"]}}
  {"fingerprint": "fa-keep", "kind": "defect", "rule_id": "WLN-TAINT", "location": {"path": "src/b.py", "line_start": 9, "line_end": 9, "col_start": 0, "col_end": 3}, "maturity": "stable", "message": "tainted b", "properties": {}, "qualname": "b.g", "related_entities": [], "severity": "WARN", "suggestion": null, "suppression_reason": null, "suppression_state": "active"}
  ```
- [ ] Create scenario_b (no manifest; prior has `src/c.py`, latest only scans `src/a.py`):
  - `20260101T000000Z-findings.jsonl`: one finding `fb-outside` at `src/c.py` + one `fb-keep` at `src/a.py`.
  - `20260102T000000Z-findings.jsonl`: only `fb-keep` at `src/a.py`. (`fb-outside` gone, but `src/c.py` not in latest path-set → indeterminate + `wardline_scope_mismatch`.)
- [ ] Create scenario_c (single snapshot): `20260101T000000Z-findings.jsonl` with two active defects, no second file.
- [ ] Create scenario_d (no manifest; full state matrix) `20260101T000000Z-findings.jsonl`:
  ```
  {"fingerprint": "fd-active", "kind": "defect", "rule_id": "WLN-1", "location": {"path": "src/a.py", "line_start": 1, "line_end": 1, "col_start": 0, "col_end": 1}, "maturity": "stable", "message": "active defect", "properties": {}, "qualname": "a.f", "related_entities": [], "severity": "ERROR", "suggestion": null, "suppression_reason": null, "suppression_state": "active"}
  {"fingerprint": "fd-waived", "kind": "defect", "rule_id": "WLN-2", "location": {"path": "src/a.py", "line_start": 2, "line_end": 2, "col_start": 0, "col_end": 1}, "maturity": "stable", "message": "waived defect", "properties": {}, "qualname": "a.g", "related_entities": [], "severity": "WARN", "suggestion": null, "suppression_reason": "accepted risk", "suppression_state": "waived"}
  {"fingerprint": "fd-baselined", "kind": "defect", "rule_id": "WLN-3", "location": {"path": "src/a.py", "line_start": 3, "line_end": 3, "col_start": 0, "col_end": 1}, "maturity": "stable", "message": "baselined defect", "properties": {}, "qualname": "a.h", "related_entities": [], "severity": "INFO", "suggestion": null, "suppression_reason": "pre-existing", "suppression_state": "baselined"}
  {"fingerprint": "fd-judged", "kind": "defect", "rule_id": "WLN-4", "location": {"path": "src/a.py", "line_start": 4, "line_end": 4, "col_start": 0, "col_end": 1}, "maturity": "stable", "message": "judged defect", "properties": {}, "qualname": "a.i", "related_entities": [], "severity": "CRITICAL", "suggestion": null, "suppression_reason": "agent-judged false positive", "suppression_state": "judged"}
  {"fingerprint": "fd-fact", "kind": "fact", "rule_id": "WLN-FACT", "location": {"path": "src/a.py", "line_start": 5, "line_end": 5, "col_start": 0, "col_end": 1}, "maturity": "stable", "message": "non-defect fact", "properties": {}, "qualname": "a.j", "related_entities": [], "severity": "NONE", "suggestion": null, "suppression_reason": null, "suppression_state": "active"}
  ```
- [ ] Write failing test in `tests/test_wardline_adapter.py`:
  ```python
  import shutil

  FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "wardline"


  def _seed_scenario(tmp_path: Path, name: str) -> Path:
      dest = tmp_path / ".wardline"
      shutil.copytree(FIXTURE_ROOT / name, dest)
      return tmp_path


  def test_scenario_a_resolution(tmp_path):
      data = WardlineAdapter(_seed_scenario(tmp_path, "scenario_a")).list_peer_facts()
      assert [r["fingerprint"] for r in data["resolved_or_unseen"]] == ["fa-resolved"]
      assert data["summary"]["indeterminate"] == 0
      assert not any(d["code"] == "wardline_scan_identity_absent" for d in data["degraded"])
      validate_wardline_peer_facts(data)


  def test_scenario_b_scope_mismatch(tmp_path):
      data = WardlineAdapter(_seed_scenario(tmp_path, "scenario_b")).list_peer_facts()
      assert data["resolved_or_unseen"] == []
      assert data["summary"]["indeterminate"] == 1
      assert any(d["code"] == "wardline_scope_mismatch" for d in data["degraded"])
      assert any(d["code"] == "wardline_scan_identity_absent" for d in data["degraded"])
      validate_wardline_peer_facts(data)


  def test_scenario_c_single_snapshot(tmp_path):
      data = WardlineAdapter(_seed_scenario(tmp_path, "scenario_c")).list_peer_facts()
      assert any(d["code"] == "wardline_single_snapshot" for d in data["degraded"])
      validate_wardline_peer_facts(data)


  def test_scenario_d_state_matrix(tmp_path):
      data = WardlineAdapter(_seed_scenario(tmp_path, "scenario_d")).list_peer_facts()
      assert data["summary"]["by_suppression_state"] == {"active": 1, "waived": 1, "baselined": 1, "judged": 1}
      assert data["summary"]["non_defect"] == 1 and data["summary"]["defect"] == 4
      validate_wardline_peer_facts(data)
  ```
- [ ] Run it, expect PASS (adapter logic already exists from A1–A6):
  `uv run pytest tests/test_wardline_adapter.py -k "scenario" -q`
- [ ] Commit:
  `git add tests/fixtures/wardline tests/test_wardline_adapter.py`
  `git commit -m "test(wardline): fixture snapshot scenarios A-D for peer facts"`

---

## Task A8 — Byte-pinned golden + two-layer wire-golden test (Wardline)

**Files**
- Create `tests/fixtures/contracts/wardline/peer-facts.json` (byte-pinned `schema + data` golden).
- Create `tests/contracts/test_wardline_peer_facts_wire_golden.py` (new).

**Interfaces**

Mirror `tests/contracts/test_preflight_facts_wire_golden.py` exactly: Layer-1 `test_golden_matches_blob_pin` (git-blob SHA byte-pin) + non-circular `test_golden_matches_live_producer` (regenerate from the REAL producer over a seeded tmp project; assert `generated_at`/`producer.version` LIVE before normalizing, then deep-equal). The producer here is the MCP surface tool `PlainweaveMcpSurface.plainweave_wardline_peer_facts_list()` (built in A9). The golden vendors `{"schema": envelope["schema"], **envelope["data"]}`.

Byte-pin determinism (advisor-flagged): the seed copies `tests/fixtures/wardline/scenario_a` into `tmp/.wardline` — scenario A is same-scope with a manifest, so it emits NO `wardline_scan_identity_absent` note, NO `wardline_scope_mismatch` (no float jaccard), basename-only `source.snapshot`, and a fact count under the default limit (no truncation note). Those properties are what make the bytes stable.

> **Sequencing note:** this test depends on the A9 surface tool. Write the test now (it will FAIL importing/calling the not-yet-existing tool), implement A9, then return to compute the blob SHA. Alternatively run A9 first; either order ends with both green. The steps below assume A9 lands immediately after.

**Steps**

- [ ] Create `tests/contracts/test_wardline_peer_facts_wire_golden.py`:
  ```python
  """Plainweave-authored ``weft.plainweave.wardline_peer_facts.v1`` envelope, frozen
  to a vendored byte golden with a non-circular producer-source recheck.

  Two layers, mirroring ``test_preflight_facts_wire_golden.py``:
  * Layer-1 (``test_golden_matches_blob_pin``): git-blob byte-pin; any silent wire
    edit reds the default suite. On its own this is CIRCULAR.
  * Producer recheck (``test_golden_matches_live_producer``): re-invokes the REAL
    producer (``plainweave_wardline_peer_facts_list``) over scenario_a seeded into
    ``tmp/.wardline`` and asserts the regenerated ``schema + data`` EQUALS the golden.

  Scenario A is same-scope WITH a manifest, so the envelope carries no float jaccard,
  no scan-identity-absent note, and a basename-only source.snapshot — the properties
  that keep the byte-pin stable. ``generated_at`` / ``producer.version`` are the only
  non-deterministic fields; they are asserted LIVE then normalized to the golden's
  frozen values, exactly as the preflight golden does.
  """

  from __future__ import annotations

  import copy
  import hashlib
  import json
  import shutil
  from datetime import datetime
  from pathlib import Path
  from typing import Any, cast

  from plainweave import __version__
  from plainweave.mcp_surface import PlainweaveMcpSurface

  GOLDEN_PATH = Path(__file__).parents[1] / "fixtures" / "contracts" / "wardline" / "peer-facts.json"
  SCENARIO_A = Path(__file__).parents[1] / "fixtures" / "wardline" / "scenario_a"

  # Recompute with: git hash-object tests/fixtures/contracts/wardline/peer-facts.json
  UPSTREAM_BLOB_SHA = "<FILL AFTER FIRST GREEN REGEN>"
  _FROZEN_GENERATED_AT = "2026-06-04T10:00:00+00:00"
  _FROZEN_VERSION = "1.0.0"


  def _produce_schema_plus_data(root: Path) -> dict[str, Any]:
      shutil.copytree(SCENARIO_A, root / ".wardline")
      envelope = PlainweaveMcpSurface(root).plainweave_wardline_peer_facts_list()
      assert envelope["ok"] is True
      return {"schema": envelope["schema"], **cast(dict[str, Any], envelope["data"])}


  def test_golden_matches_blob_pin() -> None:
      assert len(UPSTREAM_BLOB_SHA) == 40 and set(UPSTREAM_BLOB_SHA) <= set("0123456789abcdef"), (
          f"UPSTREAM_BLOB_SHA must be 40 lowercase hex chars: {UPSTREAM_BLOB_SHA!r}"
      )
      data = GOLDEN_PATH.read_bytes()
      actual = hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()
      assert actual == UPSTREAM_BLOB_SHA, (
          f"vendored wardline golden changed (git blob {actual}, pinned {UPSTREAM_BLOB_SHA}); "
          "if deliberate, regenerate from the producer, refreeze generated_at/version, re-pin in the same commit."
      )


  def test_golden_matches_live_producer(tmp_path: Path) -> None:
      """Non-circular recheck: the volatile fields (generated_at, producer.version) live
      in the envelope ``meta``, which the golden does NOT vendor (it vendors only
      ``schema + data``). The data payload is therefore fully deterministic, so no
      normalization is needed — assert deep equality directly. If a future field adds a
      non-deterministic value INTO data, port the preflight normalize-then-compare block."""
      golden = cast(dict[str, Any], json.loads(GOLDEN_PATH.read_text("utf-8")))
      regenerated = _produce_schema_plus_data(tmp_path)
      assert golden["schema"] == "weft.plainweave.wardline_peer_facts.v1"
      assert "generated_at" not in regenerated, "data must stay deterministic; generated_at belongs in meta"
      assert regenerated == golden, (
          "the live wardline_peer_facts producer drifted from the vendored golden — "
          "regenerate and re-pin per the RE-VENDOR PROCEDURE."
      )
  ```
- [ ] Run it, expect FAIL (`plainweave_wardline_peer_facts_list` not yet on the surface):
  `uv run pytest tests/contracts/test_wardline_peer_facts_wire_golden.py -q`
- [ ] (After A9) regenerate the golden bytes from the live producer:
  ```python
  # one-off in a scratch script or REPL, run from repo root:
  import json, shutil, tempfile
  from pathlib import Path
  from plainweave.mcp_surface import PlainweaveMcpSurface
  root = Path(tempfile.mkdtemp())
  shutil.copytree("tests/fixtures/wardline/scenario_a", root / ".wardline")
  env = PlainweaveMcpSurface(root).plainweave_wardline_peer_facts_list()
  payload = {"schema": env["schema"], **env["data"]}
  Path("tests/fixtures/contracts/wardline/peer-facts.json").write_text(
      json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
  ```
  Then compute and paste the blob SHA into `UPSTREAM_BLOB_SHA`:
  `git hash-object tests/fixtures/contracts/wardline/peer-facts.json`
- [ ] Run it, expect PASS:
  `uv run pytest tests/contracts/test_wardline_peer_facts_wire_golden.py -q`
- [ ] Register the golden in `REQUIRED_FIXTURES` (`tests/contracts/test_contract_fixtures.py`) — see C1; and add a `test_wardline_peer_facts_fixture_contract` that runs `validate_wardline_peer_facts` over the golden (free cross-check, mirrors `test_preflight_facts_fixture_contract`):
  ```python
  from tests.wardline_contract import validate_wardline_peer_facts

  def test_wardline_peer_facts_fixture_contract() -> None:
      fixture = load_fixture("wardline/peer-facts.json")
      assert fixture["schema"] == "weft.plainweave.wardline_peer_facts.v1"
      validate_wardline_peer_facts({k: v for k, v in fixture.items() if k != "schema"})
  ```
- [ ] Commit:
  `git add tests/fixtures/contracts/wardline tests/contracts/test_wardline_peer_facts_wire_golden.py tests/contracts/test_contract_fixtures.py`
  `git commit -m "test(wardline): byte-pinned wire golden + producer recheck"`

---

## Task A9 — Surface: service `_wardline_adapter()` + MCP tool + metadata + resource + doctor

**Files**
- Modify `src/plainweave/service.py` (add `_wardline_adapter()` after `_loomweave_adapter()` ~L2594).
- Modify `src/plainweave/mcp_surface.py` (add `_wardline_adapter()`, `plainweave_wardline_peer_facts_list()`, `MCP_TOOL_METADATA` entry, `MCP_RESOURCE_URIS` entry, `CONTRACT_RESOURCES` entry).
- Modify `src/plainweave/mcp_server.py` (add `@mcp.tool()` wrapper).
- Modify `src/plainweave/cli_commands.py` (add `_doctor_wardline_check`, wire into `run_doctor`).
- Modify `tests/test_mcp_read_surface.py` (add tool name to `expected_tools` ~L108-126).
- Modify `tests/fixtures/contracts/mcp/tool-inventory.json`, `tests/fixtures/contracts/mcp/resource-inventory.json` (add the tool/URI), and `tests/contracts/test_contract_fixtures.py` (add to the two hardcoded inventory expectations).

**Interfaces**

Real exemplar signatures to mirror:
- `PlainweaveService._loomweave_adapter(self) -> LoomweaveAdapter: return LoomweaveAdapter(self.root)` (service.py:2594).
- `PlainweaveMcpSurface._loomweave_adapter(self) -> LoomweaveAdapter: return LoomweaveAdapter(self.root)` (mcp_surface.py:685).
- `PlainweaveMcpSurface.plainweave_loomweave_catalog_list(self, *, limit=50, offset=0)` — validates pagination, calls the adapter, wraps in `success_envelope("weft.plainweave.loomweave_catalog.v1", data, project=self._project_key())`, catches `PlainweaveError` via `self._error(exc)`.
- `MCP_TOOL_METADATA` entry shape: `{"name","mutates":False,"local_only":True,"peer_side_effects":[],"authority_boundary":<str>}`.
- `_doctor_catalog_check(root)` (cli_commands.py:509) — `LoomweaveAdapter(root).health()`, returns `{"id","status","detail","fixable","fixed","next_action"}`.

Produces:
- `PlainweaveService._wardline_adapter(self) -> WardlineAdapter`.
- `PlainweaveMcpSurface._wardline_adapter(self) -> WardlineAdapter`.
- `PlainweaveMcpSurface.plainweave_wardline_peer_facts_list(self, *, limit: int = 50, offset: int = 0) -> JsonObject` → `success_envelope("weft.plainweave.wardline_peer_facts.v1", data, project=self._project_key())`.
- `mcp_server.plainweave_wardline_peer_facts_list(limit: int = 50, offset: int = 0) -> dict[str, Any]`.
- `cli_commands._doctor_wardline_check(root: Path) -> dict[str, object]`.

**Steps**

- [ ] Write failing test in `tests/test_mcp_read_surface.py`:
  ```python
  def test_mcp_wardline_peer_facts_returns_advisory_envelope_without_verdicts(tmp_path: Path) -> None:
      service_for(tmp_path)  # initialize the plainweave store
      wdir = tmp_path / ".wardline"
      wdir.mkdir()
      record = {
          "fingerprint": "d1", "kind": "defect", "rule_id": "WLN-1",
          "location": {"path": "src/a.py", "line_start": 1, "line_end": 1, "col_start": 0, "col_end": 1},
          "maturity": "stable", "message": "m", "properties": {}, "qualname": "a.f",
          "related_entities": [], "severity": "CRITICAL", "suggestion": None,
          "suppression_reason": None, "suppression_state": "active",
      }
      (wdir / "20260101T000000Z-findings.jsonl").write_text(json.dumps(record), encoding="utf-8")
      envelope = PlainweaveMcpSurface(tmp_path).plainweave_wardline_peer_facts_list()
      assert envelope["schema"] == "weft.plainweave.wardline_peer_facts.v1"
      assert envelope["ok"] is True
      from tests.wardline_contract import validate_wardline_peer_facts
      validate_wardline_peer_facts(envelope["data"])
  ```
  Also extend `expected_tools` in `test_mcp_tool_inventory_is_agent_task_surface` (~L108) with `"plainweave_wardline_peer_facts_list"`.
- [ ] Run it, expect FAIL:
  `uv run pytest tests/test_mcp_read_surface.py -k "wardline or tool_inventory" -q`
- [ ] Minimal impl — `src/plainweave/service.py` after `_loomweave_adapter` (and import `WardlineAdapter`):
  ```python
      def _wardline_adapter(self) -> WardlineAdapter:
          return WardlineAdapter(self.root)
  ```
  Add to the top-level import block (mirroring the `LoomweaveAdapter` import at service.py:26):
  ```python
  from plainweave.wardline_adapter import WardlineAdapter
  ```
- [ ] Minimal impl — `src/plainweave/mcp_surface.py`:
  - import: `from plainweave.wardline_adapter import WardlineAdapter`
  - add the `MCP_TOOL_METADATA` entry (alphabetical placement is not required; the inventory fixture sorts):
    ```python
      "plainweave_wardline_peer_facts_list": {
          "name": "plainweave_wardline_peer_facts_list",
          "mutates": False,
          "local_only": True,
          "peer_side_effects": [],
          "authority_boundary": (
              "Reads Wardline's local findings snapshots as advisory peer facts; it runs no scan, makes no "
              "trust decision, and emits no verdict. Wardline owns trust policy."
          ),
      },
    ```
  - append to `MCP_RESOURCE_URIS`: `"plainweave://contracts/weft.plainweave.wardline_peer_facts.v1"`.
  - add to `CONTRACT_RESOURCES`:
    ```python
      "plainweave://contracts/weft.plainweave.wardline_peer_facts.v1": {
          "contract": "weft.plainweave.wardline_peer_facts.v1",
          "required_sections": [
              "source", "freshness", "facts", "resolved_or_unseen",
              "engine_metrics", "summary", "degraded", "authority_boundary", "notes",
          ],
          "freshness_states": ["current", "stale", "unavailable"],
          "suppression_states": ["active", "waived", "baselined", "judged"],
          "degrade_codes": [
              "wardline_findings_absent", "wardline_single_snapshot", "wardline_scope_mismatch",
              "wardline_scan_identity_absent", "wardline_ruleset_mismatch",
          ],
          "authority_boundary": "Advisory Wardline findings read from local .wardline snapshots; no verdict, no scan.",
      },
    ```
  - add the surface method + adapter accessor:
    ```python
      def _wardline_adapter(self) -> WardlineAdapter:
          return WardlineAdapter(self.root)

      def plainweave_wardline_peer_facts_list(self, *, limit: int = 50, offset: int = 0) -> JsonObject:
          try:
              self._validate_pagination(limit, offset)
              data = self._wardline_adapter().list_peer_facts(limit=limit, offset=offset)
          except PlainweaveError as exc:
              return self._error(exc)
          return success_envelope("weft.plainweave.wardline_peer_facts.v1", data, project=self._project_key())
    ```
- [ ] Minimal impl — `src/plainweave/mcp_server.py` (after `plainweave_verification_status_list`, before `register_resource`):
  ```python
      @mcp.tool()
      def plainweave_wardline_peer_facts_list(limit: int = 50, offset: int = 0) -> dict[str, Any]:
          """Read local Wardline findings as advisory peer facts (active/waived/baselined/judged,
          defect/non-defect, resolved-or-unseen). Runs no scan and emits no verdict."""
          return active_surface.plainweave_wardline_peer_facts_list(limit=limit, offset=offset)
  ```
- [ ] Minimal impl — `src/plainweave/cli_commands.py` (add `_doctor_wardline_check`, import `WardlineAdapter`, add to `run_doctor` checks):
  ```python
  from plainweave.wardline_adapter import WardlineAdapter

  def _doctor_wardline_check(root: Path) -> dict[str, object]:
      """Wardline findings binding: the sibling-owned trust-gate output Plainweave reads
      as advisory peer facts. Report-only (consumer boundary; Plainweave never scans)."""
      try:
          health = WardlineAdapter(root).health()
      except Exception as exc:  # never let a sibling probe crash doctor
          return {
              "id": "wardline_findings",
              "status": "warn",
              "detail": f"could not probe the Wardline findings ({type(exc).__name__})",
              "fixable": False,
              "fixed": False,
              "next_action": "wardline scan .  (Plainweave consumes its findings; the sibling owns the scan)",
          }
      raw_status = health.get("adapter_status")
      status = raw_status if isinstance(raw_status, dict) else {}
      if status.get("status") == "unavailable":
          return {
              "id": "wardline_findings",
              "status": "warn",
              "detail": "no .wardline findings snapshot present; peer facts are unavailable (not clean)",
              "fixable": False,
              "fixed": False,
              "next_action": "wardline scan .  (writes .wardline/<ts>-findings.jsonl)",
          }
      count = status.get("snapshot_count")
      detail = f"Wardline findings available ({count} snapshot(s))"
      if status.get("status") == "degraded":
          detail += "; <2 snapshots, resolved/unseen unavailable"
      return {
          "id": "wardline_findings",
          "status": "ok",
          "detail": detail,
          "fixable": False,
          "fixed": False,
          "next_action": None,
      }
  ```
  And in `run_doctor` (cli_commands.py:589) extend the checks list:
  ```python
      checks = [store_check, _doctor_catalog_check(root), _doctor_wardline_check(root), _doctor_mcp_check()]
  ```
- [ ] Update inventory fixtures + the two hardcoded inventory test expectations:
  - `tests/fixtures/contracts/mcp/tool-inventory.json`: insert the `plainweave_wardline_peer_facts_list` entry so `[tool["name"] for tool in tools] == sorted(expected_tools)` still holds.
  - `tests/fixtures/contracts/mcp/resource-inventory.json`: append the new URI in the SAME order as `MCP_RESOURCE_URIS`.
  - `tests/contracts/test_contract_fixtures.py`: add `"plainweave_wardline_peer_facts_list"` to `test_mcp_tool_inventory_fixture_contract`'s `expected_tools`, and append the URI to `test_mcp_resource_inventory_fixture_contract`'s expected `resources` list.
- [ ] Run the full MCP surface + contract + doctor suite, expect PASS:
  `uv run pytest tests/test_mcp_read_surface.py tests/test_mcp_server.py tests/contracts/test_contract_fixtures.py -k "wardline or inventory or tool or resource or doctor" -q`
  Then return to A8 and make the wire-golden green (regenerate + pin).
- [ ] Commit:
  `git add src/plainweave/service.py src/plainweave/mcp_surface.py src/plainweave/mcp_server.py src/plainweave/cli_commands.py tests/test_mcp_read_surface.py tests/fixtures/contracts/mcp tests/contracts/test_contract_fixtures.py`
  `git commit -m "feat(wardline): surface peer facts via service/MCP/doctor + contract resource"`

---

## Task B1 — Warpline producer: reuse entity-intent resolution → status mapping

**Files**
- Modify `src/plainweave/mcp_surface.py` (add `_requirements_enrichment_status`).
- Create `tests/test_warpline_requirements_enrichment.py` (new).

**Interfaces**

Reuses (real, mcp_surface.py):
- `PlainweaveMcpSurface._entity_intent_context_item(self, service: PlainweaveService, entity_ref: str, traces: Sequence[TraceLink]) -> JsonObject` returns `{"input_ref","resolution":{"state": "resolved|resolved_no_binding|unresolved","matched_refs",...,"local_catalog":{"state": "resolved|unresolved|unavailable",...},"peer_resolution":{...}},"bindings":[...],"requirement_trail":[...],"orphan","freshness","drift"}`.
- `PlainweaveMcpSurface.plainweave_entity_intent_context_get(self, *, entity_refs)` builds `traces = service.trace_for()` then one item per ref.

Status mapping (spec §6.2 + cardinal §4 invariant; the dead-binding case is `unavailable`, NOT `absent` — there IS a binding pointing at something un-loadable, so "definitively no requirement" cannot be claimed):

| Condition (from the reused item) | status |
|---|---|
| `requirement_trail` non-empty (≥1 alive requirement binding) | `present` |
| `matched_refs` empty (no trace) + `local_catalog.state == "resolved"` | `absent` |
| `matched_refs` empty + `local_catalog.state == "unresolved"` | `unavailable` |
| trace matched but `requirement_trail` empty (binding → un-loadable requirement) | `unavailable` |
| `local_catalog.state == "unavailable"` (catalog/store error) | `unavailable` |

`present` carries a non-empty `requirements` array (§6.3); `absent`/`unavailable` carry `requirements: []` plus a `reason`.

Produces:
- `PlainweaveMcpSurface._requirements_enrichment_status(self, item: JsonObject) -> tuple[str, str | None]` → `(status, reason)`.

**Steps**

- [ ] Write failing test `tests/test_warpline_requirements_enrichment.py`:
  ```python
  from __future__ import annotations

  from pathlib import Path

  from tests.loomweave_test_utils import seed_loomweave_catalog

  from plainweave.mcp_surface import PlainweaveMcpSurface
  from plainweave.models import TraceRef
  from plainweave.service import PlainweaveService
  from plainweave.store import migrate


  def _seed_bound(tmp_path: Path) -> tuple[PlainweaveMcpSurface, dict[str, str]]:
      # Verified pattern from tests/contracts/test_preflight_facts_wire_golden.py::_seed_preflight_project.
      # `service_for` is a PER-FILE local helper elsewhere (not importable); seed directly.
      db_path = tmp_path / ".plainweave" / "plainweave.db"
      migrate(db_path, project_key="AUTH")
      service = PlainweaveService(db_path, root=tmp_path)
      seed = seed_loomweave_catalog(tmp_path)
      draft = service.create_requirement(
          "Reject expired tokens", "The API shall reject expired bearer tokens.", "human:john"
      )
      service.add_acceptance_criterion(draft.id, "Expired tokens return 401.", actor="human:john")
      service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")
      service.create_trace_link(
          TraceRef("loomweave_entity", seed["public_locator"]),
          "satisfies",
          TraceRef("requirement_version", f"{draft.id}@1"),
          actor="human:john",
          authority="accepted",
      )
      return PlainweaveMcpSurface(tmp_path), seed


  def _item(surface: PlainweaveMcpSurface, root: Path, ref: str) -> dict[str, object]:
      service = surface._service()
      return surface._entity_intent_context_item(service, ref, service.trace_for())


  def test_status_present_when_alive_requirement_bound(tmp_path: Path) -> None:
      surface, seed = _seed_bound(tmp_path)
      status, reason = surface._requirements_enrichment_status(_item(surface, tmp_path, seed["public_sei"]))
      assert status == "present"
      assert reason is None


  def test_status_absent_when_resolved_but_unbound(tmp_path: Path) -> None:
      surface, seed = _seed_bound(tmp_path)
      status, reason = surface._requirements_enrichment_status(_item(surface, tmp_path, seed["module_sei"]))
      assert status == "absent"
      assert reason


  def test_status_unavailable_when_unresolved(tmp_path: Path) -> None:
      surface, _seed = _seed_bound(tmp_path)
      status, reason = surface._requirements_enrichment_status(
          _item(surface, tmp_path, "loomweave:eid:doesnotexist00000000000000000000")
      )
      assert status == "unavailable"
      assert reason
  ```
  (The `_seed_bound` / `_item` helpers are defined in the import block above — all imports verified from `tests/contracts/test_preflight_facts_wire_golden.py::_seed_preflight_project`. `surface._service()` is the real surface accessor (mcp_surface.py:673) which requires the migrated db to exist — it does, because `_seed_bound` migrated it.)
- [ ] Run it, expect FAIL:
  `uv run pytest tests/test_warpline_requirements_enrichment.py -q`
- [ ] Minimal impl — add to `src/plainweave/mcp_surface.py`:
  ```python
      def _requirements_enrichment_status(self, item: JsonObject) -> tuple[str, str | None]:
          resolution = cast(JsonObject, item["resolution"])
          local = cast(JsonObject, resolution["local_catalog"])
          requirement_trail = cast(list[object], item["requirement_trail"])
          matched = cast(list[object], resolution["matched_refs"])
          if requirement_trail:
              return "present", None
          if local["state"] == "unavailable":
              return "unavailable", "Local Loomweave catalog could not be consulted; cannot determine requirements."
          if not matched:
              if local["state"] == "resolved":
                  return "absent", "Entity resolves locally but no requirement is bound to it."
              return "unavailable", "Entity identity is not resolvable locally; cannot determine requirements."
          # A trace matched but no alive requirement loaded behind it: this is "cannot
          # tell", never "definitively none" (no-silent-clean, spec §4).
          return "unavailable", "A binding exists but its requirement could not be resolved; cannot determine."
  ```
- [ ] Run it, expect PASS:
  `uv run pytest tests/test_warpline_requirements_enrichment.py -q`
- [ ] Commit:
  `git add src/plainweave/mcp_surface.py tests/test_warpline_requirements_enrichment.py`
  `git commit -m "feat(warpline): entity resolution -> requirements_enrichment status mapping"`

---

## Task B2 — Warpline item-level shape (§6.3)

**Files**
- Modify `src/plainweave/mcp_surface.py` (add `_requirements_enrichment_items`).
- Modify `tests/test_warpline_requirements_enrichment.py`.

**Interfaces**

Spec §6.3 item (advisory, no verdict tokens):
```
{
  "requirement_id": "req-N",
  "stable_id": "plainweave:req:<...>",
  "version": 1,
  "type": "functional | nonfunctional | constraint | ...",
  "criticality": "low | medium | high | critical",   # advisory ordering signal, NOT a gate
  "binding": {
    "relation": "satisfies | verifies | derives | ...",
    "actor_kind": "agent | human",
    "freshness": "current | stale | orphaned | unknown"
  }
}
```

VERIFIED source-of-truth (do not re-derive): `RequirementRecord` / `_record_dict` (cli_commands.py:1174) does NOT carry `type` or `criticality` — its keys are `{requirement_id, id, stable_id, current_version, active_draft_id, status, current_version_record}`. The `type`/`criticality`/`version` triple comes from `PlainweaveService.requirement_preflight_profile(requirement_id: str) -> dict[str, object]` (service.py:1579), which returns exactly `{"id","requirement_id","stable_id","version","criticality","type"}` — the SAME source the preflight producer uses for its requirement sub-dict. So this producer threads `service` and looks the profile up; it does NOT read `type`/`criticality` off `_record_dict` (that would silently emit nulls — the §4 trap). The binding block comes from `_trace_dict` (cli_commands.py:1202, VERIFIED keys include `relation`, `authority`, `freshness`). Map `authority`→`actor_kind`: `accepted|human_proposed|human_attested` → `human`, else `agent`.

The reused item's `requirement_trail` entries carry `{"requirement": _record_dict(...), "via_bindings": [_trace_dict(...)...], "verification", "goal_trail"}`; `entry["requirement"]["requirement_id"]` is the key into `requirement_preflight_profile`.

Produces:
- `PlainweaveMcpSurface._requirements_enrichment_items(self, service: PlainweaveService, item: JsonObject) -> list[JsonObject]` — one §6.3 item per `requirement_trail` entry; pulls `version/type/criticality` from `service.requirement_preflight_profile(...)`, builds `binding` from the first via-binding.
- `PlainweaveMcpSurface._actor_kind_from_authority(self, authority: str) -> str`.

**Steps**

- [ ] Write failing test in `tests/test_warpline_requirements_enrichment.py`:
  ```python
  def test_present_item_shape(tmp_path: Path) -> None:
      surface, seed = _seed_bound(tmp_path)
      service = surface._service()
      items = surface._requirements_enrichment_items(service, _item(surface, tmp_path, seed["public_sei"]))
      assert len(items) == 1
      it = items[0]
      assert set(it) == {"requirement_id", "stable_id", "version", "type", "criticality", "binding"}
      assert it["stable_id"].startswith("plainweave:req:")
      # anti-trap: type/criticality must come from requirement_preflight_profile, NOT be silent nulls
      assert it["version"] == 1
      assert it["criticality"] is not None
      assert it["type"] is not None
      assert set(it["binding"]) == {"relation", "actor_kind", "freshness"}
      assert it["binding"]["actor_kind"] == "human"  # trace authority == "accepted"
      assert it["binding"]["relation"] == "satisfies"
  ```
- [ ] Run it, expect FAIL:
  `uv run pytest tests/test_warpline_requirements_enrichment.py -k "item_shape" -q`
- [ ] Minimal impl — add to `src/plainweave/mcp_surface.py` (`version/type/criticality` from `requirement_preflight_profile`, binding from the verified `_trace_dict` keys):
  ```python
      def _actor_kind_from_authority(self, authority: str) -> str:
          return "human" if authority in {"accepted", "human_proposed", "human_attested"} else "agent"

      def _requirements_enrichment_items(
          self, service: PlainweaveService, item: JsonObject
      ) -> list[JsonObject]:
          items: list[JsonObject] = []
          for entry in cast(list[JsonObject], item["requirement_trail"]):
              record = cast(JsonObject, entry["requirement"])
              profile = service.requirement_preflight_profile(str(record["requirement_id"]))
              via = cast(list[JsonObject], entry["via_bindings"])
              binding_trace = via[0] if via and isinstance(via[0], dict) else {}
              authority = str(binding_trace.get("authority", ""))
              items.append(
                  {
                      "requirement_id": profile["requirement_id"],
                      "stable_id": profile["stable_id"],
                      "version": profile["version"],
                      "type": profile["type"],
                      "criticality": profile["criticality"],
                      "binding": {
                          "relation": binding_trace.get("relation"),
                          "actor_kind": self._actor_kind_from_authority(authority),
                          "freshness": binding_trace.get("freshness"),
                      },
                  }
              )
          return items
  ```
- [ ] Run it, expect PASS:
  `uv run pytest tests/test_warpline_requirements_enrichment.py -k "item_shape" -q`
- [ ] Commit:
  `git add src/plainweave/mcp_surface.py tests/test_warpline_requirements_enrichment.py`
  `git commit -m "feat(warpline): requirements_enrichment item-level shape (spec 6.3)"`

---

## Task B3 — `weft.plainweave.requirements_enrichment.v1` envelope (`plainweave_requirements_enrichment_get`)

**Files**
- Modify `src/plainweave/mcp_surface.py` (add `plainweave_requirements_enrichment_get` + `_requirements_enrichment_item`).
- Modify `tests/test_warpline_requirements_enrichment.py`.

**Interfaces**

Spec §6.4 envelope `data`:
```
{
  "items": [
    {"entity_ref": "<ref>", "status": "present|absent|unavailable",
     "requirements": [ <§6.3 item> ], "reason": "...|null",
     "freshness": "current|stale|orphaned|unknown|unavailable"}
  ],
  "summary": {"present": N, "absent": N, "unavailable": N}
}
```
Plus a top-level `authority_boundary` INSIDE data: `{"local_only": true, "live_peer_calls": false, "governance_verdicts": false, "requirements_owner": "plainweave"}`.

Produces:
- `PlainweaveMcpSurface.plainweave_requirements_enrichment_get(self, *, entity_refs: Sequence[str]) -> JsonObject` — validates refs via `self._validate_entity_refs` (reused), builds items via `_result`/the service, wraps with `success_envelope("weft.plainweave.requirements_enrichment.v1", data, project=self._project_key())`.
- `PlainweaveMcpSurface._requirements_enrichment_item(self, item: JsonObject) -> JsonObject` — combines status + items + freshness.

Freshness rule (no-silent-clean): `unavailable` status → `freshness: "unavailable"`; otherwise carry the reused item's `freshness.state` (which is itself one of `current|stale|orphaned|unknown|unavailable`).

**Steps**

- [ ] Write failing test in `tests/test_warpline_requirements_enrichment.py`:
  ```python
  def test_envelope_mixed_states(tmp_path: Path) -> None:
      surface, seed = _seed_bound(tmp_path)
      envelope = surface.plainweave_requirements_enrichment_get(
          entity_refs=[seed["public_sei"], seed["module_sei"], "loomweave:eid:missing00000000000000000000000000"]
      )
      assert envelope["schema"] == "weft.plainweave.requirements_enrichment.v1"
      assert envelope["ok"] is True
      data = envelope["data"]
      statuses = {it["entity_ref"]: it["status"] for it in data["items"]}
      assert statuses[seed["public_sei"]] == "present"
      assert statuses[seed["module_sei"]] == "absent"
      assert statuses["loomweave:eid:missing00000000000000000000000000"] == "unavailable"
      assert data["summary"] == {"present": 1, "absent": 1, "unavailable": 1}
      assert data["authority_boundary"]["requirements_owner"] == "plainweave"
      present = next(it for it in data["items"] if it["status"] == "present")
      assert present["requirements"]  # non-empty per §6.3
      for it in data["items"]:
          if it["status"] != "present":
              assert it["requirements"] == [] and it["reason"]
  ```
- [ ] Run it, expect FAIL:
  `uv run pytest tests/test_warpline_requirements_enrichment.py -k "envelope" -q`
- [ ] Minimal impl — add to `src/plainweave/mcp_surface.py`:
  ```python
      def plainweave_requirements_enrichment_get(self, *, entity_refs: Sequence[str]) -> JsonObject:
          validation_error = self._validate_entity_refs(entity_refs)
          if validation_error is not None:
              return validation_error

          def action(service: PlainweaveService) -> JsonObject:
              traces = service.trace_for()
              items = [
                  self._requirements_enrichment_item(
                      service, self._entity_intent_context_item(service, ref, traces)
                  )
                  for ref in entity_refs
              ]
              summary = {"present": 0, "absent": 0, "unavailable": 0}
              for entry in items:
                  summary[str(entry["status"])] += 1
              return {
                  "items": items,
                  "summary": summary,
                  "authority_boundary": {
                      "local_only": True,
                      "live_peer_calls": False,
                      "governance_verdicts": False,
                      "requirements_owner": "plainweave",
                  },
              }

          return self._result("weft.plainweave.requirements_enrichment.v1", action)

      def _requirements_enrichment_item(self, service: PlainweaveService, item: JsonObject) -> JsonObject:
          status, reason = self._requirements_enrichment_status(item)
          requirements = self._requirements_enrichment_items(service, item) if status == "present" else []
          if status == "unavailable":
              freshness = "unavailable"
          else:
              freshness = str(cast(JsonObject, item["freshness"]).get("state", "unknown"))
          return {
              "entity_ref": item["input_ref"],
              "status": status,
              "requirements": requirements,
              "reason": reason,
              "freshness": freshness,
          }
  ```
- [ ] Run it, expect PASS:
  `uv run pytest tests/test_warpline_requirements_enrichment.py -k "envelope" -q`
- [ ] Commit:
  `git add src/plainweave/mcp_surface.py tests/test_warpline_requirements_enrichment.py`
  `git commit -m "feat(warpline): requirements_enrichment.v1 envelope assembly"`

---

## Task B4 — `tests/warpline_contract.py` validator + no-verdict

**Files**
- Create `tests/warpline_contract.py` (new).
- Create `tests/contracts/test_warpline_contract.py` (new).

**Interfaces**

Mirror the no-verdict scan from `tests/preflight_contract.py`. KEY DIFFERENCE from the Wardline validator (A6): the requirements-enrichment payload has NO `severity` field anywhere, so this validator needs NO severity allowlist branch (do not copy A6's severity check). It DOES need the `present`/`absent`/`unavailable` invariants and the §6.3 item-shape check.

Produces:
```python
ENRICHMENT_STATUSES = {"present", "absent", "unavailable"}
ENRICHMENT_FRESHNESS = {"current", "stale", "orphaned", "unknown", "unavailable"}
ENRICHMENT_DATA_KEYS = {"items", "summary", "authority_boundary"}
ENRICHMENT_ITEM_KEYS = {"entity_ref", "status", "requirements", "reason", "freshness"}
ENRICHMENT_REQUIREMENT_KEYS = {"requirement_id", "stable_id", "version", "type", "criticality", "binding"}
ENRICHMENT_BINDING_KEYS = {"relation", "actor_kind", "freshness"}
ENRICHMENT_AUTHORITY_KEYS = {"local_only", "live_peer_calls", "governance_verdicts", "requirements_owner"}
def assert_no_warpline_verdicts(value: object) -> None: ...
def validate_requirements_enrichment(payload: dict[str, Any]) -> None: ...
```

**Steps**

- [ ] Write failing test `tests/contracts/test_warpline_contract.py`:
  ```python
  from __future__ import annotations

  import pytest

  from tests.warpline_contract import assert_no_warpline_verdicts, validate_requirements_enrichment


  def test_validator_accepts_minimal_payload() -> None:
      validate_requirements_enrichment(
          {
              "items": [
                  {"entity_ref": "loomweave:eid:x", "status": "unavailable",
                   "requirements": [], "reason": "cannot determine", "freshness": "unavailable"}
              ],
              "summary": {"present": 0, "absent": 0, "unavailable": 1},
              "authority_boundary": {"local_only": True, "live_peer_calls": False,
                                     "governance_verdicts": False, "requirements_owner": "plainweave"},
          }
      )


  def test_present_requires_non_empty_requirements() -> None:
      with pytest.raises(AssertionError):
          validate_requirements_enrichment(
              {
                  "items": [{"entity_ref": "e", "status": "present", "requirements": [],
                             "reason": None, "freshness": "current"}],
                  "summary": {"present": 1, "absent": 0, "unavailable": 0},
                  "authority_boundary": {"local_only": True, "live_peer_calls": False,
                                         "governance_verdicts": False, "requirements_owner": "plainweave"},
              }
          )


  def test_rejects_verdict_token() -> None:
      with pytest.raises(AssertionError):
          assert_no_warpline_verdicts({"status": "blocked"})
  ```
- [ ] Run it, expect FAIL:
  `uv run pytest tests/contracts/test_warpline_contract.py -q`
- [ ] Minimal impl — create `tests/warpline_contract.py`:
  ```python
  """Single source of truth for the ``weft.plainweave.requirements_enrichment.v1`` shape.

  Mirrors the no-verdict discipline of ``tests/preflight_contract.py``. This payload has
  NO ``severity`` field, so (unlike the wardline validator) there is no severity allowlist.
  """

  from __future__ import annotations

  from typing import Any

  ENRICHMENT_STATUSES = {"present", "absent", "unavailable"}
  ENRICHMENT_FRESHNESS = {"current", "stale", "orphaned", "unknown", "unavailable"}
  ENRICHMENT_DATA_KEYS = {"items", "summary", "authority_boundary"}
  ENRICHMENT_ITEM_KEYS = {"entity_ref", "status", "requirements", "reason", "freshness"}
  ENRICHMENT_REQUIREMENT_KEYS = {"requirement_id", "stable_id", "version", "type", "criticality", "binding"}
  ENRICHMENT_BINDING_KEYS = {"relation", "actor_kind", "freshness"}
  ENRICHMENT_AUTHORITY_KEYS = {"local_only", "live_peer_calls", "governance_verdicts", "requirements_owner"}

  _VERDICT_KEYS = {"allow", "allowed", "block", "blocked", "verdict", "decision", "gate", "enforcement"}
  _VERDICT_VALUE_TOKENS = {
      "allow", "allowed", "block", "blocked", "block_candidate", "deny", "denied",
      "approved", "rejected", "pass_fail", "verdict",
  }


  def assert_no_warpline_verdicts(value: object) -> None:
      if isinstance(value, dict):
          assert _VERDICT_KEYS.isdisjoint(value), f"verdict-like key in {sorted(value)}"
          for item in value.values():
              assert_no_warpline_verdicts(item)
      elif isinstance(value, list):
          for item in value:
              assert_no_warpline_verdicts(item)
      elif isinstance(value, str):
          assert value.strip().lower() not in _VERDICT_VALUE_TOKENS, f"verdict-like value: {value}"


  def validate_requirements_enrichment(payload: dict[str, Any]) -> None:
      """Structurally validate a requirements-enrichment *data* payload (no envelope wrapper)."""
      assert set(payload) == ENRICHMENT_DATA_KEYS, f"section drift: {sorted(payload)}"

      summary = payload["summary"]
      assert set(summary) == ENRICHMENT_STATUSES
      counts = {status: 0 for status in ENRICHMENT_STATUSES}
      items = payload["items"]
      assert isinstance(items, list)
      for item in items:
          assert set(item) == ENRICHMENT_ITEM_KEYS, f"item key drift: {sorted(item)}"
          assert item["status"] in ENRICHMENT_STATUSES
          assert item["freshness"] in ENRICHMENT_FRESHNESS
          counts[item["status"]] += 1
          requirements = item["requirements"]
          assert isinstance(requirements, list)
          if item["status"] == "present":
              assert requirements, "present status must carry a non-empty requirements array (spec 6.3)"
              assert item["reason"] is None
          else:
              assert requirements == [], "non-present status must carry an empty requirements array"
              assert isinstance(item["reason"], str) and item["reason"], "non-present status must carry a reason"
          for requirement in requirements:
              assert set(requirement) == ENRICHMENT_REQUIREMENT_KEYS, f"requirement key drift: {sorted(requirement)}"
              assert set(requirement["binding"]) == ENRICHMENT_BINDING_KEYS
              assert requirement["binding"]["actor_kind"] in {"agent", "human"}
      assert summary == counts, f"summary {summary} disagrees with item counts {counts}"

      authority = payload["authority_boundary"]
      assert set(authority) == ENRICHMENT_AUTHORITY_KEYS
      assert authority["governance_verdicts"] is False
      assert authority["live_peer_calls"] is False
      assert authority["local_only"] is True
      assert authority["requirements_owner"] == "plainweave"

      assert_no_warpline_verdicts(payload)
  ```
- [ ] Run it, expect PASS:
  `uv run pytest tests/contracts/test_warpline_contract.py -q`
- [ ] Wire it into the B3 envelope test: add `validate_requirements_enrichment(envelope["data"])` to `test_envelope_mixed_states`. Run `uv run pytest tests/test_warpline_requirements_enrichment.py -q`, expect PASS.
- [ ] Commit:
  `git add tests/warpline_contract.py tests/contracts/test_warpline_contract.py tests/test_warpline_requirements_enrichment.py`
  `git commit -m "test(warpline): requirements_enrichment.v1 structural validator + no-verdict scan"`

---

## Task B5 — Structure-only wire-golden (Warpline; no byte-pin)

**Files**
- Create `tests/fixtures/contracts/warpline/requirements-enrichment.json` (representative golden, NOT byte-pinned).
- Create `tests/contracts/test_requirements_enrichment_wire_golden.py` (new).

**Interfaces**

Per spec §11, the Warpline item schema is *proposed* until §7.3 ratification, so this wire-golden pins STRUCTURE only (no git-blob byte-pin): the producer recheck regenerates from the live producer over a seeded project and asserts the regenerated `data` passes `validate_requirements_enrichment` AND structurally matches the vendored golden (status set, item keys), but does NOT assert byte-equality. The module docstring must explain why (avoid an expensive re-freeze on every speculative schema tweak before ratification). Model the recheck on `test_preflight_facts_wire_golden.py::test_golden_matches_live_producer` minus the blob-pin and minus deep byte-equality; model the validator cross-check on `test_contract_fixtures.py::test_intent_coverage_fixture_contract`.

**Steps**

- [ ] Create `tests/contracts/test_requirements_enrichment_wire_golden.py`:
  ```python
  """Plainweave-authored ``weft.plainweave.requirements_enrichment.v1`` producer golden,
  STRUCTURE-pinned only — deliberately NOT byte-pinned.

  Per the design spec (§11), the item-level schema for Warpline's reserved
  ``enrichment.requirements`` slot is *proposed* until the interface-lock owner ratifies
  it (handoff: docs/handoffs/2026-06-27-warpline-interface-lock-item-schema.md). Byte-
  pinning now would force an expensive re-freeze on every pre-ratification tweak. So this
  test pins STRUCTURE: it regenerates the payload from the REAL producer over a seeded
  project, asserts it passes ``validate_requirements_enrichment``, and asserts the
  committed golden does too and agrees on the status set and item keys. When the schema is
  ratified, convert this to a two-layer byte-pin mirroring the wardline wire golden.
  """

  from __future__ import annotations

  import json
  from pathlib import Path
  from typing import Any, cast

  from plainweave.mcp_surface import PlainweaveMcpSurface
  from tests.warpline_contract import (
      ENRICHMENT_ITEM_KEYS,
      ENRICHMENT_STATUSES,
      validate_requirements_enrichment,
  )
  # reuse the B1/B3 seed helper:
  from tests.test_warpline_requirements_enrichment import _seed_bound

  GOLDEN_PATH = Path(__file__).parents[1] / "fixtures" / "contracts" / "warpline" / "requirements-enrichment.json"


  def test_golden_is_structurally_valid() -> None:
      golden = cast(dict[str, Any], json.loads(GOLDEN_PATH.read_text("utf-8")))
      assert golden["schema"] == "weft.plainweave.requirements_enrichment.v1"
      validate_requirements_enrichment({k: v for k, v in golden.items() if k != "schema"})


  def test_live_producer_matches_golden_structure(tmp_path: Path) -> None:
      surface, seed = _seed_bound(tmp_path)
      envelope = surface.plainweave_requirements_enrichment_get(
          entity_refs=[seed["public_sei"], seed["module_sei"], "loomweave:eid:missing00000000000000000000000000"]
      )
      assert envelope["ok"] is True
      data = cast(dict[str, Any], envelope["data"])
      validate_requirements_enrichment(data)

      golden = cast(dict[str, Any], json.loads(GOLDEN_PATH.read_text("utf-8")))
      golden_data = {k: v for k, v in golden.items() if k != "schema"}
      assert set(golden_data["summary"]) == ENRICHMENT_STATUSES
      assert {it["status"] for it in data["items"]} <= ENRICHMENT_STATUSES
      for item in data["items"]:
          assert set(item) == ENRICHMENT_ITEM_KEYS
      # structure agreement, NOT byte equality (schema un-ratified, see module docstring)
      assert {it["status"] for it in golden_data["items"]} == {it["status"] for it in data["items"]}
  ```
- [ ] Run it, expect FAIL (golden file missing):
  `uv run pytest tests/contracts/test_requirements_enrichment_wire_golden.py -q`
- [ ] Generate the golden from the live producer (one-off, same seed as the test), then hand-freeze `meta.generated_at`/`producer.version` to representative values is NOT needed (golden vendors `schema + data`; meta is not vendored). Write `tests/fixtures/contracts/warpline/requirements-enrichment.json` as `{"schema": "weft.plainweave.requirements_enrichment.v1", **data}` with present/absent/unavailable all represented.
- [ ] Run it, expect PASS:
  `uv run pytest tests/contracts/test_requirements_enrichment_wire_golden.py -q`
- [ ] Add `test_requirements_enrichment_fixture_contract` to `tests/contracts/test_contract_fixtures.py` (validator cross-check, mirrors `test_intent_coverage_fixture_contract`) and register the golden in `REQUIRED_FIXTURES` (C1).
- [ ] Commit:
  `git add tests/fixtures/contracts/warpline tests/contracts/test_requirements_enrichment_wire_golden.py tests/contracts/test_contract_fixtures.py`
  `git commit -m "test(warpline): structure-only requirements_enrichment wire golden"`

---

## Task B6 — Surface: MCP tool + metadata + resource for requirements enrichment

**Files**
- Modify `src/plainweave/mcp_surface.py` (`MCP_TOOL_METADATA`, `MCP_RESOURCE_URIS`, `CONTRACT_RESOURCES`).
- Modify `src/plainweave/mcp_server.py` (`@mcp.tool()` wrapper).
- Modify `tests/test_mcp_read_surface.py` (`expected_tools`).
- Modify `tests/fixtures/contracts/mcp/tool-inventory.json`, `tests/fixtures/contracts/mcp/resource-inventory.json`, `tests/contracts/test_contract_fixtures.py` (both inventory expectations).

**Interfaces**

Real exemplar: `mcp_server.plainweave_entity_intent_context_get(entity_refs: list[str]) -> dict[str, Any]: return active_surface.plainweave_entity_intent_context_get(entity_refs=entity_refs)`.

Produces:
- `mcp_server.plainweave_requirements_enrichment_get(entity_refs: list[str]) -> dict[str, Any]`.
- `MCP_TOOL_METADATA["plainweave_requirements_enrichment_get"]`.
- `MCP_RESOURCE_URIS += "plainweave://contracts/weft.plainweave.requirements_enrichment.v1"`.
- `CONTRACT_RESOURCES["plainweave://contracts/weft.plainweave.requirements_enrichment.v1"]`.

**Steps**

- [ ] Write failing test in `tests/test_mcp_read_surface.py`:
  ```python
  def test_mcp_requirements_enrichment_tool_is_advertised_and_callable(tmp_path: Path) -> None:
      service_for(tmp_path)
      seed_loomweave_catalog(tmp_path)
      envelope = PlainweaveMcpSurface(tmp_path).plainweave_requirements_enrichment_get(
          entity_refs=["loomweave:eid:public00000000000000000000000000"]
      )
      assert envelope["schema"] == "weft.plainweave.requirements_enrichment.v1"
      assert "plainweave_requirements_enrichment_get" in MCP_TOOL_METADATA
  ```
  And add `"plainweave_requirements_enrichment_get"` to `expected_tools` in `test_mcp_tool_inventory_is_agent_task_surface`.
- [ ] Run it, expect FAIL:
  `uv run pytest tests/test_mcp_read_surface.py -k "requirements_enrichment or tool_inventory" -q`
- [ ] Minimal impl — `src/plainweave/mcp_surface.py` add the metadata entry:
  ```python
      "plainweave_requirements_enrichment_get": {
          "name": "plainweave_requirements_enrichment_get",
          "mutates": False,
          "local_only": True,
          "peer_side_effects": [],
          "authority_boundary": (
              "Returns local Plainweave requirement facts for Warpline's reserved enrichment slot as "
              "present|absent|unavailable; an identity gap is 'unavailable' (cannot tell), never 'absent'. "
              "No verdict; Plainweave owns requirements."
          ),
      },
  ```
  append to `MCP_RESOURCE_URIS`: `"plainweave://contracts/weft.plainweave.requirements_enrichment.v1"`; add to `CONTRACT_RESOURCES`:
  ```python
      "plainweave://contracts/weft.plainweave.requirements_enrichment.v1": {
          "contract": "weft.plainweave.requirements_enrichment.v1",
          "required_sections": ["items", "summary", "authority_boundary"],
          "statuses": ["present", "absent", "unavailable"],
          "status_meaning": {
              "present": "peer present, ≥1 alive requirement bound",
              "absent": "peer present, definitively no requirement bound",
              "unavailable": "cannot determine (identity gap, dead binding, or store error) — NOT 'no requirements'",
          },
          "schema_status": "item-level shape PROPOSED; pending Warpline interface-lock ratification (spec 11)",
          "authority_boundary": "Plainweave owns requirements; advisory only; no governance verdict.",
      },
  ```
- [ ] Minimal impl — `src/plainweave/mcp_server.py` (after the wardline tool):
  ```python
      @mcp.tool()
      def plainweave_requirements_enrichment_get(entity_refs: list[str]) -> dict[str, Any]:
          """Return local Plainweave requirement facts for Warpline's reserved enrichment slot,
          per entity as present|absent|unavailable. An identity gap is 'unavailable', never 'absent'."""
          return active_surface.plainweave_requirements_enrichment_get(entity_refs=entity_refs)
  ```
- [ ] Update inventory fixtures + both hardcoded expectations (`tool-inventory.json`, `resource-inventory.json`, and `test_mcp_tool_inventory_fixture_contract` / `test_mcp_resource_inventory_fixture_contract` in `test_contract_fixtures.py`) to include the new tool + URI, preserving sort order (tools) / `MCP_RESOURCE_URIS` order (resources).
- [ ] Run it, expect PASS:
  `uv run pytest tests/test_mcp_read_surface.py tests/test_mcp_server.py tests/contracts/test_contract_fixtures.py -k "requirements or enrichment or inventory or tool or resource" -q`
- [ ] Commit:
  `git add src/plainweave/mcp_surface.py src/plainweave/mcp_server.py tests/test_mcp_read_surface.py tests/fixtures/contracts/mcp tests/contracts/test_contract_fixtures.py`
  `git commit -m "feat(warpline): surface requirements_enrichment MCP tool + contract resource"`

---

## Task C1 — Register both contract goldens in `REQUIRED_FIXTURES`

**Files**
- Modify `tests/contracts/test_contract_fixtures.py` (`REQUIRED_FIXTURES`).

**Interfaces**

`REQUIRED_FIXTURES` is a set of fixture paths relative to `tests/fixtures/contracts/`; `test_required_fixture_plan_files_exist` asserts every listed path exists. (The two new fixture-contract tests `test_wardline_peer_facts_fixture_contract` (A8) and `test_requirements_enrichment_fixture_contract` (B5) should already be present.)

**Steps**

- [ ] Write/confirm failing assertion — add to `REQUIRED_FIXTURES`:
  ```python
      "wardline/peer-facts.json",
      "warpline/requirements-enrichment.json",
  ```
- [ ] Run, expect PASS (both golden files exist from A8/B5):
  `uv run pytest tests/contracts/test_contract_fixtures.py::test_required_fixture_plan_files_exist tests/contracts/test_contract_fixtures.py -k "wardline_peer_facts_fixture or requirements_enrichment_fixture" -q`
- [ ] Commit:
  `git add tests/contracts/test_contract_fixtures.py`
  `git commit -m "test(contracts): register wardline + warpline goldens in REQUIRED_FIXTURES"`

---

## Task C2 — `make ci` green + `wardline scan` clean (final gate)

**Files**
- No new files; fix any mypy/ruff/coverage findings surfaced across all modules touched.

**Interfaces**

`make ci` = `lint` (`ruff check src tests` + `ruff format --check src tests`) + `typecheck` (`mypy`, strict) + `test-cov` (`pytest --cov=plainweave --cov-report=term-missing --cov-fail-under=90`). The trust-boundary gate is `wardline scan . --fail-on ERROR` (exit 0 = clean).

**Steps**

- [ ] Run the full gate, expect any failures to be fixed in place (typing on the new `JsonObject`-heavy adapter is the likely mypy hotspot; ruff line-length/format on the new modules; coverage on any unexercised branch — add a unit test rather than a pragma):
  `make ci`
- [ ] Run the trust-boundary gate over the touched files (the adapter reads external JSONL input — boundary code), expect exit 0:
  `wardline scan . --fail-on ERROR`
- [ ] Fix findings at the boundary (e.g. malformed-JSON handling in `_load_snapshot` is already defensive; confirm no untrusted path is interpolated into a sink). Re-run both until green.
- [ ] Commit any fixups:
  `git add -A`
  `git commit -m "chore(peer-facts): green make ci + wardline scan for wardline/warpline producers"`

---

## Self-review notes

**Orchestrator self-review (writing-plans skill, 2026-06-27) — PASSED.**
- *Spec coverage:* every spec section maps to a task — §5→A1–A9, §6→B1–B6, §7 (peer
  prompts) already delivered under `docs/handoffs/`, §8→A9/B6, §9→A6/A7/A8/B4/B5/C1,
  §10→C2, §11 caveats→A8 byte-pin + B5 structure-only pin. No gaps.
- *Placeholder scan:* clean. The `...` at A4 and the `def …: ...` lines in A6/B4 are
  spec-quotes / signature declarations inside Interfaces blocks; every implementation
  step carries complete real code.
- *Type consistency:* verified — real signatures threaded throughout
  (`_entity_intent_context_item`, `requirement_preflight_profile`, `_trace_dict`,
  `success_envelope`, `_result`); the B1 status table and B2 item builder agree.
- *Spec reconciliation:* three plan-vs-code corrections were folded back into the spec
  so the design doc stays honest — the 5th status case (dead binding → `unavailable`,
  §6.2), the `requirement_preflight_profile` sourcing note (§6.3), and the `<engine>`
  path sentinel (§5.2).

RESOLVED during authoring (recorded so the executor does not re-litigate):

RESOLVED during authoring (recorded so the executor does not re-litigate):
- `type`/`criticality`/`version` are sourced from `PlainweaveService.requirement_preflight_profile()` (service.py:1579), NOT `_record_dict` (which lacks them) — B2 threads `service` accordingly. Confirmed against `RequirementRecord` (models.py:42) and the preflight producer's own usage.
- `_trace_dict` (cli_commands.py:1202) confirmed to carry `relation`/`authority`/`freshness` for the B2 binding block.
- `service_for` is a per-file local helper, not importable; `test_warpline_requirements_enrichment.py` defines its own `_seed_bound`/`_item` from the verified `_seed_preflight_project` pattern.

Open items for the executor:
- [ ] Confirm the Wardline golden's `data` contains no `generated_at`/version (lives in `meta`, un-vendored) so the byte-pin needs no normalization; if a future field changes that, port the preflight normalize-then-compare block.
- [ ] The A9 wardline MCP test uses `json.dumps`; ensure `import json` is present at the top of `tests/test_mcp_read_surface.py` (add if absent).
- [ ] Confirm the two inventory fixtures + their two hardcoded test expectations + `test_mcp_read_surface.py::expected_tools` all agree after both tools land (no stragglers).
- [ ] Spec-vs-code deltas surfaced during build (record here).
