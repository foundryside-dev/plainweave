# Plainweave Current State        Checkpoint: 2026-06-24 · (commit recorded below)

## The bet right now

The code-up intent graph (`SEI → requirement → goal`, with orphans/trace/corpus) is
**proven on Plainweave itself and reproduced on two live sibling peers** (Lacuna,
Loomweave) — the cross-member seam (PDR-004) holds on real peer catalogs. The active
bet is now to make the north-star honestly computable (scope the public-surface
denominator) and to keep proving the seam on further peers. Metric: north-star.

## In flight

- **North-star coverage gap** — Loomweave-catalog public-surface tagging is per-repo;
  complete on Loomweave, degraded on Lacuna/Plainweave. Plainweave-side fix: surface
  `coverage.complete` to any north-star computation. · tracker: plainweave-44be10cc2c (open, P2).
- **Public-surface denominator semantics** — exclude test/perf/CI-script namespaces so
  "public surface" means the real exported API. · tracker: plainweave-7be2817d58 (open, P3).
- **Pre-alpha-scale preflight perf** — fan-out cap + N+1 connections; deferred until a
  real corpus makes them bite. · tracker: plainweave-706d80dc8e, plainweave-3edcd19943 (P3).
- **Semantic-similarity hint** — DEFERRED by PDR-003. · tracker: plainweave-02376962ab.

## Open questions / blocked-on-owner

- **`plainweave-44be10cc2c` resolution is owner-driven** — the catalog-tagging half is a
  sibling obligation; do not file a Loomweave hub ticket unilaterally. (The Plainweave-side
  half is in scope.) Loomweave already ships complete coverage, so this is a per-repo gap.
- **vision.md authority grant** lacks `Granted by / Last reviewed / Review cadence` slots.
  Owner confirmed the grant as-is this session; adding the metadata is a vision edit (gates to owner).

## Last checkpoint did

- Ran the live peer dogfood (Lacuna, Loomweave) per owner direction; recorded PDR-008
  (cross-member seam validated on real peers; coverage gap confirmed per-repo).
- Added the peer-dogfood readings to metrics.md; filed plainweave-7be2817d58 (denominator
  semantics). All guardrails intact on both peers; no reversal trigger fired.
- Peer repos left pristine — corpora built in scratch stores only.

## Next session, start here

Decide whether to (a) implement the Plainweave-side north-star fixes
(`plainweave-44be10cc2c` surface coverage.complete; `plainweave-7be2817d58` scope
public-surface namespaces) to produce a clean headline north-star on Loomweave, or
(b) dogfood additional peers. Both move the north-star.
