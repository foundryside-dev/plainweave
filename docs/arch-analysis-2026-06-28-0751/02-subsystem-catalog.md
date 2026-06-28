# 02 — Subsystem Catalog

**Subject:** Plainweave · **Live tree:** HEAD `8258f76` · **Date:** 2026-06-28
**Method:** 5 parallel `codebase-explorer` agents read 100% of their assigned
source; the orchestrator reconciled all inter-subsystem edges against the
Loomweave global graph (`02`/`temp/dependency-reconciliation.md`). Citations are
`file:line` against the live tree; coupling/fan-in figures are Loomweave at
`e95b6ad` (see basis-fidelity note in `01-discovery-findings.md`).

8 subsystems are cataloged. The defining structural fact is that **all three
delivery surfaces (CLI, MCP, Web) are thin adapters over one
`PlainweaveService`**, which is simultaneously the use-case tier, the
data-access tier, and the intent-graph engine.

## Cross-cutting themes (verified by ≥2 explorers)

- **Connect-per-call / N+1 is pervasive and is the dominant scaling+concurrency
  risk.** `store.connect` opens a fresh SQLite connection per operation (no
  pool), in `DELETE` journal mode (no WAL → writers exclusive-lock readers).
  It surfaces as: a connection per catalog entity in coverage
  (`service.py:1467→1479→1529-1550`); two connections per Loomweave
  `list_catalog`; 3 service calls × entire-corpus in MCP preflight
  (`mcp_surface.py:990,1084-1086`, no pagination); and per-draft dossier fetches
  per web render (`views.py:82-100`). Two open P3 tracker tasks already name it.
- **DB exceptions escape the `ErrorCode` contract.** Only domain failures route
  through `_error`→`PlainweaveError`; raw `connection.execute` is unguarded, so
  `sqlite3.IntegrityError`/`OperationalError` propagate past callers that switch
  on `ErrorCode`. Compounded by `count(*)+1` id generation (race) and no
  `busy_timeout`/WAL/`BEGIN IMMEDIATE` — fails *safe* (UNIQUE/PK) but a
  concurrent loser surfaces raw, not as a clean `CONFLICT`.
- **`cli_commands.py` is a de-facto shared services/DTO layer.** The MCP surface
  imports its private serializers + `inspect_project`; the new CLI
  `wardline-peer-facts` handler lazily imports `PlainweaveMcpSurface`. **No
  module-load cycle exists** (Loomweave `cycles:[]`; the function-local import
  deliberately dodges one) — but it is a real bidirectional surface↔surface
  coupling that inverts the intended layering.
- **Honest enrich-only degradation everywhere** (a strength): typed
  `unavailable`/closed degrade vocab, never an implied-clean; `live_peer_calls`
  is hard-`False`; drift is flagged `stale`, never silently dropped.
- **Non-deterministic `generated_at`** (`datetime.now(UTC)` default) defeats
  byte-stable golden comparison unless callers inject the timestamp.

---

## Domain Service Core

**Location:** `src/plainweave/service.py`, `src/plainweave/models.py`, `src/plainweave/bindings.py`

**Responsibility:** The domain orchestrator — a single `PlainweaveService`
(`service.py:64`) owning every traceability use case (requirement lifecycle,
acceptance criteria, trace links, goals/intent edges, code-entity & SEI
bindings, baselines, verification, dossiers, and the intent-graph reads) over a
directly-accessed SQLite store, emitting an append-only event log; advisory and
enrich-only.

