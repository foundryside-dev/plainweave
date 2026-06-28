# 05 — Code Quality Assessment

**Subject:** Plainweave · **Live tree:** HEAD `8258f76` · **Date:** 2026-06-28
A severity-rated technical-debt register with `file:line` evidence and a
remediation per item. Findings are reconciled across all 5 explorers + the
validation gate (all structural claims VERIFIED against live source).

**Severity is rated against the product's stated scope** — single-operator,
local-first, advisory/enrich-only. An item marked Medium that says "fine at
single-operator scale" would be High for a multi-tenant server; the rating
reflects *Plainweave's* intended deployment, and each item names the scenario
that escalates it.

| Severity | Count | Meaning |
|----------|-------|---------|
| High | 4 | Should be addressed before scale or before relying on a stated contract |
| Medium | 8 | Real debt; bounded today, escalates under concurrency/growth |
| Low | 11 | Hygiene / clarity / dead code / test discipline |

---

## Hotspot map (files by risk concentration)

| File | LOC | Risk | Why |
|------|-----|------|-----|
| `service.py` | 3027 | **High** | God object: use-case + data-access + intent engine; N+1; unguarded SQL |
| `mcp_surface.py` | 1653 | **High** | Preflight O(corpus) fan-out, no pagination; CLI coupling; unguarded tool |
| `store.py` | 311 | **Medium** | Connect-per-call, no WAL, no explicit busy_timeout, non-version-aware migrate |
| `cli_commands.py` | 1631 | **Medium** | De-facto shared DTO layer (surface↔surface coupling); exit-code divergence |
| `web/` | ~900 | **Medium** | No authN/authZ + `--host` exposure; a11y ungated in CI; per-render N+1 |
| `loomweave_adapter.py` | 657 | **Low** | Multi-connection per read; conditional local-only |
| `envelopes.py` | 115 | **Low** | Non-deterministic `generated_at`; hard-coded error schema version |

---

## Correctness

**Q1 · DB exceptions escape the `ErrorCode` contract · High**
Only domain failures route through `_error`→`PlainweaveError` (`service.py:3020`).
Raw `connection.execute(...)` is never wrapped, so `sqlite3.IntegrityError`/
`OperationalError` propagate past callers that switch on `ErrorCode` — both
surface result paths (`_result`, `_handle_output`) catch `except PlainweaveError`
only (validated end-to-end). A caller relying on the documented closed vocab
cannot catch a DB failure.
→ **Fix:** wrap store operations in a boundary that maps `sqlite3.Error`
subclasses to `PlainweaveError` — UNIQUE/PK constraint violations → `CONFLICT`,
other `IntegrityError` (FK/NOT NULL/CHECK) → `VALIDATION`, else `INTERNAL` — or
add a generic-exception arm to the two result adapters. Low effort, closes a
stated contract.

**Q2 · `count(*) + 1` id generation is racy · Medium**
`_next_requirement_number:2110`, `_next_link_number:2137`, `_next_evidence_number:2149`
derive ids from a live `count(*)`. Fails *safe* (every id feeds a UNIQUE/PK
column, `store.py:40-41`), so a concurrent second writer collides on a constraint
rather than duplicating — but it surfaces as a raw `IntegrityError` (see Q1), not
a clean `CONFLICT`. Escalates the moment two agents/processes write concurrently.
→ **Fix:** `BEGIN IMMEDIATE` serializes writers so the second transaction sees
the committed count and *prevents* the race outright (an alternative to mapping
the collision to `CONFLICT` per Q1, not a pairing), or use a monotonic sequence
table; pairs with Q3.

## Performance / scalability

**Q3 · Connect-per-call + no WAL = contention ceiling · High**
`store.connect:11-19` opens a fresh connection per op (fan-in 44, no pool) and
never sets `journal_mode`, so the DB runs in default `DELETE` mode where a writer
takes an exclusive lock blocking all readers. With three concurrent surfaces
(MCP/web/CLI) this is the hard concurrency ceiling. It also relies on the
*implicit* stdlib `busy_timeout` default (5000ms from `sqlite3.connect(timeout=5.0)`)
— `connect` sets no pragma and exposes no timeout param.
→ **Fix:** enable WAL (`pragma journal_mode=WAL`) + set `busy_timeout` explicitly
in `connect`; introduce a request-scoped/unit-of-work connection so a logical
operation reuses one connection. (Tracker P3 `3edcd19943`.)

