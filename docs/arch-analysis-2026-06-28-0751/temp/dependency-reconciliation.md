# Dependency Reconciliation (orchestrator-owned, from Loomweave global graph)

Region-isolated explorers report one-sided edges. This is the authoritative
inter-subsystem map, derived from the global index (commit `e95b6ad`), to
override conflicting explorer claims at merge time.

## Hard facts (Loomweave-verified)

- **No circular imports** anywhere (`module_circular_import_list` → `cycles: []`).
- **Surfaces are thin over one service.** All three import `PlainweaveService`
  and dispatch through it:
  - CLI: `cli_commands.py:51 from plainweave.service import PlainweaveService`;
    handlers are `lambda service: service.<method>(...)` routed via
    `_handle_service_result` (fan-in 24).
  - MCP: `mcp_surface.py:30` same import; tools are `def action(service): ...`
    closures routed via `_result` (fan-in 16).
  - Web: `web.context`, `web.views`, `web.routes.requirements`,
    `web.routes.review` all import `plainweave.service` (Loomweave `imports_in`).
- **Service → outbound:** `bindings`, `errors`, `intent_graph`,
  `loomweave_adapter`, `wardline_adapter` (references_out / imports_out).
  So the **service composes the sibling adapters**, not the surfaces.
- **Persistence is reached per-use-case, not pooled.** `store.connect`
  (contextmanager, fresh `sqlite3.connect` each call; sets `foreign_keys=on`,
  `row_factory=Row`; store.py:11–19) has fan-in 44. Callers = ~35 distinct
  `PlainweaveService.*` methods, each opening its own connection
  (`create_requirement`, `approve_requirement`, `intent_corpus`,
  `intent_orphans`, `intent_trace`, `requirement_dossier`, `search_requirements`,
  `requirement_preflight_profile`, …). **This is the N+1 / per-call-connect
  pattern at the source.**

## Layering exceptions / leaks to flag

- **CLI bypasses the service to hit the store directly** in
  `cli_commands.initialize_project` (cli_commands.py:1115) and
  `cli_commands.inspect_project` (cli_commands.py:1129) — both call
  `store.connect()` directly. Plausibly justified (init runs `migrate` before a
  service exists; inspect/doctor does raw introspection) but it IS a hole in the
  "surfaces only talk to the service" rule. Note in catalog + quality.
- **`loomweave_adapter.py:600` opens its own `sqlite3.connect`** — reading
  *Loomweave's* catalog DB (a different database), not the plainweave store.
  Expected for a read adapter, but means two distinct SQLite touch-points.

## Canonical dependency direction (for diagrams)

```
CLI ─┐
MCP ─┼─▶ PlainweaveService (Domain Service Core)
Web ─┘        │
              ├─▶ Intent Graph (types/contract; logic lives IN service.py:1311-1507)
              ├─▶ Sibling-Tool Adapters ─▶ Loomweave DB (ro SQLite, +cond. HTTP identity)
              │                          └▶ Wardline (.wardline/*-findings.jsonl, files only)
              ├─▶ Persistence (store.connect, per-call, no pool/WAL) ─▶ SQLite (.plainweave/, schema v2)
              └─▶ Response Contract (envelopes/errors) ◀─ also used by all surfaces
CLI ┄┄(init/inspect only)┄┄▶ Persistence            [layering exception]
MCP ◀┄┄(serializers + inspect_project)┄┄ CLI         [surface↔surface coupling]
MCP/CLI ──produce──▶ requirements_enrichment.v1 ▶ (Warpline's reserved slot; Plainweave is PRODUCER, no warpline adapter)
```

**Corrections from explorer reads (override my pre-catalog assumptions):**
- **Warpline is consumed-by, not depended-on.** No warpline adapter in `src/`
  (grep empty). Plainweave *produces* `plainweave_requirements_enrichment_get`
  ("for Warpline's reserved enrichment slot", mcp_surface.py:189,759).
- **Two honesty contracts at two layers** (both real): the MCP tool metadata
  uses `mutates/local_only/peer_side_effects:[]` (mcp_surface.py:43-194); the
  Wardline adapter uses an `authority_boundary{local_only, live_peer_calls:False,
  …}` dict (wardline_adapter.py:244-249). The doctrine field names live in the
  MCP layer, not the adapter layer.
- **Loomweave local-only is conditional:** read-only SQLite by default, but a
  live HTTP identity path is gated on `WEFT_LOOMWEAVE_URL`; local-only holds
  only if the caller picks `resolve_identity_local` (loomweave_adapter.py:237).

Schema: `SCHEMA_VERSION = 2` (store.py:8); intent tables added in v2 over the
v1 precursor without rewriting precursor rows (test:
`test_schema_v2_adds_intent_tables_without_rewriting_precursor_rows`).
