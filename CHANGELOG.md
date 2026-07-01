# Changelog

All notable changes to Plainweave are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and Plainweave adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.2.1] — 2026-07-01

Error-legibility (functional-honesty) fixes surfaced by clean-room dogfooding: an error must
*say what it knows*, and a hint that doesn't point at the real fix misdirects. Additive and
backward-compatible — the `weft.plainweave.error.v1` envelope and the `ErrorCode` vocabulary
are unchanged.

### Fixed
- **Version-conflict errors now disclose the actual version.** A `CONFLICT` on a requirement
  version or a draft revision previously reported only `"expected version does not match current
  version"` with empty `details`, forcing callers to probe for the real value. Both optimistic-
  concurrency guards now name the expected and current values in the message, in structured
  `details` (`{expected_version, current_version}` / `{expected_draft_revision,
  current_draft_revision}`), and in a hint that names the recovery
  (e.g. `Retry with --expected-version 0.`).
- **Cause-specific error hints; dropped the misleading blanket hint.** `_error` no longer stamps
  `"Refresh local Plainweave state and retry."` on every error — it misdirected, e.g. a missing
  `--actor` VALIDATION error, down a dead path. Each error now carries a cause-appropriate hint
  from a per-`ErrorCode` map (VALIDATION/NOT_FOUND never claim staleness; `CONFLICT` legitimately
  suggests a refetch), with precise hints for the missing-actor, verification-method /
  evidence-status, and trace-relation cases, plus an honest INTERNAL hint on the MCP
  preflight-severity guard.

## [1.2.0] — 2026-06-30

Closes the CLI/MCP parity gap for the 1.1 peer-facts producers (they shipped MCP-only),
delivers the operator web UX + accessibility overhaul, hardens three federation seams,
ships the `plainweave-workflow` agent skill, and fixes the wheel build. Additive and
backward-compatible; the new surfaces are advisory and verdict-free like the rest of
Plainweave.

### Added
- **`plainweave wardline-peer-facts [--json] [--limit N] [--offset N]`** — surfaces the
  full `weft.plainweave.wardline_peer_facts.v1` envelope over the CLI (previously MCP-only),
  reusing the existing MCP surface. Reads `.wardline/*-findings.jsonl` only (no store
  required); an absent `.wardline/` reports `freshness: unavailable`, never clean.
- **`plainweave requirements-enrichment <entity_ref>... [--json]`** — surfaces the full
  `weft.plainweave.requirements_enrichment.v1` envelope over the CLI (previously MCP-only).
  Accepts a SEI or a dotted locator; preserves the no-silent-clean contract
  (`present`/`absent`/`unavailable` — an identity gap is `unavailable`, never `absent`).
  Now consumed live by Warpline as the 4th `consult_federation` member (Warpline PDR-0008;
  validated end-to-end, Plainweave PDR-017).
