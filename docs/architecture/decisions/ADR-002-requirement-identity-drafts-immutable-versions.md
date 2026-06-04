# ADR-002: Requirement Identity, Drafts, And Immutable Versions

**Status**: Proposed
**Date**: 2026-06-04
**Deciders**: Charter maintainers
**Context**: Charter must prevent accidental mutation of approved requirement text while keeping draft editing lightweight.

## Summary

Charter will separate requirement identity, mutable drafts, and immutable approved versions into distinct model concepts and storage tables.

## Context

The first planning pack placed fields such as `statement` near the requirement identity row and in version rows. That risks ambiguity: an implementation could mutate approved text by updating the identity row. Charter needs a hard boundary between identity and content.

## Decision

We will model:

- `requirements`: stable identity, human-readable ID, current pointers, aggregate status, classification fields;
- `requirement_drafts`: mutable draft content and proposed revisions;
- `requirement_versions`: immutable approved content snapshots.

Approved versions are never updated. Revisions create new drafts and, after approval, new version rows. Requirement IDs are never reused.

## Alternatives Considered

### Alternative 1: Single mutable `requirements` table

**Pros**:
- Simple schema.
- Easy CLI implementation.

**Cons**:
- Approved text can be mutated accidentally.
- Harder to prove version immutability.
- Weak audit posture.

**Why rejected**: It violates Charter's core obligation/version authority.

### Alternative 2: Event sourcing only

**Pros**:
- Full historical reconstruction.
- Natural audit trail.

**Cons**:
- Too heavy for v0.1.
- More complex queries and migrations.

**Why rejected**: Append-only events are required, but current-state tables keep v0.1 small.

## Consequences

### Positive

- Approved requirement text is protected structurally.
- Supersede/deprecate behavior is explicit.
- State-machine and database tests can prove immutability.

### Negative

- More tables and joins in v0.1.
- CLI commands need clear draft/version language.

## Implementation Notes

State machine:

```text
draft -> approved -> draft_revision -> approved
draft -> rejected
approved -> deprecated
approved -> superseded
```

Storage baseline:

```text
requirements(id, stable_id, current_version, active_draft_id, status, type, criticality, ...)
requirement_drafts(draft_id, requirement_id, base_version, title, statement, ...)
requirement_versions(requirement_id, version, title, statement, statement_hash, approved_by, ...)
```

Every approving mutation requires `actor`, `idempotency_key`, and `expected_version` where applicable.

## Related Decisions

- ADR-001: Charter authority boundary.
- ADR-003: Trace-link ontology and authority states.
- ADR-004: CLI/MCP JSON envelope and error policy.
