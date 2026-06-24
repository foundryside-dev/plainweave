# PDR-008: Cross-Member Seam Validated on Live Peers (Lacuna, Loomweave)

Date: 2026-06-24   Status: accepted   Author: agent:claude-product-owner   Owner sign-off: n/a (within grant; peer dogfood run per owner direction this session)
Related: PDR-004 (cross-member seam policy), PDR-005, PDR-006, tracker plainweave-7be2817d58

## Context

PDR-005 proved the golden vector on Plainweave itself; PDR-006 flagged the north-star
denominator as degraded on Plainweave's own catalog. The cross-member seam (PDR-004)
had never been exercised under *real peer* data. Per owner direction, ran the dogfood
against two live siblings — Lacuna and Loomweave — reading each peer's own Loomweave
catalog read-only and building the corpus in a scratch store (both peer repos left pristine).

## Options considered

1. Treat the self-dogfood as sufficient — but leaves PDR-004 unexercised on real peers.
2. Dogfood two live peers, deliberately one with degraded coverage and one with complete
   coverage, to test both the seam and the honest-degradation behavior on real catalogs.

## The call

Option 2. Results:

| Peer | Catalog coverage | Public surfaces | Recorded / bound | Honest orphans | North-star | Denominator |
|------|------------------|-----------------|------------------|----------------|------------|-------------|
| Lacuna | incomplete (2/4 tag classes) | 4 | 4 / 3 | 1 | 3/4 = 75% | QUALIFIED |
| Loomweave | **complete (4/4)** | 45 | 45 / 10 | 35 | 10/45 = 22% | **TRUSTWORTHY** |

Both: SEIs consumed opaquely (none minted), no release/allow/block verdict, bindings carry
`agent:` provenance, `trace` resolves code→requirement→goal, `orphans` honestly lists the
unjustified surfaces. The seam holds on both.

## Rationale

This validates PDR-004 under real peer data on two distinct siblings and **de-risks PDR-006**:
the coverage gap is a *per-repo* Loomweave-catalog-tagging property, not a Plainweave
limitation — on a complete-coverage peer (Loomweave) the north-star is honestly computable
over the full public surface. A secondary finding (Loomweave's public-surface tags include
`tests.perf.*` / `scripts.check-*` entry-points, inflating the denominator) is filed as
plainweave-7be2817d58 for Plainweave-side surface-class scoping. Does not supersede PDR-006;
refines its outlook.

## Reversal trigger

Reopen if a future complete-coverage peer cannot produce honest trace/orphan results, or if
the seam ever emits a non-degraded (false-clean) result against a peer catalog that is
actually degraded.
