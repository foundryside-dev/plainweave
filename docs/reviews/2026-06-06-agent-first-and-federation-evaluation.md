# Plainweave as an Agent-First Tool — Evaluation & Federation Readiness

Date: 2026-06-06 · Basis: `main` @ `cf0bf8a` (agentic MCP read surface shipped).
Method: read of the agentic-interface design spec, the first-principles read-surface
review, the five ADRs, `concept.md`, the roadmap, the shipped `service.py` /
`mcp_surface.py` / `cli_commands.py` / `store.py` / `errors.py` / `envelopes.py`,
and cross-repo reading of the `~/weft` hub + Filigree / Loomweave(Weftweave) /
Wardline / Legis.

---

## Verdict

**Plainweave's agent-first *design* is genuinely strong; its agent-first *mechanics*
and *federation wiring* are pre-alpha.** The hard conceptual work is done and done
well: a typed authority/freshness model that never collapses proposed/inferred/
stale/accepted facts, a dossier-as-single-context-object, a declared read-only
authority boundary, uniform JSON envelopes, and "switch on `error.code`, not message
text." What's missing is the operational plumbing that lets an agent run Plainweave *in
a loop without corrupting it or getting stuck* — recoverable errors, idempotent
write verbs, safe concurrency — and the federation adapters that make Plainweave a
first-class citizen of the suite. Most of the latter is correctly deferred by the
roadmap; the former are **latent defects in the surface that already shipped**, and
they are the high-value findings here.

### Prioritized shortlist (highest agent-impact first)

| # | Finding | Class | Severity |
|---|---|---|---|
| 1 | Errors carry no recovery payload — hardcoded hint, empty `details`, no `INVALID_TRANSITION` code, no current-version on `CONFLICT`, no transitions verb | Latent (shipped) | **P1** |
| 2 | Idempotency holes on the loop verbs (`record_verification_evidence`, `add_verification_method`, `propose_trace_link`, `create_baseline`, `reject_requirement`) | Latent (shipped) | **P1** |
| 3 | `connect()` sets no `busy_timeout` and no WAL → immediate `database is locked` under any read/write overlap | Latent (shipped) | **P1/P2** (posture-dependent) |
| 4 | Discoverability asymmetry — MCP self-describes (capabilities + contracts); the CLI has no machine-readable catalogue; contract resources are prose, not JSON Schema | Latent (shipped) | **P2** |
| 5 | Loop doesn't close — `computed_gaps` are ephemeral, `next_actions` often lack a runnable `command`, no project-wide work queue, no gap→Filigree-issue bridge | Latent + design | **P2** |
| 6 | `weft.*` → `weft.*` naming drift (54 schema sites + `~/weft` pointers) vs. the canonical `~/weft` hub | Federation hygiene | **P2** (time-boxed) |
| 7 | Federation adapters absent — SEI snapshot not stored on trace links; no Loomweave/Filigree/Wardline/Legis binding; `weft.plainweave.preflight_facts.v1` producer not built | Deferred-by-design | tracked, P1–P2 on roadmap |

---

## 1. What is already agent-first (credit where due)

These are real and verified — do not regress them:

- **Typed truth, never flattened.** Authority + freshness are first-class on every
  fact: drafts ≠ approved, proposed traces ≠ accepted, stale evidence stays visible
  but is not current satisfaction (`spec:175-177`; reason-coded verification status
  `service.py` `verification_status`). This is the single most important agent-safety
  property — it stops an agent from mistaking its own guess for accepted truth.
- **The dossier is the right primitive.** One call returns identity, authority
  summary, record/version/draft, criteria (current vs draft), trace summaries,
  verification status + current/stale evidence, baseline exposure, computed gaps,
  peer facts, and next actions (`requirement_dossier.v1`). "Fetch one dense dossier
  before acting" is exactly the orientation an agent wants.
