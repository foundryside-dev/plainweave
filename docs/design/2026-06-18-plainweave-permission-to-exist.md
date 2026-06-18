# Design — Plainweave: the "permission for code to exist" member (Charter, reframed + renamed)

**Date:** 2026-06-18 · **Status:** DESIGN — brainstormed + approved section-by-section; feeds a
proposed PDR. **OWNER-GATED** (vision/strategy change + member admission §7 + naming) — this
document *designs* the member; the owner decides whether to adopt it as a bet and admit/promote it.
**Working name:** **Plainweave** (supersedes "Charter" — taken on PyPI; owner's call, "or similar").
**Precursor:** the existing `~/charter` repo (local core + read-only agentic MCP, started 2026-06-04).

---

## 1. The reframe (what changed)

Charter's current canon frames it **requirements-down**: a store of obligations, traceability,
baselines, and verification evidence — *"what must be true, how do we know."* Read that way it is a
project-management overlay, and it has been treated as second-class (not in the five-member cutover;
"federation adapters pending").

This design **inverts it to code-up**. Every code entity must earn its existence by tracing to a
requirement; the member becomes a **continuous legitimacy check on the code itself** — *"why does
this code exist?"* — and, more importantly, the **home of the team's accreted, code-grounded
intent**, a corpus a human or agent can read and reason about.

The foundational value is **not** catching orphan code (that is one query). It is that binding code
to requirements accretes a **living, reviewable requirements corpus** so a reader can ask
*"why do we have three requirements for reporting that are all the same?"* — and, one level up,
*"why do we have a requirement that ladders to no strategic goal we still hold?"*

**Positioning (the reason it is first-class):** Plainweave **moves the refactor lever up the
Meadows leverage hierarchy** — from the lowest-leverage altitude (rename this function, extract that
class — parameters) to a high-leverage one (*why does this submodule exist; does it serve a goal we
still hold?* — goals and structure). It graduates the member from PM overlay to the authority that
owns **intent, grounded in real code**.

## 2. Gap-naming (the admission move)

Like **Tabard** (PDR-0028, the *who* coordinate), this is **admission by gap-naming** (doctrine §7,
stage 1): we recognize the *position* — "the permission-for-code-to-exist / code-grounded-intent
coordinate" — and the *name* (**Plainweave**), and declare *something fills this*. The
implementation follows; the existing `~/charter` core is its seed, reconceived around the
permission-to-exist model and renamed for publication. The position + name are what get seated; the
build is a downstream bet.

## 3. The model — a traceability graph of intent

Plainweave holds a directed graph:

```
strategic goal ──▲── requirement ──▲── code SEI (leaf)
   (root intent)          (obligation)          (the thing that exists)
```

- **Leaves** = code entities (Loomweave SEIs — modules + public surfaces). **Interior nodes** =
  typed intent nodes at any altitude (requirement, strategic goal). Altitudes are just node types;
  the graph does not fix the number of levels.
- **Edges** mean *"justified by / satisfies."*
- **A node with no upward edge is the reviewable question, at every level:** code leaf with no
  requirement = *"why does this code exist?"*; requirement with no goal = *"what am I doing here?"*
- **Requirements are trivially mintable** (shells welcome — e.g. "must have a module called X").
  This is by design: the corpus tolerates mess; value comes from the mess being **visible and
  queryable**, so it gets consolidated later. Cheap minting *feeds* the corpus.
- **Code leaves are keyed by Loomweave SEI**, so bindings survive rename/move.

**Default trace altitude:** modules + public/exported surfaces must trace; private internals inherit
their container's justification (uses Loomweave's public/internal distinction). This is where
"why does this exist?" actually bites — a *new public capability* with no requirement.

## 4. Division of labor — Plainweave builds none of Legis's machinery

| Tool | Owns | Plainweave does NOT rebuild |
|------|------|------------------------------|
| **Plainweave** | the intent graph (goals↔requirements↔SEI bindings) + the **reasoning reads** (orphans at any level, coverage/trace, the readable corpus, optional similarity hint). Its unique domain: **accreted, code-grounded intent.** | — |
| **Loomweave** | the entity catalog (what exists; public vs internal), SEI identity, the **rename feed** (bindings survive rename), and the **semantic-search engine** (now built — see §7). | identity/rename tracking; embedding/semantic machinery |
| **Legis** | the **git/CI boundary surfacing**, **all graded enforcement** (advisory default; dial-up per repo via policy cells), and the **audit trail**. | enforcement engine, override/audit machinery, boundary integration |

Plainweave is deliberately **thin on teeth and audit** (delegates to Legis) and **thick on the
intent corpus and the reads** (its domain). The binding reuses the **ADR-029 entity-association
contract** (SEI-keyed, `content_hash_at_attach` drift detection — the same pattern Filigree uses to
bind issues to code), not a new link store.

## 5. Write path — authoring-time binding ("speak SEI at entry," extended to intent)

