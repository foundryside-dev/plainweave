# 04 — Final Report

**Subject:** Plainweave · **Live tree:** HEAD `8258f76` · **Date:** 2026-06-28
**Analysis:** Architect-Ready track. 5 parallel subsystem explorers (100% source
read per slice) + orchestrator edge-reconciliation against the Loomweave graph +
an independent validation gate (verdict **PASS-WITH-FIXES**, all 8 high-stakes
claims VERIFIED against live source, fixes applied). Companion docs:
`01-discovery-findings`, `02-subsystem-catalog`, `03-diagrams`,
`05-quality-assessment`, `06-architect-handover`.

---

## Executive summary

Plainweave is a **code-grounded requirements-traceability / intent-corpus**
service — the "permission for code to exist" member of the Weft federation. It
maintains a graph (`strategic goal ▲ requirement ▲ code-SEI`) where every public
code surface should ladder up to a requirement and every requirement up to a
goal; the north-star read is **`intent_coverage`** (the fraction of public
surfaces that are justified). Its doctrine is **advisory / enrich-only**: it
never gates, delegating teeth + audit to Legis and identity + semantics to
Loomweave.

**The architecture is clean, conventional, and well-tested — a textbook layered
service whose discipline is real, not aspirational.** Three thin delivery
surfaces (a `plainweave` CLI, a read-only `plainweave-mcp` server, an optional
single-operator web console) sit over one `PlainweaveService`, an SQLite store,
two read-only sibling adapters, and a uniform versioned-envelope response
contract. There are **no circular module imports**, a **closed 10-value error
vocabulary**, **event-sourcing with DB-trigger immutability**, **golden-vector
contract tests for every cross-member seam**, and an enforced **≥90% branch-
coverage gate**. For a 1.1.0 product the contract discipline is genuinely strong.

**The risk is concentrated in two places, both well-understood and bounded by
the product's single-operator local-first model:**
1. **One 3027-LOC god object** (`PlainweaveService`) that is simultaneously the
   use-case tier, the data-access tier (raw inline SQL, no repository), *and* the
   intent-graph engine. It is the dominant maintainability liability.
2. **A pervasive connect-per-call / N+1 SQLite pattern with no WAL**, which makes
   reads O(corpus) on the hot paths (MCP preflight, coverage, the web review
   queue) and serializes concurrent surfaces on the writer lock. The team already
   tracks this (two open P3 tasks).

Neither is a correctness defect at the intended scale; both are scaling/
maintainability ceilings. One genuine correctness gap exists — **DB exceptions
escape the documented `ErrorCode` contract** — that is cheap to close.

**Verdict: architecturally sound and production-credible for its stated scope
(single-operator, local-first, advisory). The refactor levers are a service
decomposition and a persistence-layer fix; both are well-isolated.**

---

## Architecture at a glance

| Dimension | Finding |
|-----------|---------|
| Shape | Layered service: 3 surfaces → 1 domain service → store + adapters + contract |
| Source size | ~9.6K LOC src / ~10.1K LOC tests (361 test functions) |
| Subsystems | 8 (Domain Service Core, Intent Graph, CLI, MCP, Web UI, Persistence, Sibling Adapters, Response Contract) |
| Entry points | `plainweave` (CLI), `plainweave-mcp` (read-only MCP); web is a CLI subcommand behind the `[web]` extra |
| Persistence | SQLite (stdlib `sqlite3`, no ORM), schema v2, connect-per-call, `DELETE` journal mode |
| Write surface | Web console **only** (MCP is read-only; CLI mutates via the service) |
| External seams | reads Loomweave (catalog/SEI) + Wardline (findings); produces enrichment for Warpline; coverage facts ride to Legis at git/CI |
| Module cycles | none (`cycles:[]`) |
| Quality gates | ruff + `mypy --strict` + pytest `fail_under=90` (branch) — enforced via `make ci` |

The dependency story (verified against the Loomweave graph): **all three surfaces
depend on the service and the response contract; the service fans out to
persistence, the intent-graph types, and the adapters.** Two edges break the
clean layering — see "Structural exceptions" below.

---

## What is done well (evidence-anchored strengths)

- **Uniform, machine-switchable response contract.** Every CLI/MCP/service
  response is wrapped through central choke points (`_handle_service_result`
  fan-in 24, `_result` fan-in 16) into a versioned `weft.plainweave.*` envelope
  with a closed `ErrorCode` StrEnum (fail-closed: unknown codes raise). Three
  `PEER_*` codes carry sibling-degradation *into* the error contract — a
  thoughtful federation-aware design.