- **Frozen degraded-state contract for `weft.plainweave.loomweave_catalog.v1`** — the
  Loomweave catalog producer's `unavailable`-adapter envelope is now pinned by a structural
  validator + golden routed through the same oracle as live output (no-silent-clean: an
  unavailable adapter never returns a clean-empty page). Seam-hardening, no behavior change
  (PDR-018, production blocker #3).
- **Contract test for the Filigree seam** — pins `open_linked_work` as reserved-but-never-
  emitted by the local-only producer (absence is the in-band `linked_work_facts_unavailable`
  warning), the `filigree_issue` trace opacity + canonical relations, and the dossier's
  advisory boundary (PDR-018, production blocker #5).
- **`plainweave-workflow` skill pack** — a federation-standard agent skill (`SKILL.md` +
  reference sheets) authored in-package (`src/plainweave/skills/`), shipped as package data
  and dogfooded into the repo's `.claude/` + `.agents/` skill trees. Documents the
  read/author/verify workflow, the doctrine invariants (advisory-only, no-silent-clean,
  enrich-only, zero minted SEIs), and the cross-member peer-facts seams.

### Changed
- **Operator web UI — UX + accessibility overhaul (PDR-016)** — adopted the site-kit design
  tokens and fixed contrast, focus-ring, and target-size; restored readable visited primary
  anchors (a global `a:visited` rule had out-specified `.btn--primary`, dropping the link to
  a ~1.7:1 WCAG AA failure once visited); and now dismiss toasts on every page (moved to
  `base.html` so script-less pages such as the requirement dossier are covered too).

### Fixed
- **Loomweave read-path trace enrichment now honors the `local_only` authority boundary
  (RED-2)** — the read path no longer reaches past the local store when the boundary is set.
- `requirements_enrichment` now drops `rejected` trace links before building the view — a
  reviewed-and-rejected binding no longer reads as requirement coverage (`present`); a
  rejected-only entity that resolves locally reads `absent`. _(Folded in from a sibling
  product's contract work.)_
- `plainweave doctor` Wardline-findings remediation is now root-aware (`cd <root> &&
  wardline scan .` when the inspected root is not the cwd). _(Folded in from a sibling
  product's contract work.)_
- ADR-006 now documents that the preflight producer emits 8 of its 11 fact kinds and why the
  other three are superseded (dedicated wardline producer) or sibling-gated (Filigree); added
  the previously-missing behavioral coverage for the `orphaned_entity_link` fact (PDR-018,
  production blocker #4).
- **Wheel build (PDR-017)** — removed a redundant
  `[tool.hatch.build.targets.wheel.force-include]` block that re-mapped `web/templates` +
  `web/static` (already vendored by the `src/plainweave` src-layout), colliding on
  `web/static/.gitkeep` and breaking `uv build`. The wheel now builds with each web asset
  shipped exactly once, so a clean `uv tool install` again advertises every CLI verb — this
  was darkening Warpline's requirements federation member in practice.

## [1.1.0] — 2026-06-27

Operator-facing web UX, SEI conformance, and cross-member peer facts. Additive and
backward-compatible: the 1.0 CLI, MCP surface, store schema, and JSON envelopes are
unchanged. New surfaces are advisory and verdict-free like the rest of Plainweave.

### Added
- **Operator web UI** (`plainweave web`, optional `plainweave[web]` extra) — a
  read-and-author mirror of the intent graph for non-CLI operators: intent dashboard
  (coverage / orphans / in-band no-silent-clean banner), corpus browse
  (search / status / orphan filters), requirement detail & authoring (current-vs-draft,
  conflict-preserves-text, two-step draft approval), goals + laddering, and a unified
  review queue (drafts + proposed trace links; accept / reject with a required reason;
  extra confirm step for accepting drifted links).
- **SEI conformance** — Plainweave becomes the 4th SEI conformer; producer freeze
  (wire golden) for the Legis preflight-facts envelope.
- **Cross-member peer facts** — two local-first, advisory producers with frozen `.v1`
  contracts (no-verdict-validated, explicit degraded state, no silent-clean):
  - `weft.plainweave.wardline_peer_facts.v1` — surfaces Wardline findings
    (active / waived / baselined / judged, defect / non-defect) plus resolved-or-unseen,
    computed against the actually re-scanned scope (scan-identity manifest primary, with a
    path-set heuristic fallback that flags itself in-band).
  - `weft.plainweave.requirements_enrichment.v1` — the Plainweave-owned producer for
    Warpline's reserved `enrichment.requirements` slot (`present | absent | unavailable`;
    an unresolved entity or a dead binding maps to `unavailable`, never `absent`).
  - Surfaced via two read-only MCP tools and a `plainweave doctor` Wardline health line.

### Security & hardening
- **CSRF protection** — body-preserving middleware; the token is minted before
  `call_next` and embedded via `request.state`; cold-start 403 fixed.
- **Input hygiene** — input-validation 400s, authority / operator-actor attribution, and
  output hygiene on the web surface.
- **Accessibility** — structural accessibility contracts in the test suite and a recorded
  manual AT gate.

### Documentation
- README install + coverage north-star note; CONTRIBUTING; web UI quickstart; webUX design
  spec + implementation plan; peer-facts design spec + 3 owner-gated sibling handoff prompts.

## [1.0.0] — 2026-06-25

First stable release. The code-up intent graph and its read/write surface are
stable; the JSON envelopes are versioned and the MCP surface is read-only,
advisory, and verdict-free. (Stable *behaviour and contracts* — cross-language
coverage *completeness* remains a documented roadmap item, not a 1.0 gate.)

### Added
- **Code-up intent graph** — `Loomweave SEI → requirement → goal`. Requirements
  are trivially mintable; a node with no upward edge is a reviewable question.
- **Read primitives** — `intent coverage` (the self-computed north-star, honestly
  qualified in-band: namespace scoping, `denominator_complete`, `present_plugins`,
  bounded evidence), `intent orphans`, `intent trace`, `intent corpus`.
- **Authoring surface** — `goal`, `req` (draft/approve/supersede/deprecate),
  `bind sei`, `catalog record`, `trace`, `criterion`, `verify`, `baseline`, `actor`.
- **Local store & verification reads** — `init` (create a `.plainweave/` store),
  `status` (requirement verification status), `dossier` (per-requirement dossier).
- **Cross-member seams** — Loomweave catalog adapter (consumes SEIs opaquely,
  never mints), Legis preflight advisory cell, peer-ready entity-intent-context API.
- **MCP server** (`plainweave-mcp`) — read-only mirror of the intent reads;
  `mutates:false`, `local_only:true`, no peer side effects.
- **`doctor` + `--fix`** — federation-parity health check (store/schema, the
  Loomweave catalog binding, the MCP surface), `--root`, `--json`, non-zero exit
  on unresolved problems. `--fix` applies idempotent in-place store repairs.
- **Cross-member regression harness** — Plainweave demonstrated against the Lacuna
  specimen as a deterministic tour member (intent-coverage capability demos).

### Guardrails (machine-enforced)
- Advisory only — zero release allow/block verdicts; verdict vocabulary is rejected
  by the shared contract validator.
- Zero Plainweave-minted SEIs; sibling SEIs consumed opaquely.
- No silent-clean — a degraded or language-partial denominator is flagged in-band.

[1.2.1]: https://github.com/foundryside-dev/plainweave/releases/tag/v1.2.1
[1.2.0]: https://github.com/foundryside-dev/plainweave/releases/tag/v1.2.0
[1.1.0]: https://github.com/foundryside-dev/plainweave/releases/tag/v1.1.0
[1.0.0]: https://github.com/foundryside-dev/plainweave/releases/tag/v1.0.0
