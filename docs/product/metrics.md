# Plainweave Beta Metrics

## North Star

At least 90 percent of sampled public surfaces in the beta proving repo can
answer "why does this exist?" through `SEI -> requirement -> goal`.

## Input Metrics

- Count of public code entities recorded from the catalog.
- Count of code entities bound to requirements.
- Count of requirements linked to goals.
- Count of orphan code entities and orphan requirements.
- Count of corpus rows with both goal and code context.

## Guardrails

- Zero Plainweave allow/block release decisions.
- Zero Plainweave-minted SEIs.
- Zero agent-created bindings represented as accepted human truth.
- Zero silent-clean results when peer context is absent or stale.

## Validation Method

Run the golden vector on Plainweave first, then on Loomweave as the default
representative sibling. Sample public surfaces, compute trace coverage, and
inspect orphan output for honest gaps.
