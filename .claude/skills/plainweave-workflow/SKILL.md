---
name: plainweave-workflow
description: >
  This skill should be used when the user asks "why does this code exist",
  "what's our intent coverage", "find orphan code / requirements / goals",
  "trace this requirement up to a goal or down to code", "bind this SEI /
  entity to a requirement", "draft / approve / supersede a requirement", "show
  the requirement dossier", "what's unverified or stale", "baseline the
  requirements", or when working in a project that uses Plainweave for code-up
  requirements traceability and intent. Provides the read/author/verify
  workflow, the doctrine invariants (advisory-only, no-silent-clean,
  enrich-only, zero minted SEIs), and the cross-member peer-facts surfaces.
---

# Plainweave Workflow

Plainweave is the Weft federation's **requirements and verification authority** —
"the permission-for-code-to-exist member." It maintains a **code-up intent graph**
(`Loomweave SEI → requirement → goal`) in a local `.plainweave/` store and answers
one question for every public surface: *"why does this exist?"* It is **advisory**:
it surfaces facts and lets agents decide; it never emits an allow/block verdict.

Prefer the MCP tools (`mcp__plainweave__*`) when available; fall back to the
`plainweave` CLI. Every read CLI takes `--json` to emit a versioned envelope.

## The model — three altitudes, one graph

```
goal            strategic intent ("ship trustworthy federation seams")
  ↑ links
requirement     a reviewable statement ("the producer must never silent-clean")
  ↑ binds
code (SEI)      a Loomweave-identified public entity (function/class/module)
```

A node with **no upward edge** is an **orphan** — a reviewable question, not an
error. Code that skips its bind is exactly what surfaces. Requirements are
trivially mintable; consolidation ("these three are the same") is **agent-driven**
off the corpus, never an automated verdict.

## Core read workflow — the four intent primitives

```bash
plainweave intent coverage              # north-star: fraction of public surfaces that answer "why?"
plainweave intent orphans code          # unjustified nodes at an altitude: code | requirement | goal
plainweave intent trace code <node_id>  # justification neighborhood up to goals / down to code
plainweave intent corpus                # readable dump of requirements + their code/goal links
```

- **`coverage`** is the self-computed north-star. It is **honestly qualified
  in-band**: `denominator_complete`, `present_plugins`, namespace scoping, bounded
  evidence. Scope the denominator with `--exclude-namespace PREFIX` (default excludes
  `scripts.`, `tests.`) and `--surface-class {cli-command,entry-point,exported-api,http-route}`.
  It **never reports a silent clean** when the denominator is partial.
- **`orphans <altitude>`** lists nodes with no upward justification edge. Triage,
  don't panic — an orphan is "should this be bound, or is it genuinely standalone?"
- **`trace <altitude> <node_id>`** walks both directions from a node.
- **`corpus`** is the artifact a curator reads to spot duplicates before consolidating.

## Authoring workflow — draft → criterion → approve → bind → ladder

Requirements are versioned with a draft/approve lifecycle:

```bash
plainweave req add --title "…" --statement "…" [--actor human:<you>]   # create a DRAFT
plainweave criterion add …                                            # acceptance criteria on the active draft
plainweave req approve                                                 # promote the active draft
plainweave req supersede … | req deprecate … | req reject             # later lifecycle moves
```

Bind code and ladder to strategy:

```bash
plainweave bind sei <entity_id> <requirement_id> [--entity-kind …] [--content-hash …]
plainweave goal add "…"                       # strategic intent node
plainweave goal link <goal_id> <requirement_id>
```

Trace links (graph edges) have their own propose/review lifecycle — a proposed
link is a *suggestion*, accepted is *fact*, rejected never reads as coverage:

```bash
plainweave trace propose --from-kind … --from-id … --relation … --to-kind … --to-id … [--confidence N]
plainweave trace accept <link_id> | trace reject <link_id>
plainweave trace list
```

> **Rejected ≠ absent coverage.** A reviewed-and-rejected binding does **not**
> read as requirement coverage; the view drops `rejected` trace links before
> computing `present`/`absent`.

## Verification — methods, evidence, status

```bash
plainweave verify method …           # define how a requirement is verified
plainweave verify evidence …         # record evidence against a method
plainweave status requirement <id>   # verification status for one requirement
plainweave status unverified         # requirements with no verification
plainweave status stale              # requirements whose evidence has gone stale
plainweave dossier <requirement_id>  # the full per-requirement dossier (advisory boundary)
```

Lock and compare requirement sets over time:

```bash
plainweave baseline create …    # lock the approved-requirement set
plainweave baseline diff <id>   # drift of current approved vs a baseline
plainweave baseline list | baseline show <id>
```

## Doctrine — the hard invariants (do not violate)

Plainweave's behaviour is contract-validated against these; violating them is
rejected by the shared validators, not merely discouraged.

- **Advisory, never gates.** Zero release allow/block/approved/verdict tokens.
  Coverage facts ride out at the git/CI boundary *through Legis* — Plainweave adds
  no enforcement of its own. Any teeth are dialled up by the consumer via Legis cells.
- **No silent-clean.** A degraded or language-partial denominator, an unavailable
  adapter, or an unresolved identity is **flagged in-band** — never collapsed to a
  clean-empty result. `unavailable` ("I can't tell") is distinct from `absent`
  ("definitively none") and from a clean `present`.
