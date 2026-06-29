# ADR-006: Legis Preflight Fact Envelope

**Status**: Accepted
**Date**: 2026-06-04
**Deciders**: Plainweave maintainers
**Context**: Legis owns commit/preflight governance. Plainweave must contribute requirement facts without deciding gates.

## Summary

Plainweave will expose a versioned `weft.plainweave.preflight_facts.v1` envelope for Legis. The envelope contains scoped facts, provenance, freshness, and summary counts. It does not contain commit allow/block decisions.

## Context

Legis Chill mode is valuable as a single-shot fault-and-context report. Plainweave should contribute impacted requirements, stale verification, missing traceability, baseline drift, and linked work/finding facts. Legis decides how these facts affect the boundary.

## Decision

Plainweave will provide preflight facts with:

- `schema`;
- `producer` metadata including tool, version, and project;
- `scope` describing pending diff or commit range;
- `generated_at`;
- top-level `freshness`;
- `facts[]`;
- summary counts for `info`, `warn`, and `block_candidate`;
- warnings.

Plainweave may classify a fact as `block_candidate`, but Legis alone decides whether the configured mode blocks, coaches, surfaces, or records override.

## Alternatives Considered

### Alternative 1: Return human text only

**Pros**:
- Easy to show in preflight output.

**Cons**:
- Legis would parse prose.
- Facts would not be stable across versions.

**Why rejected**: Legis needs structured facts independent of Plainweave internals.

### Alternative 2: Plainweave decides pass/fail

**Pros**:
- Simple local gate.
- Good for standalone CI scripts.

**Cons**:
- Violates Legis authority.
- Pulls governance into Plainweave.

**Why rejected**: Plainweave exposes facts; Legis governs.

## Consequences

### Positive

- Legis integration is versioned and testable.
- Plainweave can provide Chill value without becoming a gate.
- Consumers do not need Plainweave table knowledge.

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

### Emission status (annotated 2026-06-29, PDR-018 — seam hardening)

The local-only producer emits **8 of the 11** kinds above. Three are deliberately
**not emitted** by this producer, and their absence is reported in-band as
`info`/`freshness: unavailable` warnings (`linked_work_facts_unavailable`,
`finding_facts_unavailable`) — never as an empty-but-ok fact list (no-silent-clean):

- `active_finding_linked`, `waived_finding_linked` — **superseded** by the dedicated
  `weft.plainweave.wardline_peer_facts.v1` producer (PDR-014), which surfaces the same
  local `.wardline/*-findings.jsonl` data. Wiring them into the preflight envelope as
  well is an owner-gated ADR fork, intentionally **not** taken (PDR-018).
- `open_linked_work` — **sibling-gated**: no in-grant local Filigree source exists
  (`.filigree/` is a Filigree-owned DB; the live `entity_association` read would break
  `authority_boundary.live_peer_calls=false`). Handed off as
  `docs/handoffs/2026-06-29-filigree-linked-work-facts.md`.

Reversal trigger: if a boundary-clean local Filigree facts artifact (mirroring
`.wardline/*.jsonl`) lands, `open_linked_work` becomes emittable in-grant and this
fork reopens.

## Related Decisions

- ADR-001: Plainweave authority boundary.
- ADR-004: CLI/MCP JSON envelope and error policy.
- ADR-005: Loomweave SEI consumer contract.

## Federation References

The `weft.plainweave.preflight_facts.v1` envelope defined here is Plainweave-owned;
this ADR is its authoritative spec. It is registered in the Weft hub's
cross-product contract index for discovery: `~/weft/contracts-index.md`. The
federation model and SEI keying it builds on are authoritative in
`~/weft/doctrine.md` and `~/weft/sei-standard.md`.