**Key Components:**
- `service.py` (3027 LOC, one class, ~40 public use-case methods + ~70 private
  helpers): requirement lifecycle (`create_requirement:454`, `update_draft:512`,
  `approve_requirement:565`, `supersede:626`, `reject:720`, `deprecate:758`);
  acceptance criteria (`810`/`871`); trace links funnel through
  `_transition_trace:2386` with relation/transition whitelists (`2767`/`2782`);
  goals & intent edges (`create_goal:1020`, `link_goal_to_requirement:1060`);
  ADR-029 SEI bindings (`record_code_entity:1137`, `bind_sei_to_requirement:1198`
  → `entity_associations`); baselines (`create_baseline:304`, `diff_baseline:372`,
  immutability by DB triggers `store.py:178`); verification
  (`add_verification_method:148`, `record_verification_evidence:197`,
  `_compute_verification_status:2307`, `_evidence_authority:2994`); dossier
  (`requirement_dossier:260` + `_dossier_*` assemblers); actor registry with
  genesis-attester bootstrap (`register_actor:78`, `108-124`).
- **High-fan-in private cluster** (the monolith's cohesion): `_error:3020` (sole
  `PlainweaveError` factory, fan-in 36), `_now:3026`, `_require_actor:2968`,
  `_record_event:2792` (append-only `events` writer), `_requirement_row:2086`
  (multi-key resolver).
- `models.py` (310 LOC) — ~30 frozen domain dataclasses; pure leaf (stdlib only).
- `bindings.py` (98 LOC) — ADR-029 `SeiBinding` value object (`:29`), drift helper
  `is_drifted:91`; declares the `loomweave:eid:` scheme FROZEN (consumed, never
  minted, `:16`). Pure leaf.

**Dependencies:**
- Inbound: CLI (`cli_commands.py:1226`), MCP (`mcp_surface.py:743`), Web
  (`web/context.py:28`) each construct `PlainweaveService`; tests.
- Outbound: Persistence (`from plainweave.store import connect`, `service.py:60`;
  calls `connect()` in every method — it *is* the data-access tier, no repo);
  Sibling-Tool Adapters (built per-call, `_loomweave_adapter:2595`,
  `_wardline_adapter:2598`); Intent Graph (imports its types, `service.py:15`);
  Response Contract (`from plainweave.errors import ErrorCode, PlainweaveError`).

**Patterns Observed:**
- Canonical use-case template: `_require_actor` → validate → `_now()` →
  `with connect()` → `_requirement_row()` → SQL mutate → `_record_event()` →
  `commit()` → return a frozen `*_from_row` dataclass.
- Event sourcing: every mutation appends `EVT-{uuid4}` to the trigger-protected
  append-only `events` table (`_record_event:2792`, `store.py:269`).
- Optimistic concurrency + idempotency: writes gate on
  `expected_version`/`expected_draft_revision`; approve/supersede/deprecate cache
  & replay responses in `idempotency_keys` (`574-582`, `_idempotency_payload:2872`).
- Authority from the registry, not the actor string: `_evidence_authority:2994`
  derives authority from `actors.kind`; a free-form `--actor` defaults to
  least-privileged `agent_reported`. `_require_actor` is only a non-empty check —
  normal-write attribution is honour-system by design.
- Enrich-only trace hydration with explicit drift (`_trace_from_row:2449` →
  `freshness=stale` + `content_hash_drift` on mismatch).

**Concerns:**
- **God object / no layering** — 3027-LOC class spanning ~13 aggregates is both
  use-case and data-access tier (raw inline SQL). The dominant maintainability
  risk (`service.py:64-3027`).
- **DB exceptions escape `ErrorCode`** (`connection.execute` unwrapped) — see
  cross-cutting themes. Fully verifiable in `service.py` + `store.py`.
- **`count(*)+1` id generation is not concurrency-safe** (`2110`,`2137`,`2149`);
  fails safe via UNIQUE/PK but yields a raw exception under contention.
- **N+1 connections in coverage** — `intent_coverage:1415` →
  `_goal_nodes_for_surface:1529` opens a fresh `connect()` per surface inside the
  per-entity loop.

**Confidence:** High — 100% of `service.py`/`models.py`/`bindings.py`/`store.py`
read; inbound edges cross-checked via Loomweave callers (dynamic-construction
candidates corroborated by import grep).

