# Plainweave Roadmap            Updated: 2026-06-24 (PDR-009)

> Sequencing, WSJF / cost-of-delay, and dated forecasts are produced by
> /axiom-program-management. This file records bets as INTENT, not a delivery
> schedule. Do not compute WSJF here; hand the committed bet over for sequencing.

## Now (committed, in-flight)

- **Dogfood against live sibling peers** — Lacuna + Loomweave done (PDR-008): the
  code-up graph and the cross-member seam (PDR-004) reproduce on real sibling corpora.
  Remaining: more peers as desired; keep proving the seam holds. · metric: north-star.
- **Lacuna demonstration mix** — keep a deliberate covered + uncovered specimen so the
  intent reads (coverage/orphans/trace) show a real *partial* reading, not a clean
  100%/0%. Owner notes this work is being driven via Plainweave. · metric: north-star (demo).

## Next (shaped, decreasing certainty)

- **Explicit degraded peer-state envelopes** for live Loomweave and Legis adapters.
- **Contract fixtures** for the intent-graph and binding envelopes (shared
  structural validator already landed for preflight, F5).
- **Bound preflight project-scope fan-out** + revisit the N+1 connection pattern
  once a real corpus makes them bite. · tracker: plainweave-706d80dc8e,
  plainweave-3edcd19943 (currently acceptable at pre-alpha scale).

## Later (directional bets, no order, no dates)

- **Cross-member coverage completeness** — a peer's north-star can only cover languages
  whose public surface its Loomweave plugin tags. The Rust plugin's public-surface tagging
  is weak: on the Loomweave peer `present_plugins` shows core/python/rust, yet all tagged
  public surfaces are `python:`. Plainweave already surfaces the gap (`present_plugins`);
  **closing it upstream is owner-gated** (sibling obligation — do not file a Loomweave
  ticket unilaterally). Owner-raised this session as the most pressing remaining gap.
- Optional Loomweave semantic-similarity hint over requirement text — DEFERRED by
  PDR-003; advisory only, never a dedup verdict. · tracker: plainweave-02376962ab.
- Corpus-curation workflows for duplicate or overlapping requirements.
- Formal suite membership package — **owner-gated** (PDR-002).
- Public release and packaging (final name, PyPI, hub roster) — **owner-gated** (PDR-002).

## Done since last checkpoint (2026-06-21 → 06-24)

- **`intent_coverage` read primitive shipped to `main`** (PDR-009): the product
  self-computes the north-star honestly — scoped denominator (excl. `tests.`/`scripts.`),
  `denominator_complete`, `present_plugins`, bounded evidence (`max_surfaces`) — advisory,
  no verdict (machine-enforced). Closes plainweave-44be10cc2c + plainweave-7be2817d58;
  reviewed (15-agent adversarial pass, 0 blockers); fixed a deprecated-requirement
  numerator-inflation defect; kept the intent_trace explain/count split (52b743d5b9).
- Beta vertical slice shipped: intent-graph model, ADR-029 SEI binding, read
  primitives (orphans/trace/corpus), authoring-time write surface.
- Cross-member seams: Loomweave catalog adapter, Legis preflight advisory cell,
  peer-ready entity-intent-context API.
- Independent review cycle: 3 findings fixed (F1/F2/F5); 2 perf findings deferred.
- **Beta-candidate golden-vector gate: PASS on Plainweave self-dogfood** (PDR-005).
- **Cross-member seam validated on live peers** Lacuna + Loomweave (PDR-008).