- **Declared authority boundary.** `plainweave_project_context_get` returns
  `authority_boundary {mutations:false, live_peer_calls:false, release_verdicts:false}`
  and per-capability `mutates/local_only/peer_side_effects` (`mcp_surface.py:154-169`).
  The agent can know what Plainweave will and won't do before calling.
- **Uniform envelopes + code-based errors.** Every command → `{schema, ok,
  data|error, warnings, meta}`; errors are a versioned enum the agent branches on,
  not prose (`envelopes.py`, `errors.py`). Pagination is explicit
  (`items/has_more/next_offset`), never implying an unpaginated list is exhaustive.

## 2. Latent agent-hostile gaps in the shipped surface (the crown jewels)

These are **not** on the roadmap as known omissions — they are defects in what
already ships, and they are what most degrade my (the agent's) ability to use Plainweave.

### 2.1 Errors don't tell the agent the next action — P1
The service error factory hardcodes the affordance away:
`_error(code, message)` always sets `recoverable=True`, a static
`hint="Refresh local Plainweave state and retry."`, and **no `details`**
(`service.py:_error`). So:
- A `CONFLICT` from an optimistic-lock miss does **not** carry the actual current
  version the agent should have passed — it must issue a fresh read and re-derive.
- There is **no `INVALID_TRANSITION` code** and **no transitions-list verb**; an
  illegal lifecycle/trace transition surfaces as a generic `CONFLICT`/`POLICY_REQUIRED`
  with no "from→to allowed" set.
- Richer errors exist only where hand-built in the MCP validators
  (`details.allowed`, specific hint — `mcp_surface.py:355-379`); these are the
  exception.

Plainweave is materially behind its sibling Filigree here, which ships an
`INVALID_TRANSITION` code that names the next status plus a
`workflow_transition_list` recovery verb. **Recommendation:** make `_error` accept
`details` and a per-call hint; on `CONFLICT` include `current_version`; add an
`INVALID_TRANSITION` code carrying `{from, to, allowed:[...]}`; add a
`transitions`/`valid_next` read verb. This is the difference between an agent that
self-corrects and one that flails.

### 2.2 The loop verbs aren't idempotent — P1
Optimistic locking + idempotency keys exist on the terminal-version transitions
(`approve` / `supersede` / `deprecate`) but **not** on the high-frequency verbs an
agent pipeline actually hammers (verified by signature):
- `record_verification_evidence` — no key (a retry after an ambiguous failure writes
  a **duplicate evidence row**).
- `add_verification_method`, `propose_trace_link`, `create_baseline`,
  `reject_requirement` — no key.

The verbs most likely to be called in a retry loop are exactly the ones with no
replay protection. For an audit-of-record tool, duplicate evidence/links are
corruption, not noise. **Recommendation:** extend the existing `idempotency_keys`
replay machinery (already used by approve/supersede/deprecate) to these verbs.

### 2.3 Storage concurrency posture is unsafe-by-default — P1/P2
`connect()` runs `sqlite3.connect` + `pragma foreign_keys=on` and nothing else
(`store.py:11-19`) — **no `busy_timeout`, no WAL/`journal_mode`, no `synchronous`
tuning.** SQLite's default `busy_timeout` is `0`, so a writer that overlaps another
writer *or a long-running MCP read* fails immediately with `database is locked`
rather than waiting. For a tool whose pitch is "agents maintain this during ordinary
development," that is concrete and agent-hostile.
- If Plainweave is **single-writer-per-repo by design**, say so explicitly in an ADR —
  and still add `busy_timeout` (read/write overlap happens even with one writer once
  MCP reads run concurrently with a CLI write).
- If concurrent agents are in scope, this is a real defect: add `busy_timeout`
  (e.g. 5s), `journal_mode=WAL`, `synchronous=NORMAL`.
There is an `axiom-embedded-database` discipline in this environment that closes
exactly this; an audit pass against it is cheap insurance.

### 2.4 Discoverability is MCP-only and sub-schema — P2
An MCP agent can self-describe (capabilities via `project_context_get`, six contract
resources). A **CLI-only agent cannot**: `doctor` returns only
`{initialized, project_key, schema_version, db_path}`; there is no `plainweave
capabilities`, no `plainweave contracts`, no machine-readable command/output catalogue
(`cli_commands.py`). And the contract resources themselves are "compact contract
summaries, not full JSON Schema documents" (first-principles review) — an agent
cannot machine-validate output against a published schema. **Recommendation:** a
CLI `capabilities`/`contracts` verb that emits the same metadata MCP exposes, and a
schema-publication slice (real JSON Schema per `weft.plainweave.*.v1`).

### 2.5 The loop doesn't close — P2
The dossier surfaces gaps and next actions, but the agent can't act on them within
the same surface:
- `computed_gaps` are **ephemeral** (computed per dossier read) — there is no
  durable, ownable gap record an agent can track or hand to a human.
- Many `next_actions` carry `command=None` (criteria, evidence, stale, waiver) — a
  reason but nothing runnable.
- There is **no project-wide work queue** — no Filigree-style `work_ready` /
  `session_context` analogue. `status unverified` / `status stale` are flat,
  unprioritised lists.
**Recommendation:** durable gap lifecycle (gap → acknowledged → resolved), every
`next_action` carries an executable `command`, a `plainweave work next` /
`session_context` surface, and a bridge that promotes a Plainweave gap into a Filigree
issue (binding by opaque issue id — see §4).

### 2.6 No dry-run, no live batch — P2
No mutator previews its effect or the resulting version before committing (no
`dry_run`/`--check` anywhere). `batch_envelope` exists but is dead code — every
mutation is single-target, so bulk evidence/approve is N calls with N conflict
windows. Agents plan; let them preview and batch. (The roadmap's future MCP mutation
surface already lists dry-run + idempotency as requirements — bring those forward to
the CLI too.)

## 3. Deferred-by-design (acknowledged — not re-litigated)

These are correctly P0-excluded / roadmapped; flagging only to confirm scope:
- **MCP mutation surface** (writes are CLI-only today, deliberately excluded from the
  P0 read slice; P1 on the roadmap with proposed-by-default + actor + idempotency +
  dry-run + policy metadata). *Value-add note:* this is the surface that resolves the
  read-then-can't-act friction in §2.5/§2.6 — when it lands, verify it closes that
  loop, and unify it with the CLI write semantics rather than forking a second model.
- **Durable gap lifecycle, impact analysis, review/approval queues, import/export** —
  all P1+. Note: the roadmap itself calls impact analysis ("what requirements are
  impacted by this change?") *the main product value*, yet it is deferred and absent
  from the shipped agent surface — worth a conscious priority check, since it is the
  question `concept.md` opens with.

## 4. Federation wiring (Filigree, Wardline, Loomweave/Weftweave, Legis)

Per `~/weft/doctrine.md`, the suite has **no shared bus, no orchestrator, and no
neutral identity oracle**; binding is point-to-point against each peer's own surface,
keyed on **SEI** (opaque Stable Entity Identifier, LOCKED 2026-06-05) for code and on
opaque peer ids for issues/findings/attestations. Plainweave is the federation's
read-only **obligations** consumer. All four Plainweave adapters are currently
**unimplemented** (no peer source files under `src/plainweave/`) — this is expected at
pre-alpha, but here is what "first-class" requires:

### 4.1 Naming drift — reconcile while pre-alpha (P2, sequencing decision)
Verified: the hub is `~/weft` (`~/weft` does not exist); the canonical Plainweave
contract is `weft.plainweave.preflight_facts.v1` (`~/weft/contracts-index.md`); yet
Plainweave ships **`weft.plainweave.*`** schema names (54 sites incl. every contract
fixture) and `concept.md`/ADR-001/005/006 point at `~/weft/*`. Renaming is a breaking
contract change, but Plainweave is pre-alpha with adapters pending — **now is the window,
before any external consumer locks onto `weft.plainweave.*`.** Maintainer owns the
sequencing (single rename commit + fixture regen + ADR pointer sweep). Don't ship the
Legis adapter under the old namespace.

### 4.2 SEI plumbing on trace links — the core integration unit
Plainweave's `trace_links` store a generic opaque `(to_kind, to_id)` with no SEI
snapshot. ADR-005 specifies storing a Loomweave code target as an **opaque SEI plus a
snapshot tuple**: locator, content hash, lineage status, Loomweave version, observed-at.
Adopt the suite's **two-axis freshness**: identity (ALIVE/ORPHANED, owned by
Loomweave's `resolve_sei`) and content (FRESH/STALE, owned by Plainweave's stored
content-hash compared at read time — exactly Filigree's `content_hash_at_attach`
pattern). Concretely: add the snapshot columns, resolve file/symbol inputs through
Loomweave at propose-time, mark links stale/orphaned on refresh, and degrade to fragile
file/symbol refs when Loomweave is absent (never destructively mutate on `PEER_ABSENT`).
**Consumers MUST NOT parse the SEI.**

> **Escalate, don't guess — SEI prefix conflict.** The LOCKED standard
> (`~/weft/sei-standard.md`) and Filigree ADR-017 use `loomweave:eid:`; Loomweave's
> *shipping* code mints `weftweave:eid:` (`loomweave/.../sei.rs`), and `concept.md:393`
> shows a third stale form (`sei:01HX…`). A fail-closed "is-this-already-an-SEI" guard
> that hard-codes the wrong reserved prefix mishandles backfilled values. Plainweave must
> key on whatever the authority *emits at integration time*; surface this cross-suite
> conflict to `~/weft` rather than picking a prefix.

### 4.3 The one outbound producer — `weft.plainweave.preflight_facts.v1` → Legis
Plainweave's only thing it *produces* to a peer (ADR-006): a facts envelope (kinds:
`requirement_touched`, `requirement_verification_stale/_missing`, `baseline_drift`,
`trace_gap`, `open_linked_work`, `active_finding_linked`, …). Plainweave may classify a
fact as `block_candidate` but **Legis alone decides** the commit boundary. This is the
highest-leverage adapter for the "agent about to commit" loop and should lead the
federation build.

