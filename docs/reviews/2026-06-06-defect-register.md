# Charter Defect Register — 2026-06-06

Source: six-subagent code audit of `main` (commit `cf0bf8a`) comparing the
shipped code against the roadmap, plans, specs, and ADRs. 139 tests pass; these
are gaps *behind* a green suite.

Each defect is self-contained for subagent hand-off: evidence, root cause, fix
approach, and acceptance criteria. The **Conflict group** field tells the
orchestrator how to parallelize without edit collisions — agents in the same
group must run serially *or* in separate worktrees (`isolation: "worktree"`);
agents in different groups are independent and can run concurrently.

Severity uses the project P-scale (P0 critical … P4 backlog).

---

## Conflict groups (for parallel burn-down)

| Group | Primary file(s) | Defects |
|---|---|---|
| **SERVICE** | `src/charter/service.py` | D1, D4, D5, D11 |
| **STORE** | `src/charter/store.py` (+ service ID alloc) | D2, D12 |
| **MCP** | `src/charter/mcp_surface.py` | D8, D9, D13 |
| **TESTS** | `tests/**` (new/own files) | D6, D7 |
| **DOCS** | `docs/**` | D15 |
| **FEATURE** | spans service+store+cli+mcp | D3, D14 |

Recommended wave plan:
- **Wave 1 (parallel, no conflicts):** one agent per group → D1 (SERVICE), D2
  (STORE), D8 (MCP), D6 (TESTS), D15 (DOCS). Use worktree isolation since
  several touch large shared files.
- **Wave 2:** remaining SERVICE (D4, D5, D11), STORE (D12), MCP (D9, D13),
  TESTS (D7) — sequence within each group.
- **Wave 3 (features, scoped design first):** D3, D14.

---

## P1 — Integrity / unmet Definition-of-Done

### D1 — Verification attestation authority is spoofable
- **Status:** ✅ RESOLVED (2026-06-06) via **Option 1 (actor registry), genesis-gated**.
  - **Authority resolution:** `_evidence_authority` now derives authority from
    the registered `actors` record (`_actor_kind`), never the raw actor string.
    It denies `waived`/`manual` unless the actor is a registered
    `human`/`attester`, and defaults unknown actors (bare, or spoofed `human:`)
    to least-privileged `agent_reported`. This closes the **inline** spoof and
    the bare-actor waiver/manual holes.
  - **Registration is gated, not open:** granting a `human`/`attester` kind
    requires the registrant to *already* be a registered attester, except the
    first (genesis) grant when none exists yet. So an agent cannot mint a fake
    human and then attest — the discriminating check "can an agent obtain
    `waiver`/`human_attested` via the shipped CLI?" is now **no, once a genesis
    attester is established** (verified end-to-end:
    `test_agent_cannot_fabricate_waiver_via_registration`,
    `test_cli_agent_cannot_register_attester_after_genesis`).
  - **Residual (honest):** the *genesis* attester grant is first-come and must
    be established out-of-band at project setup; and because the store is
    local-first, anyone who can run the CLI can edit the `.db` directly — the
    filesystem is the ultimate trust boundary. The fix makes CLI fabrication a
    deliberate, **audit-logged** act (`actor_registered` events), not a
    one-liner; it is not cryptographic prevention.
  - New `register_actor` service verb + `charter actor register` CLI wire the
    previously-dead `actors` table. Tests: `tests/state/test_actor_registry.py`
    + CLI coverage in `tests/test_cli_verification.py`.
  - **Note for D15:** the roadmap caveat for attestation authority should now
    read "registry-gated, audited; genesis + filesystem are the trust boundary,"
    not "honour-system pending actor registry."
  - **Tracked follow-ups (so the residual does not vanish):**
    - `charter-59e4af3aaf` (feature, P2) — seed the genesis attester at
      `charter init` to close the genesis land-grab race.
    - `charter-606b6e0a94` (task, P3) — `register_actor` re-registration polish
      (no-op idempotency + audited kind changes).
    - The `charter actor register` verb now has full contract-fixture parity
      with every other CLI verb (`cli/actor-register-json.json` + structural and
      live-output contract tests), so the agentic read surface stays consistent.
- **Severity:** P1 · **Type:** integrity / security · **Group:** SERVICE
- **Files:** `src/charter/service.py:1995-2007` (authority resolution),
  `src/charter/store.py:32-36` (dead `actors` table)
