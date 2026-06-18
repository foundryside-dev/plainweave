# Plainweave MODULE MAP — precursor core → reframed target

**Date:** 2026-06-18 · **Scope:** repo standup (initiate, not build). This audits
the carried-forward `~/charter` precursor core against the Plainweave reframe
([design](design/2026-06-18-plainweave-permission-to-exist.md)) and marks, per
module, what **carries forward** vs. what must be **reshaped**. Reshape work is
filed in this repo's `.filigree` tracker — this map is the orientation, not the
plan.

## The shift in one line

The precursor is **requirements-down** (a store of obligations + verification
evidence). The reframe is **code-up**: every code entity (a Loomweave SEI) must
trace to a requirement; requirements ladder to goals; the hero value is the
readable, queryable **intent corpus**. The data model is mostly intact; the
*center of gravity*, the *read surface*, and the *binding contract* move.

## Module-by-module

| Module | What it is today | Verdict | Notes |
| ------ | ---------------- | ------- | ----- |
| `models.py` | Requirement (draft/version/record), AcceptanceCriterion, TraceRef/TraceLink, Baseline(+diff), Verification(method/evidence/status), Dossier* dataclasses, Actor | **Carry forward + extend** | The requirement/trace/verification model is the foundation. **Add** the typed intent-node layer: a *strategic goal* node type and the goal↔requirement edge, so the graph spans goal → requirement → code SEI. Generalize "trace" to the upward-justification edge. |
| `store.py` | SQLite store + migrations + event log | **Carry forward** | Storage, migrations, and the append-only event stream are reusable as-is. New tables/migrations for goal nodes and (if not delegated) any local binding cache ride on the existing migration machinery. |
| `service.py` (2.1k LOC) | Requirement lifecycle, criteria, trace propose/accept/reject, baselines, verification, dossiers, peer-fact plumbing | **Carry forward core; reshape edges + reads** | Requirement/version/criteria/baseline/verification logic carries forward. **Reshape:** (1) code↔requirement binding should ride the **ADR-029 entity-association contract** (SEI-keyed, `content_hash_at_attach` drift), not only the native `trace_links` store; (2) add the goal altitude; (3) add the code-up **orphan** computation at every level. |
| `mcp_surface.py` / `mcp_server.py` | Read-only agentic MCP surface (project context, requirement search/show, dossiers, trace listing, baselines, verification status) | **Carry forward; add the three primitives** | Existing reads stay. **Add** `orphans(level)`, `trace(node)` (the graph-walk, up to goals + down to code), and `corpus()` (the readable requirements-with-links dump). These are stubbed now — see `intent_graph.py` / backlog. |
| `cli_commands.py` / `cli.py` | Full CLI over the precursor surface | **Carry forward; extend** | CLI is reusable. New verbs follow the read primitives + the authoring-time bind. |
| `envelopes.py` | Standard JSON envelope (`schema`/`ok`/`data`/`warnings`/`meta.producer`) | **Carry forward** | Producer renamed to `plainweave`. Honesty/freshness labelling fits the reframe directly. |
| `errors.py` | `ErrorCode` (generic: VALIDATION, PEER_ABSENT, PEER_STALE, …) + `PlainweaveError` | **Carry forward** | Peer-absent/stale codes already model enrich-only/honest-degradation. |
| `paths.py` | `.plainweave/` repo-local dir + db path | **Carry forward** | Repo-local store; renamed from `.charter/`. |
| `_version.py` / `__init__.py` / `__main__.py` | Package version + entry points | **Carry forward** | Reset to `0.0.1` (fresh package identity). |

## What is genuinely NEW (stubbed now, built later)

These target interfaces are **stubbed with `implementation pending — see backlog`
markers** in this standup (`src/plainweave/intent_graph.py`,
`src/plainweave/bindings.py`); none are half-wired:

1. **The intent graph** — goal node type + goal↔requirement edge layered over the
   existing requirement/trace model (`intent_graph.py`).
2. **`orphans(level)` / `trace(node)` / `corpus()`** — the three composable read
   primitives over that graph (`intent_graph.py`).
3. **ADR-029 SEI binding** — code-leaf ↔ requirement binding via the
   entity-association contract, keyed by `loomweave:eid:` SEI, drift-detected by
   `content_hash_at_attach` (`bindings.py`).
4. **Authoring-time write path** — the inline "bind this SEI to a requirement
   (or mint a shell) and optionally ladder to a goal" surface ("speak SEI at
   entry," extended to intent).
5. **Legis advisory boundary cell** — coverage facts surfaced at the git/CI
   boundary; advisory by default, dial-up via Legis policy cells.
6. **Optional Loomweave-semantic similarity hint** — thin reuse of Loomweave's
   shipped semantic search over requirement text; assists the curator, not a
   dedup engine.

## Out (per the design's YAGNI)

An automated dedup/clustering engine; a hard gate; Plainweave-side enforcement /
override / audit machinery (Legis owns it); Plainweave-side identity / rename
tracking (Loomweave owns it). Cross-member seams are **additive, hub-blessed,
prove-the-need** — never pre-frozen sibling obligations.
