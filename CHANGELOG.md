# Changelog

All notable changes to Plainweave are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and Plainweave adheres to
[Semantic Versioning](https://semver.org/).

## [1.1.0] — 2026-06-26

Operator-facing web UX and SEI conformance. Additive and backward-compatible:
the 1.0 CLI, MCP surface, store schema, and JSON envelopes are unchanged. The
web UI is an optional `plainweave[web]` extra; it stays advisory and verdict-free
like the rest of the surface.

### Added
- **Operator web UI** (`plainweave web`, optional `plainweave[web]` extra) — a
  read-and-author mirror of the intent graph for non-CLI operators:
  - **Intent dashboard** — coverage, orphans, and an in-band no-silent-clean
    banner when the denominator is degraded or language-partial.
  - **Corpus browse** — search / status / orphan filters with inline per-row
    target expansion.
  - **Requirement detail & authoring** — current-vs-draft side-by-side; create /
    edit with conflict-preserves-text UX; two-step draft approval with
    out-of-band status/badge/empty-state results.
  - **Goals** — goals list, goal creation, and laddering requirements to goals.
  - **Review queue** — unified drafts + proposed trace links; accept / reject
    with a required-reason two-step, plus an extra confirm step for accepting
    drifted links.
- **SEI conformance** — Plainweave becomes the 4th SEI conformer; producer freeze
  (wire golden) for the Legis preflight-facts envelope.

### Security & hardening
- **CSRF protection** — middleware that mints a token before `call_next`,
  embeds it via `request.state`, and preserves the request body for downstream
  handlers; cold-start 403 fixed.
- **Input hygiene** — input-validation 400s, authority/operator-actor
  attribution, and output hygiene on the web surface.
- **Accessibility** — structural accessibility contracts in the test suite and a
  recorded manual AT gate.

### Documentation
- README installation + coverage north-star note; CONTRIBUTING, changelog URL;
  web UI quickstart; webUX MVP design spec and implementation plan.

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

[1.1.0]: https://github.com/foundryside-dev/plainweave/releases/tag/v1.1.0
[1.0.0]: https://github.com/foundryside-dev/plainweave/releases/tag/v1.0.0
