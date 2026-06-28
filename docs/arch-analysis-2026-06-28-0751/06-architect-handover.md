# 06 — Architect Handover

**Subject:** Plainweave · **Live tree:** HEAD `8258f76` · **Date:** 2026-06-28
**Purpose:** Convert the analysis into a sequenced, behaviour-preserving
improvement backlog an architect can drive. Each initiative names the
quality-register items it closes (`Q#` → `05-quality-assessment.md`), its
dependencies, effort, risk, and acceptance criteria. Feeds
`/axiom-system-architect` (assess → prioritize → catalog-debt).

## Guiding constraints (read before sequencing)

1. **Preserve the doctrine.** Advisory / enrich-only / thin / prescribe-nothing
   is the product thesis and is faithfully implemented. No initiative here adds
   enforcement, a heavier dependency, or a sibling-machinery rebuild.
2. **Behaviour-preserving first.** The contract discipline (versioned envelopes,
   closed `ErrorCode`, golden-vector seam tests, ≥90% branch gate) is an asset —
   it makes refactors *safe*. Every initiative must keep `make ci` green and the
   golden vectors byte-stable (Q17 is a prerequisite for that on timestamped
   payloads).
3. **Right-size for the target.** Plainweave is single-operator/local-first. Do
   **not** gold-plate it into a multi-tenant server (no auth framework, no
   connection-pool library, no async rewrite). Fixes should remove ceilings and
   close stated contracts, not chase scale the product does not target.

---

## Initiative A — Persistence hardening *(do first; unblocks B & D)*

**Closes:** Q1, Q2, Q3, Q5, Q7 · **Effort:** S–M · **Risk:** Low · **Blast radius:** `store.py` + the data-access call sites

The single highest-leverage move: make the persistence seam correct and
contention-survivable before anything else touches it.

- Set `pragma journal_mode=WAL` and an explicit `busy_timeout` in
  `store.connect` (Q3) — removes the implicit stdlib-default dependency and the
  writer-blocks-readers ceiling.
- Add a `sqlite3.Error` → `PlainweaveError` mapping at the store boundary
  (UNIQUE/PK violation→`CONFLICT`; other `IntegrityError`→`VALIDATION`; else
  `INTERNAL`) so DB failures honour the documented `ErrorCode` contract (Q1).
  Prevent the `count(*)+1` race (Q2) by serializing writers with `BEGIN
  IMMEDIATE` (or a monotonic sequence), not by retry alone.
- Reuse one connection per logical operation; thread the open connection into
  `_goal_nodes_for_surface` (Q5) and the Loomweave adapter reads (Q7).

**Acceptance:** a concurrent-writer test produces `CONFLICT` (not raw
`IntegrityError`); WAL confirmed via `pragma journal_mode`; `busy_timeout` set
explicitly (no reliance on the stdlib default); `make ci` green.
*(Note: this does NOT remove the suppressed `ResourceWarning: unclosed database`
— production connections already close deterministically; that warning is a
test-fixture issue, see Q23 / Initiative G.)*

## Initiative B — Service decomposition *(depends on A)*

**Closes:** Q9, Q12 · **Effort:** L · **Risk:** Medium (mitigated by the test suite) · **Blast radius:** `service.py`

Break the 3027-LOC god object in behaviour-preserving stages, each landing
independently with green CI:

1. **Extract a repository / data-access layer** (enabled by A's connection
   seam) — moves the raw SQL out of the use-case methods. This is the structural
   keystone.
2. **Relocate the intent-graph computation** (`service.py:1311-1507`) into
   `intent_graph.py` so the product's defining capability lives in the module
   that names it (Q12); wire the dead `IntentGraphReads` facade or retire it (Q19).
3. **Split aggregates** (requirements / traces / baselines / verification) into
   per-aggregate service modules sharing the `_error`/`_now`/`_require_actor`/
   `_record_event`/`_requirement_row` helper cluster.

**Acceptance:** no single module > ~1000 LOC; coverage/orphans/trace logic
importable from `intent_graph`; every stage keeps the golden vectors and ≥90%
gate; public method signatures unchanged (surfaces untouched).

## Initiative C — Surface-contract cleanup

**Closes:** Q10, Q16, Q17, Q18, Q22 · **Effort:** M · **Risk:** Low · **Blast radius:** `cli_commands.py`, `mcp_surface.py`, `envelopes.py`

- Extract the shared `_*_dict` serializers + `inspect_project`/
  `_current_project_key` into a neutral `serialization.py` both surfaces import,
  dissolving the surface↔surface coupling and the function-local-import
  workaround (Q10).
- Make `generated_at` an injectable clock parameter at the envelope boundary
  (Q17) — also the prerequisite for byte-stable goldens under Initiative B.
- Guard `project_context_get` like its sibling tools (Q16); add a schema-version
  registry (Q18); drop the no-op `list_result` param (Q22).

**Acceptance:** `mcp_surface` no longer imports from `cli_commands`; a golden
vector is byte-identical across two runs without test-side timestamp injection.

## Initiative D — Read-path scaling *(depends on A)*

