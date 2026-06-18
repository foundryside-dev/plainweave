# ADR-005: Loomweave SEI Consumer Contract

**Status**: Accepted
**Date**: 2026-06-04
**Deciders**: Plainweave maintainers
**Context**: Loomweave owns code identity and SEI. Plainweave needs rename-resilient requirement-to-code links without becoming an identity authority.

## Summary

Plainweave will consume Loomweave SEI as an opaque peer identifier. It may store SEI values and snapshots in trace links, but it will never derive, parse, mint, or reinterpret SEI.

## Context

Plainweave's first killer federation workflow is requirement impact that survives code moves and renames. That requires Loomweave SEI. The same integration can accidentally violate Weft boundaries if Plainweave starts making identity decisions.

The Stable Entity Identity standard Plainweave conforms to as a consumer is owned by the Weft hub: `~/weft/sei-standard.md` (Loomweave is the identity authority/implementer; Plainweave is a consumer). This ADR records only Plainweave's consumer-side contract; the SEI shape itself is normative there.

## Decision

When Loomweave is present and advertises required capabilities, Plainweave will:

- resolve user-provided file/line/symbol/locator inputs through Loomweave;
- store `loomweave_entity` trace targets using opaque SEI;
- store a target snapshot with locator, content hash, lineage status, Loomweave version, and observed time;
- mark links stale or orphaned based on Loomweave refresh results;
- degrade to fragile file/symbol refs when Loomweave or SEI is absent.

## Alternatives Considered

### Alternative 1: Store file paths and symbols only

**Pros**:
- Works without Loomweave.
- Simple v0.1 implementation.

**Cons**:
- Links rot on rename/move.
- Fails the first high-value Plainweave + Loomweave workflow.

**Why rejected as primary**: Fragile refs are fallback only.

### Alternative 2: Plainweave derives stable IDs

**Pros**:
- Reduces dependency on Loomweave availability.
- Could work for simple Python cases.

**Cons**:
- Violates Loomweave authority.
- Creates competing identity scheme.
- Breaks Weft federation.

**Why rejected**: Loomweave owns identity.

## Consequences

### Positive

- Requirement links can survive rename/move.
- Identity failure is visible through stale/orphaned states.
- Plainweave remains an SEI consumer only.

### Negative

- Entity-grade impact requires Loomweave availability and capability freshness.
- Plainweave must handle peer absence and stale capability state carefully.

## Implementation Notes

Refresh outcomes:

```text
same SEI + same hash -> current
same SEI + changed hash -> accepted link stays, verification becomes stale
lineage alive + locator changed -> update snapshot, keep link
SEI orphaned -> link orphaned, create trace_orphaned gap
Loomweave absent -> freshness unknown, no destructive mutation
```

## Related Decisions

- ADR-001: Plainweave authority boundary.
- ADR-003: Trace-link ontology and authority states.
- ADR-004: CLI/MCP JSON envelope and error policy.

## Federation References

- SEI standard (authoritative): `~/weft/sei-standard.md`.
- Cross-product contract index: `~/weft/contracts-index.md`.
