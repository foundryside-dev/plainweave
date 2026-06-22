# 02 — Subsystem Catalog

*Six subsystems, identified by responsibility cohesion and dependency direction.
Dependency edges are import-confirmed; coupling/fan-in figures from the Loomweave
index (HEAD `72e8df2`). "Inbound/Outbound" list **intra-package** subsystems
only.*

> **Validation note (see `temp/validation-catalog.md`):** fan-in figures below
> are **test-inclusive** (they count test callers). App-only *production* fan-in
> is lower — e.g. `create_requirement` 6 (not 31), `approve_requirement` 6,
> `store.connect` 32 (not 48). `store.connect` is still the repo's
> highest-coupled entity. The god-object verdict rests on LOC + method count,
> which are independent of caller counts.

Dependency direction (leaf → root):

```
CLI ─┐                    Intent Graph & Bindings
     ├─► Service Core ─► Store ─► (SQLite)   (reframe stubs: standalone,
MCP ─┘        │                                 not yet wired to anything)
   │  │       └─► Domain Model & Errors ◄── (used by every layer)
   └──┴─► Envelopes (cross-cutting output contract)
```

---

## 1. Domain Model & Errors

**Location:** `src/plainweave/models.py`, `src/plainweave/errors.py`,
`src/plainweave/paths.py`

**Responsibility:** Define the immutable domain vocabulary (dataclasses), the
error taxonomy, and repo-local path resolution shared by every other layer.

**Key Components:**
- `models.py` — **25** frozen dataclasses (the project-wide data-model count of
  29 = 25 here + 3 in `intent_graph` + 1 in `bindings`): requirement identity
  (`RequirementDraft`/`RequirementVersion`/`RequirementRecord`),
  `AcceptanceCriterion`, traceability (`TraceRef`/`TraceLink`), baselines
  (`Baseline`/`BaselineMember`/`BaselineDiff`), verification
  (`VerificationMethod`/`VerificationEvidence`/`RequirementVerificationStatus`),
  dossier sections (`RequirementDossier` + ~8 `Dossier*`), `Actor`.
- `errors.py` — `ErrorCode` enum (incl. `PEER_ABSENT`/`PEER_STALE` for
  enrich-only degradation) + `PlainweaveError`.
- `paths.py` — `.plainweave/` dir, `plainweave_db_path`, `project_root`,
  `default_project_key`.

**Dependencies:**
- Inbound: Service Core, MCP Read Surface, CLI, Envelopes.
- Outbound: none (pure leaf; no intra-package imports).

**Patterns Observed:** Immutable value objects (frozen dataclasses); explicit
closed error vocab switched on by `code` not message; identity-vs-version split
(ADR-002).

**Concerns:** `models.py` mixes core domain types with read-model/DTO types
(the `Dossier*` aggregate sections are presentation-shaped). Minor — but the
boundary between "domain" and "read model" is not physically separated.

**Confidence:** High — full data-model inventory from Loomweave + source.

---

## 2. Persistence / Store

**Location:** `src/plainweave/store.py`

**Responsibility:** Own the SQLite connection, schema creation/migration, schema
metadata, and the append-only event log substrate.

**Key Components:**
- `connect(db_path)` — connection factory. **Fan-in 48** — the single
  highest-coupled entity in the repo; every write path opens through it.
- `migrate(...)` — 227-line in-code schema migration (fan-in 19).
- `read_schema_meta(...)` — schema-version metadata read.

**Dependencies:**
- Inbound: Service Core, CLI (`cli_commands` calls `connect`/`migrate` directly).
- Outbound: none (stdlib `sqlite3` only).

**Patterns Observed:** No ORM — raw `sqlite3` with `Row` factory. In-code
migration ladder. Append-only event stream + idempotency tables (consumed by the
Service Core) give the core a replay-safe, auditable spine.

**Concerns:** (1) `cli_commands` calls `store.connect`/`migrate` directly rather
than only through the Service Core — persistence access is not fully funneled
through the service boundary. (2) Migrations are a single growing in-code
function rather than versioned migration files (acceptable at this size; watch
as schema grows for the reframe).

