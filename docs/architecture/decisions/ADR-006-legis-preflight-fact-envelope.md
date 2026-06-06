# ADR-006: Legis Preflight Fact Envelope

**Status**: Accepted
**Date**: 2026-06-04
**Deciders**: Charter maintainers
**Context**: Legis owns commit/preflight governance. Charter must contribute requirement facts without deciding gates.

## Summary

Charter will expose a versioned `weft.charter.preflight_facts.v1` envelope for Legis. The envelope contains scoped facts, provenance, freshness, and summary counts. It does not contain commit allow/block decisions.

## Context

Legis Chill mode is valuable as a single-shot fault-and-context report. Charter should contribute impacted requirements, stale verification, missing traceability, baseline drift, and linked work/finding facts. Legis decides how these facts affect the boundary.

## Decision

Charter will provide preflight facts with:

- `schema`;
- `producer` metadata including tool, version, and project;
- `scope` describing pending diff or commit range;
- `generated_at`;
- top-level `freshness`;
- `facts[]`;
- summary counts for `info`, `warn`, and `block_candidate`;
- warnings.

Charter may classify a fact as `block_candidate`, but Legis alone decides whether the configured mode blocks, coaches, surfaces, or records override.

## Alternatives Considered

### Alternative 1: Return human text only

**Pros**:
- Easy to show in preflight output.

**Cons**:
- Legis would parse prose.
- Facts would not be stable across versions.

**Why rejected**: Legis needs structured facts independent of Charter internals.

### Alternative 2: Charter decides pass/fail

**Pros**:
- Simple local gate.
- Good for standalone CI scripts.

**Cons**:
- Violates Legis authority.
- Pulls governance into Charter.

**Why rejected**: Charter exposes facts; Legis governs.

## Consequences

### Positive

- Legis integration is versioned and testable.
- Charter can provide Chill value without becoming a gate.
- Consumers do not need Charter table knowledge.

### Negative

- Requires early contract fixture discipline.
- Some local users may still want `--fail-on`; that must remain local advisory behavior, not Legis governance.

## Implementation Notes

Initial fact kinds:

```text
requirement_touched
requirement_nearby
requirement_verification_stale
requirement_verification_missing
baseline_drift
trace_gap
open_linked_work
active_finding_linked
waived_finding_linked
orphaned_entity_link
untraced_change
```

## Related Decisions

- ADR-001: Charter authority boundary.
- ADR-004: CLI/MCP JSON envelope and error policy.
- ADR-005: Clarion SEI consumer contract.

## Federation References

The `weft.charter.preflight_facts.v1` envelope defined here is Charter-owned;
this ADR is its authoritative spec. It is registered in the Loom hub's
cross-product contract index for discovery: `~/loom/contracts-index.md`. The
federation model and SEI keying it builds on are authoritative in
`~/loom/doctrine.md` and `~/loom/sei-standard.md`.
