# Plainweave Current State        Checkpoint: 2026-06-28 (PDR-015; prior PDR-013, PDR-014) · (commit recorded below)

## The bet right now

**Harden + build out, under the soft-launch / RC posture** (owner-stated: Plainweave is
published but has no users yet, so iteration is cheap). The active theme is
**production-readiness hardening**: PDR-014 retired 3 of the 5 named blockers; PDR-015 this
session closed the peer-facts MCP/CLI parity gap and added cross-member regression coverage.
The carried **coverage-completeness** frontier remains the genuine north-star mover but is
owner-gated / sibling-paced. Metric: production-readiness (surface parity + regression);
north-star (completeness) unchanged.

## In flight

- **Release `1.2.0`** — `release/1.2.0` branch is cut (CHANGELOG still `[Unreleased]`); the
  version question (refold 1.1.0 vs ship 1.2.0) is effectively **resolved to 1.2.0**.
  Remaining: finalize the CHANGELOG version/date, and the PyPI publish (held, owner-gated).
- **Peer-facts CLI parity — DELIVERED + merged to `main`** (PDR-015):
  `plainweave wardline-peer-facts` / `requirements-enrichment` reuse `PlainweaveMcpSurface`;
  `make ci` green (378 tests, 91.14% cov); `wardline scan` clean. Lacuna's tour gained
  `plainweave+wardline` / `plainweave+warpline` cells (sibling repo, Lacuna PDR-0015) —
  **two clean-checkout prerequisites remain owner-side** (see escalations).
- **Operator web UX overhaul — landed concurrently** (`main`: `9f00ae0`, `4c12d7f` — UI/a11y
  overhaul, site-kit tokens, design review). NOT a decision of this session and has **no PDR
  from this vantage**; recommend its own `/product-checkpoint` so its rationale + reversal
  trigger are recorded.
- **Peer-facts sibling wiring** — 3 owner-gated handoff prompts (`docs/handoffs/`) not yet
  dispatched: Warpline consumer, Wardline scan-identity metadata, Warpline interface-lock
  item-schema ratification.
- **Deferred perf/hint** (unchanged, acceptable at pre-alpha scale): `plainweave-706d80dc8e`,
  `plainweave-3edcd19943` (P3); semantic-similarity hint `plainweave-02376962ab` (PDR-003).

## Open questions / blocked-on-owner (escalations)

- **Push `main` + finalize `release/1.2.0` + publish.** `main` is well ahead of
  `origin/main` and now carries peer-facts CLI parity + the web overhaul. Pushing
  `foundryside-dev/plainweave` is outward-facing (needs `tachyon-beep`, `gh auth switch`);
  finalizing 1.2.0 + the held PyPI publish are owner calls.
- **Lacuna tour — two clean-checkout prerequisites** (the new cells are correct but not
  reproducibly green on a fresh clone until): (1) **install the updated plainweave** —
  blocked by a pre-existing wheel-build packaging bug (`force-include` double-adds
  `web/static/.gitkeep`), filed as observation **`plainweave-obs-6a7255ffbe`**; (2)
  regenerate `docs/tour.md` on a clean tree (a pre-existing `legis govern` leg bakes
  tree-cleanliness into the byte-locked doc; concurrent dirt left it `[WARN]`). Both recorded
  in Lacuna PDR-0015.
- **Hand off the 3 peer prompts** to the sibling owners (Warpline/Wardline) — owner-gated.
- **Cross-member coverage completeness** (carried, most pressing north-star mover) — Rust
  public surface untagged upstream on Loomweave; owner-gated (sibling obligation).
- **Carried:** `vision.md` authority-grant metadata still missing (a vision edit, owner-gated);
  publishing a headline north-star number remains owner-gated (PDR-002/009).

## Last checkpoint did (this session)

- **Delivered peer-facts CLI parity** (PDR-015, accepted): two CLI subcommands reusing the MCP
  surface; folded in two owner-directed sibling-contract fixes (rejected-trace enrichment +
  root-aware doctor remediation). `make ci` green (378 tests, 91.14% cov); merged to `main`.
- **Built the Lacuna cross-member tour demos** (Lacuna PDR-0015): `plainweave+wardline`
  (full resolved/unseen) + `plainweave+warpline`, each asserting the no-silent-clean invariant.
- **Ran an adversarial multi-lens review** (ultracode workflow): fixed 4 real findings
  (temp-dir cleanup, per-conjunct drop-tests, PEP8); rejected 4 false positives. Filed the
  packaging-bug observation; recorded the 2 tour prerequisites.

## Next session, start here

**Owner calls on the release + push escalations** (finalize 1.2.0 + the held publish + push
`main`), then close the two Lacuna-tour prerequisites (fix the packaging bug → install
plainweave → clean-tree `make tour`). Also: **checkpoint the concurrent web UX overhaul** so
it carries a PDR. Then continue **harden + build** (remaining blockers: Loomweave-owned
identity resolution, Legis fact emission, Filigree contract tests) or pivot to
coverage-completeness if the owner wants product movement.
