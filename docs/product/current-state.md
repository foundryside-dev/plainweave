# Plainweave Current State        Checkpoint: 2026-06-28 (PDR-015; prior PDR-013, PDR-014) · (commit recorded below)

## The bet right now

**Harden + build out, under the soft-launch / RC posture** (owner-stated: Plainweave is
published but has no users yet, so iteration is cheap). The active theme is
**production-readiness hardening**: PDR-014 retired 3 of the 5 named production blockers
(live-data peer adapters, explicit degraded-state, Warpline/Wardline contract tests).
The carried **coverage-completeness** frontier remains the genuine north-star mover but is
owner-gated / sibling-paced. Metric: production-readiness (blockers retired); north-star
(completeness) unchanged.

## In flight

- **1.1.0 release ceremony** — operator web UI + SEI conformance is on `main`; the public
  site is live; `release/1.1.0` (PR #2) is OPEN; **PyPI publish HELD** (owner-gated).
- **Peer-facts sibling wiring** — 3 owner-gated handoff prompts written (`docs/handoffs/`),
  not yet handed off: Warpline consumer, Wardline scan-identity metadata (owner building in
  parallel for integration testing), Warpline interface-lock item-schema ratification.
- **Peer-facts CLI parity + Lacuna tour demos** (PDR-015; branch
  `feat/lacuna-peer-facts-tour-cli-parity`) — `plainweave wardline-peer-facts` /
  `requirements-enrichment` CLI subcommands close the MCP-only gap; the Lacuna tour gains
  `plainweave+wardline` / `plainweave+warpline` cells (full resolved/unseen). Recorded
  Lacuna-side as PDR-0015. Not a release blocker; no public push without owner sign-off.
- **Deferred perf/hint** (unchanged, acceptable at pre-alpha scale): preflight project-scope
  fan-out + N+1 connections — `plainweave-706d80dc8e`, `plainweave-3edcd19943` (P3);
  semantic-similarity hint — `plainweave-02376962ab` (deferred, PDR-003).

## Open questions / blocked-on-owner (escalations)

- **Push `main`?** `main` is **33 commits ahead of `origin/main`** (unpushed). Pushing the
  public repo `foundryside-dev/plainweave` is outward-facing and needs the `tachyon-beep`
  account (`gh auth switch`). Owner: push, or hold.
- **Release version + publish.** Fold peer-facts into a re-cut **1.1.0**, or ship it as
  **1.2.0**? And proceed with the held 1.1.0 PyPI publish (PR #2), or keep holding?
- **Hand off the 3 peer prompts** to the sibling owners (Warpline/Wardline) — sibling
  obligations, owner-gated. Owner: dispatch, or hold.
- **Cross-member coverage completeness** (carried, most pressing north-star mover) — Rust
  public surface untagged upstream on Loomweave; closing it is owner-gated (sibling
  obligation, do not file unilaterally).
- **Carried:** `vision.md` authority-grant metadata (`Granted by`/`Last reviewed`/`Review
  cadence`) still missing — grant was confirmed AS WRITTEN this session; adding metadata is
  a vision edit, owner-gated. Publishing a headline north-star number remains owner-gated
  (PDR-002/009).

## Last checkpoint did

- **Ratified the operator web UI** as a standing bet (PDR-013, owner-explicit) and recorded
  the soft-launch/RC posture — reconciling the workspace, which had it as "unapproved."
- **Delivered peer facts** (PDR-014): `weft.plainweave.wardline_peer_facts.v1` +
  `weft.plainweave.requirements_enrichment.v1` merged to `main` (`bc37a24`) via 17-task
  subagent-driven TDD + opus whole-branch review; `make ci` green (355 tests, 90.94% cov);
  `wardline scan` clean. Wrote 3 owner-gated peer prompts; reconciled the spec freshness vocab.
- Reconciled roadmap/metrics to reality (1.1.0, the live site, peer-facts).

## Next session, start here

**Get the owner's calls on the escalations** — push `main` + the release-version decision
(1.1.0 refold vs 1.2.0) + the held publish, and whether to hand off the 3 peer prompts.
Then continue **harden + build** (next production blockers: Loomweave-owned identity
resolution, Legis fact emission, Filigree contract tests), or pivot to the carried
**coverage-completeness** north-star if the owner wants product (not surface) movement.
