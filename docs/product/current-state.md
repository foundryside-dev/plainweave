# Plainweave Current State        Checkpoint: 2026-06-25 · (commit recorded below)

## The bet right now

The north-star is **self-computable** (PDR-009, `intent_coverage`). The open frontier is
**coverage *completeness***: the headline number leans on namespace scoping and on the peer's
plugin tagging, and the **Rust public surface is untagged upstream** (owner-raised, most
pressing). This session delivered two adjacent things — a durable Lacuna **regression-harness**
for the intent semantics (PDR-010) and **doctor → federation parity** (PDR-011, operability /
launch-readiness) — neither moves the north-star number; the completeness gap is still the bet.
Metric: north-star (completeness).

## In flight

- **Pre-alpha preflight perf** — fan-out cap + N+1 connections; deferred until a real corpus
  makes them bite. · tracker: plainweave-706d80dc8e, plainweave-3edcd19943 (P3).
- **Semantic-similarity hint** — DEFERRED by PDR-003. · tracker: plainweave-02376962ab.
- **Federation operability — remaining install surfaces** — `doctor`/`--fix` done; the
  agent-orientation surfaces (skill pack / SessionStart hook / `.mcp.json` self-registration /
  `install` command) are a deferred future onboarding bet (PDR-011, Option 2). Not committed.

## Open questions / blocked-on-owner

- **PUSH decision (new this session, owner-gated — publication, PDR-002).** Two feature
  branches are merged to their **local `main`s, green, and UNPUSHED**: the doctor parity
  (Plainweave `main`, merge `fd96d59`) and the Lacuna intent-harness (Lacuna `main`, merge
  `d09da33`). Pushing to origin is outward-facing → **do you want either/both pushed?**
- **Cross-member coverage completeness (carried, most-pressing).** A peer's north-star can only
  cover languages whose Loomweave plugin tags the public surface; the Rust plugin's tagging is
  weak (Loomweave `present_plugins`=core/python/rust, yet all 45 tagged surfaces are `python:`).
  Plainweave surfaces the gap (`present_plugins`); **closing it upstream is owner-gated** (do not
  file a Loomweave ticket unilaterally). DECIDE: drive Loomweave-side Rust tagging vs. Plainweave-
  side accommodation only.
- **Publishing a headline north-star number remains owner-gated** (PDR-002): computable, but the
  real-API denominator on Loomweave is **1** (44/45 are test/CI harness).
- **vision.md authority-grant metadata** (`Granted by` / `Last reviewed` / `Review cadence`) still
  missing; adding them is a vision edit → gates to owner (carried).
- **(Lacuna-owner dependency, informational.)** Lacuna's `vision.md` tool enumeration omits
  Plainweave though the tour now drives it — recorded in **Lacuna PDR-0005** for the *Lacuna*
  owner to ratify (demonstrated-not-rostered) or fold in. Not Plainweave's to edit.

## Last checkpoint did

- **PDR-010** — delivered the Lacuna intent **regression-harness**: Plainweave as Lacuna's 6th
  tour member, 4 `pw-*` capability demos over a deterministic 2-covered:2-uncovered mix (oracle
  2/4 default, 2/3 scoped). Banked honestly as demonstrator/regression-harness, NOT north-star.
  Merged to Lacuna's local `main`; 2 plan rounds + a code review (2 HIGH fixed). Lacuna PDR-0005.
- **PDR-011** — brought `plainweave doctor` to **federation parity**: `--fix`/`--root`/non-zero
  exit; checks store/schema, the Loomweave catalog binding (report-only, consumer boundary), and
  the MCP surface; envelope v1→v2. `make ci` green (mypy strict, 235 tests, 90.11% cov); wardline clean.
- Both merged to **local `main`s only — unpushed** (push decision pending, above).

## Next session, start here

1. **Resolve the PUSH decision** with the owner (both branches are merged + green, awaiting it).
2. **DECIDE the cross-member coverage-completeness gap** (carried, owner-raised, most pressing):
   drive Loomweave-side Rust public-surface tagging (owner-gated sibling obligation) vs. limit
   Plainweave to honestly surfacing the gap. This moves north-star *completeness*, not computability.