- **Honest enrich-only degradation, never an implied-clean.** Sibling absence is
  a typed `unavailable` with a closed degrade vocabulary ("result is unavailable,
  not clean"); `live_peer_calls` is hard-`False`; content-hash drift is flagged
  `stale`, never silently dropped. This is the doctrine actually implemented, not
  just documented.
- **Integrity pushed into the database.** Append-only `events`, immutable
  approved requirement text, locked-baseline immutability — all enforced by SQL
  triggers, not just Python. Writes use optimistic concurrency (`expected_version`)
  + replayable idempotency keys.
- **Identity that survives refactors.** Code leaves are keyed by Loomweave SEI
  (ADR-029 entity-associations with `content_hash_at_attach` drift detection),
  so bindings outlive rename/move.
- **Test discipline is real.** 361 tests; a genuine ≥90% branch-coverage gate;
  golden-vector wire-contract tests for *every* seam (preflight, wardline/warpline
  peer facts, envelopes); a vendored SEI-conformance oracle with a drift gate.
- **Clean module graph.** No import cycles; pure-leaf models/types; lazy imports
  keep the web framework optional.

## Where the risk concentrates (ranked)

1. **God object — `PlainweaveService` (3027 LOC).** One class, ~13 aggregates,
   use-case + data-access + intent-engine in one file. Cohesion is held together
   by a high-fan-in private helper cluster (`_error`, `_now`, `_require_actor`,
   `_record_event`, `_requirement_row`). Dominant maintainability risk; the
   product's *defining capability* (coverage/orphans/trace) is buried at
   `service.py:1311-1507` rather than isolated in the `intent_graph` module that
   names it.
2. **Connect-per-call / N+1 + no WAL.** `store.connect` (fan-in 44) opens a fresh
   connection per op with no pool, in `DELETE` journal mode. Hot paths are
   O(corpus): MCP `preflight_facts_get` defaults to scanning the entire corpus
   with 3 service calls per requirement and *no pagination*; `intent_coverage`
   opens a connection per catalog surface; the web review queue re-fetches a
   dossier per draft per render. Concurrent surfaces serialize on the writer lock.
3. **DB exceptions escape the `ErrorCode` contract (correctness).** Only domain
   failures route through `_error`→`PlainweaveError`; raw `connection.execute` is
   unguarded, so `sqlite3.IntegrityError`/`OperationalError` propagate past
   callers that switch on `ErrorCode`. Validated end-to-end (both surface result
   paths catch `except PlainweaveError` only).
4. **Surface↔surface coupling.** `cli_commands.py` is a de-facto shared
   services/DTO layer: the MCP surface imports its private serializers +
   `inspect_project`; the new CLI handler lazily imports `PlainweaveMcpSurface`.
   No module-load cycle (the function-local import dodges it), but a real
   architectural inversion.
5. **Web exposure with no authN/authZ.** The sole write surface authenticates a
   process-singleton operator with CSRF as the only request-level control; a
   settable `--host 0.0.0.0` exposes all 7 write endpoints with no compensating
   gate. By design for local-first, but the flag has no guard.

Full severity-rated catalogue with remediations in `05-quality-assessment.md`;
sequenced backlog in `06-architect-handover.md`.

## Structural exceptions to the clean layering

- **CLI → Persistence (direct).** `init`/`inspect` call `store.connect()`
  directly, bypassing the service — plausibly justified (`init` migrates before a
  service exists) but a documented hole in "surfaces only talk to the service."
- **MCP → CLI (serializers).** The DTO layer lives in `cli_commands.py`, not a
  neutral contract module, so the two agent surfaces are mutually dependent.

## Maturity & fitness for purpose

The README claims 1.0/"Production-Stable"; the code is at **1.1.0**. The green
gate (lint + strict types + 90% branch coverage) is enforced and the contract
discipline is real, so "stable behaviour and contracts" is a *fair* claim. Two
honesty caveats worth carrying: (a) the web review-queue **accessibility
behaviour** (focus management + live-region announcements) the README emphasizes
is **manual-AT-only and ungated in CI** — only structural contracts are tested;
(b) the suppressed `ResourceWarning: unclosed database` in `pyproject.toml` is
blamed on "store-layer connections," but production connections close
deterministically in `finally` — the warning is actually a **test-fixture** leak
(see Q23 in `05`), and the suppression comment is misleading, not evidence of a
production defect.

Against its doctrine — **coordinate-not-gate, enrich-only, speak-SEI-at-entry,
don't-duplicate, prescribe-nothing** — the implementation is faithful: it is
genuinely thin (one runtime dep, `mcp`), genuinely advisory (no enforcement
path), genuinely enrich-only (typed degradation), and genuinely composable
(three primitives, not canned reports). The architecture serves the product
thesis well.

## Limitations of this analysis

- **Static analysis only.** No runtime profiling; performance claims rest on
  call-shape (e.g. "O(corpus)"), not measured latency. The N+1 is confirmed in
  *code structure*, not benchmarked.
- **Index/live split.** Loomweave structural integers (fan-in/out, coupling)
  derive from commit `e95b6ad`; the live tree is `8258f76` (+80 LOC in 2 files —
  the peer-facts CLI/MCP parity subcommands). All catalog claims were read from
  live source; the integers were additionally grep-confirmed by the validator
  (the index DB was mid-rebuild during validation). **Re-run `loomweave analyze`
  before treating coupling integers as current-HEAD.**
- **Tests read for evidence, not audited.** Coverage *gate* confirmed from config;
  the suite was not independently re-run in this pass.
