# 01 — Discovery Findings

*Holistic assessment of Plainweave. Evidence drawn from repo layout, Loomweave
index (HEAD `72e8df2`, fresh), `pyproject.toml`, `README.md`,
`docs/MODULE-MAP.md`, and direct source reads.*

## 1. What this project is

**Plainweave** is a member of the "Weft federation" of developer tools. Its
charter (README, `pyproject.toml`): hold the team's **code-grounded intent** as a
traceability graph — `strategic goal ──▲── requirement ──▲── code SEI (leaf)` —
where every code entity must "earn its existence" by laddering up to a
requirement, and every requirement up to a goal. A node with no upward edge is a
reviewable question ("why does this code exist?").

It is deliberately a **thin, advisory** member:
- It owns the **intent graph** + reasoning reads.
- It **delegates** identity/rename tracking and semantic search to **Loomweave**,
  and enforcement/override/audit to **Legis** (it builds none of that itself).
- Bindings reuse the **ADR-029 entity-association contract** (SEI-keyed, with
  `content_hash_at_attach` drift detection), not a new link store.

**Critical status fact (README §Status, MODULE-MAP):** this repo is a *reframe +
rename of a precursor* (`~/charter`). The **precursor's local
requirements/verification core is intact and green**; the **reframed feature
set** (intent graph, SEI bindings, authoring-time write path, Legis boundary
cell, similarity hint) is **stubbed with backlog markers, not implemented**.
Development Status classifier: `2 - Pre-Alpha`.

## 2. Technology stack

| Concern | Choice |
| --- | --- |
| Language | Python `>=3.12` (uses `StrEnum`, modern typing) |
| Packaging | `hatchling`, `uv`, src-layout (`src/plainweave`) |
| Runtime dep | **`mcp>=1.2.0`** (official Python MCP SDK) — the *only* runtime dependency |
| Persistence | **stdlib `sqlite3`** (no ORM); schema via in-code migrations |
| Quality tooling | `ruff` (E,F,I,UP,B,SIM), `mypy --strict`, `pytest` + `pytest-cov` (branch), coverage gate `fail_under = 90` |
| Entry points | console scripts `plainweave` (CLI) and `plainweave-mcp` (MCP server) |

Notably lean: a single third-party runtime dependency. Self-contained by design
(enrich-only doctrine: siblings absent → degrade honestly, not crash).

## 3. Entry points (Loomweave-confirmed)

- `plainweave.cli.main` (`cli.py:22`) — CLI entry; console script `plainweave`.
- `plainweave.mcp_server.main` (`mcp_server.py:127`) — MCP stdio server; console
  script `plainweave-mcp`.
- `plainweave.__main__` — `python -m plainweave`.

Two front doors (CLI, MCP) over one service core. No HTTP routes (Loomweave:
zero `http-route` tags) — the MCP server speaks stdio via the SDK.

## 4. Directory structure & size

```
src/plainweave/
  service.py        2136  ← PlainweaveService god-class (orchestration core)
  mcp_surface.py    1141  ← agentic MCP read surface (PlainweaveMcpSurface)
  cli_commands.py   1066  ← CLI command handlers
  models.py          273  ← 29 dataclasses (domain model)
  store.py           254  ← SQLite connect + migrate + event log
  mcp_server.py      132  ← MCP server wiring (tool registration)
  envelopes.py       115  ← standard JSON envelope (schema/ok/data/warnings/meta)
  intent_graph.py    113  ← REFRAME: intent-graph reads — STUB (NotImplementedError)
  bindings.py         71  ← REFRAME: ADR-029 SEI bindings — STUB (NotImplementedError)
  cli.py              35  ← CLI argparse entry
  errors.py           34  ← ErrorCode enum + PlainweaveError
  paths.py            24  ← .plainweave/ repo-local dir + db path
  __main__.py / __init__.py / _version.py   (package plumbing)
                  ─────
                   5408 total
```

