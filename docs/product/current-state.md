# Plainweave Current State        Checkpoint: 2026-06-25 (1.0 release) · (commit recorded below)

## The bet right now

**Plainweave 1.0.0 is shipped** — live on PyPI, public repo + CI/CD (PDR-012). The north-star
is self-computable (PDR-009) and 1.0 ships **stable behaviour + contracts**. The open product
frontier is unchanged: **coverage *completeness*** — the owner-raised cross-member language gap
(the Rust public surface is untagged upstream). 1.0 does not close it; the README/CHANGELOG are
deliberately honest that completeness is a roadmap item. Metric: north-star (completeness).

## In flight

- **Pre-alpha preflight perf** — fan-out cap + N+1 connections; deferred until a real corpus
  makes them bite. · tracker: plainweave-706d80dc8e, plainweave-3edcd19943 (P3).
- **Semantic-similarity hint** — DEFERRED by PDR-003. · tracker: plainweave-02376962ab.
- **Federation operability — remaining install surfaces** — `doctor`/`--fix` shipped (PDR-011);
  skill pack / SessionStart hook / `.mcp.json` self-registration / `install` command are a
  deferred future onboarding bet, not committed.

_(The build epic `plainweave-c2d58800a0` was closed this checkpoint — realized by the 1.0 release.)_

## Open questions / blocked-on-owner

- **Operator web-UI direction (new — owner decision).** A concurrent session committed an
  owner-gated webUX design brainstorm (`plainweave[web]`, Starlette+HTMX over PlainweaveService)
  to `main`; it's now public and in the `v1.0.0` tag (docs-only — the wheel is code-identical).
  The **direction itself is unapproved** (vision-level, a new human-facing surface). Owner: ratify,
  shelve, or route it. Also note: **another session is active on this repo** — coordinate.
- **Cross-member coverage completeness (carried, most pressing).** A peer's north-star covers
  only languages its Loomweave plugin tags; the Rust surface is untagged upstream. Plainweave
  surfaces the gap (`present_plugins`); **closing it is owner-gated** (sibling obligation — do
  not file a Loomweave ticket unilaterally). DECIDE: drive Loomweave-side Rust tagging vs. accommodate.
- **Publishing a headline north-star number remains owner-gated** (PDR-002): computable, but the
  real-API denominator on Loomweave is **1** (44/45 are test/CI harness).
- **vision.md authority-grant metadata** (`Granted by` / `Last reviewed` / `Review cadence`) still
  missing; adding them is a vision edit → gates to owner (carried).
- **Release hardening (minor, offered).** Pin the workflow actions (a Node-20 deprecation warning
  fired); add a required reviewer on the `pypi` environment to gate future publishes.

## Last checkpoint did

- **PDR-012 — released Plainweave 1.0.0 to PyPI** (owner-directed): packaging (version, LICENSE,
  CHANGELOG, Production/Stable), CI + release workflows, version-bump-robust contract suite; created
  the public repo `foundryside-dev/plainweave` + configured topics / `pypi` Trusted-Publishing env /
  `main` branch protection; tagged `v1.0.0` → built + published (wheel + sdist + attestations). Verified live.
- **Accepted as-shipped** ("leave it, good shape") despite a docs-only concurrent commit swept into
  the tag — wheel is code-identical; 1.0.0 is immutable on PyPI.
- Reconciled the tracker: closed the realized build epic `plainweave-c2d58800a0`.

## Next session, start here

**DECIDE the cross-member coverage-completeness gap** (carried, owner-raised, most pressing) — drive
Loomweave-side Rust public-surface tagging (owner-gated sibling obligation) vs. limit Plainweave to
honestly surfacing it. This moves north-star *completeness*. Separately, surface the **web-UI direction**
for an owner ratify/shelve decision, and coordinate with the concurrent session on this repo.
