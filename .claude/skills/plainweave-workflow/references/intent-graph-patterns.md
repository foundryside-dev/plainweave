# Intent-graph patterns

Deep-dive patterns for working the `SEI → requirement → goal` graph. Load when you
hit one of these specific situations.

## Reading coverage honestly

`plainweave intent coverage` reports the fraction of public surfaces that answer
"why does this exist?" — but the **number is meaningless without its qualifiers**.
Always read these from the envelope before quoting a percentage:

- **`denominator_complete`** — `false` means the surface inventory is partial
  (e.g. a language plugin is absent). A high percentage over an incomplete
  denominator is not a clean bill of health; say so.
- **`present_plugins`** — which language/surface extractors actually ran. Coverage
  is only as complete as this list.
- **Namespace scope** — the denominator excludes `scripts.` and `tests.` by
  default. Add `--exclude-namespace PREFIX` (repeatable) to scope out generated or
  vendored namespaces; never silently widen it to flatter the number.
- **Surface class** — `--surface-class {cli-command,entry-point,exported-api,http-route}`
  restricts the denominator. Use it to answer "how covered is the HTTP surface
  specifically?" rather than the blended figure.
- **`--max-surfaces N`** caps the evidence lists, **not** the counts — counts are
  never truncated, so a capped list still reports the true total.

The honest move when coverage looks high: state the figure *and* the denominator
qualifiers in the same breath ("92% of exported-api surfaces, but
`denominator_complete: false` — the Rust plugin didn't run").

## Triaging orphans at each altitude

`plainweave intent orphans {code,requirement,goal}` returns nodes with no upward
edge. The triage question differs by altitude:

- **code orphans** — a public entity bound to no requirement. Ask: should this be
  bound (then `bind sei`), or is it genuinely infrastructural/standalone? Don't
  reflexively mint a shell requirement just to clear the orphan — that manufactures
  vanity coverage.
- **requirement orphans** — an approved requirement laddered to no goal. Either
  link it (`goal link`) or accept it as a leaf with a note. A pile of goal-less
  requirements is a signal the goal layer is under-modelled.
- **goal orphans** — a goal with no requirements beneath it. Usually means intent
  was declared but never decomposed into reviewable requirements.

## Corpus-driven consolidation

`plainweave intent corpus` is the curator's artifact. Consolidation is **agent-
driven, never automated**: read the corpus, spot "these three say the same thing,"
then supersede the duplicates into one canonical requirement (`req supersede`) and
re-bind. Plainweave serves the substrate; it does not auto-merge. The optional
Loomweave semantic-similarity hint *assists* this read — it is explicitly not a
dedup engine and never acts on its own.

## Requirement lifecycle

Requirements are versioned with an explicit draft/approve flow:

1. `req add` creates a **draft** (the "active draft" for the project).
2. `criterion add` attaches acceptance criteria to the active draft.
3. `req approve` promotes it. Approved requirements are what baselines lock.
4. `req supersede` creates a new version that replaces an approved one;
   `req deprecate` retires one; `req reject` discards an unwanted draft.

Trace links carry their own review state: `propose → accept | reject`. A **proposed**
link is a suggestion; only **accepted** links count as justification; **rejected**
links are dropped before coverage is computed (a rejected binding never reads as
`present`).

## Baselines & drift

`plainweave baseline create` locks the current approved-requirement set under a
name. Later, `plainweave baseline diff <id>` shows how the live approved set has
drifted (added / removed / superseded). Use a baseline at a release boundary or a
review milestone, then diff against it to answer "what requirements moved since we
agreed this set?" Baselines are immutable once created — `show`/`list` read them.

## Verification, not validation

`verify method` declares *how* a requirement is checked; `verify evidence` records a
concrete result against a method; `status` reports the rollup
(`requirement` / `unverified` / `stale`). Evidence goes **stale** when the thing it
attested to has moved on — `status stale` surfaces exactly those, so re-verification
is targeted rather than wholesale. The `dossier` is the full advisory picture for one
requirement (statement, criteria, bindings, verification) — it reports, it does not
gate.