Organization is **by layer/responsibility**, not by feature. ~80% of src LOC
sits in three modules (`service`, `mcp_surface`, `cli_commands`).

Tests: `tests/` ~5.3K LOC across `tests/contracts/` (fixture-driven contract
tests), `tests/state/` (lifecycle/state-machine tests), and top-level
read-surface tests, plus `tests/fixtures/contracts/` golden fixtures. Test LOC ≈
src LOC — a strong test posture for the as-built core.

## 5. Domain model (Loomweave data-model inventory: 29 dataclasses)

- **Requirement identity:** `RequirementDraft` (mutable) → `RequirementVersion`
  (immutable) → `RequirementRecord`; `AcceptanceCriterion` (per ADR-002).
- **Traceability:** `TraceRef`, `TraceLink` (ontology + authority states per
  ADR-003).
- **Baselines:** `Baseline`, `BaselineMember`, `BaselineDiff(+Item)`.
- **Verification:** `VerificationMethod`, `VerificationEvidence`,
  `RequirementVerificationStatus`, `VerificationReason`.
- **Dossiers:** `RequirementDossier` + ~8 `Dossier*` section dataclasses (the
  agent-facing aggregate read).
- **Actor:** `Actor` (attribution / actor registry).
- **Reframe (stubbed):** `IntentNode`, `Trace`, `CorpusEntry`, `IntentLevel`
  (`intent_graph.py`); `SeiBinding` (`bindings.py`).

## 6. Candidate subsystems (6)

Identified by responsibility cohesion + dependency direction:

1. **Domain Model & Errors** — `models.py`, `errors.py` (+ `paths.py`).
2. **Persistence / Store** — `store.py` (SQLite, migrations, event log).
3. **Service Core (PlainweaveService)** — `service.py`. The orchestration
   god-class all front doors call.
4. **MCP Read Surface** — `mcp_surface.py`, `mcp_server.py`, `envelopes.py`.
5. **CLI** — `cli.py`, `cli_commands.py`, `__main__.py`.
6. **Intent Graph & Bindings (Reframe target)** — `intent_graph.py`,
   `bindings.py`. *Interface-only stubs.*

## 7. Architectural shape (first read)

- Classic **layered / transaction-script** architecture: CLI + MCP (presentation)
  → `PlainweaveService` (application/business) → `store.connect`/`migrate`
  (persistence) → SQLite. `models` is the shared data layer; `envelopes`/`errors`
  are cross-cutting output/contract concerns.
- `PlainweaveService` is a **facade + god-object**: highest-coupled methods in
  the repo are all `PlainweaveService.*` (`create_requirement` fan-in 31,
  `record_verification_evidence` 24, `approve_requirement` 21…); `store.connect`
  has fan-in 48 (every write path opens a connection).
- **Append-only event log** (`store.migrate`, `service._record_event`) +
  **idempotency** machinery (`_store_idempotency`, `_idempotent_*`) indicate a
  deliberate auditability/replay-safety posture in the core.
- **Contract discipline:** standard JSON envelope (`envelopes.py`), explicit
  `ErrorCode` vocab including peer `PEER_ABSENT`/`PEER_STALE` (enrich-only honest
  degradation), 6 ADRs, and golden contract fixtures under `tests/fixtures`.

## 8. Key risks surfaced for downstream docs

- **`service.py` god-class** (2136 LOC, ~29 public + ~40 private methods) — the
  dominant maintainability risk and refactor target.
- **`mcp_surface.py` / `cli_commands.py`** are both 1K+ LOC presentation modules
  that likely duplicate shaping logic over the same service calls.
- **As-built vs. target gap:** the headline feature (the code-up intent graph) is
  unimplemented; the repo today is the precursor requirements core under a new
  name. Any architecture verdict must hold these two layers apart.

**Confidence:** High for the as-built core (direct source + Loomweave + tests +
MODULE-MAP corroborate). High for the stub status of the reframe (explicit
`NotImplementedError` + docstrings).
