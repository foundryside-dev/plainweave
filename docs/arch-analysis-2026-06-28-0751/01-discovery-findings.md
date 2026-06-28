# 01 — Discovery Findings (Holistic Assessment)

**Subject:** Plainweave · **Live tree:** HEAD `8258f76` · **Date:** 2026-06-28
**Method:** filesystem scan + Loomweave index + product docs. Evidence is cited
as `file:line` (live tree) or Loomweave fan-in/out (indexed commit).

> **Basis fidelity (read this).** The catalog and concerns reflect the **live
> working tree at HEAD `8258f76`** (what the explorers read). Loomweave's
> structural metrics (coupling, fan-in/out, caller lists, `cycles:[]`) reflect
> the **indexed commit `e95b6ad`**, which is **6 commits / +80 net src LOC
> behind** — and that delta is confined to **two files**
> (`cli_commands.py` +77, `mcp_surface.py` +9/−3): the `wardline-peer-facts`
> and `requirements-enrichment` CLI/MCP parity subcommands plus a peer-facts
> fix. **All other modules are byte-identical**, so the god-object / N+1 /
> layering findings are unaffected. Two index-vs-live discrepancies to carry
> forward: (a) the live CLI exposes 16 commands / 38 handlers vs. the indexed
> set; (b) the new `handle_wardline_peer_facts` adds a **function-local (lazy)
> import** of `PlainweaveMcpSurface` — a CLI↔MCP coupling absent from the
> e95b6ad graph (hence the index's `cycles:[]`), confirmed by explorers reading
> live. Refresh with `loomweave analyze` before treating the edge metrics as
> current.

---

## 1. What Plainweave is

A **code-grounded requirements-traceability and intent-corpus** service — the
"permission for code to exist" member of the Weft federation. It maintains a
traceability graph:

```
strategic goal ──▲── requirement ──▲── code SEI (leaf)
   (root intent)      (obligation)        (the thing that exists)
```

Edges mean *"justified by / satisfies."* Leaves are Loomweave SEIs (stable
code identities surviving rename/move); interior nodes are typed intent nodes.
The headline metric is **`intent_coverage`** — the fraction of public code
surfaces that ladder up to a requirement. Doctrine: **advisory / enrich-only**
(Plainweave never gates; it delegates teeth + audit to Legis and identity +
semantics to Loomweave). README:50–115.

**Maturity:** README declares 1.0 / "Production/Stable" (pyproject classifier
`Development Status :: 5`); green gate = ruff + mypy `strict` + pytest at
≥90% coverage. Tests (~10.1K LOC) slightly exceed source (~9.6K LOC).

## 2. Technology stack

- **Language:** Python ≥3.12 (`.python-version`, `requires-python`).
- **Runtime deps:** `mcp>=1.2.0` only (the official MCP SDK). Deliberately thin.
- **Optional extra `[web]`:** `starlette`, `uvicorn`, `jinja2` — the operator UI.
- **Persistence:** SQLite via stdlib `sqlite3` (no ORM); `store.py` owns
  connect + schema migration.
- **Build/tooling:** `hatchling`, `uv`, `ruff` (E,F,I,UP,B,SIM; line 120),
  `mypy --strict`, `pytest` + `coverage` (gated). `Makefile`/`make ci`.
- **Entry points (`pyproject [project.scripts]`):**
  - `plainweave = plainweave.cli:main` — CLI
  - `plainweave-mcp = plainweave.mcp_server:main` — read-only MCP server
  - (web is a CLI subcommand `plainweave web`, gated behind the extra)
- Loomweave confirms exactly **two `entry-point`-tagged functions**:
  `plainweave.cli.main`, `plainweave.mcp_server.main`.

## 3. Codebase shape (measured)

Source is a **mostly-flat module package** under `src/plainweave/` (17 direct
modules, 8653 LOC) plus a `web/` subpackage (~900 LOC). LOC by module:

| Module | LOC | Role (first read) |
|--------|-----|-------------------|
| `service.py` | **3027** | `PlainweaveService` — the domain god-object; all use-cases |
| `mcp_surface.py` | 1653 | MCP tool implementations (read + preflight + peer facts) |
| `cli_commands.py` | 1631 | CLI subcommand handlers |
| `loomweave_adapter.py` | 657 | Loomweave catalog/SEI/semantic enrichment seam |
| `wardline_adapter.py` | 373 | Wardline peer-facts seam |
| `store.py` | 311 | SQLite connect + schema migration |
| `models.py` | 310 | domain dataclasses / typed records |
| `web/routes/review.py` | 258 | ratification queue routes |
| `web/routes/requirements.py` | 215 | requirement authoring routes |
| `mcp_server.py` | 184 | MCP server wiring (`create_mcp_server`) |
| `intent_graph.py` | 184 | coverage / orphans / trace graph computation |
| `web/views.py` | 130 | view-model assembly |
| `envelopes.py` | 115 | versioned success/error JSON envelopes |
| `bindings.py` | 98 | ADR-029 SEI entity-association bindings |
| `web/app.py` | 80 | Starlette app factory |
| `web/context.py` | 61 | request/service context |
| `web/server.py` | 59 | uvicorn launcher |
| smaller: `web/routes/{goals,intent}.py`, `cli.py`, `errors.py`, `paths.py`, `web/errors.py`, `__main__.py` | <50 each | wiring / leaf contracts |

`src/plainweave/experimental/` exists but holds **no live `.py`** (only stale
`__pycache__` for a `plan_check` module) — a dead/abandoned package to flag.

## 4. Subsystems identified (7)

1. **Domain Service Core** — `service.py`, `models.py`, `intent_graph.py`,
   `bindings.py`. The `PlainweaveService` orchestrates every use-case (create/
   approve requirement, acceptance criteria, verification evidence, trace links,
   dossier, baseline, events). `intent_graph` computes coverage/orphans/trace.
2. **MCP Surface** — `mcp_server.py` (`create_mcp_server`, fan-out 21),
   `mcp_surface.py`. Read-only tools (`mutates:false`, `local_only:true`)
   mirroring intent reads + `preflight_facts` + Wardline peer facts.
3. **CLI Surface** — `cli.py` (`main`, entry-point), `cli_commands.py`.
   Argparse dispatch over `init/intent/req/goal/bind/catalog/criterion/verify/
   status/dossier/baseline/actor/doctor/web`.
4. **Web UI** — `web/` Starlette operator console (browse corpus, author
   requirements, ratify drafts/trace links). Local-first, single-operator,
   advisory.
5. **Persistence** — `store.py`. SQLite `connect` (fan-in **44** — the single
   most-coupled entity in the codebase) + `migrate` (schema, fan-in 14).
6. **Sibling-Tool Adapters** — `loomweave_adapter.py` (catalog/SEI/semantic),
   `wardline_adapter.py` (peer facts). Enrich-only seams; siblings absent ⇒
   explicit `unavailable`, never an implied clean state.
7. **Response Contract / Cross-cutting** — `envelopes.py` (versioned envelopes),
   `errors.py` (closed error-code vocab, fan-in 18), `paths.py` (store-path
   resolution), `_version.py`.

## 5. Coupling & risk signals (from the index, pre-catalog)

- **`store.connect` fan-in 44** — every persistence path opens its own
  connection (per-call connect pattern). Two open P3 tracker tasks confirm the
  smell: *"N+1 SQLite connections per scoped requirement"* and *"`project`
  scope fans out over all requirements with no cap / facts pagination."*
- **`service.py` at 3027 LOC** is a god-object: `_error`, `_now`,
  `_require_actor`, `_record_event`, `_requirement_row` are high-fan-in private
  helpers shared across dozens of use-cases. Prime refactor target for the
  quality pass.
- Envelope/error helpers (`_error` fan-in 36, `envelopes.success_envelope`
  fan-in 11, `errors` module fan-in 18) show a **consistent response contract**
  applied uniformly — a strength.
- Surfaces are thin over the service: `_handle_service_result` (CLI, fan-in 24)
  and `_result` (MCP, fan-in 16) are the uniform service→surface adapters.

## 6. Open questions for the catalog/quality pass

- Exact dependency direction between `service` ↔ adapters (does the service call
  adapters, or do surfaces compose them?) — confirm inbound/outbound per entry.
- Web UI mutation surface vs. the "MCP is read-only" claim — where do writes
  land and how is the single-operator actor enforced?
- SQLite migration/versioning discipline in `store.migrate` (idempotency,
  forward-only?).
- The dead `experimental/` package — confirm it is truly unreferenced.
- Test-to-subsystem mapping for the quality pass (conformance/contracts dirs
  suggest golden-vector seams).