- **Evidence (reproduced live by audit):**
  - Authority is decided solely by `actor.startswith("agent:")`.
  - An agent passing `--actor human:fake` records a `waived`/`manual`
    attestation → requirement status becomes `waived`.
  - A **bare actor with no prefix** (e.g. `codex`) skips the `agent:` guard
    entirely and records a waiver/manual attestation.
  - The `actors` table exists in the schema but is **never read or written**
    (zero call sites).
- **Root cause:** anti-fabrication relies on an honour-system string prefix;
  there is no actor identity/role source of truth.
- **DoD violated:** roadmap "Verification Core" — *"agents cannot fabricate
  external/manual attestation authority."*
- **Fix approach (decide one, surface trade-off to maintainer):**
  1. Resolve authority from a registered-actor record (`actors.role`) instead
     of the raw string, defaulting unknown/unregistered actors to the
     least-privileged `agent_reported`; **deny** `waived`/`manual` unless the
     actor is a registered human/attester. *(Preferred — uses the table that
     already exists.)*
  2. If a registry is out of scope now: make the guard **deny-by-default** —
     any actor not explicitly proven human cannot set `waived`/`manual`
     authority; treat a missing/non-`human:` prefix as agent.
- **Acceptance criteria:**
  - `--actor human:fake` (unregistered) can **no longer** produce `waived` or
    `human_attested`/`waiver` authority.
  - A bare/no-prefix actor cannot record `waived` or `manual` evidence.
  - New tests cover: bare actor, spoofed `human:` prefix, and the legitimate
    human path still works.
  - If the `actors` table stays unused after the fix, either wire it in or file
    D-followup to drop it (don't leave dead schema).

### D2 — Approved requirement versions are DELETE-able (immutability hole + ID-reuse risk)
- **Severity:** P2 · **Type:** integrity · **Group:** STORE
- **Files:** `src/charter/store.py:76-84` (UPDATE-only trigger),
  `src/charter/service.py:1456-1471` (`count(*)+1` ID allocation)
- **Evidence:** `requirement_versions` has a `before update` trigger guarding
  title/statement/hash, but **no `before delete` trigger**. `DELETE FROM
  requirement_versions WHERE version=1` succeeds at runtime. Sibling immutable
  tables all guard delete (`events` `store.py:223`, `verification_evidence`
  `store.py:198`, `baseline_members` `store.py:159`) — this one is the
  exception. Because requirement/criterion IDs are minted with `count(*)+1`, a
  delete elsewhere would also enable **ID reuse**, violating ADR-002
  ("Requirement IDs are never reused").
- **Fix approach:**
  - Add `before delete` abort trigger on `requirement_versions` (mirror the
    evidence/baseline pattern); consider also guarding UPDATE of the remaining
    columns, not just title/statement/hash.
  - Replace `count(*)+1` minting with a monotonic source (`max(num)+1` or a
    counter in `schema_meta`) so uniqueness no longer depends on the no-delete
    invariant.
  - This is a schema change → bump `user_version`/migration per the store's
    migration mechanism; add a migration test.
- **Acceptance criteria:**
  - `DELETE FROM requirement_versions` raises (abort) at the DB layer.
  - A test proves ID allocation does not reuse a number after a (hypothetical)
    row removal, or proves removal is impossible.
  - `test_store_migrations.py` covers the new trigger like it does the others.

### D15 — Roadmap overstates "installed" for trace links and verification
- **Severity:** P2 · **Type:** documentation honesty · **Group:** DOCS
- **Files:** `docs/agentic-doors-replacement-roadmap.md` (gap table +
  "Installed On Main")
- **Evidence:** roadmap lists trace links and verification as plainly
  "Installed on main," but (a) trace staleness/orphaning is never computed and
  those states are unreachable through CLI/MCP (D3), and (b) the verification
  authority guarantee does not hold under an adversarial actor (D1).
- **Fix approach:** annotate both rows with the precise deferral/limitation
  ("trace freshness states modelled but not computed or operator-settable; see
  D3", "attestation authority is honour-system pending actor registry; see
  D1"). Do **not** silently downgrade — state what works and what doesn't.
- **Acceptance criteria:** roadmap no longer reads as if these guarantees are
  fully delivered; each caveat links to its tracking defect.

---

## P2 — Lifecycle / contract gaps

### D4 — No re-draft/amend path for an approved requirement (ADR-002 `draft_revision`)
- **Severity:** P2 · **Type:** feature gap / ADR compliance · **Group:** SERVICE
- **Files:** `src/charter/service.py:399` (`base_version` always `None`),
  `service.py:428-429` (`update_draft` rejects when no active draft),
  ADR-002 state machine `docs/architecture/decisions/ADR-002-*.md:70-75`,
  `src/charter/store.py:54` (`base_version` column exists, unused)
- **Evidence:** ADR-002 defines `approved → draft_revision → approved`. No
  service method opens a draft on an approved requirement; `supersede` (full
  inline restatement) is the only post-approval text-change route. The
  `base_version` column and `draft_revision` concept are plumbed but never
  exercised.
- **Fix approach:** add an `amend_requirement` (or `open_draft`) service verb +
  CLI that creates a new draft from the current approved version, stamping
  `base_version`; approving it supersedes correctly. Event-logged, idempotent,
  optimistic-locked, consistent with existing verbs.
- **Acceptance criteria:** can open a draft on an approved req, edit, approve →
  new version N+1 with `base_version=N`; prior version marked superseded;
  events recorded; tests + CLI contract fixture added.

### D5 — Evidence carry-forward absent (roadmap DoD vs spec divergence)
- **Severity:** P2 · **Type:** divergence to reconcile · **Group:** SERVICE
- **Files:** `src/charter/service.py` (no carry-forward anywhere; grep for
  `carry`/`carried` returns zero), roadmap "Verification Core" DoD vs
  `docs/superpowers/specs/2026-06-05-charter-verification-status-design.md`
- **Evidence:** roadmap DoD: *"superseding a requirement makes prior evidence
  stale unless explicitly carried forward."* The staleness half works; the
  carry-forward escape hatch has no column, method, flag, or test. The design
  spec deliberately omits it — so roadmap and spec disagree.
- **Fix approach (decision required, surface to maintainer):**
  - **Option A (reconcile down):** strike "unless explicitly carried forward"
    from the roadmap; confirm spec is authoritative. *(Cheapest; do this if
    carry-forward isn't actually wanted yet.)*
  - **Option B (build it):** add a `verify evidence carry-forward
    METHOD_ID/REQ_ID --actor` verb that re-stamps prior passing evidence to the
    new version with provenance preserved (and authority rules from D1
    enforced). Tests + fixture.
- **Acceptance criteria:** roadmap and spec agree; if built, a superseded req
  with carried-forward evidence reports `satisfied`, not `stale`, and the
  carry-forward is auditable in events.

### D13 — MCP read-only is by-construction, not structurally enforced
- **Severity:** P2 · **Type:** hardening · **Group:** MCP
- **Files:** `src/charter/mcp_surface.py:319-329` (`_service()` returns a full
  read/write `CharterService`), `src/charter/store.py:12-19` (`connect()` opens
  a writable connection — no `mode=ro`/`query_only`)
- **Evidence:** no mutation is reachable through the *current* handler set, and
  a snapshot test guards it — but the guarantee is "handlers happen not to call
  mutators," not "mutation is impossible." A future handler edit could mutate
  and only break if the snapshot test's call list is extended.
- **Fix approach:** give the surface a read-only path — either a read-only
  `CharterService` view exposing only `_dossier_dict`/`_record_dict`/etc., or a
  `query_only=ON` / `mode=ro` connection for MCP reads. Keep the snapshot test
  as belt-and-braces.
- **Acceptance criteria:** a deliberately-added mutation call inside an MCP
  handler fails (raises) at runtime, not just in a snapshot diff; existing read
  tests still pass.

---

## P3 — Test coverage of existing guarantees

### D6 — Trace state-transition guard is untested
- **Severity:** P3 · **Type:** test gap · **Group:** TESTS
- **Files:** guard at `src/charter/service.py:1797-1805`; tests
  `tests/state/test_trace_links.py`
- **Evidence:** `_validate_trace_transition` allow-map looks correct
  (double-accept and reject-terminality both raise `CONFLICT`) but **no test
  exercises any illegal transition**. Only relation validation is covered.
- **Fix approach:** add tests for double-accept, reject-then-accept,
  accept-after-reject, and each terminal/illegal edge in the allow-map.
- **Acceptance criteria:** every disallowed edge in the map has a test asserting
  `CONFLICT`; at least one allowed edge per source state is asserted to succeed.

### D7 — Append-only triggers not directly tested
- **Severity:** P3 · **Type:** test gap · **Group:** TESTS
- **Files:** triggers `src/charter/store.py:191-203` (evidence),
  `store.py:216-228` (events); tests `tests/test_store_migrations.py`
- **Evidence:** the UPDATE/DELETE-abort triggers on `verification_evidence` and
  `events` fire at runtime (audit confirmed manually) but no test asserts it —
  unlike baselines, which are covered.
- **Fix approach:** add migration/store tests asserting UPDATE and DELETE on
  both tables raise `IntegrityError`, mirroring `test_store_migrations.py:187-312`.
- **Acceptance criteria:** four assertions (UPDATE+DELETE × evidence+events) all
  raising.

---

## P3 — Code smells / cleanup

### D8 — Dead branch in MCP `_result`
- **Severity:** P3 · **Type:** code smell · **Group:** MCP
- **Files:** `src/charter/mcp_surface.py:310-317`
- **Evidence:** `if list_result: return success_envelope(...)` / `else: return
  success_envelope(...)` — both arms identical; `list_result` is threaded
  through but does nothing.
- **Fix:** collapse to one return; drop the unused `list_result` plumbing.
- **Acceptance criteria:** branch removed, all MCP tests still pass.

### D9 — List tools bypass `list_envelope` helper
- **Severity:** P3 · **Type:** maintainability · **Group:** MCP
- **Files:** `src/charter/mcp_surface.py:347-351` build `{items,has_more,
  next_offset}` by hand instead of using `envelopes.py:81-97 list_envelope`
- **Evidence:** output shape is correct, but pagination structure is duplicated
  rather than sourced from the helper. Coordinate with D8 (same file).
- **Fix:** route list tools through `list_envelope`.
- **Acceptance criteria:** single source of truth for list shape; contract
  fixtures unchanged.

### D11 — `update_draft` bumps revision on no-op edits
- **Severity:** P3 · **Type:** code smell · **Group:** SERVICE
- **Files:** `src/charter/service.py:433`
- **Evidence:** calling `update_draft` with no changed fields still increments
  `draft_revision` and writes an event (fields default to existing values).
- **Fix:** short-circuit when nothing changed (no revision bump, no event), or
  document the bump as intentional. Surface choice to maintainer.
- **Acceptance criteria:** no-op update either is a no-op (preferred) or is
  explicitly documented + tested as intentional.

### D12 — Dead `freshness` column on evidence
- **Severity:** P3 · **Type:** schema cleanup · **Group:** STORE
- **Files:** `src/charter/service.py:1573-1574,1615-1616` (freshness synthesized
  on read), persisted `freshness` column always `"current"`
- **Evidence:** staleness is computed at read time from
  `requirement_version != current_version`; the stored `freshness` column is
  never updated and is effectively dead data.
- **Fix:** drop the persisted column (migration) **or** document it as
  reserved. Coordinate with D2 (same file, same migration mechanism — consider
  doing both store changes in one migration).
- **Acceptance criteria:** no dead persisted state, or an explicit comment +
  test pinning it as reserved.

---

## Deferred features (design before code — not "burn-down" defects)

### D3 — Trace staleness/orphaning is never computed and is unreachable via CLI/MCP
- **Severity:** P1 (product value) but **deferred by plan** · **Type:** feature
  · **Group:** FEATURE
- **Files:** `src/charter/service.py:528-620` (`supersede` doesn't touch
  `trace_links`), `mark_trace_stale`/`mark_trace_orphaned` (`service.py:891-895`)
  have no CLI/MCP exposure
- **Evidence:** an `accepted` link to a now-superseded requirement stays
  `accepted`/`current`; `stale`/`orphaned` are reachable only from the
  in-process API. The plan **explicitly defers** computed freshness, so this is
  documented, not hidden — but it is the trace subsystem's core value per
  ADR-003. Pair with D15 (document) as the cheap interim step.
- **Why not a simple burn-down:** needs a design decision (when does supersede
  cascade to links? auto-stale vs operator-confirmed? expose setters on CLI/MCP
  or compute purely?). Run a scoped design pass before implementation.

### D14 — Baseline diff `changed` status is structurally unreachable
- **Severity:** P3 · **Type:** defensive-code decision · **Group:** FEATURE
- **Files:** `src/charter/service.py:304-306`
- **Evidence:** `changed` fires only when same version + different
  statement_hash, which immutability makes impossible; real changes surface as
  `superseded_since_baseline`. Harmless defensive branch, untested.
- **Fix (decision):** either keep as a corruption-detector and add a test that
  forces the condition, or remove it. Surface to maintainer.
- **Acceptance criteria:** branch is tested or removed; diff summary semantics
  documented.

---

## Summary counts

| Severity | Count | IDs |
|---|---|---|
| P1 | 1 | D1 |
| P2 | 5 | D2, D4, D5, D13, D15 |
| P3 | 7 | D6, D7, D8, D9, D11, D12, D14 |
| Deferred feature | 1 | D3 |
| **Total** | **14** | |
