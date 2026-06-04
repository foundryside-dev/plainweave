# ADR-003: Trace-Link Ontology And Authority States

**Status**: Proposed
**Date**: 2026-06-04
**Deciders**: Charter maintainers
**Context**: Charter's highest product risk is agent-generated traceability that looks accepted but is not trustworthy.

## Summary

Charter will use a fixed trace-link ontology with canonical relation direction and explicit authority/freshness states. Agents may propose traceability freely, but accepted traceability is a separate state.

## Context

Requirements traceability fails when links are inconsistent or unverifiable. Agentic workflows increase the risk because agents can create many plausible links quickly. Charter must enable this productivity without creating false certainty.

## Decision

We will define a canonical trace graph:

- relation direction is fixed in storage;
- accepted, proposed, inferred, imported, stale, and orphaned states are distinct;
- high-risk link classes require acceptance by default;
- stale and orphaned links are retained, not deleted.

Canonical examples:

```text
clarion_entity --satisfies--> requirement_version
file_ref --fragile_satisfies--> requirement_version
verification_method --verifies--> requirement_version
verification_record --evidences--> verification_method
test_selector --provides_evidence_for--> verification_method
filigree_issue --implements_work_for--> requirement_version
filigree_issue --resolves_gap--> gap
wardline_finding --violates--> acceptance_criterion
legis_attestation --attests--> requirement_version
```

## Alternatives Considered

### Alternative 1: Free-form relations

**Pros**:
- Flexible.
- Easy to add new relation names.

**Cons**:
- Agents create equivalent but incompatible graphs.
- Impact analysis becomes unreliable.
- Contract tests cannot enforce meaning.

**Why rejected**: Charter needs machine-usable traceability, not prose tags.

### Alternative 2: Only accepted links

**Pros**:
- Simple authority model.
- Less review burden in data model.

**Cons**:
- Agents cannot safely assist with discovery.
- Valuable suggestions are lost.
- Forces either manual-only traceability or false accepted links.

**Why rejected**: Proposed links are central to agent-first workflow.

## Consequences

### Positive

- Agents can propose links without fabricating project truth.
- Impact analysis has stable graph semantics.
- Contract fixtures can reject inverted or ambiguous relations.

### Negative

- New relation types require ADR-backed schema evolution.
- Users need link-review workflow for accepted traceability.

## Implementation Notes

Trace states:

```text
proposed -> accepted
proposed -> rejected
proposed -> stale
accepted -> stale
accepted -> orphaned
stale -> proposed
stale -> accepted
stale -> rejected
orphaned -> proposed
orphaned -> rejected
```

Default acceptance policy:

- Agents may create `agent_proposed` links.
- High, safety, and security requirement links to code entities, Wardline findings, Legis attestations, or manual attestations require acceptance.
- Low-criticality test links may be auto-accepted only if project policy enables it.

## Related Decisions

- ADR-001: Charter authority boundary.
- ADR-002: Requirement identity, drafts, and immutable versions.
- ADR-004: CLI/MCP JSON envelope and error policy.
- ADR-005: Clarion SEI consumer contract.
