# 04 — Final Report

**Project:** Plainweave · **Commit:** `72e8df2` · **Date:** 2026-06-21 ·
**Deliverable:** Architect-Ready (Option C) · **Strategy:** sequential analysis +
subagent validation/quality gates

## Executive summary

Plainweave is a small (~5.4K src LOC), single-language (Python 3.12) tool that is
a **reframe + rename of a precursor (`~/charter`)**. It aspires to be the Weft
federation's holder of *code-grounded intent*: a traceability graph where every
code entity (a Loomweave SEI) must ladder up to a requirement and every
requirement up to a goal, surfacing a readable, queryable **intent corpus**.

The most important finding of this analysis is a **two-layer reality**:

1. **What is built** — a competent, well-tested requirements/verification engine
   carried forward from the precursor: requirement lifecycle, acceptance
   criteria, trace links, baselines, verification, dossiers, all over an
   append-only event-logged SQLite store, exposed through a CLI and a read-only
   MCP surface with disciplined JSON envelopes and a closed error vocabulary.
   **This core is green and dependable (quality 3/5).**

2. **What is named but not built** — the headline reframe (the intent graph's
   `orphans`/`trace`/`corpus` primitives, the goal altitude, ADR-029 SEI
   bindings, the authoring-time write path). These are **honest
   `NotImplementedError` stubs**; the project has, in effect, *built a solid
   requirements engine and a correct edge-store, then named itself after a
   graph-traversal feature it has not started.*

The structure carries the reframe's **data** well (the generic `trace_links`
table is the right substrate) but its **behavior** poorly: the reframe will, on
the current trajectory, be absorbed into a 2136-LOC `PlainweaveService`
god-object that is already the dominant maintainability risk — and the reframe's
defining edge (`requirement → goal`) does not yet exist even as a relation triple.

## Architecture at a glance

- **Style:** layered / transaction-script. CLI + MCP (presentation) →
  `PlainweaveService` (application) → `store` (persistence) → SQLite. `models`
  is the shared data layer; `envelopes` + `errors` are cross-cutting contracts.
- **Six subsystems:** Domain Model & Errors · Persistence/Store · Service Core ·
  MCP Read Surface · CLI · Intent Graph & Bindings (reframe, stubbed). See
  `02-subsystem-catalog.md`; diagrams in `03-diagrams.md`.
- **Two entry points:** `plainweave` (CLI) and `plainweave-mcp` (MCP stdio).
- **One runtime dependency** (the MCP SDK); raw `sqlite3`; enrich-only/advisory
  doctrine (siblings absent → honest degradation).

## Top findings (ranked)

| # | Finding | Severity | Where |
| --- | --- | --- | --- |
| 1 | `PlainweaveService` god-object: 2136 LOC, 1 class, 6 responsibility clusters | **High** | `service.py` |
| 2 | Reframe's `requirement → goal` edge + graph-walk behavior do not exist; trace ontology is a hardcoded allow-list; `trace_for` is single-hop SQL | **High** (reframe-blocking) | `service.py:1877`, `:977` |
| 3 | Homeless serialization layer: `mcp_surface` imports private `_*_dict` from `cli_commands` (layering inversion) | **High** | `mcp_surface.py:9–17` |
| 4 | Leaky persistence boundary: CLI calls `store.connect/migrate` directly | High | `cli_commands.py:39` |
| 5 | Oversized presentation modules + partial read-shaping duplication | Medium | `mcp_surface.py`, `cli_commands.py` |
| 6 | Domain model mixes value objects with `Dossier*` read-models | Medium | `models.py:186–272` |
| 7 | Monolithic in-code migration; no version-upgrade ladder | Medium (time-bomb) | `store.py:22–251` |

Full register + evidence: `05-quality-assessment.md`.

## Strengths worth protecting

The generic typed-edge store, the code→requirement edge already modeled, the
append-only event log + idempotency spine, the closed error/envelope contracts
(ADR-004), 6 ADRs, and a test suite roughly equal in size to the source with
golden contract fixtures and a 90% branch-coverage gate. These are real and
should be preserved through any refactor.

## The one decision that matters

**Decompose `PlainweaveService` first; build the intent graph second.** Doing it
in the other order produces a ~2500-LOC god-object that is materially harder to
break up, and bolts the reframe's defining feature onto the project's worst
structural defect. The decomposition is behavior-preserving and backstopped by
the existing test suite. Sequenced remediation is in `06-architect-handover.md`.

## Method & confidence

Sequential analysis by one analyst over a Loomweave-indexed tree (fresh at
`72e8df2`), with the subsystem catalog independently **validated**
(`temp/validation-catalog.md`, verdict PASS-WITH-NOTES — two corrections applied:
`models.py` holds 25 dataclasses not 29; coupling fan-ins are test-inclusive) and
the quality assessment produced by independent `architecture-critic` and
`debt-cataloger` passes. Confidence **High** for the as-built findings (all
line-cited and corroborated). Known gaps: coverage not re-executed; the
`.filigree` backlog + implementation plan not read (the decompose-vs-build
sequencing may already be planned there — verify).

## Deliverables index

| Doc | Contents |
| --- | --- |
| `00-coordination.md` | configuration, strategy, execution log |
| `01-discovery-findings.md` | holistic scan, stack, subsystem identification |
| `02-subsystem-catalog.md` | six subsystem entries (validated) |
| `03-diagrams.md` | C4 context / module / component / domain diagrams |
| `04-final-report.md` | this synthesis |
| `05-quality-assessment.md` | strengths, debt register, sequencing |
| `06-architect-handover.md` | prioritized improvement plan |
| `temp/validation-catalog.md` | catalog validation report |
