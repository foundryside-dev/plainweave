# ADR-005: Clarion SEI Consumer Contract

**Status**: Accepted
**Date**: 2026-06-04
**Deciders**: Charter maintainers
**Context**: Clarion owns code identity and SEI. Charter needs rename-resilient requirement-to-code links without becoming an identity authority.

## Summary

Charter will consume Clarion SEI as an opaque peer identifier. It may store SEI values and snapshots in trace links, but it will never derive, parse, mint, or reinterpret SEI.

## Context

Charter's first killer federation workflow is requirement impact that survives code moves and renames. That requires Clarion SEI. The same integration can accidentally violate Loom boundaries if Charter starts making identity decisions.

## Decision

When Clarion is present and advertises required capabilities, Charter will:

- resolve user-provided file/line/symbol/locator inputs through Clarion;
- store `clarion_entity` trace targets using opaque SEI;
- store a target snapshot with locator, content hash, lineage status, Clarion version, and observed time;
- mark links stale or orphaned based on Clarion refresh results;
- degrade to fragile file/symbol refs when Clarion or SEI is absent.

## Alternatives Considered

### Alternative 1: Store file paths and symbols only

**Pros**:
- Works without Clarion.
- Simple v0.1 implementation.

**Cons**:
- Links rot on rename/move.
- Fails the first high-value Charter + Clarion workflow.

**Why rejected as primary**: Fragile refs are fallback only.

### Alternative 2: Charter derives stable IDs

**Pros**:
- Reduces dependency on Clarion availability.
- Could work for simple Python cases.

**Cons**:
- Violates Clarion authority.
- Creates competing identity scheme.
- Breaks Loom federation.

**Why rejected**: Clarion owns identity.

## Consequences

### Positive

- Requirement links can survive rename/move.
- Identity failure is visible through stale/orphaned states.
- Charter remains an SEI consumer only.

### Negative

- Entity-grade impact requires Clarion availability and capability freshness.
- Charter must handle peer absence and stale capability state carefully.

## Implementation Notes

Refresh outcomes:

```text
same SEI + same hash -> current
same SEI + changed hash -> accepted link stays, verification becomes stale
lineage alive + locator changed -> update snapshot, keep link
SEI orphaned -> link orphaned, create trace_orphaned gap
Clarion absent -> freshness unknown, no destructive mutation
```

## Related Decisions

- ADR-001: Charter authority boundary.
- ADR-003: Trace-link ontology and authority states.
- ADR-004: CLI/MCP JSON envelope and error policy.