**Q4 · MCP preflight project-scope fan-out, no pagination · High**
A bare `plainweave_preflight_facts_get()` (default `scope_kind="pending_diff"`,
no ids) can't resolve the diff locally → falls back to the *entire* corpus via
`search_requirements()` (`mcp_surface.py:990`), then runs **3 service calls per
requirement** (`requirement_preflight_profile`/`verification_status`/
`requirement_dossier`, `:1084-1086`, the dossier itself composite). O(corpus),
**no `limit`/`offset` exposed** on the tool. `scope_kind="project"` same path.
→ **Fix:** expose `limit`/`offset`; batch the per-requirement queries into
set-based reads; cap/paginate the default scope. (Tracker P3 `706d80dc8e`.)

**Q5 · N+1 connections in `intent_coverage` · Medium**
`service.py:1467` loops catalog entities → `:1479 _goal_nodes_for_surface` →
`:1529-1550` opens its own `with connect(...)` **per entity**. (Sibling helpers
correctly take an existing connection — this one regressed.)
→ **Fix:** thread the open connection into `_goal_nodes_for_surface`. Small,
local, high payoff. (No dedicated tracker task — a distinct N+1 site from the
preflight one in `3edcd19943`; closed by Initiative A.)

**Q6 · Web review queue O(requirements) per render · Medium**
`pending_items` does `search_requirements()` then a `requirement_dossier()` per
draft (`views.py:82-100`); `_pending_count` recomputes the whole queue after
every mutation (`review.py:41-42,116,198,215`); `_resolve_titles` fetches a
dossier per draft-only requirement.
→ **Fix:** batch the per-draft fetches; cache/derive the pending count.

**Q7 · Adapter multi-connection per read · Low**
`LoomweaveAdapter.list_catalog` opens one connection in `_schema_state()` then a
second for the page query (same in `_resolve_identity_sqlite`).
→ **Fix:** reuse one connection per adapter call.

**Q8 · Post-materialization pagination in MCP `_list` · Low**
`_list:841` builds the full result then slices `items[offset:offset+limit]` —
bounds the payload, not the underlying work.
→ **Fix:** push limit/offset into the service query.

## Maintainability / structure

**Q9 · God object: `PlainweaveService` (3027 LOC) · High**
One class spans ~13 aggregates and is use-case + data-access (raw inline SQL, no
repository) + intent-graph engine. The product's defining capability lives at
`service.py:1311-1507`, not in the `intent_graph` module that names it.
→ **Fix (staged, behaviour-preserving):** (1) extract a thin repository/data-
access layer (centralizes `connect` — also the seam for Q1/Q3); (2) move
coverage/orphans/trace computation into `intent_graph`; (3) split aggregates
(requirements, traces, baselines, verification) into per-aggregate service
modules sharing the helper cluster. Sequenced in `06-architect-handover.md`.

**Q10 · Surface↔surface coupling (`cli_commands` as shared DTO layer) · Medium**
The MCP surface imports CLI-owned private serializers (`mcp_surface.py:9`) +
`inspect_project` (`:395-413,825-829`); the CLI handler lazily imports
`PlainweaveMcpSurface` (`cli_commands.py:1103,1114`). No module-load cycle (the
function-local import dodges it), but the DTO layer is misplaced.
→ **Fix:** extract the shared `_*_dict` serializers + `inspect_project`/
`_current_project_key` into a neutral `serialization.py`/read-helpers module both
surfaces depend on; removes the function-local-import workaround.

**Q11 · Migration is not version-aware · Medium**
`migrate:22-306` stamps `SCHEMA_VERSION=2` but never branches on it — it re-runs
`create … if not exists` + one guarded `ALTER`; no per-version upgrade steps, no
down-migrations.
→ **Fix:** introduce a migration ladder keyed on `schema_meta.schema_version`
before the next breaking schema change (the `read_schema_meta`/SCHEMA_MISMATCH
plumbing already exists to detect drift).

**Q12 · Intent-graph contract/impl split · Low**
A reader expecting coverage logic in `intent_graph.py` finds only types; the
algorithms are 1100+ lines away in `service.py`. (Resolved by Q9 step 2.)

## Reliability / security

**Q13 · Web: no authN/authZ + settable `--host` · Medium**
Identity is a launch-time process singleton (`context.py:26-51`); CSRF is the
only request-level control. `--host 0.0.0.0` (`server.py:15`) exposes all 7
write endpoints with zero auth and no compensating gate. By design for
local-first, but the flag is unguarded.
→ **Fix:** refuse a non-loopback bind unless an explicit `--insecure`/token is
supplied; or add a shared-secret on unsafe methods. At minimum, document the
exposure on the flag's help text.

**Q14 · Review-queue accessibility ungated in CI · Medium**
Only *structural* a11y contracts are automated (`tests/web/test_a11y_contracts.py`);
the focus-move + live-region announcement behaviour the README emphasizes
(README:188-192) is manual NVDA/VoiceOver only.
→ **Fix:** add a headless driver assertion (the repo already has a web Playwright
harness) for focus target + `#sr-status` text after approve/accept/reject — turns
a documented manual gate into a CI gate.

