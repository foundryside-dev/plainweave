# Changelog

All notable changes to Plainweave are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and Plainweave adheres to
[Semantic Versioning](https://semver.org/).

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

[1.0.0]: https://github.com/foundryside-dev/plainweave/releases/tag/v1.0.0