**Confidence:** High.

---

## 3. Service Core — `PlainweaveService`

**Location:** `src/plainweave/service.py` (2136 LOC)

**Responsibility:** The application/business layer. One class orchestrating the
entire as-built domain: requirement lifecycle, acceptance criteria, trace
link propose/accept/reject/stale/orphan, baselines + diff, verification methods +
evidence + status computation, requirement dossiers, idempotency, and the event
log.

**Key Components (all `PlainweaveService` methods):**
- Requirement lifecycle: `create_requirement` (fan-in 31), `update_draft`,
  `approve_requirement` (21), `supersede_requirement`, `reject_requirement`,
  `deprecate_requirement`.
- Trace: `propose_trace_link`, `create_trace_link`, `accept/reject/mark_stale/
  mark_orphaned`, `trace_for`.
- Verification: `add_verification_method`, `record_verification_evidence`
  (fan-in 24), `verification_status`, `_compute_verification_status`.
- Baselines: `create_baseline`, `diff_baseline`, `show/list_baseline`.
- Aggregates: `requirement_dossier`, `requirement_preflight_profile`.
- 64 private helpers: `_record_event`, `_store_idempotency`/`_idempotent_*`,
  `_dossier_*`, `_validate_*`, row↔dataclass mappers, ID/sequence allocators.

**Dependencies:**
- Inbound: CLI, MCP Read Surface.
- Outbound: Store, Domain Model & Errors.

**Patterns Observed:** Facade over the store; transaction-script per operation;
state-machine validation for trace links and requirement status; explicit
idempotency keys; event sourcing of mutations.

**Concerns:** **God-object.** 2136 LOC / one class / ~29 public + ~40 private
methods (29 public + 64 private) spanning six distinct responsibility clusters
(requirements, criteria, trace, verification, baselines, dossiers). Its trace
ontology is a **hardcoded allow-list** of `(from_kind, relation, to_kind)`
triples in `_validate_trace_relation` (`service.py:1877`) — which already
contains `loomweave_entity satisfies requirement_version` but **no `goal` node
kind and no `requirement → goal` edge**; the reframe's central edge type does not
exist here yet. This is the repo's dominant
maintainability and testability risk and the clearest refactor target (extract
per-aggregate services/repositories). Detailed in `05-quality-assessment.md`.

**Confidence:** High — full method inventory + coupling data.

---

## 4. MCP Read Surface

**Location:** `src/plainweave/mcp_surface.py` (1141), `mcp_server.py` (132),
`envelopes.py` (115)

**Responsibility:** Expose the read-only, agent-facing MCP tool surface
(`plainweave_*` tools: project context, requirement search/get/dossier, trace
listing, baselines, verification status, preflight facts, entity-intent context)
as standard JSON envelopes; register them on an MCP stdio server.

**Key Components:**
- `mcp_surface.PlainweaveMcpSurface` — the tool methods (e.g.
  `plainweave_preflight_facts_get` fan-out 11, plus requirement/dossier/baseline/
  verification reads). `MCP_RESOURCE_URIS`.
- `mcp_server.create_mcp_server` (fan-out 14) / `main` — SDK wiring + entry point.
- `envelopes.py` — `success_envelope`/`error_envelope`/`list_envelope`
  (`schema`/`ok`/`data`/`warnings`/`meta.producer`); cross-cutting output contract
  (ADR-004).

**Dependencies:**
- Inbound: none (it is a front door); `mcp_server` ← console script.
- Outbound: Service Core, Domain Model & Errors, Envelopes, `paths`,
  **and `cli_commands` (CLI subsystem)** — see Concerns.

**Patterns Observed:** Read-only surface (tests assert tools do not mutate
state); envelope-wrapped, schema-tagged responses; honest peer-absence labelling.

