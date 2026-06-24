# PDR-006: North-Star Is Coverage-Blocked Pending Catalog Completeness

Date: 2026-06-24   Status: superseded by PDR-009   Author: agent:claude-product-owner   Owner sign-off: n/a (within grant)
Related: metrics.md (north-star, guardrails), tracker plainweave-44be10cc2c, PDR-005
Superseded: 2026-06-24 by PDR-009 — its reversal trigger fired (plainweave-44be10cc2c closed); the north-star is now self-computable via the intent_coverage primitive, with the qualification discipline carried forward.

## Context

metrics.md's north-star is "≥90% of sampled public surfaces can answer 'why does this
exist?' via SEI→requirement→goal." The self-dogfood (PDR-005) justified 2/2 of the
*explicitly-tagged* public surfaces, but `plainweave_loomweave_catalog_list` returns
`coverage.complete=false`: of the four public-surface tag classes
[cli-command, entry-point, exported-api, http-route] only `entry-point` is present;
the other three are absent and visibility is `unknown` for all non-entry-point
entities. The north-star *denominator* is degraded.

## Options considered

1. Report north-star as 100% (2/2 of what's tagged) — looks like a pass, but treats a
   known-incomplete denominator as complete: a vanity metric and a silent-clean result.
2. Report north-star as measurable-but-coverage-blocked, qualified to the tagged
   surface, and file the denominator gap — honest and actionable; no headline pass yet.
3. Record nothing until full coverage — clean, but hides a real reproducible reading
   and the dependency gap.

## The call

Option 2. North-star recorded as "100% of the explicitly-tagged public surface (2/2);
full-surface percentage indeterminate — denominator degraded." Filed
`plainweave-44be10cc2c` for the catalog coverage gap.

## Rationale

A percentage over a known-incomplete denominator is a vanity metric. Plainweave's own
guardrail — "zero silent-clean results when peer context is absent or stale" — demands
the degradation be reported, not papered over. The in-scope Plainweave-side fix (surface
`coverage.complete` to any north-star computation) is captured on the ticket; the
catalog-tagging fix is Loomweave-side and **owner-driven** (a sibling obligation).

## Reversal trigger

Revisit the north-star's measurability when `plainweave-44be10cc2c` closes (catalog
emits cli-command/exported-api/http-route + visibility) or an alternate public-surface
enumeration is available. Until then every north-star reading MUST be qualified to the
measurable surface.