### 4.4 Inbound binds — Filigree / Wardline / Legis
Point-to-point, opaque ids, no shared registry: requirement↔issue (Filigree —
mirror its `entity_associations` consumer pattern), finding↔requirement (Wardline —
an active finding can mark a requirement unsatisfied in the dossier),
attestation references (Legis — display in dossiers, never authoritative).

### 4.5 Actor / identity — align with ADR-012, do not invent a competing model
The suite has **no shared actor registry and doctrine forbids one**; actor identity is
an *unauthenticated claim*, with the **transport as the trust boundary** (Filigree
ADR-012). Filigree's `verified_actor` = resolved OS user, recorded-and-warned,
stdio/CLI only, never carried on the federation wire.

This directly informs the D1 work just landed (see §5): **Plainweave's actor registry is
a Plainweave-*local*, project-scoped (by DB file) attestation-authority construct — it
does NOT constitute a shared identity oracle and so does not violate the doctrine.**
The right reconciliation is to align Plainweave's actor semantics with ADR-012
(actor-as-claim + optional transport-verified actor), not to grow a parallel identity
system.

## 5. Through-line to the D1 fix (just landed)

The D1 attestation-authority fix introduced a local `actors` registry with kinds
{human, agent, attester} and genesis-gating. Two connections to this evaluation:

