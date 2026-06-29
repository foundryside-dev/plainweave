# Explorer E5 — Catalog Entries

Basis commit `e95b6ad`. All claims cite `file:line` against the working tree as read; Loomweave index fresh.

---

## Persistence

**Location:** `src/plainweave/store.py`, `src/plainweave/paths.py`

**Responsibility:** Owns the single SQLite database — connection lifecycle, the forward-only schema migration, and store-path resolution — for the whole intent-corpus / traceability domain.

**Key Components:**
- `store.py:11-19` `connect(db_path)` — a `@contextmanager` that opens a fresh `sqlite3.connect(db_path)`, sets `row_factory = sqlite3.Row` and `pragma foreign_keys = on`, yields, and closes deterministically in `finally`. Loomweave fan-in **44** (single most-coupled entity) — confirmed below.
- `store.py:22-306` `migrate(db_path, *, project_key)` — idempotent schema setup: `mkdir(parents=True, exist_ok=True)` then one `executescript` of 17 `create table if not exists` + immutability/append-only triggers, a guarded ad-hoc `alter table idempotency_keys add column request_hash` (store.py:296-297), and stamps `schema_meta` with `project_key` (insert-or-ignore) and `schema_version` (upsert). `SCHEMA_VERSION = 2` (store.py:8).
- `store.py:309-311` `read_schema_meta(connection)` — read side of `schema_meta`; the SCHEMA_MISMATCH detection input.
- `paths.py:9-24` — `project_root` / `plainweave_dir` / `plainweave_db_path` (`.plainweave/plainweave.db`) / `default_project_key` (sanitised dir name, fallback `"LOCAL"`).
- Schema enforces domain invariants in SQL: immutable approved requirement text (`requirement_versions_text_immutable` trigger, store.py:76-84), locked-baseline + baseline-member immutability (store.py:178-217), append-only `verification_evidence` (store.py:244-256) and `events` (store.py:269-281). ADR-029 drift column `entity_associations.content_hash_at_attach` is declared here (store.py:160); the drift *comparison* lives in the service layer, not here.

**Dependencies:**
- Inbound: Domain Service Core (`PlainweaveService.*` — ~38 methods each open `with connect(...)`), CLI Surface (`cli_commands.initialize_project`, `inspect_project`), test suites.
- Outbound: stdlib `sqlite3`, `pathlib`, `contextlib` only. No ORM, no driver, no pool.

**Patterns Observed:**
- **Connect-per-operation (confirmed).** `entity_callers_list` on `store.connect` returns one edge per service method (`create_requirement`, `approve_requirement`, `intent_trace`, `get_requirement`, …) plus the two CLI handlers and `migrate` — every domain operation opens and closes its own connection; there is no shared/long-lived connection and no pool (store.py:11-19; verified against Loomweave caller set).
- Idempotent, **non-version-aware** migration: `migrate` *stamps* `SCHEMA_VERSION` but never branches on it — it re-runs the full `create … if not exists` script every call and applies one guarded `ALTER`; no per-version upgrade steps and no down-migrations (store.py:293-305).
- Per-connection `pragma foreign_keys = on` (store.py:15) — correct, since FK enforcement is per-connection in SQLite.
- Invariants pushed into SQL triggers rather than enforced only in Python (store.py:76-281).

**Concerns:**
- **Connect-per-call + no WAL = cross-surface write/read serialization.** `connect` never sets `journal_mode`, so the DB runs in default `DELETE` (rollback-journal) mode where a writer takes an exclusive lock that blocks all readers. With three concurrent surfaces (MCP, web, CLI) all opening their own connections, this is the contention ceiling (store.py:11-19; no `journal_mode`/`wal` anywhere in `src/plainweave/`).
- **Confirmed N+1 connections.** In the catalog-with-goals path, `for entity in items:` (service.py:1467) calls `self._goal_nodes_for_surface(entity.sei)` (service.py:1479), and `_goal_nodes_for_surface` (service.py:1529-1550) opens its own `with connect(...)` — i.e. one fresh SQLite connection **per catalog entity**. (Distinct from the in-loop helpers `_goal_ids_for_requirement`/`_entity_ids_for_requirement`, which correctly take an existing `connection` and do *not* re-open.) This is the open tracker's "N+1 SQLite connections per scoped requirement / unbounded project-scope fan-out."
- **Undocumented dependence on the stdlib busy_timeout default.** `test_store_connections_configure_busy_timeout` (tests/test_store_migrations.py:60-65) asserts `pragma busy_timeout >= 5000` and **passes** — but `connect` sets no `busy_timeout` pragma. The 5000 ms comes solely from `sqlite3.connect`'s default `timeout=5.0`. `connect` exposes no timeout parameter, so this is a latent, undocumented reliance on a stdlib default (the lock-wait window that makes connect-per-call survivable), not an explicit contract.

