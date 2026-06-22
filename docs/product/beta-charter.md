# Plainweave Beta Charter

## Bet

Plainweave beta proves one product bet: a local-first CLI/MCP member can answer
"why does this code exist?" by exposing a code-up graph:

`Loomweave SEI -> Plainweave requirement -> Plainweave goal`

The beta is a candidate for suite membership, not formal admission. Public
release, final naming, PyPI publication, hub roster edits, and sibling-owner
obligations remain owner-gated.

## Target User

The primary beta user is an agent or maintainer working in a Weft suite repo who
needs a concise, local, inspectable answer for why a module or public surface
exists.

## Acceptance Bar

- A public code entity can be recorded from a Loomweave-style catalog.
- A SEI can be bound to an existing requirement with actor, hash, freshness, and
  provenance preserved.
- A requirement can ladder to a strategic goal.
- `orphans(code)`, `trace(node)`, and `corpus()` are available through service,
  CLI, and MCP read surfaces.
- Plainweave reports local facts only; it does not mint SEIs, enforce release
  decisions, or convert agent proposals into accepted human truth.

## Stage Gates

- Foundation gate: schema v2 migrates without rewriting precursor requirement,
  baseline, evidence, or event rows.
- Graph gate: goals, goal-requirement edges, code entities, and SEI bindings are
  persisted and queryable.
- Read gate: `orphans`, `trace`, and `corpus` are behavior-tested across service,
  CLI, and MCP.
- Boundary gate: Loomweave and Legis remain authority owners; Plainweave
  degrades explicitly when peer facts are absent.
- Beta-candidate gate: a golden vector can be demonstrated first on Plainweave
  itself and then on Loomweave as the default representative sibling.

## Non-Goals

- DOORS replacement breadth.
- Semantic deduplication or automatic consolidation.
- Release gates, allow/block decisions, or audit enforcement.
- SEI minting, parsing, rename ownership, or lineage authority.
- Formal suite admission or public publication without owner approval.

## RAID

- Risk: duplicate truth between old `trace_links` and ADR-029 bindings.
  Response: schema v2 treats ADR-029 entity associations as canonical for code
  bindings and keeps old trace links as precursor evidence.
- Risk: false clean results when Loomweave is absent.
  Response: public entity recording is explicit and local; future live peer
  adapters must return degraded freshness rather than empty success.
- Risk: product ambiguity around suite membership.
  Response: candidate status is documented here and final admission remains
  owner-gated.
- Dependency: Loomweave public-surface catalog and SEI identity.
- Dependency: Legis advisory fact envelope for future boundary checks.
