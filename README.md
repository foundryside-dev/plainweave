# Plainweave

**Permission for code to exist.**

Plainweave is the Weft federation member that holds the team's **code-grounded
intent**: a traceability graph in which every code entity must earn its
existence by laddering up to a requirement, and every requirement must ladder up
to a strategic goal. A node with no upward edge — at any level — is a reviewable
question:

- a public capability with no requirement → *"why does this code exist?"*
- a requirement with no goal → *"what am I doing here?"*

The point is **not** catching orphan code (that is one query). The point is that
binding code to requirements accretes a **living, readable requirements corpus**
an agent or human can reason over — *"why do we have three requirements for
reporting that are all the same?"* — and consolidate. Plainweave **moves the
refactor lever up the Meadows leverage hierarchy**: from the lowest altitude
(rename this function, extract that class) to a high one (*why does this
submodule exist; does it still serve a goal we hold?*).

> **Status — gap-named, pre-build.** Plainweave is seated by *gap-naming* (the
> same admission move as Tabard): the *position* — "the permission-for-code-to-exist /
> code-grounded-intent coordinate" — and the *name* are recognized; the build
> follows. It is **not** part of the five-member launch cutover, and it has not
> been granted formal membership — that is owner-gated, pending a PDR. This repo
> is the **initiated foundation**, reframed and renamed from the `~/charter`
> precursor. The feature build comes from a separate implementation plan; the
> current backlog lives in this repo's `.filigree` tracker.

## The model — a traceability graph of intent

```text
strategic goal ──▲── requirement ──▲── code SEI (leaf)
   (root intent)        (obligation)        (the thing that exists)
```

- **Leaves** are code entities — Loomweave SEIs (modules + public surfaces).
  **Interior nodes** are typed intent nodes (requirement, strategic goal) at any
  altitude; altitudes are just node types, the graph does not fix the number of
  levels.
- **Edges** mean *"justified by / satisfies."*
- **Requirements are trivially mintable** (shells welcome). The corpus tolerates
  mess by design — value comes from the mess being *visible and queryable*, then
  consolidated. Cheap minting *feeds* the corpus.
- **Code leaves are keyed by Loomweave SEI**, so bindings survive rename/move.
- **Default trace altitude:** modules and public/exported surfaces must trace;
  private internals inherit their container's justification.

## A thin member — Plainweave builds none of its siblings' machinery

Plainweave is **advisory by default** and deliberately thin on teeth and audit.
It owns the intent graph and the reasoning reads; it delegates everything else.

| Tool          | Owns                                                                                                                   | Plainweave does **not** rebuild         |
| ------------- | ---------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| **Plainweave** | the intent graph (goals ↔ requirements ↔ SEI bindings) + the reasoning reads. Its domain: **accreted, code-grounded intent.** | —                                       |
| **Loomweave**  | the entity catalog (what exists; public vs internal), SEI identity, the **rename feed**, and the **semantic-search engine**.   | identity/rename tracking; embeddings    |
| **Legis**      | the **git/CI boundary surfacing**, **all graded enforcement** (advisory default; dial-up per repo via policy cells), and the **audit trail**. | enforcement engine; override/audit      |

Bindings reuse the **ADR-029 entity-association contract** (SEI-keyed, with
`content_hash_at_attach` drift detection — the same pattern Filigree uses to
bind issues to code), not a new link store.

## Surfaces

**Write path — authoring-time binding** ("speak SEI at entry," extended to
intent). When an agent creates or commits a module / public entity, Plainweave
offers an inline bind: *link this SEI to a requirement* (existing or a freshly
minted shell) and optionally *ladder that requirement to a goal*. Cheap, inline,
attributed. Code that skips the bind is exactly what surfaces as an orphan.

**Read surfaces — three composable graph primitives** (built for unanticipated
agent use, not canned reports):

- `orphans(level)` — unlinked nodes at the code / requirement / goal altitude.
- `trace(node)` — up to goals, down to code.
- `corpus()` — the readable dump of requirements with their code- and goal-links:
  the artifact a curator reads to spot *"these three are the same."* Consolidation
  is **agent-driven**; Plainweave serves the substrate, not an automated verdict.

**Boundary** — coverage facts ride out at the git/CI boundary through Legis
(*"this change adds N public entities bound to no requirement"*). **Advisory by
default;** any repo wanting teeth dials it up through Legis's policy cells.
Plainweave adds no enforcement of its own.

**Optional similarity hint** — Loomweave now ships semantic search, so a thin
*"these requirements look like the same thing"* hint becomes **reuse of a proven
sibling capability** rather than a from-scratch ML build. It *assists* the
curator; it is explicitly not a dedup engine.

## Doctrine fit

- **Coordinate, not gate** — advisory default.
- **Enrich-only** — Plainweave absent → Loomweave, Legis, and the code are
  unaffected; solo mode degrades to manual file/symbol refs.
- **Speak-SEI-at-entry** — binding at authoring keeps code on the moat.
- **Don't-duplicate** — Legis owns teeth + audit; Loomweave owns identity +
  semantics.
- **Prescribe-nothing** — a general graph + queries; agents compose uses we
  haven't imagined.

## Cross-member seams

The seams (Plainweave → Loomweave catalog/rename/semantic; Plainweave → Legis
boundary) are **hub-blessed** and **prove-the-need**: built as additive adapters
on Plainweave's side, never pre-frozen sibling obligations until the need is
shown live (golden vector / live consumption). Each seam ships with a
blast-radius map + dated counterpart tickets.

## Documentation

- [`docs/design/`](docs/design/) — the canonical design ("permission for code to
  exist"). **Start here.**
- [`docs/MODULE-MAP.md`](docs/MODULE-MAP.md) — what the precursor core carries
  forward vs. what the reframe reshapes.
- [`docs/README.md`](docs/README.md) — index of canon vs. precursor-era docs.

## Development

Plainweave uses [uv](https://docs.astral.sh/uv/), `hatchling`, `ruff`, `mypy`,
and `pytest`.

```bash
uv sync --group dev
make ci          # lint + typecheck + test (coverage-gated)
```

The runtime package depends on the official Python MCP SDK for `plainweave-mcp`.

### What works today (carried forward from the precursor)

The precursor's local requirements/verification core is intact and green — a
foundation to reshape, not the reframed feature set. See the MODULE MAP for the
current → target audit. The code-up read primitives (`orphans`/`trace`/`corpus`),
the SEI-keyed ADR-029 bindings, and the authoring-time write path are **stubbed
with backlog markers**, not yet implemented.