1. **`verified_actor` is a better genesis anchor than "first-come."** The open D1
   follow-up `plainweave-59e4af3aaf` (seed the genesis attester at `init`) currently
   risks a first-come land-grab. ADR-012's `verified_actor` (resolved OS user, trusted
   because the transport/OS is the boundary) is the doctrine-aligned answer: the OS
   user who runs `plainweave init` is the natural, transport-verified genesis attester.
   *(Captured as a comment on `plainweave-59e4af3aaf`.)*
2. **Plainweave-local, not federated.** State plainly in any federation work that the
   actor registry is project-scoped and is not a shared registry — pre-empting the
   careless reading that it competes with the suite's no-oracle doctrine.

---

## 6. Value-adds beyond linkage — what the federation *creates*

The §4 adapters are framed as plumbing ("Plainweave binds to peer X"). The real
justification for building them is the *emergent* capability that no single tool can
produce. Unifying frame: **Plainweave owns the obligation; Weftweave owns the code
structure the obligation is about; Wardline owns automated evidence about whether a
trust/safety obligation holds; Filigree owns the work; Legis owns the gate.** Every
integration below is a new *channel* into Plainweave's obligation model — and the
highest-value items are cross-channel contradiction detection.

> Naming: **Loomweave is now Weftweave** (confirmed by maintainer 2026-06-06). The code
> identity authority is referred to as Weftweave below; reinforces §4.1.

