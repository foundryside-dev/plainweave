# 05 — Code Quality & Architecture Assessment

*Synthesized from an independent `architecture-critic` pass and a `debt-cataloger`
pass, both evidence-backed at HEAD `72e8df2` and cross-checked against the
catalog. Severity reflects as-built maintainability + reframe-blocking impact,
not runtime/operational risk (Pre-Alpha, local SQLite, stdio MCP, no HTTP
surface, single runtime dep → low operational blast radius).*

## Verdict

The **as-built core is a competently engineered, well-tested layered application
with one serious structural defect (the `PlainweaveService` god-object) and two
real but contained coupling smells.** Core quality: **3/5** — acceptable, no
critical or security issues, dragged down by the god-object and a homeless
serialization layer.

The structure is a **sound data foundation but a poor behavioral foundation for
the reframe.** The generic `trace_links` edge table is genuinely reusable for the
intent graph. The *service layer* is not: on the current trajectory the reframe
gets absorbed into the same god-object that is already the dominant risk, and the
reframe's defining edge (`requirement → goal`) does not yet exist even in embryo.
**The highest-leverage decision in the project — decompose the service before
building the graph, or staple the graph onto the god-object — is currently
undecided and undocumented in code.**

## Strengths (specific, evidence-backed)

1. **The edge store is the right substrate for the graph.** `trace_links`
   (`service.py:926`) stores `from_kind/from_id → relation → to_kind/to_id` with
   `state`/`authority`/`freshness`/`confidence` — structurally a typed directed
   edge table, exactly what `goal → requirement → code` needs. The reframe does
   not need a new link store (MODULE-MAP's "storage carries forward" is correct).
2. **The code→requirement edge already exists.** `_validate_trace_relation`
   (`service.py:1877`) canonicalizes `(loomweave_entity, satisfies,
   requirement_version)`. The lower half of the intent ladder is modeled today.
3. **Disciplined contract surface.** Standard JSON envelope (`envelopes.py`),
   closed `ErrorCode` vocab switched on `code` not message,
   `PEER_ABSENT`/`PEER_STALE` modeling honest enrich-only degradation (ADR-004).
   Doctrine-to-code fidelity, not aspiration.
4. **Auditable spine.** Append-only event log (`_record_event`,
   `service.py:1901`) + idempotency machinery + explicit state-machine validation
   for trace transitions (`_validate_trace_transition`, `service.py:1891`) — a
   deliberate replay-safe posture, rare at this size. **Preserve it through any
   refactor.**
5. **Strong test posture for the core.** Test LOC ≈ src LOC, golden contract
   fixtures (`tests/fixtures/contracts/`), branch coverage gate `fail_under=90`.
   The carried-forward core is genuinely green, and the suite is the safety net
   that makes the recommended decomposition low-risk.
6. **Honest stubs.** `intent_graph.py` / `bindings.py` define data shapes and
   `raise NotImplementedError(_PENDING)` with docstrings pointing at the design +
   backlog; `service.py` imports neither. The unbuilt is unambiguously unbuilt —
   the correct way to stand up a reframe.

## Technical Debt Register (as-built)

> Reframe stubs are **planned scope, excluded** from debt. `src/` carries **zero
> TODO/FIXME/HACK markers** (grep + Loomweave `entity_todo_list` both empty) and
> **no confirmed dead code** in as-built code (the 143 Loomweave dead-candidates
> are low-confidence false positives — argparse-registered `handle_*`/`_register_*`
> thunks + the reframe stubs).

| ID | Title | Location | Category | Sev | Effort |
| --- | --- | --- | --- | --- | --- |
| **DEBT-01** | `PlainweaveService` god-object (2136 LOC, 1 class, 29 pub + 64 priv, 6 clusters) | `service.py` | god-object | **High** | L |
| **DEBT-02** | Homeless serialization layer shared via private cross-module imports | `cli_commands.py:717–1066` → imported by `mcp_surface.py:9–17` | misplaced-layer / coupling | **High** | M |
| **DEBT-03** | Leaky persistence boundary: CLI bypasses service to hit the store | `cli_commands.py:39`, used `:627–629,647–648` | coupling / misplaced-layer | **High** | S |
| **DEBT-04** | Oversized presentation modules, co-mingled concerns | `mcp_surface.py` (1141), `cli_commands.py` (1066) | cohesion | Med | M |
| **DEBT-05** | Partial duplication of read-shaping (shared mappers + inline MCP literals) | `mcp_surface.py` (many `:345…:1126`) vs `cli_commands` mappers | duplication | Med | M |
| **DEBT-06** | Domain model mixes value objects with presentation read-models (10 of 25 are `Dossier*`) | `models.py:186–272` | misplaced-layer | Med | M |
| **DEBT-07** | In-code monolithic migration; flat `SCHEMA_VERSION = 1`, no upgrade ladder | `store.py:22–251` | migration | Med | M now / L later |
| **DEBT-08** | Weak subsystem modularity (Loomweave clustering signal) — *symptom of 01/02/03* | whole import graph | architecture | Low | — |
| **DEBT-09** | `.env` flagged with high-entropy secret — **not committed** (gitignored), hygiene only | `.env:1` | hygiene | Low | S |

### The reframe-readiness finding (cross-cuts DEBT-01)

`_validate_trace_relation` (`service.py:1877–1889`) is a hardcoded `set` of
`(from_kind, relation, to_kind)` triples with **no `goal` kind and no
`requirement → goal` triple**, and `trace_for` (`service.py:977`) is a
**single-hop SQL `WHERE` filter, not a graph walk**. So the reframe's two named
primitives are net-new behavior: `trace(node)`/`orphans(level)` need recursive
graph traversal that has no precursor, and the "altitudes are just node types,
not fixed levels" design promise (`intent_graph.py:36`) directly contradicts a
hardcoded triple allow-list. *"The data model carries forward" is true for the
table and misleading for the behavior.*

## Risk assessment & sequencing

- **DEBT-01 is highest-leverage and most expensive to defer:** every reframe
  reshape (binding contract, goal altitude, orphan computation) lands on this
  class; deferring the split compounds against planned scope, producing a
  ~2500-LOC god-object that is materially harder to break up.
- **DEBT-02 / DEBT-03 are low-risk, high-value mechanical extractions** — safe to
  do first; they de-risk DEBT-04 / DEBT-05 and remove the only layering inversion.
- **DEBT-07 is a time-bomb:** cheap now (single version), expensive once the
  reframe adds goal-node / binding-cache tables and existing DBs need in-place
  upgrade. Address before the reframe touches the schema.
- Decomposition is **behavior-preserving and test-backed** — the existing suite
  backstops it. Risk of acting: Low. Risk of not acting: rises monotonically.

## Confidence, gaps, caveats

- **Confidence: High** for DEBT-01…07 and all strengths — every claim is a
  line-cited source read cross-checked against Loomweave and the independent
  catalog. **Medium** on DEBT-05 *severity* (partial duplication, drift-risk not
  gross copy-paste).
- **Gaps:** (1) coverage not re-executed — the 90% gate + green status are taken
  from config + prior analysis, not re-run; no per-cluster `service.py` unit
  tests were observed (plausible but unverified test gap). (2) The `.filigree`
  backlog epics (`plainweave-c2d58800a0` + siblings) and the referenced
  implementation plan were **not** read — the decompose-vs-build *sequencing* may
  already be planned there; if so, the "unmanaged gap" framing softens to "verify
  the plan decomposes first."
- **Caveats:** no security/perf assessment warranted by current scope; if a
  future seam adds a network surface (e.g. a Legis HTTP boundary), trust-boundary
  review (wardline) becomes load-bearing and is out of scope here.