---

## Intent Graph

**Location:** `src/plainweave/intent_graph.py`

**Responsibility:** Defines the intent-graph vocabulary and read contract — the
`goal ▲ requirement ▲ code-SEI` node/altitude types and the
coverage/orphans/trace/corpus result records (including the honest north-star
`IntentCoverage`) — over which `PlainweaveService` computes the actual reads.

**Key Components:**
- `intent_graph.py` (184 LOC, pure type/contract, no DB): `IntentLevel:28`
  (CODE/REQUIREMENT/GOAL); `IntentNode:44`, `Trace:55`, `CorpusEntry:67`;
  `IntentCoverage:100` + `IntentCoverageSurface:84` with honesty fields
  `denominator_complete:117`, `surfaces_truncated:124`, `excluded_*:121-122`,
  `adapter_status/adapter_degraded:125-126` (docstring: ADVISORY, never
  pass/fail, `:108`); `DEFAULT_INTENT_COVERAGE_EXCLUDED_NAMESPACES=("scripts.",
  "tests.")` (`:80`); injectable `IntentGraphReads:141` facade.
- **Computation lives in the service, not here:** `intent_orphans:1311`,
  `intent_trace:1346`, `intent_corpus:1388`, `intent_coverage:1415` are all in
  `service.py`. This file is the typed boundary they return across.

**Dependencies:**
- Inbound: Domain Service Core (imports types, `service.py:15`); CLI/MCP/Web
  serialize the result types; `IntentGraphReads` is constructed **only by tests**.
- Outbound: none — stdlib `dataclasses`/`enum`/`typing` only. Dependency-free leaf.

**Patterns Observed:**
- Honesty qualifiers surfaced, not computed away: counts are always full while
  evidence lists are bounded by `max_surfaces` with `surfaces_truncated`
  flagging drops; `denominator_complete` from `coverage["complete"]`
  (`service.py:1497`); `present_plugins` carried verbatim from
  `loomweave_adapter.py:203`.
- Coverage counts LIVE justification only (`_live_requirement_ids_for_entity`,
  `status in ('draft','approved')`), deliberately diverging from `intent_trace`
  which keeps surfacing deprecated reqs — "trace *explains*, coverage *counts*"
  (`service.py:1537-1539`).
- Prescribe-nothing: three composable primitives (orphans/trace/corpus), not
  canned reports. Frozen-dataclass value objects throughout.

**Concerns:**
- **`IntentGraphReads` facade is dead in production** — advertised as injectable
  for adapters but only tests construct it; contract and real reads can drift
  independently. Either wire it in or mark it test scaffolding.
- **Contract/implementation split is non-obvious** — a reader expecting the
  coverage logic here finds only types; the algorithms are 1100+ lines away in
  `service.py` (docstring points there, mitigating not removing).
- `IntentCoverage` is a wide 15-field record for downstream serializers to track.

**Confidence:** High — 100% of `intent_graph.py` + the four computing methods
read; dead-facade verified via Loomweave callers (test-only).

---

## CLI Surface

**Location:** `src/plainweave/cli.py`, `src/plainweave/cli_commands.py`

**Responsibility:** Exposes local-core operations as the `plainweave` console
command — an argparse subcommand tree whose handlers call the service and render
its envelopes as stdout (JSON/text) + exit codes.

**Key Components:**
- `cli.py` (38 LOC) — `build_parser:14-22` (late-imports `add_web_subcommand` to
  keep web optional), `main:25-38` (entry point `pyproject.toml:39`); dispatch is
  a table over argparse `set_defaults(handler=)`, no if/elif ladder.
- `cli_commands.py` (1631 LOC) — `register_commands:56-135` + eleven `_register_*`
  helpers define **16 top-level commands / 38 leaf handlers**: `init`, `doctor`,
  `req` (8), `criterion`, `trace`, `catalog`, `goal`, `bind`, `intent`,
  `baseline`, `actor`, `verify`, `status`, `dossier`, `wardline-peer-facts`,
  `web`.
