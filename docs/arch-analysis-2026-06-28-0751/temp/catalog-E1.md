## Domain Service Core

**Location:** `src/plainweave/service.py`, `src/plainweave/models.py`, `src/plainweave/bindings.py`

**Responsibility:** The domain orchestrator — a single `PlainweaveService` class that owns every requirements-traceability use case (requirement lifecycle, acceptance criteria, trace links, goals/intent edges, code-entity & SEI bindings, baselines, verification methods/evidence, dossiers, and the intent-graph reads) over a directly-accessed SQLite store, emitting an append-only event log and advisory enrich-only reads.

**Key Components:**
- `service.py` (3027 LOC, one class `PlainweaveService` at `service.py:64`) — ~40 public use-case methods plus ~70 private helpers. Notable surfaces:
  - Requirement lifecycle: `create_requirement` (`service.py:454`), `update_draft` (`512`), `approve_requirement` (`565`), `supersede_requirement` (`626`), `reject_requirement` (`720`), `deprecate_requirement` (`758`).
  - Acceptance criteria: `add_acceptance_criterion` (`810`), `list_acceptance_criteria` (`871`).
  - Trace links: `propose_trace_link`/`create_trace_link` (`905`/`923`), `accept`/`reject`/`mark_stale`/`mark_orphaned` (`994`–`1004`) all funnel through `_transition_trace` (`2386`); canonical relation/transition whitelists at `_validate_trace_relation` (`2767`) and `_validate_trace_transition` (`2782`).
  - Goals & intent edges: `create_goal` (`1020`), `link_goal_to_requirement` (`1060`), `goals_for_requirement` (`1112`).
  - Code entities & SEI bindings (ADR-029): `record_code_entity` (`1137`), `bind_sei_to_requirement` (`1198`, persists into `entity_associations`), `list_sei_bindings` (`1286`).
  - Baselines: `create_baseline` (`304`), `diff_baseline` (`372`); locked-baseline immutability enforced by DB triggers (`store.py:178`).
  - Verification: `add_verification_method` (`148`), `record_verification_evidence` (`197`), status engine `_compute_verification_status` (`2307`), authority resolver `_evidence_authority` (`2994`).
  - Dossier: `requirement_dossier` (`260`) assembles authority summary, traces, verification, baseline exposure, `_dossier_computed_gaps` (`1802`), `_dossier_next_actions` (`1876`), `_dossier_peer_facts` (`2565`).
  - Actor registry / trust boundary: `register_actor` (`78`) with genesis-attester bootstrap (`108`–`124`).
  - High-fan-in private cluster: `_error` (`3020`, the only `PlainweaveError` factory), `_now` (`3026`), `_require_actor` (`2968`), `_record_event` (`2792`, the append-only `events` writer), `_requirement_row` (`2086`, multi-key resolver matching `display_id`/`requirement_id`/`stable_id`). These five are called by nearly every method and are what keep the monolith cohesive.
- `models.py` (310 LOC) — ~30 frozen domain dataclasses (typed records): `Actor`, `RequirementDraft`/`Version`/`Record`, `AcceptanceCriterion`, `TraceRef`/`TraceLink`, `IntentGoal`/`IntentEdge`, `CodeEntity`, `Baseline`/`Member`/`Diff`, verification records, and the full `RequirementDossier` section tree (`models.py:222`–`311`). Pure leaf — imports only `dataclasses`/`typing` (`models.py:1`–`4`).
- `bindings.py` (98 LOC) — ADR-029 SEI value object `SeiBinding` (`bindings.py:29`) with a `sei` back-compat alias (`51`), storage-free constructor `bind_sei_to_requirement` (`56`), and drift helper `is_drifted` (`91`). Pure leaf — only `dataclasses`/`datetime`/`typing`. Comment declares the `loomweave:eid:` scheme FROZEN (consumed, never minted, `bindings.py:16`).

