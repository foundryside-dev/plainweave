# 06 — Architect Handover

*Transition document from archaeology → improvement planning. Turns the findings
in `05-quality-assessment.md` into a sequenced, behavior-preserving plan. The
governing principle: **decompose the service before building the reframe**, and
do the cheap mechanical extractions first to de-risk the larger ones.*

## Guardrails for all work below

- **Behavior-preserving.** The existing test suite (≈ src LOC, golden contract
  fixtures, 90% branch gate) is the safety net. Run `make ci` after each step;
  no green, no merge.
- **Preserve the spine.** The append-only event log (`_record_event`),
  idempotency machinery (`_idempotent_*`), and trace state-machine validation are
  load-bearing correctness assets — carry them into the new structure intact, do
  not rewrite them.
- **SEI scheme is frozen.** `loomweave:eid:...` is consumed, never minted or
  reinterpreted (`bindings.py` docstring). Reframe work depends on Loomweave for
  identity/rename and on Legis for any teeth/audit — build neither here.
- **Verify the backlog first.** Read `plainweave-c2d58800a0` (epic) + siblings
  and the referenced implementation plan before acting — the sequencing below may
  already be partly planned; reconcile rather than duplicate.

## Recommended sequence

### Phase 0 — Cheap, high-value extractions (de-risk everything else)

These are mechanical, low-risk, and remove the layering inversions that make the
big refactor cleaner.

1. **Extract `serializers.py` / `views.py` (DEBT-02).** Move the `_*_dict`
   mappers + `inspect_project` + `_current_project_key` out of `cli_commands.py`
   into a neutral module as public API. Repoint both `cli_commands` and
   `mcp_surface` at it. Removes the `mcp → cli` private-import inversion.
   *Effort: M. Risk: Low.*
2. **Close the persistence boundary (DEBT-03).** Add `PlainweaveService.initialize()`
   / `inspect()` (or a small `bootstrap` seam) owning `migrate`/`connect`/
   `read_schema_meta`; remove the `store` import from `cli_commands`. Service
   becomes the sole funnel into persistence. *Effort: S. Risk: Low.*
3. **Split `models.py` (DEBT-06).** Move the 10 `Dossier*` read-model dataclasses
   to `read_models.py` (or co-locate with the dossier assembler from Phase 1).
   *Effort: M. Risk: Low.*

### Phase 1 — Decompose `PlainweaveService` (DEBT-01) — *do before the reframe*

Split the god-object along its six existing responsibility clusters, behind a
thin facade so callers (CLI, MCP) need not change all at once:

- `RequirementService` (lifecycle: create/update/approve/supersede/reject/deprecate
  + acceptance criteria)
- `TraceService` (propose/create/accept/reject/stale/orphan + `trace_for`)
- `VerificationService` (methods, evidence, status computation)
- `BaselineService` (create/diff/list/show)
- `DossierAssembler` (the `_dossier_*` read aggregation)
- A shared **persistence-repository / unit-of-work** layer holding `connect`,
  `_record_event`, `_idempotent_*`, the row↔dataclass mappers, and ID allocators.

Keep `PlainweaveService` as a façade delegating to these, then migrate callers
incrementally. *Effort: L. Risk: Low (test-backed). This is the highest-leverage
item; deferring it compounds against the reframe.*

### Phase 2 — Schema upgrade ladder (DEBT-07) — *before the reframe touches the DB*

Replace the flat `SCHEMA_VERSION = 1` + monolithic `migrate()` with a versioned
step structure (ordered `(from_version, fn)` ladder or per-version SQL keyed off
the stored `schema_version`). Extend `tests/test_store_migrations.py` to assert
*upgrade* steps, not just first-creation. Needed because the reframe adds
goal-node and (possibly) binding-cache tables to existing databases.
*Effort: M now / L if deferred.*

### Phase 3 — Build the reframe on the clean base

Only after Phases 0–2. The reframe-readiness finding (`05`, `service.py:1877`,
`:977`) dictates the shape:

1. **Data-drive the trace ontology.** Move the hardcoded `(from_kind, relation,
   to_kind)` allow-list out of the (now-decomposed) service into a registry/table
   so new altitudes don't require hand-editing a `set`. Add the `goal` node kind
   and the `requirement → goal` ("justified by") triple — the reframe's defining
   edge.
2. **Implement the graph walk.** Build `trace(node)` / `orphans(level)` as
   recursive-CTE graph queries over `trace_links` inside a dedicated
   **`IntentGraphService`** (wiring up `intent_graph.IntentGraphReads`), *not* as
   more methods on the façade. `trace_for`'s single-hop filter is the precursor to
   replace, not extend.
3. **Wire ADR-029 bindings (`bindings.py`).** Implement `bind_sei_to_requirement`
   / `is_drifted` against the entity-association contract, keyed by SEI with
   `content_hash_at_attach` drift detection. Consume Loomweave for SEI
   resolution; do not build identity locally.
4. **Authoring-time write path + Legis boundary cell** per the design — advisory
   by default; surface coverage facts at the git/CI boundary through Legis.

## Cross-pack recommendations

- **Security / threat modeling:** *Not warranted now* — local SQLite, stdio MCP,
  no network surface, one runtime dep. **Re-evaluate** (e.g. `ordis-security-architect`,
  `wardline` trust-boundary review) if/when a network seam is added (Legis HTTP
  boundary). The repo already wires `wardline` as its trust-boundary gate
  (CLAUDE.md) — run `wardline scan . --fail-on ERROR` on any boundary-touching
  reframe code.
- **Test gaps:** run a coverage pass (`ordis-quality-engineering:analyze-test-gaps`)
  to confirm per-cluster `service.py` coverage before decomposition, so the safety
  net is verified, not assumed.
- **Decomposition execution:** the `axiom-python-engineering:refactoring-architect`
  agent is the right tool to sequence the Phase-1 extraction as behavior-preserving
  moves.

## Open questions for the owner / next architect

1. Does the `.filigree` epic + implementation plan already sequence
   *decompose-before-build*? If not, this handover argues it should.
2. Is the goal altitude meant to live in `trace_links` (generic edge reuse) or a
   dedicated table? The analysis recommends edge reuse (the substrate already
   supports it), with the ontology data-driven.
3. What is the intended migration story for *existing* `.plainweave` databases
   once goal nodes ship — confirm Phase 2 lands first.

## Definition of done for the improvement effort

- `PlainweaveService` is a thin façade; no single core class exceeds ~400 LOC.
- No presentation module imports another presentation module's privates.
- `store` is imported only by the persistence/service layer.
- The trace ontology is data-driven and includes the `goal` kind + `requirement →
  goal` edge.
- `orphans`/`trace`/`corpus` are implemented and tested over the graph; the
  `NotImplementedError` stubs are gone.
- `make ci` green throughout; coverage gate held at ≥90%.