**Closes:** Q4, Q6, Q8 · **Effort:** M · **Risk:** Low · **Blast radius:** `mcp_surface.py`, `web/views.py`, `service.py`

- Add `limit`/`offset` to `plainweave_preflight_facts_get`; batch the 3-calls-
  per-requirement into set-based reads; cap/paginate the default project scope
  (Q4 — tracker P3 `706d80dc8e`).
- Batch the web review-queue per-draft dossier fetches; derive/cache the pending
  count (Q6). Push pagination into the service query for MCP `_list` (Q8).

**Acceptance:** a bare `preflight_facts_get` on a large corpus issues O(1)
set-queries, not O(corpus); the two open P3 tracker tasks close.

## Initiative E — Web hardening

**Closes:** Q13, Q14, Q15 · **Effort:** S–M · **Risk:** Low · **Blast radius:** `web/`

- Refuse a non-loopback `--host` bind unless an explicit `--insecure` / token is
  given; at minimum document the exposure on the flag (Q13).
- Promote the manual review-queue a11y behaviour (focus move + `#sr-status`
  announcement) to a CI gate using the existing web Playwright harness (Q14).
- Branch CSRF body-parsing on `Content-Type` or test+document the urlencoded
  constraint (Q15).

**Acceptance:** starting `--host 0.0.0.0` without the ack fails closed; a headless
test asserts focus + live-region text after approve/accept/reject.

## Initiative F — Migration framework *(before the next breaking schema change)*

**Closes:** Q11 · **Effort:** M · **Risk:** Medium · **Blast radius:** `store.py`

Introduce a version-aware migration ladder keyed on
`schema_meta.schema_version` (the `read_schema_meta`/SCHEMA_MISMATCH plumbing
already detects drift). Not urgent while the schema is stable; **required before
any change that needs a data transform** (the current `create-if-not-exists`
approach cannot evolve existing rows).

**Acceptance:** a v2→v3 migration with a data transform runs forward
idempotently and is covered by `test_store_migrations`.

## Initiative G — Hygiene sweep *(any time; trivial)*

**Closes:** Q19, Q20, Q21, Q23 · **Effort:** S · **Risk:** None

Delete the empty `experimental/` package (Q20, confirmed unreferenced); resolve
the `status requirement` / `verify status` duplicate (Q21); decide
`IntentGraphReads` (Q19, folds into B); close test-fixture connections explicitly
and correct/narrow the misleading `ResourceWarning` suppression (Q23).

---

## Sequencing & dependency graph

```
A (persistence)  ──►  B (service decomposition)
      │                     │
      └──────►  D (read scaling)
C (surface contract) ──► (enables byte-stable goldens for B)
E (web)   F (migration)   G (hygiene)   ── independent, schedule freely
```

**Recommended order:** A → C → B → D, with E/F/G interleaved opportunistically.
A is first because it is the shared seam every other data-touching change passes
through; C is cheap and removes the goldens' non-determinism that B needs.

## Effort × impact

| Initiative | Effort | Impact | When |
|------------|--------|--------|------|
| A Persistence hardening | S–M | **High** | Now |
| C Surface contract | M | Medium | Now (cheap, unblocks B goldens) |
| B Service decomposition | L | **High** | After A/C |
| D Read scaling | M | Medium-High | After A (closes 2 P3s) |
| E Web hardening | S–M | Medium | Scheduleable |
| F Migration framework | M | Medium | Before next schema break |
| G Hygiene | S | Low | Any time |

## What to leave alone (anti-gold-plating)

- **The enrich-only / advisory posture** — do not add enforcement.
- **The single-runtime-dependency footprint** — no ORM, no pool library, no
  async rewrite; the connection-reuse fix in A is sufficient.
- **The honest-degradation contract** (typed `unavailable`, `PEER_*` codes,
  drift flagging) — a strength; extend the pattern, don't replace it.
- **Web as a single-operator console** — do not build a multi-user auth system;
  the bind-guard in E is the proportionate control.

## Cross-pack recommendations

- **`/axiom-system-architect`** — drive this backlog: `assess-architecture` for
  an independent critique, then `prioritize-improvements` / `catalog-debt`.
- **`/axiom-embedded-database` (`audit-sqlite-discipline`)** — Initiatives A & F
  are squarely SQLite-discipline work (WAL, busy_timeout, isolation, migration
  ladder); this pack's reviewer covers exactly those sheets.
- **`/ordis-security-architect` (`threat-model`)** — scope the web write-surface
  exposure (Q13) for the `--host` threat model before promoting any non-loopback
  deployment.
- **`/axiom-python-engineering` (`refactoring-architect`)** — the staged,
  behaviour-preserving god-object split in Initiative B.

## Open tracker linkage (already filed)

- P3 `706d80dc8e` — preflight `project` scope fan-out, no cap/pagination → **D/Q4**
- P3 `3edcd19943` — preflight N+1 connections per scoped requirement → **A/Q3 + D/Q4**
  (Q5 — the *intent_coverage* N+1 — is a separate site with no dedicated task,
  also closed by A)
- P3 `02376962ab` — optional Loomweave-semantic similarity hint (a feature, not
  debt; out of scope for this remediation backlog)
