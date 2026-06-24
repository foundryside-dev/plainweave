# Plainweave Beta Metrics

## North Star

At least 90 percent of sampled public surfaces in the beta proving repo can
answer "why does this exist?" through `SEI -> requirement -> goal`.

> CAVEAT (PDR-009, supersedes PDR-006): the north-star is now self-computed by the
> `intent_coverage` primitive. Every reading is qualified IN-BAND by three signals that
> must travel with any number: (a) namespace scoping (default `tests.`/`scripts.` excluded
> — "public surface" means the real exported API); (b) `denominator_complete` (tag-class
> completeness only — NOT language coverage); (c) `present_plugins` (the catalog's language
> span). A `denominator_complete=true` reading can still be language-partial. Publishing a
> headline number remains owner-gated (PDR-002).

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

## Readings

### 2026-06-24 — Plainweave self-dogfood (PDR-005)

| Metric | Reading |
|--------|---------|
| Public code entities recorded | 2 (`cli.main`, `mcp_server.main`) |
| Code entities bound to requirements | 2 |
| Requirements linked to goals | 2 |
| Orphan code entities / orphan requirements | 0 / 0 |
| Corpus rows with both goal and code context | 2 |
| **North-star** | 100% of the explicitly-tagged public surface (2/2); **full-surface % indeterminate** — denominator degraded (PDR-006, plainweave-44be10cc2c) |

Guardrails — all intact: 0 SEIs minted (consumed opaquely); 0 release/allow/block
verdicts; bindings carry an `agent:` actor (not human-accepted truth); 0 silent-clean
results — the catalog honestly reported degraded coverage. No reversal trigger fired.

### 2026-06-24 — Live peer dogfood (PDR-008)

Read each peer's own Loomweave catalog (read-only); corpus built in a scratch store
(peer repos untouched). Demonstrates the cross-member seam (PDR-004) on real peers.

| Peer | Catalog coverage | Public surfaces | Recorded / bound | Honest orphans | North-star | Denominator |
|------|------------------|-----------------|------------------|----------------|------------|-------------|
| Lacuna | incomplete (2/4) | 4 | 4 / 3 | 1 | 75% | qualified |
| Loomweave | **complete (4/4)** | 45 | 45 / 10 | 35 | 22% | **trustworthy** |

Takeaway: the coverage gap (PDR-006 / plainweave-44be10cc2c) is per-repo — on a
complete-coverage peer the north-star is honestly computable. Secondary finding: the
public-surface set includes test/perf/CI-script entry-points (plainweave-7be2817d58).
Guardrails intact on both peers; no reversal trigger fired.

### 2026-06-24 — intent_coverage primitive shipped; north-star now self-computable (PDR-009)

**PDR-006's reversal trigger FIRED:** plainweave-44be10cc2c and plainweave-7be2817d58 closed,
so the north-star is no longer coverage-blocked — the product computes it directly via
`plainweave intent coverage`. Re-read against the Loomweave peer (catalog complete, 4/4):

| Scope | Denominator | Excluded | denominator_complete | present_plugins |
|-------|-------------|----------|----------------------|-----------------|
| default (excl. `tests.`/`scripts.`) | **1** | 44 | true | core, python, rust |
| no exclusion | 45 | 0 | true | core, python, rust |

Reading: the real exported-API denominator on Loomweave is **1** (`plugins.python…server.main`);
the other 44 public-tagged surfaces are vendored `elspeth_mini` / `check-*` harness — the 22%
(10/45) figure from PDR-008 was the *unscoped* number. `present_plugins` exposes that the catalog
spans core/python/rust while every tagged public surface is `python:` — the Rust public surface is
untagged upstream (the cross-member coverage gap; owner-gated). Numerator over the committed
Plainweave intent DB is 0 (no bindings ladder Loomweave's surfaces; the dogfood's 10 were
throwaway) — an honest 0, not a defect.

Guardrails — all intact: advisory only, verdict vocabulary machine-rejected by the contract
validator; SEIs consumed opaquely; no silent-clean (degraded tag-classes AND language-partial spans
both flagged in-band). The release review fixed a real honesty defect (surfaces bound to *deprecated*
requirements were inflating the numerator). No NEW reversal trigger fired.
