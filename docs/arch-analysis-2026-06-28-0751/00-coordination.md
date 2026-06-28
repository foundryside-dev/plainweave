# 00 — Coordination Plan

## Analysis Configuration

- **Subject:** Plainweave — "permission for code to exist." Code-grounded
  requirements-traceability / intent-corpus member of the Weft federation.
- **Scope:** `src/plainweave/` (production source, ~9.6K LOC across 27 `.py`
  files) + supporting `tests/` (~10.1K LOC) for verification evidence. Docs
  read for product framing, not analyzed as code.
- **Deliverables:** **Option C — Architect-Ready** (full analysis + code-quality
  assessment + architect handover):
  - `01-discovery-findings.md` (holistic assessment)
  - `02-subsystem-catalog.md` (per-subsystem evidence-based entries)
  - `03-diagrams.md` (C4 context / container / component)
  - `04-final-report.md` (synthesis)
  - `05-quality-assessment.md` (tech debt, hotspots)
  - `06-architect-handover.md` (improvement backlog → feeds axiom-system-architect)
- **Complexity estimate:** Medium. ~9.6K LOC, Python 3.12, single deployable
  with three delivery surfaces (CLI / MCP / web) over one domain service +
  SQLite + two sibling-tool adapters. Loomweave index is **fresh**
  (1256 entities, 4282 edges, 46 fine-grained clusters), so structural facts
  are queryable rather than grep-derived.

## Orchestration Strategy — PARALLEL (with validation gates)

**Decision: parallel subsystem exploration.** Rationale:

- 7 cohesive subsystems identified (below), loosely coupled: the three
  surfaces depend on the service but not on each other; adapters and store are
  isolated; cross-cutting (envelopes/errors/paths) is leaf-level.
- Although LOC (~9.6K) is under the 20K "large" threshold, the heaviest unit
  (`service.py`, 3027 LOC) plus two ~1.6K-LOC surface modules make
  single-pass sequential analysis lossy. Parallel explorers each own a bounded
  region and return schema-conforming catalog entries with file/line evidence.
- Multi-subsystem (≥3) ⇒ **validation subagent is MANDATORY** after the
  catalog and after the final report (per the analyze-codebase contract).

**Explorer fan-out (5 agents, balanced by LOC):**

| Agent | Subsystem(s) | Modules | ~LOC |
|-------|--------------|---------|------|
| E1 | Domain Service Core | `service.py`, `models.py`, `intent_graph.py`, `bindings.py` | 3619 |
| E2 | MCP Surface | `mcp_server.py`, `mcp_surface.py` | 1837 |
| E3 | CLI Surface | `cli.py`, `cli_commands.py` | 1669 |
| E4 | Web UI | `web/` (app, server, context, views, errors, routes/*) | ~900 |
| E5 | Persistence + Sibling Adapters + Response Contract | `store.py`, `loomweave_adapter.py`, `wardline_adapter.py`, `envelopes.py`, `errors.py`, `paths.py` | ~1500 |

Then: validation gate (analysis-validator) → diagrams → final report →
validation gate → quality assessment → architect handover.

## Execution Log

- 2026-06-28 07:51 — Created workspace `docs/arch-analysis-2026-06-28-0751/`.
- 2026-06-28 07:52 — User selected **Option C (Architect-Ready)**.
- 2026-06-28 07:53 — Holistic scan complete (filesystem + Loomweave index):
  tree mapped, LOC distribution measured, entry points + coupling hotspots
  pulled, README/product framing read. Subsystems identified.
- 2026-06-28 07:54 — Strategy set to PARALLEL (5 explorers). Wrote coordination
  plan + discovery findings. Advisor sanity-checked the decomposition.
- 2026-06-28 07:55 — Dispatched 5 `codebase-explorer` agents (E1–E5). In
  parallel, orchestrator built the authoritative dependency map from the
  Loomweave global graph (no cycles; N+1 confirmed at source; CLI→store leak;
  warpline = producer seam) and gathered the test/coverage taxonomy.
- 2026-06-28 08:01–08:07 — Explorers returned (8 catalog entries). **Fidelity
  correction:** live HEAD is `8258f76`, 6 commits / +80 LOC past the indexed
  `e95b6ad` (confined to cli_commands.py + mcp_surface.py — peer-facts CLI/MCP
  parity); basis label corrected in `01`.
- 2026-06-28 08:08 — Merged `02-subsystem-catalog.md` (8 entries + cross-cutting
  themes), reconciling one-sided explorer edge claims against the global graph.
- 2026-06-28 08:09 — **Validation gate:** dispatched `analysis-validator`.
  Verdict **PASS-WITH-FIXES** — 8/8 entries contract-complete, all 8 high-stakes
  claims VERIFIED against live source, no over-claim. 3 Low citation fixes
  applied (web route locus, local-import line nums, `_register_*` count).
- 2026-06-28 08:10 — Wrote `03-diagrams.md` (6 C4-style + sequence views) from
  the verified edge map.
- 2026-06-28 08:12 — Wrote `04-final-report.md`, `05-quality-assessment.md`
  (22-item severity-rated register), `06-architect-handover.md` (7 sequenced
  initiatives → axiom-system-architect).
- 2026-06-28 08:13 — Advisor review caught (a) a dropped second validation gate
  and (b) an over-claim: Initiative A "removes the `ResourceWarning`" — but
  production connections already close deterministically; verified the warning is
  a **test-fixture** leak. Corrected → new finding **Q23**; fixed `05`/`06`.
- 2026-06-28 08:14 — **Validation gate 2:** dispatched `analysis-validator` over
  the synthesis layer (`03`–`06`). Verdict **PASS-WITH-FIXES** — all 23 Q-items
  trace to source/catalog, severity 4/8/11 consistent, diagrams faithful,
  remediations sound. 3 fixes applied: stale `ResourceWarning` clause in `04`
  (the required one); tracker `3edcd19943`→Q5 remapped to preflight Q3/Q4; SQLite
  mapping precision (UNIQUE/PK→CONFLICT; `BEGIN IMMEDIATE` prevents the race).
- _status_ — **COMPLETE & DOUBLE-VALIDATED.** All Option-C deliverables produced;
  both mandatory validation gates passed with fixes applied.

## Outcome

Plainweave is a clean, conventional, well-tested layered service (3 surfaces → 1
domain service → SQLite + adapters + contract). No module cycles; ≥90% branch
gate; golden-vector seam tests. Risk concentrates in (1) a 3027-LOC god object
and (2) a pervasive connect-per-call / N+1 / no-WAL persistence pattern; one real
correctness gap (DB exceptions escape the `ErrorCode` contract). All bounded by
the single-operator local-first scope and addressable via the handover backlog.
