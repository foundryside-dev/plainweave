# Plainweave Current State        Checkpoint: 2026-06-29 (PDR-018; prior PDR-016) · (branch feat/seam-hardening-blockers-345)

## The bet right now

**Harden + build out, under the soft-launch / RC posture** (owner-stated: Plainweave is
published but has no users yet, so iteration is cheap). The active theme is
**production-readiness hardening**. This session hardened the ratified operator web UI
(PDR-013) — two WCAG AA a11y fixes — and **delivered the full 1.2 line to `origin/main`**
(owner-directed). Metric: production-readiness (surface parity + regression + a11y guardrails);
north-star (coverage completeness) unchanged — owner-/sibling-gated.

## In flight

- **Release `1.2.0`** — `origin/main` now carries the entire 1.2 line (peer-facts CLI parity
  PDR-015 + the operator web UX/a11y overhaul PDR-016 + design-review docs). The version
  decision is **1.2.0** (owner-reaffirmed this session: "still as 1.2"). Remaining: finalize
  the CHANGELOG version/date and reconcile the `release/1.2.0` branch (it predates these merges
  and now lags `main`), then the **PyPI publish (held, owner-gated)**.
- **Operator web UI UX + a11y overhaul — DELIVERED to `main` + now carries a PDR** (PDR-016):
  site-kit tokens + this session's two a11y review fixes (visited-primary contrast restored to
  AA; toast auto-dismiss moved to `base.html` so it fires on every page). Closes the
  "web overhaul needs a PDR" gap PDR-015 flagged.
- **Peer-facts CLI parity — DELIVERED, now on `origin/main`** (PDR-015):
  `plainweave wardline-peer-facts` / `requirements-enrichment`; `make ci` green (378 tests,
  91.14% cov); `wardline scan` clean.
- **Peer-facts sibling wiring** — 3 owner-gated handoff prompts (`docs/handoffs/`) not yet
  dispatched: Warpline consumer, Wardline scan-identity metadata, Warpline interface-lock
  item-schema ratification.
- **Lacuna tour** — two clean-checkout prerequisites remain (sibling repo, Lacuna PDR-0015):
  the packaging bug below blocks `uv tool install`, and `docs/tour.md` needs a clean-tree
  regen (a `legis govern` leg byte-locks tree-cleanliness; concurrent dirt left it `[WARN]`).
- **Deferred perf/hint** (unchanged, acceptable at pre-alpha scale): `plainweave-706d80dc8e`,
  `plainweave-3edcd19943` (P3); semantic-similarity hint `plainweave-02376962ab` (PDR-003).

## Open questions / blocked-on-owner (escalations)

- **Finalize `release/1.2.0` + publish to PyPI** — held, owner-gated (publication is an
  authority-grant escalation, PDR-002/PDR-012). _(The "push `main`" half of this escalation
  was RESOLVED this session — the owner directed the merge to remote `main`.)_
- **Lacuna tour — two clean-checkout prerequisites:** (1) fix the **wheel-build packaging bug**
  (`[tool.hatch.build.targets.wheel.force-include]` double-adds `web/static/.gitkeep`),
  observation **`plainweave-obs-6a7255ffbe`** (P2), then install plainweave; (2) regenerate
  `docs/tour.md` on a clean tree.
- **Hand off the 3 peer prompts** to the sibling owners (Warpline / Wardline) — owner-gated.
- **Cross-member coverage completeness** (carried, the most pressing north-star mover) — the
  Rust public surface is untagged upstream on Loomweave; owner-gated (sibling obligation).
- **Carried vision edits (owner-gated):** `vision.md` authority-grant metadata still missing;
  "Serves" still does not name human operators (PDR-013); publishing a headline north-star
  number remains owner-gated (PDR-002/009).

## Last checkpoint did (this session)

- **Adversarially reviewed two owner-supplied web a11y findings** (did not rubber-stamp —
  confirmed CSS specificity, WCAG contrast math, and the htmx confirm-flow trace), then **fixed
  both** (`a15adb1`): visited primary links restored to AA contrast; success-toast auto-dismiss
  moved to `base.html` so confirm-step flows and the requirement dossier no longer leave it
  stuck. 0 false positives.
- **Merged `feat/lacuna-peer-facts-tour-cli-parity` → `origin/main` via PR #5** (owner-directed
  push as `tachyon-beep`): brought the web overhaul + docs + peer-facts checkpoint + a11y fixes
  to `main`. CI gate green (378 tests, 91.14% cov, 37s); branch deleted.
- **Recorded PDR-016**, closing the web-overhaul-needs-a-PDR gap PDR-015 left open.

## Next session, start here

**Owner calls on the release escalation** — finalize the `1.2.0` CHANGELOG version/date,
reconcile/retire the `release/1.2.0` branch against `main`, then the held PyPI publish. Then
close the two **Lacuna-tour prerequisites** (fix the packaging bug → install plainweave →
clean-tree `make tour`). All 5 named production blockers are now retired plainweave-side —
**PDR-018 closed the last three** (#3 Loomweave identity / #4 Legis fact emission / #5
Filigree contract tests) as test-and-docs-only hardening (390 tests, 91.18% cov; legis
cross-repo oracle stayed green; zero `src/` changes). The only open seam item is the
owner-gated Filigree `open_linked_work` handoff
(`docs/handoffs/2026-06-29-filigree-linked-work-facts.md`). Next: pivot to
**coverage-completeness** if the owner wants north-star movement, or finalize the release.
