# Plainweave SDLC Readiness Package

## Purpose

This package advances Plainweave from architecture seed to implementation-ready
SDLC artifacts. It does not approve product code by itself. Product code may
start only after the listed ADRs and v0.1 implementation plan are approved.

## Inputs

- [Concept](../../concept.md)
- [Plainweave v0.1 Product Design](2026-06-04-plainweave-v0.1-product-design.md)
- [Interface Contract Hardening](2026-06-04-plainweave-interface-contract-hardening.md)

## New Artifacts

### Prioritized ADR Set

- [ADR-001: Plainweave Authority Boundary](../../architecture/decisions/ADR-001-plainweave-authority-boundary.md)
- [ADR-002: Requirement Identity, Drafts, And Immutable Versions](../../architecture/decisions/ADR-002-requirement-identity-drafts-immutable-versions.md)
- [ADR-003: Trace-Link Ontology And Authority States](../../architecture/decisions/ADR-003-trace-link-ontology-authority-states.md)
- [ADR-004: CLI/MCP JSON Envelope And Error Policy](../../architecture/decisions/ADR-004-cli-mcp-json-envelope-error-policy.md)
- [ADR-005: Loomweave SEI Consumer Contract](../../architecture/decisions/ADR-005-loomweave-sei-consumer-contract.md)
- [ADR-006: Legis Preflight Fact Envelope](../../architecture/decisions/ADR-006-legis-preflight-fact-envelope.md)

### Traceability, Fixtures, And Gates

- [v0.1 Requirements Traceability Matrix](2026-06-04-plainweave-v0.1-traceability-matrix.md)
- [Contract Fixture Plan](2026-06-04-plainweave-contract-fixture-plan.md)
- [v0.1 Quality Gates](2026-06-04-plainweave-v0.1-quality-gates.md)

### Implementation Plan

- [v0.1 Local Core Implementation Plan](../plans/2026-06-04-plainweave-v0.1-local-core.md)
- [v0.1 Work Package Execution Guide](../plans/2026-06-04-plainweave-v0.1-work-package-execution-guide.md)

## v0.1 Scope Lock

Included:

- local requirements;
- requirement drafts;
- immutable approved versions;
- acceptance criteria;
- manual/proposed trace links;
- JSON CLI envelopes;
- state-machine and contract tests.

Deferred:

- verification records;
- baselines;
- impact engine;
- MCP mutations;
- Loomweave, Filigree, Wardline, and Legis integrations;
- future scoped-change execution authority.

## Approval Gates Before Product Code

1. ADR-001 through ADR-004 accepted.
2. ADR-005 and ADR-006 reviewed as federation guardrails.
3. RTM reviewed and v0.1 scope confirmed.
4. Contract fixture plan approved.
5. Quality gates approved.
6. v0.1 local-core implementation plan approved.

## Current Filigree Status

Filigree is configured for this repository. Initial issue capture on
2026-06-04 created the following tracker structure:

- `plainweave-2a548f14fb`: Plainweave v0.1 SDLC approval gate.
- `plainweave-04ecdc322a`: Review ADR-001 Plainweave authority boundary.
- `plainweave-3f4fc656fb`: Review ADR-002 requirement identity and versions.
- `plainweave-ee1d904f04`: Review ADR-003 trace-link ontology and authority states.
- `plainweave-b77e2069c6`: Review ADR-004 CLI/MCP envelope and error policy.
- `plainweave-25cd8816c7`: Review ADR-005 Loomweave SEI consumer contract.
- `plainweave-74041bea47`: Review ADR-006 Legis preflight fact envelope.
- `plainweave-bb5223159d`: Review v0.1 RTM, contract fixtures, and quality gates.
- `plainweave-76a416ec15`: Approve v0.1 local-core implementation plan.
- `plainweave-282796b001`: Implement Plainweave v0.1 local core.

The implementation package and all ten child implementation steps are blocked
on `plainweave-76a416ec15`. That approval item is blocked by the ADR, RTM,
contract-fixture, and quality-gate review deliverables above.