- Adapter pair: `_handle_service_result:1138` (fan-in 24) / `_handle_service_list`
  → `_handle_output:1157` (instantiates service, catches `PlainweaveError`,
  prints envelope or data). Exit mapping `_emit_error:1169` (2; 4 on INTERNAL).
- ~21 `_*_dict` shapers (`1231-1631`); `_render_dossier:1634` is the one true
  text renderer. Doctor checks store (auto-`--fix`), Loomweave, Wardline, MCP
  import (`442-663`).

**Dependencies:**
- Inbound: `plainweave` entry point; tests (14 modules). **MCP Surface reaches
  back in**: `inspect_project` imported by `mcp_surface.py:395-413,825-829` — this
  module is not a pure CLI layer.
- Outbound: Domain Service Core (`_service():1208`); Response Contract; Persistence
  (`store`/`paths` directly — `init`/`doctor` bypass the service, `cli_commands.py:50,52`);
  Sibling-Tool Adapters (doctor probes); MCP Surface (function-local imports
  `:1103`,`:1114`); Web UI
  (`add_web_subcommand`); Intent Graph + models (DTOs).

**Patterns Observed:**
- Dispatch table via `set_defaults(handler=)`; thin lambda-thunk handlers pass
  `lambda service: …` to the central adapter; web kept optional via lazy import;
  envelope-everywhere with exit codes from `PlainweaveError.code`.

**Concerns:**
- **Bidirectional CLI↔MCP coupling** (shared services/DTO layer) — see
  cross-cutting themes; the function-local `PlainweaveMcpSurface` imports at
  `cli_commands.py:1103,1114` carry a comment naming the cycle they dodge.
- **Exit-code divergence** — `init`→0, `doctor`→0/1, service handlers→0/2/4,
  argparse→2; no uniform interpretation for a CI wrapper.
- "Human-readable" output is `json.dumps(data)` for ~34/38 commands; only
  `dossier`/`doctor` produce genuine text.
- **Dead/duplicate route** — `status requirement` (`1051-1052`) merely delegates
  to `verify status`; same command exposed twice.

**Confidence:** High — both files read in full; entry point + outbound deps +
the MCP-coupling confirmed via Loomweave callers (`_handle_service_result`
fan-in 24, `traversal_complete:true`). Gap: `web/server.py` internals scoped to
the Web UI slice.

---

## MCP Surface

**Location:** `src/plainweave/mcp_server.py`, `src/plainweave/mcp_surface.py`

**Responsibility:** Exposes Plainweave's read-only advisory state to agents as a
FastMCP server — **19 `plainweave_*` tools + 15 versioned contract resources** —
translating service results into the `weft.plainweave.*` envelope contract
without mutating state or making live peer calls.

**Key Components:**
- `mcp_server.py` (184) — `create_mcp_server:11-176` builds `FastMCP("plainweave",
  json_response=True)`, registers 19 thin `@mcp.tool()` forwarders + 15
  `@mcp.resource()` readers; `main:179` is the `plainweave-mcp` entry point.
- `mcp_surface.py` (1653) — `PlainweaveMcpSurface:391` holds all tool impls
  (project/context, requirements, traces, intent graph incl. `_coverage:536`
  north-star, baselines, verification, and the three sibling surfaces
  `entity_intent_context_get:577`, `preflight_facts_get:598`,
  `wardline_peer_facts_list:751`, `requirements_enrichment_get:759`).
- `_result:724-731` (fan-in 16) is the service→envelope choke point (lazy
  `_service`, runs `action(service)`, wraps in `success_envelope`, maps
  `PlainweaveError`→`error_envelope`); 16/19 tools route through it.
