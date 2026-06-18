# ADR-001: Plainweave Authority Boundary

**Status**: Accepted
**Date**: 2026-06-04
**Deciders**: Plainweave maintainers
**Context**: Plainweave must enter Weft as a peer federation member, not as a hidden suite runtime or an extension of an existing tool.

## Summary

Plainweave will be the local-first requirements and verification authority for Weft. It owns obligations, versions, criteria, traceability, baselines, verification facts, and requirement dossiers. It does not own peer tool authorities.

## Context

Weft is a federation. Each product owns one kind of truth and remains useful alone. (The federation axiom, composition law, and authoritative roster are owned by the Weft hub: `~/weft/doctrine.md`. This ADR restates them only as context for Plainweave's own boundary, which is what it actually decides.) Plainweave must therefore satisfy three tests:

- useful as a standalone requirements and verification tool;
- additive with each peer;
- incapable of silently taking over Loomweave, Filigree, Wardline, Legis, or future scoped-change authority.

## Decision

We will define Plainweave's authority as:

- requirements and immutable approved requirement versions;
- requirement drafts;
- acceptance criteria;
- trace links and their authority/freshness states;
- verification methods and evidence records;
- baselines and baseline status;
- requirement gaps;
- requirement dossiers and impact reports.

Plainweave will not own:

- code identity, SEI, code graph, summaries, or lineage;
- issue lifecycle, claims, dependencies, or work scheduling;
- taint analysis, trust policy findings, waivers, or suppressions;
- git/CI gate decisions, sign-offs, attestations, or override trails;
- execution transactions or rollback provenance.

## Alternatives Considered

### Alternative 1: Make Plainweave a Filigree extension

**Pros**:
- Fastest to add requirement-shaped work items.
- Reuses issue lifecycle and dashboard concepts.

**Cons**:
- Requirements become workflow state, not obligations.
- Verification and baselines would be subordinate to issue lifecycle.
- Violates Weft's one-authority-per-tool model.

**Why rejected**: Plainweave's value is independent requirements truth. Filigree should track work derived from Plainweave gaps, not own the gaps or obligations.

### Alternative 2: Make Plainweave a Legis policy module

**Pros**:
- Direct preflight integration.
- Strong governance story from the start.

**Cons**:
- Turns requirements into gate inputs only.
- Makes standalone use weak.
- Risks commit-blocking behavior becoming the product center.

**Why rejected**: Plainweave must remain useful where Legis is absent and must not decide commit allow/block.

## Consequences

### Positive

- Plainweave can be used alone by small projects.
- Peer integrations remain additive and capability-gated.
- Authority boundaries are testable in contracts.

### Negative

- More explicit integration contracts are needed.
- Some workflows require two facts: Plainweave gap plus Filigree issue, or Plainweave evidence plus Legis sign-off.

### Neutral

- Plainweave may store opaque peer identifiers, but the peer remains authoritative for their meaning.

## Implementation Notes

- Every peer-derived fact must carry `source`, `authority`, and `freshness`.
- Plainweave must never treat peer absence as evidence of cleanliness or satisfaction.
- Plainweave docs must include the local security boundary: no encryption or access control beyond filesystem/repository protections.

## Related Decisions

- ADR-002: Requirement identity, drafts, and immutable versions.
- ADR-003: Trace-link ontology and authority states.
- ADR-005: Loomweave SEI consumer contract.
- ADR-006: Legis preflight fact envelope.