**Concerns:** **Cross-presentation coupling.** `mcp_surface` imports *private*
serializers from `cli_commands` (`_baseline_dict`, `_baseline_diff_dict`, `_dossier_dict`,
`_record_dict`, `_trace_dict`, `_requirement_verification_status_dict`,
`_current_project_key`, `inspect_project`). The DTO→dict shaping layer lives in
the CLI module
and is shared via underscore-private imports — a misplaced-shared-layer smell.
Either presentation surface breaks if the other's privates move.

**Confidence:** High.

---

## 5. CLI

**Location:** `src/plainweave/cli.py` (35), `cli_commands.py` (1066),
`__main__.py`

**Responsibility:** The full command-line interface over the as-built service:
argparse command registration, argument handling, service invocation, and
result→JSON/text rendering. Also hosts the shared DTO→dict serialization helpers.

**Key Components:**
- `cli.main` (fan-in 21) — argparse entry; console script `plainweave`.
- `cli_commands.register_commands` — command table.
- `cli_commands._handle_service_result` (fan-in 18) — uniform result/error
  rendering through the envelope contract.
- `cli_commands.inspect_project` + `_*_dict` serializers — also imported by the
  MCP surface (the de-facto shared serialization layer).

**Dependencies:**
- Inbound: MCP Read Surface (imports its serializers), `cli` ← console script.
- Outbound: Service Core, Store, Domain Model & Errors, Envelopes, `paths`.

**Patterns Observed:** Thin entry (`cli.py`) + fat command module; uniform
envelope-based result handling shared with MCP.

**Concerns:** (1) Hosts serialization helpers consumed by another subsystem
(MCP) — these belong in a neutral `serializers`/`views` module, not in `cli_commands`.
(2) 1066 LOC — large; command handling + serialization + project inspection are
co-mingled. (3) Calls `store.connect`/`migrate` directly.

**Confidence:** High.

---

## 6. Intent Graph & Bindings — *Reframe target (stubbed)*

**Location:** `src/plainweave/intent_graph.py` (113), `bindings.py` (71)

**Responsibility (target):** The headline reframe capability — model intent as a
directed graph (goal → requirement → code SEI) and expose the three composable
read primitives `orphans(level)` / `trace(node)` / `corpus()`; bind code leaves
to requirements via the **ADR-029 entity-association contract**, SEI-keyed
(`loomweave:eid:...`) with `content_hash_at_attach` drift detection.

**Key Components:**
- `intent_graph.py` — `IntentLevel` (StrEnum CODE/REQUIREMENT/GOAL), `IntentNode`,
  `Trace`, `CorpusEntry` dataclasses, and `IntentGraphReads.{orphans,trace,corpus}`.
- `bindings.py` — `SeiBinding` dataclass, `bind_sei_to_requirement`, `is_drifted`.

**Dependencies:**
- Inbound: none yet. Outbound: none (standalone modules; not wired to Service
  Core or Store).

**Patterns Observed:** **Interface-first stubs** — every behavioural method
`raise NotImplementedError(_PENDING)` with docstrings pointing at the design doc
and `.filigree` backlog. Data shapes are defined; behaviour is not.

**Concerns:** This is the *raison d'être* of the reframe and it is **not
implemented**. The dataclasses define the target contract but nothing ties them
to the existing `trace_links`/requirements store, to Loomweave SEI resolution, or
to a write path. Tracked: `plainweave-c2d58800a0` (epic) and siblings. Not a
defect — a deliberate, documented standup boundary — but the architecture's
center of gravity is still aspirational.

**Confidence:** High — explicit `NotImplementedError` + docstrings + MODULE-MAP.

---

## Cross-cutting observations

- **Output contract (`envelopes.py`) + error vocab (`errors.py`)** are
  consistent cross-cutting concerns used by both front doors — good contract
  discipline (ADR-004).
- **Serialization layer is homeless:** the `_*_dict` DTO mappers live in
  `cli_commands` but serve both front doors. This is the single clearest
  structural correction (extract a `views`/`serializers` subsystem).
- **Persistence boundary is leaky:** both CLI and (transitively) the service
  open the store; CLI bypasses the service for `connect`/`migrate`.
