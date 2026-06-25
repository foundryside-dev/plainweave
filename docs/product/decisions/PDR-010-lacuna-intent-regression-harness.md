# PDR-010: Lacuna Intent Regression-Harness — Demonstrator, Not North-Star Movement

Date: 2026-06-25   Status: accepted   Author: agent:claude-product-owner   Owner sign-off: build was owner-directed this session; local-only (unpushed)
Related: PDR-004 (cross-member seam), PDR-008 (seam validated read-only), PDR-002 (consumer boundary), Lacuna PDR-0005 (the Lacuna-repo side)

## Context

The "Lacuna demonstration mix" was a Now bet (roadmap/current-state): keep a deliberate
covered + uncovered specimen so the intent reads (coverage/orphans/trace) show a real
*partial* reading, not a clean 100%/0%. The human owner directed building it this session
and gave the load-bearing principle: pair healthy (justified) surfaces with honest gaps so
`intent_coverage` reports a partial ratio with real `justified` AND `unjustified` rows.
Plainweave is advisory/enrich-only/local; the cross-member seam was already proven over
Lacuna *read-only* at PDR-008 (75% on a transient scratch store).

## Options considered

1. **Read-only peer dogfood only** (as PDR-008 did) — proves the seam once, leaves no
   durable, regenerable proof; nothing the specimen re-asserts every run.
2. **A permanent in-repo tour member in Lacuna** — a self-seeding leg + catalogued lacunae
   the Lacuna tour drives and `make verify` asserts every run.

## The call

Option 2. Built Plainweave as Lacuna's 6th tour member (warpline-style NOT-A-FLAW capability
demos): a self-seeding leg seeds a deterministic **2-covered : 2-uncovered** intent corpus
over the specimen and asserts four `pw-*` facts — `pw-intent-justified`, `pw-intent-liveness`
(deprecated requirements drop from the numerator), `pw-intent-orphan`, `pw-surface-scoping`
(+ honest 2/4 degradation). Deterministic oracle: north-star **2/4 default, 2/3 scoped**;
orphans/trace/corpus all populated. Merged to Lacuna's **local `main` only** (unpushed).
Recorded Lacuna-side in **Lacuna PDR-0005**. Vetted: 2 plan-review rounds (→ "go") + a
code-review cycle that found and fixed **2 HIGH** defects (a never-raise contract escape; a
hollow liveness credit — now a positive bound-ness check via `intent trace`), regression-tested.

## Rationale

Banked **honestly as a demonstrator + deterministic regression-harness, NOT north-star
movement** — the build-trap review forced this framing. PDR-008 already proved the seam
read-only; this adds *durable, regenerable* proof that fails loud if Plainweave's
**liveness/deprecation numerator semantics** ever break — a guarantee a one-shot dogfood
cannot give. Consumer boundary (PDR-002) honored end-to-end: the leg only *consumes*
Plainweave (a `uv tool`-installed binary), no Plainweave-repo change, no specimen source
touched, no existing lacuna modified.

## Reversal trigger

Reopen if Plainweave's CLI/oracle drifts so the seed no longer reproduces deterministically
(the four stable anchor surfaces leave the catalog, or the `intent_coverage`/`intent trace`
envelope shapes change) — `make verify` in Lacuna will red and signal it — or if the harness
is ever shown to credit a `pw-*` lacuna whose underlying fact does not hold (a hollow gate).
Demote to a read-only dogfood note if Plainweave is not adopted as a recognized Weft member.
