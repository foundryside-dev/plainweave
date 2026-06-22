# PDR-003: Defer Semantic Similarity Until Core Loop Works

## Status

Accepted for beta candidate.

## Context

Semantic similarity could help find related requirements, but it can also blur
Plainweave into a deduplication engine before the basic code-up graph proves
value.

## Decision

Defer Loomweave semantic similarity hints until goals, bindings, read
primitives, and the golden vector are working. Semantic hints remain advisory
only and must not emit consolidation verdicts.

## Reversal Trigger

Revisit if corpus curation becomes blocked specifically by missing similarity
signals after the core loop is green.