**Confidence:** High — read 100% of `store.py` (311 LOC) and `paths.py` (24 LOC); cross-checked the connect-per-call claim against the full Loomweave `entity_callers_list` (44 edges); empirically ran the busy_timeout test (passes) to resolve the source-vs-test discrepancy; traced the N+1 loop to `_goal_nodes_for_surface` in source.

---

## Sibling-Tool Adapters

**Location:** `src/plainweave/loomweave_adapter.py` (657 LOC), `src/plainweave/wardline_adapter.py` (373 LOC)

**Responsibility:** Read-only seams that pull *enrichment* facts from sibling Weft tools' local artifacts (Loomweave catalog/SEI; Wardline findings) and translate sibling presence/absence/staleness into an honest, closed degrade vocabulary — never an implied clean state.

**Key Components:**
- `loomweave_adapter.py:101-194` `LoomweaveAdapter.list_catalog` — paginates public-surface + module entities from the Loomweave SQLite catalog; computes `public_surface_coverage` (closed tag set `exported-api|entry-point|http-route|cli-command`, loomweave_adapter.py:18, 196-204) and emits a `public_surface_tags_incomplete` degrade when tag classes are absent (loomweave_adapter.py:182-184, 215-223).
- `loomweave_adapter.py:232-415` identity resolution: `resolve_identity` routes to **HTTP** (`_resolve_identity_http`) when an endpoint is configured, else **SQLite** (`_resolve_identity_sqlite`); `resolve_identity_local` (loomweave_adapter.py:237-244) is the explicit local-only entry that never calls a peer.
- `loomweave_adapter.py:256-285` `_probe_sei_capability` — probes `GET /api/v1/_capabilities` and degrades `unsupported` when SEI isn't advertised, keeping "no SEI capability" orthogonal to "remote is down."
- `loomweave_adapter.py:456-500` `_entity_from_mapping` — read-time freshness: compares catalog `content_hash` vs the SEI binding `body_hash`; on mismatch sets `freshness="stale"` + `content_hash_drift` degrade (loomweave_adapter.py:472-477). `visibility_unknown` is a permanent *signal*, deliberately kept out of `degraded` (loomweave_adapter.py:462).
- `loomweave_adapter.py:596-605` `_connect` — opens Loomweave's DB **read-only** via `f"{db_path.as_uri()}?mode=ro"`, closed in `finally` ("Plainweave never mutates the Loomweave catalog").
- `wardline_adapter.py:242-326` `WardlineAdapter.list_peer_facts` — loads the latest `.wardline/*-findings.jsonl` snapshot (wardline_adapter.py:57-60), splits engine-metric records from entity findings, and computes `resolved_or_unseen` by diffing latest vs prior snapshot with scope/ruleset guards (wardline_adapter.py:136-181, 210-240). Hard-codes an `authority_boundary` block: `local_only: True`, `live_peer_calls: False`, `governance_verdicts: False`, `trust_policy_owner: "wardline"` (wardline_adapter.py:244-249).
- `wardline_adapter.py:17, 354-373` `_finding_from_record` — closed Wardline kind vocab; `non_defect = kind in {metric,fact,classification,suggestion}`.

**Dependencies:**
- Inbound: Domain Service Core (`service.py:2595-2599` `_loomweave_adapter`/`_wardline_adapter`), MCP Surface (`mcp_surface.py:746-749`), CLI Surface (`cli_commands.py:535,592` doctor health). All construct adapters fresh and root-bound (stateless).
- Outbound: Loomweave's `.weft/loomweave/loomweave.db` (read-only SQLite) and optional Loomweave HTTP identity API (`urllib`, 1.5 s timeout, loomweave_adapter.py:551-581); Wardline's `.wardline/*-findings.jsonl` files. stdlib only — **no shell-out to sibling CLIs, no MCP client**.