**Dependencies:**
- Inbound:
  - CLI Surface — `cli_commands.py` instantiates `PlainweaveService` (`cli_commands.py:1226`, Loomweave unresolved-candidate) and calls its methods (e.g. `service.intent_coverage`, `service.bind_sei_to_requirement`).
  - MCP Surface — `mcp_surface.py` instantiates it (`mcp_surface.py:743`) and calls e.g. `service.intent_coverage` (`mcp_surface.py:546`).
  - Web UI — `web/context.py:28` constructs it; `web/routes/intent.py:15` calls `ctx.service.intent_coverage`; `web/routes/{goals,requirements,review}.py` and `web/views.py` import the domain models (grep over `from plainweave.models import`).
  - Tests — `tests/state/*` and `tests/test_intent_*` exercise the service directly (the dominant resolved caller set).
- Outbound:
  - Persistence — `from plainweave.store import connect, read_schema_meta` (`service.py:60`); the service calls `connect(self.db_path)` directly in every method and is itself the data-access tier (no repository layer).
  - Sibling-Tool Adapters — `loomweave_adapter` (`PUBLIC_SURFACE_TAGS`, `LoomweaveAdapter`, `LoomweaveCatalogEntity`, `LoomweaveIdentityError`, `service.py:24`) and `wardline_adapter` (`WardlineAdapter`, `service.py:61`); built per-call via `_loomweave_adapter` (`2595`) / `_wardline_adapter` (`2598`).
  - Intent Graph — imports its types (`CorpusEntry`, `IntentCoverage`, `IntentCoverageSurface`, `IntentLevel`, `IntentNode`, `Trace`, `DEFAULT_INTENT_COVERAGE_EXCLUDED_NAMESPACES`, `service.py:15`).
  - Response Contract / Cross-cutting — `from plainweave.errors import ErrorCode, PlainweaveError` (`service.py:14`).

**Patterns Observed:**
- Canonical use-case template: `_require_actor` → validate → `_now()` → `with connect() as connection:` → `_requirement_row()` resolve → SQL mutate → `_record_event()` → `connection.commit()` → return a `*_from_row` dataclass (e.g. `create_requirement` `service.py:454`–`510`, `approve_requirement` `565`–`624`).
- Event sourcing: every mutation appends to the append-only `events` table via `_record_event` (`service.py:2792`); table is update/delete-blocked by DB triggers (`store.py:269`). Event ids are `EVT-{uuid4}` (`service.py:2812`).
- Optimistic concurrency + idempotency: writes gate on `expected_version`/`expected_draft_revision` (`_require_current_version` `2101`, draft check `529`); `approve`/`supersede`/`deprecate` cache responses in `idempotency_keys` keyed by a request hash and replay them (`574`–`582`, `_store_idempotency` `2823`, `_idempotency_payload` `2872`).
- Authority from the registry, not the actor string: `_evidence_authority` (`service.py:2994`) and `register_actor` (`78`) derive attestation authority from a registered `actors.kind`; a free-form `--actor human:fake` defaults to least-privileged `agent_reported`. `_require_actor` (`2968`) is only a non-empty check — normal-write attribution is honour-system by design.
- Multi-key entity resolution: `_requirement_row` (`2086`) and `_goal_row` (`2616`) resolve by `display_id` OR canonical id OR `stable_id`, so any identifier form works at the boundary.
- Sequential `count(*) + 1` id generation: `_next_requirement_number` (`2110`), `_next_link_number` (`2137`), `_next_evidence_number` (`2149`), etc.
- Enrich-only Loomweave trace hydration with drift: `_trace_from_row` (`2449`) re-resolves `loomweave_entity` refs via `_enrich_loomweave_trace` (`2483`), flagging `freshness=stale` + a `content_hash_drift` degraded note on hash mismatch (`2496`–`2505`); orphaned/unreachable handled by `_trace_with_degraded_snapshot` (`2521`). Degraded states are always explicit, never an implied-clean.
- Peer-fact honesty: `_dossier_peer_facts` (`service.py:2565`) holds `live_peer_calls=False` always and records a configured HTTP endpoint as a *capability*, not as evidence of a call (`2585`–`2588`).

