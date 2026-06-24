# Plainweave Roadmap            Updated: 2026-06-24 (PDR-005, PDR-006)

> Sequencing, WSJF / cost-of-delay, and dated forecasts are produced by
> /axiom-program-management. This file records bets as INTENT, not a delivery
> schedule. Do not compute WSJF here; hand the committed bet over for sequencing.

## Now (committed, in-flight)

- **Dogfood against live sibling peers** — prove the code-up graph and the
  cross-member seam (PDR-004) reproduce on real sibling corpora, not just on
  Plainweave itself. The Loomweave adapter is live; first peers this session per
  owner direction. · tracker: plainweave-c2d58800a0 · metric: north-star.
- **Make the north-star honestly computable** — Plainweave-side: surface
  `coverage.complete` to any north-star computation so a reading is never reported
  complete over a degraded denominator. · tracker: plainweave-44be10cc2c · metric:
  north-star.

## Next (shaped, decreasing certainty)

- **Explicit degraded peer-state envelopes** for live Loomweave and Legis adapters.
- **Contract fixtures** for the intent-graph and binding envelopes (shared
  structural validator already landed for preflight, F5).
- **Bound preflight project-scope fan-out** + revisit the N+1 connection pattern
  once a real corpus makes them bite. · tracker: plainweave-706d80dc8e,
  plainweave-3edcd19943 (currently acceptable at pre-alpha scale).

## Later (directional bets, no order, no dates)

- Optional Loomweave semantic-similarity hint over requirement text — DEFERRED by
  PDR-003; advisory only, never a dedup verdict. · tracker: plainweave-02376962ab.
- Corpus-curation workflows for duplicate or overlapping requirements.
- Formal suite membership package — **owner-gated** (PDR-002).
- Public release and packaging (final name, PyPI, hub roster) — **owner-gated** (PDR-002).

## Done since last checkpoint (2026-06-21 → 06-24)

- Beta vertical slice shipped: intent-graph model, ADR-029 SEI binding, read
  primitives (orphans/trace/corpus), authoring-time write surface.
- Cross-member seams: Loomweave catalog adapter, Legis preflight advisory cell,
  peer-ready entity-intent-context API.
- Independent review cycle: 3 findings fixed (F1/F2/F5); 2 perf findings deferred.
- **Beta-candidate golden-vector gate: PASS on Plainweave self-dogfood** (PDR-005).
