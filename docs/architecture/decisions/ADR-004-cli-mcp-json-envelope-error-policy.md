# ADR-004: CLI/MCP JSON Envelope And Error Policy

**Status**: Proposed
**Date**: 2026-06-04
**Deciders**: Charter maintainers
**Context**: Agent-facing CLI and MCP surfaces must be structured, retry-safe, and recoverable.

## Summary

Charter will use versioned JSON envelopes for CLI `--json`, MCP responses, and contract fixtures. Mutating tools will declare side-effect metadata and support actor attribution, idempotency, and dry-run behavior where useful.

## Context

Agents should not scrape human prose or infer recovery behavior from stack traces. Charter also needs consistent contract tests before product code expands.

## Decision

We will standardize:

- success envelope: `schema`, `ok`, `data`, `warnings`, `meta`;
- error envelope: `schema`, `ok: false`, `error.code`, `message`, `recoverable`, `hint`, `details`, `meta`;
- list envelope: `items`, `has_more`, `next_offset`;
- batch envelope: `succeeded`, `failed`;
- mutating tool metadata: `mutates`, `idempotent`, `requires_actor`, `requires_human_acceptance`, `supports_dry_run`, `peer_side_effects`, `retry_contract`.

## Alternatives Considered

### Alternative 1: Ad hoc command-specific JSON

**Pros**:
- Fastest to implement.
- Each command can return the smallest possible object.

**Cons**:
- Agents need command-specific recovery logic.
- Contract tests fragment.
- Errors drift across interfaces.

**Why rejected**: Charter's machine interfaces are first-class products.

### Alternative 2: Human text as primary interface

**Pros**:
- Easier early CLI development.
- Nice for manual exploration.

**Cons**:
- Agents scrape prose.
- Error recovery is brittle.
- Violates agent-first requirement.

**Why rejected**: Human text is presentation, not contract.

## Consequences

### Positive

- CLI and MCP parity is testable.
- Agents receive stable recovery hints.
- Retry/idempotency behavior is explicit before mutations ship.

### Negative

- Slight envelope overhead for simple commands.
- Requires fixture discipline from v0.1.

## Implementation Notes

Initial error codes:

```text
VALIDATION
NOT_FOUND
CONFLICT
POLICY_REQUIRED
PEER_ABSENT
PEER_STALE
PEER_CONTRACT
LOCKED
UNSUPPORTED
INTERNAL
```

CLI exit codes:

```text
0 success, including advisory warnings
1 local advisory failure only when --fail-on requests it
2 input/config/protocol error
3 required peer unavailable/stale
4 internal error
```

## Related Decisions

- ADR-002: Requirement identity, drafts, and immutable versions.
- ADR-003: Trace-link ontology and authority states.
- ADR-006: Legis preflight fact envelope.