When an agent creates or commits a module / public entity, Plainweave's write surface offers an
inline bind: *link this SEI to a requirement* (pick existing or mint a shell) and optionally *ladder
that requirement to a goal*. Cheap, inline, **attributed** (who bound it, when). One call via the
ADR-029 association contract — no new machinery. Code that skips the bind is exactly what surfaces
as an orphan; binding is the entry gate to being "on the moat" (per the speak-SEI-at-entry doctrine).

## 6. Read surfaces — a queryable graph, not canned reports

Three composable primitives:
- **`orphans(level)`** — unlinked nodes at the code / requirement / goal altitude.
- **`trace(node)`** — up to goals, down to code ("what satisfies this requirement"; "what justifies
  this code").
- **`corpus()`** — the readable dump of requirements with their code- and goal-links: *the artifact
  an agent or human reads to spot "these three are the same."*

These are **general graph queries**; the orphan-code report and the dup-requirements report are just
two of them. Built for unanticipated agent use (prescribe-nothing). **Consolidation is
agent-driven** — an opus-class agent reads the corpus and performs the intent-altitude refactor;
Plainweave serves the readable substrate, not an automated dedup verdict.

## 7. The semantic-similarity hint (optional, justified by reuse)

Loomweave now ships **semantic search**. That changes the cost-benefit of a *"these requirements
look like the same thing"* hint: it is no longer a from-scratch ML build but **reuse of a proven
sibling capability**, which clears the bar it would not have cleared standalone. So Plainweave MAY
offer an optional, thin similarity-hint over requirement text, leaning on Loomweave's semantic
machinery — **assisting** the agent curator, never replacing its judgment. Explicitly **not** an
elaborate dedup engine. (Whether the engine is shared as a library or reached as a blessed seam is a
plan-time question — §12.)

## 8. Boundary — Legis surfaces it, owns the teeth

Coverage facts ride out at the git/CI boundary through Legis: *"this change adds N public entities
bound to no requirement; touches M requirements that ladder to no goal."* **Advisory by default;**
any repo wanting teeth dials it up through Legis's existing policy cells. Plainweave adds no
enforcement of its own.

## 9. Doctrine fit

- **Coordinate, not gate** ✓ advisory default (re-derive any "gate" as availability/honesty).
- **Enrich-only** ✓ Plainweave absent → Loomweave, Legis, and the code are unaffected; solo mode
  degrades to manual file/symbol refs (as Charter's canon already states).
- **Speak-SEI-at-entry** ✓ binding at authoring keeps code on the moat.
- **Don't-duplicate** ✓ thin member; Legis owns teeth + audit; Loomweave owns identity + semantics.
- **Prescribe-nothing** ✓ a general graph + queries; agents compose uses we haven't imagined.

## 10. Relationship to the existing `~/charter` work

The `~/charter` repo (local core + read-only MCP) is the **precursor/seed**, not discarded. The
reframe changes the member's *center of gravity* (code-up legitimacy + intent corpus) and its *name*
(Plainweave). A plan must assess how much of the existing core carries forward vs. is reshaped.

## 11. Scope / non-goals (YAGNI)

- **OUT:** an automated dedup/clustering engine (the agent is the curator); a hard gate (advisory
  only); Plainweave-side enforcement, override, or audit machinery (Legis's); Plainweave-side
  identity/rename tracking (Loomweave's).
- **IN:** the intent graph + bindings (ADR-029 reuse), the three read primitives, the authoring-time
  write path, the Legis boundary surfacing, and the optional Loomweave-backed similarity hint.

## 12. Cross-member seams — hub-blessed, prove-the-need

The seams (Plainweave→Loomweave catalog/rename/semantic; Plainweave→Legis boundary) are
**hub-blessed** and **prove-the-need**: built as **additive adapters on Plainweave's side**, never
pre-frozen sibling obligations until the need is shown live (golden vector / live consumption). Per
the post-launch change discipline, each seam ships with a blast-radius map + dated counterpart
tickets. A plan resolves: shared-library vs blessed-seam for the semantic engine; the exact
Loomweave catalog read for "public surfaces + modules"; the Legis policy-cell shape for the advisory
default.

## 13. Owner-gated escalations (NOT decided here)

1. **Vision/strategy change** — reframing Charter from PM-overlay to first-class "intent authority."
2. **Member admission (§7)** — gap-naming Plainweave as a seated position (parallel to Tabard /
   PDR-0028); promoting it from "planned integration" toward membership.
3. **The name** — Plainweave (Charter is taken on PyPI); "or similar" per owner.

Path: this spec → a **proposed PDR** (recorded at the next `/product-checkpoint`, `Status: proposed`)
→ owner decides. `vision.md`, `roadmap.md`, and `doctrine.md`'s roster are **not** edited until then.

## 14. What a plan covers next (not now)

Carry-forward audit of `~/charter` core; the ADR-029 binding schema for requirement↔SEI; the
Loomweave catalog read (public-surface + module enumeration); the three read primitives; the
authoring-time write surface; the Legis advisory boundary cell; the semantic-hint integration
decision; and the seam contracts (additive, hub-blessed, golden-vector-gated).