### 6.1 Weftweave (code identity / graph) — turns traceability from a liability into an asset
- **Impact analysis — the deferred headline product value (`concept.md:8`).** A diff →
  Weftweave resolves changed entities to SEIs and their graph neighbourhood →
  reverse-lookup the trace links targeting those SEIs → **the exact set of
  requirements impacted by a change.** Plainweave literally cannot answer its own
  opening question without Weftweave's code graph. This is the single biggest
  value-add in the suite.
- **Refactor-resilient traceability.** Because links key on opaque SEI (identity-stable
  across renames, lineage-tracked by Weftweave), `validate_token`→`verify_token` does
  **not** orphan the requirement↔code link. Without SEI, every refactor silently rots
  traceability — this is the difference between traceability that survives real
  development and traceability that's stale in a week.
- **Change-scoped verification staleness (more precise than today's model).** Plainweave
  currently staleness-checks on *requirement version*. With Weftweave, it can stale on
  *code change*: changed SEIs → the verification methods/tests targeting them → mark
  that evidence stale because the code-under-test changed. Far fewer false "still
  satisfied" and false "now stale."
- **Orphan + untraced-surface detection (bidirectional).** Weftweave says an entity is
  ORPHANED → the requirement that claimed satisfaction-by-that-code reverts to
  at-risk/unverified. Conversely, Weftweave entities with no accepted requirement trace
  = "un-obligated surface" — candidates for *needs a requirement* or *dead code*. An
  agent deciding what's safe to touch wants this map.
- **Assisted trace proposals (keeps traceability cheap — the product's primary goal,
  `concept.md:27`).** When an agent edits in a requirement's Weftweave neighbourhood,
  Plainweave can *propose* (never accept) a trace link, so coverage grows during ordinary
  editing instead of being a separate chore.

### 6.2 Wardline (taint / trust-boundary analysis) — an automated verification channel
- **Security/safety requirements get machine evidence, not just human attestation.**
  Plainweave's verification methods are {test, analysis, inspection, manual}. Wardline is
  a first-class *automated analysis* producer: a safety requirement ("reject untrusted
  input at boundary X") is verified-or-refuted by Wardline's taint result on the entity
  that satisfies it. This converts subjective manual attestation of security properties
  into evidenced verification.
- **Counter-evidence with a distinct authority — ties directly to D1.** Most evidence
  proves *pass*; Wardline uniquely produces *fail* (an active finding is proof a
  boundary is violated). It feeds Plainweave's existing `failing`/`inconclusive` statuses
  with a new **`analysis`/`tool_attested` authority** — never `human_attested`, never
  `test_derived`. This *extends* the D1 anti-fabrication authority lattice rather than
  bypassing it: a tool can refute, but cannot mint human/waiver authority.
- **Finding accountability (both directions).** A SARIF finding floating loose is
  triage noise; bound to a requirement it becomes "violates obligation REQ-SEC-0003,"
  and its priority *derives* from that requirement's criticality. Inversely, a security
  requirement with **no Wardline coverage** = "asserted but nothing checks it" — a
  verification gap Plainweave can surface.
- **High-risk-waiver surfacing (composes with D1 waivers).** A human waiver (D1 path)
  over a requirement that has an *active* Wardline finding is exactly the case Legis/
  review must see. Plainweave can mark "waived-over-active-finding" as a distinct,
  audit-worthy state rather than a silent green.

### 6.3 Emergent (3+ tools) — the part worth building toward
- **The dossier as the federation join point (killer agent feature).** The dossier
  already reserves `peer_facts`. Filled: one read returns requirement + its code
  (Weftweave SEIs + freshness) + its findings (Wardline) + its work (Filigree) + its
  governance refs (Legis). "Everything I need before touching this surface" in one
  call. Plainweave is uniquely positioned to host it because it owns the obligation that
  ties the others together.
- **Enriched pre-commit preflight to Legis.** `weft.plainweave.preflight_facts.v1` becomes
  genuinely decisive when composed: "this commit touches REQ-AUTH entities (Weftweave)
  whose verification is stale (Plainweave) **and** that carry an active taint finding
  (Wardline) → `block_candidate`." No single tool produces that signal.
- **Composite release readiness.** Baseline diff (Plainweave) + entity lineage drift
  (Weftweave) + open findings on baselined code (Wardline) + linked open work
  (Filigree) = a real release-risk picture, aggregated by the tool that owns the
  obligations being released.
- **Contradiction detection — the highest-value governance capability.** Three-way
  consistency: requirement says X; Weftweave entity Y is traced to X; Wardline says Y
  violates a boundary; Filigree has open work on Y. When these *disagree* — requirement
  marked satisfied but finding active; code orphaned but requirement still "verified" —
  Plainweave computes a **contradiction**. Catching "we believe inconsistent things" is
  the most valuable output a governance system can produce, and it's only possible at
  the obligation layer.

**Honest caveat:** every item in §6 rides on the §4.2 SEI plumbing and the adapters.
This section is the *why* that justifies that work — the payoff narrative behind the
recommendation, not additional independent asks.

---

## Proposed issues (for approval — not auto-created)

| Proposed | Type / Pri | Finding |
|---|---|---|
| Recoverable errors: `details` + `current_version` on CONFLICT + `INVALID_TRANSITION` code + transitions verb | bug/task, P1 | §2.1 |
| Idempotency keys on `record_verification_evidence` / `add_verification_method` / `propose_trace_link` / `create_baseline` / `reject_requirement` | bug, P1 | §2.2 |
| SQLite concurrency posture: `busy_timeout` + WAL (or ADR declaring single-writer) — audit vs `axiom-embedded-database` | bug, P1/P2 | §2.3 |
| CLI capability/contract catalogue + JSON-Schema publication for `*.v1` | feature, P2 | §2.4 |
| Close the loop: durable gaps + runnable `command` on every next_action + `session_context`/`work next` + gap→Filigree bridge | feature, P2 | §2.5 |
| Dry-run/preview + wire up live batch surface | feature, P2/P3 | §2.6 |
| `weft.*`→`weft.*` namespace + `~/weft`→`~/weft` pointer reconciliation (pre-alpha window) | task, P2 | §4.1 |
| Trace-link SEI snapshot tuple + two-axis freshness (Loomweave consumer adapter) | feature, P1 | §4.2 |
| `weft.plainweave.preflight_facts.v1` producer (Legis preflight) | feature, P1 | §4.3 |

Existing related: `plainweave-59e4af3aaf` (genesis seeding — update with `verified_actor`),
`plainweave-606b6e0a94` (register_actor re-registration polish).