- **Enrich-only.** Plainweave absent → Loomweave, Legis, and the code are
  unaffected; solo mode degrades to manual file/symbol refs.
- **Zero minted SEIs.** Sibling identity (`loomweave:eid:…`) and sibling fact
  bodies are consumed **opaquely** — surfaced, never parsed or minted.
- **Local-only.** Reads compute against the local store / re-scanned scope; no live
  peer calls in the producers (`local_only: true`, `live_peer_calls: false`).

## Cross-member peer facts (advisory producers)

Two local-first producers expose Plainweave facts to siblings, each with a frozen
`.v1` contract, explicit degraded state, and no silent-clean:

```bash
plainweave wardline-peer-facts [--limit N] [--offset N] [--json]   # weft.plainweave.wardline_peer_facts.v1
plainweave requirements-enrichment <entity_ref>... [--json]        # weft.plainweave.requirements_enrichment.v1
```

- **`wardline-peer-facts`** surfaces Wardline findings (active / waived / baselined
  / judged) computed against the actually re-scanned scope. Reads `.wardline/*-findings.jsonl`
  only; an absent `.wardline/` reports `freshness: unavailable`, **never clean**.
- **`requirements-enrichment`** is the Plainweave-owned producer for **Warpline's**
  reserved `enrichment.requirements` slot. `entity_ref` is a SEI or dotted locator
  (batch many in one call). Per-entity `status`: `present` (≥1 alive binding) /
  `absent` (entity known, none bound) / `unavailable` (identity unresolved or store
  error — "I can't tell," **never** "no requirements"). This is consumed live by the
  Warpline `consult_federation` requirements member — see `references/cross-member-seams.md`.

## Health and diagnostics

```bash
plainweave init                 # create a .plainweave/ store
plainweave doctor               # federation-parity health: store/schema, Loomweave catalog binding, MCP surface
plainweave doctor --fix         # idempotent in-place store repairs, then re-check
plainweave doctor --root <dir>  # inspect a root other than cwd (remediation is root-aware)
```

`doctor` exits non-zero on unresolved problems; `--fix` is safe and idempotent.

## Response shapes & exit codes

Read surfaces emit a versioned envelope under `--json` (and the MCP tools return the
same shape):

- **Success** → `{schema: "weft.plainweave.<contract>.v1", ok: true, …, authority_boundary: {local_only: true, live_peer_calls: false, governance_verdicts: false}}`.
- **Failure** → `{ok: false, error: {code, …}}`. `code` ∈ `VALIDATION`, `NOT_FOUND`,
  `CONFLICT`, `POLICY_REQUIRED`, `PEER_ABSENT`, `PEER_STALE`, `PEER_CONTRACT`,
  `LOCKED`, `UNSUPPORTED`, `INTERNAL`. Branch on `code`, not message text.
- **Exit codes** (surface commands): `ok:true → 0`; `INTERNAL → 4`; any other
  failure (e.g. `NOT_FOUND`, uninitialised store) → `2`. An uninitialised store is a
  *genuine* producer failure (exit 2 / `ok:false`), never a faked clean — that would
  break no-silent-clean. NB: a piped exit capture (`… | head; echo $?`) reports the
  pipe tail's status, not plainweave's.

## MCP parity (read-only mirror)

The MCP server (`plainweave-mcp`) mirrors the reads — `mutates: false`,
`local_only: true`, no peer side effects: `plainweave_intent_coverage` /
`_orphans` / `_trace` / `_corpus`, `plainweave_requirement_get` / `_search` /
`_dossier`, `plainweave_verification_status_get` / `_list`, `plainweave_baseline_*`,
`plainweave_trace_link_list`, `plainweave_entity_intent_context_get`,
`plainweave_loomweave_catalog_list`, `plainweave_preflight_facts_get`,
`plainweave_project_context_get`, `plainweave_wardline_peer_facts_list`,
`plainweave_requirements_enrichment_get`.

## Reference sheets

Load these when you hit a specific challenge, not upfront:

- **`references/intent-graph-patterns.md`** — coverage-denominator scoping,
  orphan triage at each altitude, corpus-driven consolidation, baselines & drift,
  the verification lifecycle.
- **`references/cross-member-seams.md`** — the peer-facts producers and their
  freshness/degraded vocab, the Loomweave catalog/SEI seam, the Legis boundary,
  and the opacity rules for sibling identity.

## Quick decision guide

| Situation | Action |
|-----------|--------|
| "Why does this code exist?" | `plainweave intent trace code <sei>` |
| "What's our intent coverage?" | `plainweave intent coverage` (read the in-band qualifiers) |
| "What code is unjustified?" | `plainweave intent orphans code` |
| "These requirements look duplicated" | `plainweave intent corpus`, consolidate by hand |
| "Record a new requirement" | `req add` → `criterion add` → `req approve` |
| "Link this entity to a requirement" | `plainweave bind sei <entity_id> <requirement_id>` |
| "Is this requirement verified?" | `plainweave status requirement <id>` / `dossier <id>` |
| "What's gone stale?" | `plainweave status stale` |
| "Did anything drift from the baseline?" | `plainweave baseline diff <id>` |
| "What requirements bind this entity (for Warpline)?" | `plainweave requirements-enrichment <ref> --json` |
| "Is the store healthy?" | `plainweave doctor` (`--fix` to repair) |
| "Plainweave says `unavailable`" | It can't tell (identity/store) — **not** "none." Resolve identity or `init`. |