**Q15 · CSRF middleware assumes urlencoded bodies · Low**
`app.py:49-50` re-parses the raw body with `parse_qsl`; a multipart form yields
no `_csrf` field → 403. Works because all forms are urlencoded; implicit coupling.
→ **Fix:** branch on `Content-Type`, or assert the constraint in a test + comment.

**Q16 · Unguarded `project_context_get` MCP tool · Low**
Two of the three non-`_result` tools wrap work in `try/except PlainweaveError`;
`project_context_get:395-413` does not, so an error from `inspect_project`/adapter
capability escapes the envelope contract.
→ **Fix:** wrap it like its siblings (relates to Q1).

## Determinism / contract hygiene

**Q17 · Non-deterministic `meta.generated_at` · Medium**
`envelopes.py:12-13` defaults `generated_at` to `datetime.now(UTC)`; preflight
stamps it too (`mcp_surface.py:658`). Defeats byte-stable golden comparison /
response caching unless the caller injects a value.
→ **Fix:** thread an injectable clock/`generated_at` through the envelope
boundary (goldens already inject; make it a first-class parameter).

**Q18 · Error-schema version hard-coded; no registry · Low**
Success schemas are caller-supplied per-payload; the error schema is hard-coded
`error.v1` in one place (`envelopes.py:67`) with no constant/registry tying error
and success versions together.
→ **Fix:** a `SCHEMA_VERSIONS` constant/registry.

## Dead / vestigial code

**Q19 · `IntentGraphReads` facade dead in production · Low** — advertised as
injectable for adapters but only tests construct it (`intent_graph.py:141`).
→ **Fix:** wire into the read path or mark test-scaffolding.

**Q20 · `experimental/` package is empty · Low** — only stale `__pycache__` for a
`plan_check` module; `grep -rn experimental src tests` is empty (confirmed).
→ **Fix:** delete the directory.

**Q21 · Duplicate command `status requirement` == `verify status` · Low**
(`cli_commands.py:1051-1052` delegates). Two names, one behaviour.
→ **Fix:** alias explicitly or remove one.

**Q22 · Vestigial no-op `list_result` param in `_result` · Low** — both branches
return the identical envelope (`mcp_surface.py:724-731`); threaded through ~7 call
sites.
→ **Fix:** remove the parameter.

## Test & comment hygiene

**Q23 · Misleading `ResourceWarning` suppression comment + test fixtures that
leak connections · Low**
`pyproject.toml:89-93` suppresses `ResourceWarning: unclosed database`,
attributing it to "pre-existing **store-layer** connections… track the
underlying leak separately." That attribution is inaccurate: **both production
connection sites close deterministically in `finally`** — `store.connect`
(`store.py:11-19`) and `LoomweaveAdapter._connect` (`loomweave_adapter.py:596-605`,
whose own comment says "closed deterministically rather than left to GC"). The
warning under `--cov` actually originates from **test fixtures** using
`with sqlite3.connect(...) as conn` (e.g. `tests/loomweave_test_utils.py:10,90`),
which commits the transaction but does **not** close the connection (a stdlib
`sqlite3` gotcha), leaving it to GC. So this is test hygiene + a misleading
comment, **not** a production leak — and it is **not** fixed by Initiative A.
→ **Fix:** close test connections explicitly (`contextlib.closing` or an explicit
`.close()`), then narrow/remove the blanket suppression; correct the comment's
"store-layer" attribution. *(Note: this corrects a corroboration earlier drafts
attached to Q3 — the connect-per-call concern stands on connection **count** and
journal mode, not on this warning.)*

---

## Metrics snapshot

- **Tests:** 361 functions; `tests/{state(7), contracts(8), conformance(1),
  web(12)}` + 22 top-level; 62 fixtures. Branch coverage gated at
  `fail_under = 90` (`pyproject.toml`).
- **Contract tests:** golden-vector wire tests for every seam (envelopes,
  preflight, wardline/warpline peer facts, CLI contract outputs) + an SEI
  conformance drift oracle (`-m sei_drift`). Strong.
- **Suppressed `ResourceWarning: unclosed database`** (`pyproject.toml:89-93`) —
  a test-fixture leak with a misleading "store-layer" comment, **not** a
  production leak (production closes deterministically). See **Q23**; do not read
  it as evidence of a `store.py` defect.
- **Static gates:** ruff (`E,F,I,UP,B,SIM`, line 120) + `mypy --strict` over
  `src` + `tests`. Clean module graph (no import cycles).
