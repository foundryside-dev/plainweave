# Plainweave Current State

## As Of

2026-06-21

## Product State

Plainweave has moved from Charter precursor requirements-down framing toward a
code-up intent corpus. The precursor local core remains useful: requirements,
drafts, immutable versions, acceptance criteria, trace links, baselines,
verification evidence, dossiers, JSON envelopes, and read-only MCP patterns.

## Implemented Beta Foundation

- Schema v2 adds strategic goals, goal-requirement edges, code entities, and
  ADR-029-style entity associations.
- Service APIs support goal creation, goal linking, code entity recording, SEI
  binding, drift checks, and graph reads.
- CLI surfaces expose `catalog record`, `goal add`, `goal link`, `bind sei`,
  `intent orphans`, `intent trace`, and `intent corpus`.
- MCP exposes read-only `plainweave_intent_orphans`,
  `plainweave_intent_trace`, and `plainweave_intent_corpus`.

## Active Tracker Anchors

- `plainweave-44a6af082d`: intent graph data model.
- `plainweave-05f7868df0`: ADR-029 SEI binding.
- `plainweave-3a04bb7ff8`: read primitives.
- `plainweave-fba96e383e`: authoring-time write surface.

The tracker remains the tactical source of truth; this workspace records product
state and decisions, not a duplicate backlog.