**Concerns:**
- God object / missing layering: a single 3027-LOC class spans ~13 aggregates and is simultaneously the use-case layer AND the data-access layer (raw SQL inline, no repository). High-fan-in helpers keep it cohesive, but every aggregate's logic, SQL, and serialization live in one file (`service.py:64`–`3027`) — the dominant maintainability risk.
- DB exceptions escape the `ErrorCode` contract: only domain failures route through `_error`→`PlainweaveError` (`service.py:3020`); `connection.execute(...)` is never wrapped, so `sqlite3.IntegrityError`/`OperationalError` propagate raw. Callers that switch on `ErrorCode` (the documented contract) cannot catch them. Fully verifiable from `service.py` + `store.py`.
- `count(*) + 1` id generation is not concurrency-safe by construction (`service.py:2110`, `2137`, `2149`, …). It fails *safe* — every counter-derived id feeds a UNIQUE/PK column (`requirements.display_id`/`stable_id` NOT NULL UNIQUE `store.py:40`–`41`; `intent_goals` `118`–`119`; all `*_id` PKs), so a concurrent second writer collides on a constraint rather than silently duplicating. But `store.connect()` (`store.py:12`–`19`) sets only `pragma foreign_keys=on` — no `busy_timeout`, WAL, or `BEGIN IMMEDIATE` — so under contention the loser surfaces as a raw `IntegrityError`/`OperationalError` (per the contract gap above) instead of a clean `CONFLICT`. Severity is low for the documented single-writer local-first model; it would bite any multi-process/agent concurrent-write scenario.
- Per-surface connection fan-out in coverage: `intent_coverage` (`service.py:1415`) calls `_goal_nodes_for_surface` (`1529`) per catalog surface, and that helper opens a fresh `connect()` each call (`1542`) inside the per-entity loop — an N+1-connection pattern that could be slow on a large catalog. Adapters are likewise rebuilt per call (`2595`–`2599`).

**Confidence:** High — read 100% of `service.py` (3027 LOC), `models.py`, `bindings.py`, and `store.py`; cross-checked inbound edges against Loomweave `entity_callers_list`/unresolved-candidate data for `PlainweaveService`, `bind_sei_to_requirement`, and `intent_coverage`, and outbound imports against the source. Inbound mapping leans on Loomweave's dynamic-instantiation candidates (callers unresolved because the class is constructed dynamically) corroborated by the import grep, so subsystem names are well-evidenced but exact call counts are not exhaustive. Gap: I did not read `loomweave_adapter.py`/`wardline_adapter.py` internals (only their consumed surface) or the CLI/MCP/Web serializers in full — left to E-peers owning those subsystems.

---

## Intent Graph

**Location:** `src/plainweave/intent_graph.py`

**Responsibility:** Defines the intent-graph vocabulary and read contract — the node/altitude types (`goal ▲ requirement ▲ code-SEI`), the coverage/orphans/trace/corpus result records (including the honest north-star `IntentCoverage`), and a small injectable `IntentGraphReads` facade — over which `PlainweaveService` computes the actual code-up traceability reads.

**Key Components:**
- `intent_graph.py` (184 LOC) — pure type + contract module, no DB access:
  - `IntentLevel(StrEnum)` (`intent_graph.py:28`) — the three altitudes `CODE`/`REQUIREMENT`/`GOAL`; doc notes the graph does not fix the level count.
  - `IntentNode` (`44`), `Trace` (`55`, up/down justification neighbourhood), `CorpusEntry` (`67`, requirement + goal/code links).
  - `IntentCoverage` (`100`) and `IntentCoverageSurface` (`84`) — the north-star reading; honesty fields `denominator_complete` (`117`), `coverage` verbatim block (`118`), `surfaces_truncated` (`124`), `excluded_namespaces`/`excluded_count` (`121`–`122`), `adapter_status`/`adapter_degraded` (`125`–`126`). Docstring states the reading is ADVISORY, never a pass/fail (`108`).
  - `DEFAULT_INTENT_COVERAGE_EXCLUDED_NAMESPACES = ("scripts.", "tests.")` (`80`) — the default denominator scoping.
  - `IntentGraphReads` (`141`) — injectable facade with three composable reader Protocols (`orphans`/`trace`/`corpus`, `129`–`138`); each method no-ops to an empty result when its reader is unset (`164`, `173`, `181`).
- Note on where computation actually lives: the graph queries are implemented on `PlainweaveService`, NOT in this module — `intent_orphans` (`service.py:1311`), `intent_trace` (`1346`), `intent_corpus` (`1388`), `intent_coverage` (`1415`). This file is the typed boundary they return across.