- `MCP_TOOL_METADATA:43-194` — every entry asserts `"mutates":False,
  "local_only":True, "peer_side_effects":[]` (the doctrine field names live HERE,
  not in the adapters).

**Dependencies:**
- Inbound: `mcp_server.main`; `cli_commands.py` (function-local instantiation for
  parity); tests.
- Outbound: Domain Service Core (sole data authority); **CLI Surface**
  (`cli_commands.py:9` — imports its private serializers + `inspect_project`);
  Response Contract; Sibling-Tool Adapters; Intent Graph; Persistence/paths;
  models; FastMCP.

**Patterns Observed:**
- Thin-wrapper delegation; closure-over-service adapter; lazy per-call
  service/adapter construction; defensive degrade-not-fail (`NOT_FOUND` soft-
  degraded to warnings); self-describing contract via `MCP_TOOL_METADATA` +
  `CONTRACT_RESOURCES`; boundary input validation (pagination/choice/entity-ref
  caps).

**Concerns:**
- **Preflight project-scope fan-out (the surface's #1 scaling risk).** A bare
  `preflight_facts_get()` (default `pending_diff`, no ids) can't resolve the diff
  locally → falls back to the *entire* corpus via `search_requirements()` (`:990`),
  then **3 service calls per requirement** (`:1084-1086`, dossier composite),
  O(corpus), **no `limit`/`offset` exposed**. `scope_kind="project"` same path.
- **Bidirectional CLI↔MCP coupling** (no module-load cycle; see themes).
- **Vestigial no-op `list_result` param** in `_result` (both branches identical).
- **Post-materialization pagination** in `_list:841` (slices after building the
  full list — bounds payload, not work).
- **Unguarded `project_context_get:395`** — the one of three non-`_result` tools
  without `try/except`; a `PlainweaveError` would escape the envelope contract.
- Non-deterministic `generated_at` in preflight (`:658`).

**Confidence:** High — both files read in full; tool count, `_result` fan-in,
entry point, and absence of a module cycle cross-verified against Loomweave.
Gap: service/adapter internals out of slice (claims rest on call-shape).

---

## Web UI

**Location:** `src/plainweave/web/`

**Responsibility:** Optional local-first single-operator Starlette + HTMX
server-rendered console to browse the corpus and **author/ratify** requirements,
drafts, goals, and agent-proposed trace links — the federation's **sole write
surface** over `PlainweaveService` (MCP is read-only).

**Key Components:**
- `app.py` (80) — `create_app(actor, root)` factory: `/healthz`, `/static`,
  double-submit-cookie CSRF middleware (`:43-62`), `PlainweaveError` handler,
  lazy `routes.register_all`.
- `server.py` (59) — CLI `web` subcommand + uvicorn launcher; `--host`
  (default `127.0.0.1`)/`--port`(8765)/`--actor`/`--no-open`; lazy uvicorn import
  (`WEB_EXTRA_HINT` if extra absent).
- `context.py` (61) — `RequestContext.from_root` builds per-call service +
  resolves `OperatorIdentity`; `_ensure_operator:34-51` self-registers a `human`
  actor (genesis-allowed; `POLICY_REQUIRED` once an attester exists); CSRF
  helpers (constant-time). Default operator `human:operator`.
- `views.py` (130) — pure view-model layer (`build_corpus_rows`, `filter_rows`,
  `pending_items`, `coverage_banner`).
- `errors.py` (20) — `error_to_status` (`ErrorCode`→HTTP; PEER_*→502/503).
- `routes/` — **21 routes (14 GET + 7 POST)**; +`/healthz` in `app.py` = **22
  app-wide**: requirements.py (215, corpus +
  CRUD, optimistic `expected_draft_revision`, CONFLICT→200 partial), review.py
  (258, `/review` queue + approve/accept/reject), goals.py (42), intent.py (35,
  coverage dashboard). 7 writes: create_requirement, update_draft,
  approve_requirement, accept/reject_trace_link, create_goal,
  link_goal_to_requirement.
- `templates/` + `static/` — Jinja2 (base + 6 pages + 13 partials) + `app.css` /
  `htmx.min.js`; a11y structural contracts in `base.html` (skip-link, SR live
  region, `aria-current`), locked by `tests/web/test_a11y_contracts.py`.

**Dependencies:**
- Inbound: **CLI Surface only** (`plainweave web`, `cli.py:19-21`).
- Outbound: Domain Service Core (every read/write via `ctx.service`); Intent
  Graph; models; Response Contract; Persistence path resolution; Starlette/
  Jinja2/uvicorn (`[web]` extra).

**Patterns Observed:**
- App-factory + lazy route registration (package imports without the extra);
  HTMX partial-vs-full on `HX-Request`; pure unit-testable view-model layer;
  optimistic-concurrency UX (CONFLICT→200 partial preserving operator text);
  double-submit-cookie CSRF on all unsafe methods; centralized error→template
  mapping; **process-singleton operator** bound once at `create_app`; a11y
  structural contracts test-locked.

**Concerns:**
- **No authN/authZ + a settable `--host`.** Identity is a launch-time singleton;
  CSRF is the only request-level control. `--host 0.0.0.0` exposes all 7 write
  endpoints to the network with zero auth (by-design local-first, but no
  compensating gate on the flag) (`server.py:15`).
- **Core review-queue a11y behaviour unverified in CI** — only structural
  contracts are automated; focus-move + live-region announcement need a manual
  NVDA/VoiceOver pass (README:188-192).
- **CSRF middleware re-parses body as urlencoded** (`parse_qsl`, `app.py:49-50`)
  — a multipart form would 403; implicit undocumented coupling.
- **O(requirements) round-trips per render** — `pending_items` does
  search + dossier-per-draft (`views.py:82-100`); `_pending_count` recomputes the
  queue after every mutation. N+1 at single-operator scale.
- Minor: non-`PlainweaveError` exceptions hit Starlette's default 500, not the
  themed partial.

**Confidence:** High — all 11 `.py` + `base.html` + a11y test + README AT-gate
read; sole inbound launcher confirmed by grep; all 7 writes traced to concrete
service calls.

---

## Persistence

**Location:** `src/plainweave/store.py` (+ shared `paths.py`)

**Responsibility:** Owns the single SQLite database — connection lifecycle,
forward schema migration, and store-path resolution — for the whole domain.

**Key Components:**
- `connect:11-19` — `@contextmanager`, fresh `sqlite3.connect`, `row_factory=Row`,
  `pragma foreign_keys=on`, deterministic close. **Fan-in 44 (most-coupled
  entity).**
- `migrate:22-306` — idempotent: `mkdir` then one `executescript` of 17
  `create table if not exists` + immutability/append-only triggers + a guarded
  `ALTER … add column request_hash` (`:296-297`); stamps `schema_meta`.
  `SCHEMA_VERSION=2` (`:8`).
- `read_schema_meta:309` — the SCHEMA_MISMATCH detection input.
- `paths.py:9-24` — `plainweave_db_path` (`.plainweave/plainweave.db`),
  `default_project_key`.
- SQL-level invariants: immutable approved text (`:76-84`), locked-baseline +
  member immutability (`:178-217`), append-only `verification_evidence`/`events`
  (`:244-281`); ADR-029 `entity_associations.content_hash_at_attach` declared
  here (`:160`), drift *comparison* in the service layer.

**Dependencies:**
- Inbound: Domain Service Core (~38 methods), CLI (`initialize_project`,
  `inspect_project` — layering exception), tests.
- Outbound: stdlib `sqlite3`/`pathlib`/`contextlib` only. No ORM/driver/pool.

**Patterns Observed:**
- Connect-per-operation (confirmed via the 44-edge caller set); idempotent but
  **non-version-aware** migration (stamps `SCHEMA_VERSION`, never branches; no
  upgrade steps, no down-migrations); per-connection `foreign_keys=on`;
  invariants in SQL triggers.

**Concerns:**
- **Connect-per-call + no WAL (`DELETE` mode)** → a writer's exclusive lock
  blocks all readers; with 3 concurrent surfaces this is the contention ceiling.
- **Confirmed N+1** at `service.py:1467→1479→1529-1550` (one connection per
  catalog entity) — the open tracker's N+1 / unbounded project-scope item.
- **Undocumented reliance on the stdlib `busy_timeout` default** —
  `test_store_connections_configure_busy_timeout` passes only because
  `sqlite3.connect`'s default `timeout=5.0` yields `busy_timeout=5000`; `connect`
  sets no pragma and exposes no timeout param. A latent implicit contract.

**Confidence:** High — `store.py`/`paths.py` 100% read; connect-per-call checked
against the full 44-edge caller set; busy_timeout test run empirically.

---

## Sibling-Tool Adapters

**Location:** `src/plainweave/loomweave_adapter.py` (657), `src/plainweave/wardline_adapter.py` (373)

**Responsibility:** Read-only seams that pull *enrichment* facts from sibling
tools' local artifacts (Loomweave catalog/SEI; Wardline findings) and translate
presence/absence/staleness into an honest closed degrade vocabulary — never an
implied-clean state.

**Key Components:**
- `loomweave_adapter.py`: `LoomweaveAdapter.list_catalog:101-194` (paginates
  public-surface + module entities; `public_surface_coverage` over closed tag set
  `:18,196-204`; `public_surface_tags_incomplete` degrade); identity resolution
  `resolve_identity:232-415` (HTTP when endpoint configured else SQLite;
  `resolve_identity_local:237` never calls a peer); `_probe_sei_capability:256`
  (degrades `unsupported` orthogonally to "remote down"); `_entity_from_mapping:456`
  (read-time freshness: `content_hash` vs SEI `body_hash` → `stale` +
  `content_hash_drift`); `_connect:596-605` opens Loomweave's DB **read-only**
  (`?mode=ro`).
- `wardline_adapter.py`: `WardlineAdapter.list_peer_facts:242-326` (loads latest
  `.wardline/*-findings.jsonl`, splits metrics from findings, computes
  `resolved_or_unseen` by snapshot diff); hard-coded `authority_boundary`
  (`local_only:True, live_peer_calls:False, governance_verdicts:False,
  trust_policy_owner:"wardline"`, `:244-249`); closed kind vocab (`:17,354-373`).

**Dependencies:**
- Inbound: Domain Service Core (`_loomweave_adapter`/`_wardline_adapter:2595-2599`),
  MCP Surface (`:746-749`), CLI doctor (`:535,592`). All construct fresh,
  root-bound, stateless.
- Outbound: Loomweave `.weft/loomweave/loomweave.db` (ro SQLite) + optional
  Loomweave HTTP identity API (`urllib`, 1.5s); Wardline `.jsonl` files. **No
  shell-out, no MCP client.**

**Patterns Observed:**
- Enrich-only via explicit `unavailable`/degrade, never silence ("result is
  unavailable, not clean", wardline_adapter.py:250-266; `loomweave_db_missing`
  degrade, loomweave_adapter.py:517-524).
- **Two local-only postures:** Wardline is *structurally* local (files only, zero
  network code); Loomweave is local SQLite by default but carries a **live HTTP
  identity path gated on `WEFT_LOOMWEAVE_URL`** — local-only holds only if the
  caller picks `resolve_identity_local`.
- Closed degrade-code vocabularies both sides; defensive parsing throughout.

**Concerns:**
- **Multi-connection per read** — `list_catalog` opens one connection in
  `_schema_state()` then a second for the page query (same in
  `_resolve_identity_sqlite`); compounds the persistence connect-per-call pattern.
- **Doctrine field names absent here** — `meta.local_only`/`peer_side_effects:[]`
  do not appear in the adapters (they live in the MCP metadata); the realized
  adapter contract is the `authority_boundary` dict + `status:"unavailable"` +
  closed degrade vocab. Cite the actual fields.
- **No warpline adapter, by design** — Plainweave is the *producer* of
  `plainweave_requirements_enrichment_get` ("for Warpline's reserved enrichment
  slot", mcp_surface.py:189,759), not a consumer; the seam lives in the MCP/CLI
  surface, so `tests/test_warpline_requirements_enrichment.py` has no `src`
  adapter counterpart.

**Confidence:** High — both adapter files 100% read; instantiation sites + absence
of shell-out/MCP-client confirmed by grep; producer-direction confirmed at
`mcp_surface.py:189,759`.

---

## Response Contract / Cross-cutting

**Location:** `src/plainweave/envelopes.py` (115), `errors.py` (34), `paths.py` (24), `_version.py`

**Responsibility:** Defines the versioned JSON envelope shapes and the closed
error-code vocabulary every CLI/MCP/service response is wrapped in, so all
surfaces emit one uniform machine-switchable contract.

**Key Components:**
- `envelopes.py`: `success_envelope:37-51` (`{schema, ok:True, data, warnings,
  meta}`; `meta.producer={tool:"plainweave", version:__version__}`,
  `generated_at`, `project`; fan-in 11); `error_envelope:54-78` (hard-codes
  `schema:"weft.plainweave.error.v1"`, `ok:False`; `_error_code:28-34` raises on
  unknown code — fail-closed); `list_envelope`/`batch_envelope:81-115` (uniform
  pagination/batch).
- `errors.py`: `ErrorCode(StrEnum):6-16` — closed **10-value** vocab `VALIDATION,
  NOT_FOUND, CONFLICT, POLICY_REQUIRED, PEER_ABSENT, PEER_STALE, PEER_CONTRACT,
  LOCKED, UNSUPPORTED, INTERNAL` (three `PEER_*` carry sibling-degradation into
  the error contract); `PlainweaveError:19-34` bridges raised → `error_envelope`.
- `_version.py`: `__version__ = "1.1.0"` (stamped into every envelope).

**Dependencies:**
- Inbound: MCP (`_result:724` + others), CLI (`_handle_service_result:1148`,
  doctor/dossier/init), Domain Service Core (raises `PlainweaveError`;
  `_loomweave_error:2601` maps adapter reasons → `ErrorCode`).
- Outbound: `_version`, `errors`, stdlib `datetime`/`collections.abc`.

**Patterns Observed:**
- **Uniform envelope via central choke points** (`_result` / `_handle_service_result`
  + `list_/batch_` helpers) rather than scattered dict-building (Loomweave
  `traversal_complete`).
- **Versioning split by direction:** success/list/batch take a caller-supplied
  per-payload `schema`; errors use one hard-coded `error.v1`; producer
  identity+version in `meta`.
- **Closed, fail-closed error vocab** (unknown codes raise); adapter degrade
  reasons translated into the closed `ErrorCode` set at the service boundary
  (`_loomweave_error:2601-2604`), so sibling failures surface as
  `NOT_FOUND`/`CONFLICT`/`PEER_*`, not leaked reason strings.

**Concerns:**
- **`meta.generated_at` non-deterministic by default** (`datetime.now(UTC)`,
  `:12-13`) — goldens must inject it.
- **Error-schema version hard-coded in one place** (`:67`) while success schemas
  are caller-supplied — no symmetric constant/registry tying the two, so
  error/success version drift is possible.
- `paths.py`/`_version.py` — no structural concern.

**Confidence:** High — all four files 100% read; cross-surface uniformity
confirmed by reading the full `success_envelope` caller set (both choke points
present, `traversal_complete`).
