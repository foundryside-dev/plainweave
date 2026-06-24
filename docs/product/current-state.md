# Plainweave Current State        Checkpoint: 2026-06-24 · (commit recorded below)

## The bet right now

The north-star is now **self-computable inside the product** — the `intent_coverage`
primitive (PDR-009) shipped to `main`, computing "what fraction of in-scope public
surfaces answer 'why does this exist?'" with the honesty qualifiers in-band. The
computability bet is delivered. The open frontier is **coverage *completeness***: the
headline number leans on namespace scoping and on the peer's plugin tagging, and the
Rust public surface is untagged upstream. Metric: north-star.

## In flight

- **Lacuna demonstration mix** — keep a deliberate covered + uncovered specimen so the
  intent reads show a real *partial* reading, not a clean 100%/0%. Owner notes this is
  being driven via Plainweave. · metric: north-star (demo).
- **Dogfood more peers** as desired — standing activity (PDR-008); the seam holds on
  Lacuna + Loomweave.
- **Pre-alpha preflight perf** — fan-out cap + N+1 connections; deferred until a real
  corpus makes them bite. · tracker: plainweave-706d80dc8e, plainweave-3edcd19943 (P3).
- **Semantic-similarity hint** — DEFERRED by PDR-003. · tracker: plainweave-02376962ab.

## Open questions / blocked-on-owner

- **Cross-member coverage completeness (owner-raised, most-pressing gap).** A peer's
  north-star can only cover languages whose public surface its Loomweave plugin tags. The
  Rust plugin's tagging is weak: on Loomweave `present_plugins` = core/python/rust, yet all
  45 tagged public surfaces are `python:`. Plainweave already *surfaces* the gap
  (`present_plugins`); closing it upstream is a **sibling obligation → owner-gated** (do not
  file a Loomweave ticket unilaterally). DECIDE next: drive the Loomweave-side Rust tagging
  (owner's call) vs. Plainweave-side accommodation only.
- **Publishing a headline north-star number remains owner-gated** (publication, PDR-002).
  It is now computable, but leans on a "what counts as the product's API" judgment — the
  real-API denominator on Loomweave is **1** (44/45 are test/CI harness).
- **vision.md authority-grant metadata** (`Granted by` / `Last reviewed` / `Review cadence`)
  still missing; adding them is a vision edit → gates to owner (carried from last checkpoint).

## Last checkpoint did

- Built + shipped the `intent_coverage` read primitive to `main` (PDR-009); closed
  plainweave-44be10cc2c + plainweave-7be2817d58. North-star self-computable, qualified
  in-band (scoping, `denominator_complete`, `present_plugins`).
- Reviewed adversarially (15-agent pass, 0 blockers); fixed a deprecated-requirement
  numerator-inflation honesty defect; added P-A/B/C hardening (surface-class discoverability,
  `max_surfaces` bounded evidence, `present_plugins` language-span signal).
- Resolved the intent_trace design question — kept the explain/count split (plainweave-52b743d5b9
  closed; recommendation in comment 14). Flagged PDR-006's reversal trigger fired; logged the
  live-peer scoped reading in metrics.md (real-API denom=1; present_plugins=core/python/rust).

## Next session, start here

DECIDE the most pressing **coverage-completeness** gap the owner raised: cross-member
language coverage — the peer Rust public surface is untagged. Confirm with the owner whether
to drive the Loomweave-side Rust public-surface tagging (owner-gated sibling obligation) or
limit Plainweave to honestly surfacing the gap. This moves the north-star's *completeness*,
not just its computability.
