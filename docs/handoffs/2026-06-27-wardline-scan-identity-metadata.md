# Peer prompt — Wardline: emit scan-identity / scope metadata in findings output

**To:** the Wardline maintainer / implementing agent.
**From:** Plainweave (sibling handoff, 2026-06-27).
**Priority:** enabling — unblocks honest cross-snapshot consumption; not a gate.
**Status:** COORDINATED PARALLEL WORKSTREAM — the Plainweave owner is implementing this
concurrently for integration testing. The `scan_manifest` shape below is the **agreed
contract**: Plainweave's Wardline adapter consumes it as its primary scope source
(`scope.covered_paths`, `scan_id`, `ruleset_id`, `commit`) and falls back to a path-set
heuristic only when it is absent. Build to this shape so the two sides integrate.

## Context

Plainweave now reads Wardline's local `.wardline/*-findings.jsonl` snapshots and
surfaces findings as advisory peer facts, including **resolved/unseen** (a finding
present in an earlier scan but gone from the latest). Computing that honestly requires
knowing whether a missing fingerprint was *re-scanned and resolved* versus *simply not
in this run's scope*. Conflating the two is a silent-clean defect.

Today the findings JSONL carries **no scan-identity metadata** — records hold only
`fingerprint, kind, location, maturity, message, properties, qualname,
related_entities, rule_id, severity, suggestion, suppression_reason,
suppression_state`. There is no covered-surface, ruleset, or commit signal. Plainweave
currently approximates the scanned surface by the union of `location.path` values in
the latest snapshot — a heuristic that breaks when scope changes between runs (observed:
two Jun-25 snapshots had identical scope; Jun-26 widened from 2 paths to 9, jaccard 0.22).

## What to build (Wardline side)

Emit per-run scan-identity metadata so consumers can compare snapshots by exact scope.
Either form is acceptable; the first is preferred:

1. **Manifest record / header** (one record per file, distinguishable, e.g.
   `kind: "scan_manifest"`):
   ```json
   {
     "kind": "scan_manifest",
     "scan_id": "<uuid-or-content-hash>",
     "started_at": "<iso8601>",
     "commit": "<git-sha-or-null>",
     "ruleset_id": "<id+version>",
     "scope": {
       "selector": "<the path/glob/scope arg used>",
       "covered_paths": ["src/...", "..."]   // the actual scanned surface
     }
   }
   ```
2. **Per-finding scope key** — at minimum a stable `scan_id` and `ruleset_id` on every
   record, plus a way to recover `covered_paths`.

## Hard invariants

- Additive and backward-compatible — do not change the existing finding fields or the
  `fingerprint` derivation; consumers read findings opaquely.
- The `covered_paths` (or scope selector) must reflect what was *actually* scanned, so
  "missing fingerprint inside covered scope" = resolved, and "missing fingerprint
  outside covered scope" = not-scanned (consumer reports `unavailable`).

## Acceptance criteria

- Two consecutive `.wardline/*-findings.jsonl` snapshots can be compared by an explicit
  scope key without guessing from `location.path`.
- A consumer can distinguish `resolved` from `not re-scanned` for every prior
  fingerprint, with no heuristic.
- Existing consumers that ignore the new metadata keep working unchanged.

## References

- Plainweave spec: `docs/superpowers/specs/2026-06-27-peer-facts-wardline-warpline-design.md`
  §5.3 (the path-set heuristic this metadata replaces) and §4 (no-silent-clean).
