# Plainweave Beta Solution Architecture

## Scope

The beta candidate is suite-program scope L because it depends on Plainweave,
Loomweave, Filigree, and Legis contracts. Implementation stays in M-sized local
Plainweave slices: schema, service, CLI, MCP, docs, and tests.

## Components

- Store: schema v2 adds `intent_goals`, `intent_edges`, `code_entities`, and
  `entity_associations`.
- Service: owns local mutation and read behavior for goals, bindings, drift
  checks, and intent graph queries.
- CLI: provides authoring-time and local ingestion commands.
- MCP: exposes read-only graph primitives for agents.
- Product docs: preserve beta bet, metrics, and owner-gated decisions.

## Interfaces

- `catalog record`: records a code entity discovered by a sibling catalog.
- `goal add`: creates a strategic goal.
- `goal link`: links a goal to a requirement.
- `bind sei`: binds a code entity to a requirement with actor, hash, freshness,
  and provenance.
- `intent orphans`: lists nodes with no upward justification edge.
- `intent trace`: returns the up/down neighborhood for a code, requirement, or
  goal node.
- `intent corpus`: returns requirements with linked goals and code entities.
- MCP read tools mirror the three intent read primitives and remain local-only.

## Migration And Compatibility

Schema v2 is additive. It does not rewrite approved requirement text, baselines,
verification evidence, or events. Existing precursor trace links remain valid.
ADR-029-style entity associations become the canonical local binding surface for
code-to-requirement links.

## Authority Boundaries

- Loomweave owns SEI identity and lineage.
- Filigree owns tactical work tracking.
- Legis owns policy enforcement and audit.
- Plainweave owns local intent facts and readable trace context only.

## Deferred

- Live Loomweave catalog adapter.
- Live Legis advisory fact adapter.
- Semantic similarity hint.
- Formal suite admission and public release.
