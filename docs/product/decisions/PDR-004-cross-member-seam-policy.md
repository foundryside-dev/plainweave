# PDR-004: Keep Cross-Member Seams Additive And Authority-Preserving

## Status

Accepted for beta candidate.

## Context

Plainweave needs facts from Loomweave and Legis, but those products own their
respective authority surfaces.

## Decision

Plainweave adapters must be additive and explicit:

- Consume Loomweave SEIs opaquely; do not mint or reinterpret them.
- Emit Legis advisory facts only; do not decide allow/block outcomes.
- Use versioned envelopes.
- Report degraded or absent peer context honestly.

## Reversal Trigger

Revisit only with owner approval and a suite-level architecture decision.