**Patterns Observed:**
- **Enrich-only enforced via explicit `unavailable`/degrade, never silence.** Wardline with no snapshot returns `freshness:"unavailable"`, empty facts, a `wardline_findings_absent` degrade, and the note *"result is unavailable, not clean"* (wardline_adapter.py:250-266). Loomweave with a missing DB returns adapter `status:"unavailable"` + `loomweave_db_missing` degrade (loomweave_adapter.py:517-524). Sibling absence is always typed, never an implied pass.
- **Two different local-only postures.** Wardline is *structurally* local (files only, zero network code). Loomweave is local SQLite (`mode=ro`) by default but carries a **live HTTP identity path** gated on `WEFT_LOOMWEAVE_URL` / `.weft/loomweave/ephemeral.port` (loomweave_adapter.py:583-594); the local-only guarantee therefore depends on the caller choosing `resolve_identity_local` over `resolve_identity`.
- Closed degrade-code vocabularies on both sides (loomweave: `loomweave_db_missing|loomweave_schema_missing|sei_support_missing|content_hash_drift|public_surface_tags_incomplete|…`; wardline: the five `WARDLINE_DEGRADE_*` constants, wardline_adapter.py:10-14).
- Defensive parsing throughout — malformed JSONL lines skipped (wardline_adapter.py:98-106), non-object HTTP bodies → `identity_contract` degrade (loomweave_adapter.py:575-580).

**Concerns:**
- **Multi-connection per read inside the Loomweave adapter.** `list_catalog` calls `_schema_state()` (opens one read-only connection, loomweave_adapter.py:119/526) and then opens a *second* `with self._connect()` for the page query (loomweave_adapter.py:135) — two connections per call; same shape in `_resolve_identity_sqlite` (schema probe + query). Compounds the persistence connect-per-call pattern on the read path.
- **Doctrine field-names from the brief are not all present in code.** `meta.local_only` and `peer_side_effects: []` do **not** appear in these adapters; the realized contract is Wardline's `authority_boundary` dict + `status:"unavailable"` + the closed degrade vocab. Downstream cross-references should cite the actual fields, not the doctrine labels.
- **No warpline adapter exists, by design** — and this is the correct cross-reference, not a gap: `grep -rn warpline src/plainweave/` is empty. Plainweave does not *consume* warpline; it *produces* `plainweave_requirements_enrichment_get`, described as "local Plainweave requirement facts for **Warpline's reserved enrichment slot**" (mcp_surface.py:189, 759). That producer seam lives in the MCP Surface (`mcp_surface.py`/`mcp_server.py`/`cli_commands.py`), so `tests/test_warpline_requirements_enrichment.py` has no `src` adapter counterpart by intent.
- ADR-029 association-level drift (`content_hash_at_attach`) is **not** handled here — the adapter only compares its own catalog hash vs SEI `body_hash`. Association drift detection is a Domain Service Core / Intent Graph concern (evidenced by `tests/state/test_trace_links.py` read-time-drift tests).

**Confidence:** High — read 100% of both adapter files; verified instantiation sites and the absence of CLI shell-out / MCP-client code by grep; confirmed via `mcp_surface.py:189,759` that warpline is the consumer (Plainweave the producer), which fully explains the missing adapter.

---

## Response Contract / Cross-cutting

**Location:** `src/plainweave/envelopes.py` (115 LOC), `src/plainweave/errors.py` (34 LOC), `src/plainweave/paths.py` (24 LOC), `src/plainweave/_version.py`

**Responsibility:** Defines the versioned JSON envelope shapes and the closed error-code vocabulary that every CLI / MCP / service response is wrapped in, so all surfaces emit one uniform, machine-switchable contract.

