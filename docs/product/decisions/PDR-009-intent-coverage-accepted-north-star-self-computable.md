# PDR-009: intent_coverage Primitive Accepted — North-Star Is Now Self-Computable

Date: 2026-06-24   Status: accepted   Author: agent:claude-product-owner   Owner sign-off: n/a (within grant)
Supersedes: PDR-006 (north-star coverage-blocked posture)
Related: metrics.md (north-star, guardrails), PDR-005, PDR-008, tracker plainweave-44be10cc2c (closed), plainweave-7be2817d58 (closed), plainweave-52b743d5b9 (closed)

## Context

PDR-006 recorded the north-star as coverage-blocked: a reading over a degraded denominator
is a vanity metric, so every reading had to be qualified to the explicitly-tagged surface
until plainweave-44be10cc2c closed. The two in-flight Now bets — surface `coverage.complete`
to any north-star computation (44be10cc2c) and scope test/perf/CI-script namespaces out of
the denominator (7be2817d58) — were the gating work. PDR-006's reversal trigger ("revisit
when 44be10cc2c closes") has now fired: both tickets closed this session.

## Options considered

1. Keep computing the north-star ad hoc (the dogfood's throwaway script) — proven, but
   un-owned by the product; nothing the product itself emits or guards.
2. Build a first-class read primitive that computes the north-star honestly and carries the
   coverage caveat + scoping in its own versioned envelope — the product answers "how
   complete is our intent coverage?" without a side script.

## The call

Option 2. Shipped `intent_coverage` (service + CLI `plainweave intent coverage` + MCP
`plainweave_intent_coverage`, envelope `weft.plainweave.intent_coverage.v1`) to `main`. It
enumerates the public-surface denominator from the Loomweave catalog, counts a surface as
justified iff its SEI ladders up to a *live* (draft/approved) requirement→goal, and carries
the honesty qualifiers in-band:

- `denominator_complete` mirrors catalog tag-class completeness (closes 44be10cc2c);
- default namespace scoping excludes `tests.`/`scripts.` so the denominator is the real
  exported API, caller-overridable (closes 7be2817d58);
- `present_plugins` exposes the catalog's language/plugin span;
- `surfaces_truncated` + `max_surfaces` bound a read's size without truncating counts.

Advisory only — a fact, never a pass/fail on the 90% target; the verdict vocabulary is
machine-rejected by the shared contract validator. Reviewed via a 15-agent adversarial pass
(0 blockers); one real honesty defect fixed.

## Rationale

The product now computes what the dogfood computed by hand, and emits + guards the honesty
the guardrails demand (no silent-clean: a degraded or language-partial denominator is flagged
in-band, not papered over). The review found and fixed a real honesty defect — surfaces bound
to *deprecated* requirements were inflating the numerator — so the count now matches the
product's own definition of a live obligation (consistent with intent_corpus/intent_orphans).

Two honesty qualifiers are load-bearing and SURVIVE this PDR:

- `denominator_complete=true` certifies *tag-class* presence, NOT *language* coverage. On the
  Loomweave peer the catalog spans core/python/rust yet all 45 public surfaces are `python:` —
  `present_plugins` makes that visible so a complete reading is never misread as whole-product.
- The headline number leans heavily on scoping (44 of 45 Loomweave surfaces are test/perf/CI
  harness; the real exported-API denominator is 1). What counts as "the product's API" is a
  publishing-time judgment, not the primitive's to make.

## Reversal trigger

Reopen if (a) a north-star reading is ever presented or published WITHOUT its scoping +
`denominator_complete` + `present_plugins` qualifiers (that re-creates the vanity-metric /
silent-clean failure PDR-006 guarded against), or (b) the default `tests.`/`scripts.` scoping
is shown to systematically mis-scope a real exported API. Publishing an actual headline
north-star number remains owner-gated (publication, PDR-002).