**Dependencies:**
- Inbound:
  - Domain Service Core — `service.py:15` imports the types; the service's four `intent_*` methods construct and return them.
  - CLI / MCP / Web Surfaces — consume the result types via the service: `intent_coverage` is called by `cli_commands.py`, `mcp_surface.py:546`, and `web/routes/intent.py:15` (Loomweave callee candidates), which serialize `IntentCoverage`.
  - Tests — `IntentGraphReads` (the facade class itself) is constructed ONLY by tests (`tests/test_target_interfaces.py:32`, `tests/test_target_interface_stubs.py`); no production caller wires it (Loomweave `entity_callers_list` on `IntentGraphReads` returns only test candidates).
- Outbound:
  - None within Plainweave — imports only stdlib `dataclasses`, `enum.StrEnum`, `typing.Protocol` (`intent_graph.py:21`–`25`). A dependency-free leaf module.

**Patterns Observed:**
- Honesty qualifiers surfaced, not computed-away: `IntentCoverage.numerator`/`denominator`/`ratio` are always the full counts while the evidence lists are bounded by `max_surfaces`, with `surfaces_truncated` flagging dropped rows (`service.py:1483`–`1492`). `denominator_complete` is derived from `coverage["complete"]` (`service.py:1497`), and the whole `coverage` block (including `present_plugins`) is carried verbatim from the Loomweave adapter (`coverage = dict(page.coverage)` `service.py:1456`; `present_plugins` originates in `loomweave_adapter.py:203`, not in this subsystem). A degraded denominator is therefore never presented as a complete-surface reading.
- Coverage counts LIVE justification only: `_goal_nodes_for_surface` (`service.py:1529`) uses `_live_requirement_ids_for_entity` (`service.py:2730`, `status in ('draft','approved')`), deliberately diverging from `intent_trace`, which keeps surfacing deprecated requirements — documented in-code as "trace *explains*, coverage *counts*" (`service.py:1537`–`1539`). A binding whose only requirement is deprecated is correctly not counted.
- Namespace scoping + surface-class filtering: default `scripts.`/`tests.` exclusion (`intent_graph.py:80`) applied in `intent_coverage` (`service.py:1476`), with caller override and validated `surface_classes` (`_validated_surface_classes` `service.py:1509`).
- Prescribe-nothing read surface: `IntentGraphReads` offers three composable graph primitives rather than canned reports (docstring `intent_graph.py:142`–`147`); orphans = "nodes with no upward edge" at any altitude.
- Frozen-dataclass value objects throughout — every result type is `@dataclass(frozen=True)`.

**Concerns:**
- `IntentGraphReads` facade is dead in the production path: its docstring advertises "a small injectable facade for tests and adapters" (`intent_graph.py:18`, `142`), but no production adapter constructs it — every shipping read goes directly through `PlainweaveService.intent_*`. The contract and the real reads can drift independently because nothing but tests binds them together (Loomweave callers: tests only). Either wire it into the read path or mark it test-scaffolding.
- Contract/implementation split is non-obvious: a reader expecting the coverage/orphan/trace logic in `intent_graph.py` finds only types; the algorithms are 1100+ lines away in `service.py`. The module docstring points at `plainweave.service` (`intent_graph.py:15`–`18`), which mitigates but does not remove the indirection.
- `IntentCoverage` is a wide record (15 fields, `intent_graph.py:114`–`126`) mixing headline counts, evidence lists, scoping echoes, and adapter-health blocks; correct for an honest reading but a lot of surface for downstream serializers to keep in sync.

**Confidence:** High — read 100% of `intent_graph.py` (184 LOC) and the four computing methods plus their private helpers in `service.py`; verified the dead-facade claim via Loomweave `entity_callers_list` on `IntentGraphReads` (test-only candidates) and the `present_plugins` provenance via grep into `loomweave_adapter.py:203`. Gap: I did not read `loomweave_adapter.py`'s `_public_surface_coverage` body in full (only confirmed where `present_plugins`/`coverage.complete` originate), so the exact contents of the verbatim `coverage` block are owned by the Sibling-Tool Adapters slice.