**Key Components:**
- `envelopes.py:37-51` `success_envelope(schema, data, …)` — `{schema, ok:True, data, warnings, meta}`; `meta` carries `producer={tool:"plainweave", version:__version__}`, `generated_at` (ISO, defaults to `now(UTC)`), and `project` (envelopes.py:16-21). Loomweave fan-in 11.
- `envelopes.py:54-78` `error_envelope(code, message, *, recoverable, hint, details, …)` — hard-codes `schema:"weft.plainweave.error.v1"` and `ok:False`; `_error_code` (envelopes.py:28-34) coerces a str into `ErrorCode`, raising `ValueError` on an unknown code (fail-closed contract).
- `envelopes.py:81-115` `list_envelope` (`items`/`has_more`/`next_offset`) and `batch_envelope` (`succeeded`/`failed`) — thin wrappers over `success_envelope`, so pagination/batch shapes are uniform.
- `errors.py:6-16` `ErrorCode(StrEnum)` — closed 10-value vocab: `VALIDATION, NOT_FOUND, CONFLICT, POLICY_REQUIRED, PEER_ABSENT, PEER_STALE, PEER_CONTRACT, LOCKED, UNSUPPORTED, INTERNAL` (three `PEER_*` codes carry sibling-degradation into the error contract).
- `errors.py:19-34` `PlainweaveError` — exception carrying `code`/`message`/`recoverable`/`hint`/`details`, the bridge from raised errors to `error_envelope`.
- `paths.py` (shared with Persistence) — store-path/project-key resolution.
- `_version.py:1` `__version__ = "1.1.0"` — stamped into every envelope's `meta.producer.version`.

**Dependencies:**
- Inbound: MCP Surface (`mcp_surface.py:724` `_result`, plus `read_resource`, `plainweave_loomweave_catalog_list`, `plainweave_project_context_get`, `plainweave_wardline_peer_facts_list`), CLI Surface (`cli_commands.py:1148` `_handle_service_result`, `handle_doctor`, `handle_dossier`, `handle_init`), Domain Service Core (raises `PlainweaveError`; `service.py:2601` `_loomweave_error` maps adapter reasons → `ErrorCode`).
- Outbound: `_version` (`__version__`), `errors` (`ErrorCode`), stdlib `datetime`/`collections.abc`.

**Patterns Observed:**
- **Uniform envelope via central choke points.** `entity_callers_list` on `success_envelope` shows it is reached through one wrapper per surface — `mcp_surface._result` and `cli_commands._handle_service_result` — plus the `list_/batch_` helpers, rather than scattered ad-hoc dict-building, giving consistent cross-surface shape (verified, traversal_complete).
- **Versioning split by direction.** Success/list/batch take a *caller-supplied* `schema` string (per-payload contract id, e.g. `weft.plainweave.requirements_enrichment.v1`); errors use a *single hard-coded* `weft.plainweave.error.v1`. Producer identity + version live in `meta`, decoupled from the payload schema.
- **Closed, fail-closed error vocab.** Unknown error codes raise rather than pass through (envelopes.py:33-34); switch-on-`code` is guaranteed by `StrEnum` (errors.py).
- Adapter degrade reasons are translated into the closed `ErrorCode` set at the service boundary (`service.py:2601-2604` `_loomweave_error`), so sibling failures surface as `NOT_FOUND`/`CONFLICT`/`PEER_*` rather than leaking adapter-internal reason strings.

**Concerns:**
- **`meta.generated_at` is non-deterministic by default** — `_generated_at` falls back to `datetime.now(UTC)` (envelopes.py:12-13) unless the caller threads a value through; envelope snapshots/goldens must inject `generated_at` to be reproducible.
- **Error-schema version is hard-coded in one place** (`envelopes.py:67`) while success schemas are caller-supplied — a future `error.v2` is a single-point edit, but there is no symmetric constant/registry tying error and success schema versions together, so drift between them is possible.
- No structural concern in `paths.py`/`_version.py` (verified: error handling N/A for pure path/string resolution; both are trivially correct).

**Confidence:** High — read 100% of `envelopes.py`, `errors.py`, `paths.py`, `_version.py`; confirmed cross-surface uniformity by reading the full `success_envelope` caller set (traversal_complete, both CLI and MCP choke points present) and the `_loomweave_error` reason→ErrorCode mapping in source.
