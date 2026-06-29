# PDR-016: Operator web UI UX + a11y overhaul hardened and delivered to main

Date: 2026-06-28   Status: accepted   Author: agent (product checkpoint; a11y review + merge driven this session)   Owner sign-off: EXPLICIT (owner supplied the two a11y review findings to evaluate, then directed "commit these and merge back to remote main … still as 1.2, we haven't published it yet")
Related: PDR-013 (operator web UI ratified as a standing bet — this hardens it, it is not a new bet), PDR-015 (the concurrent 1.2 line this rode in on), PDR-002 / PDR-012 (publication owner-gated — the held PyPI publish)

## Context

PDR-013 ratified the operator web UI as a standing product bet. Since then a **UX +
a11y overhaul** (commit `9f00ae0`: site-kit design-token adoption, contrast / focus-ring /
target-size fixes) and its design-review docs (`4c12d7f`) landed on the
`feat/lacuna-peer-facts-tour-cli-parity` branch carrying **no PDR**. PDR-015's checkpoint
flagged this explicitly as a decision-without-provenance gap and asked the next checkpoint
to record the overhaul with a rationale + reversal trigger. This checkpoint does that, and
folds in this session's a11y review-fix work and the delivery to `main`.

## Options considered

1. The two owner-supplied a11y review findings — **adversarially verify** before fixing vs
   accept-as-given. Verified (CSS specificity math, WCAG contrast computation, the htmx
   confirm-flow trace); both confirmed real, **0 false positives**.
2. Toast-dismiss fix scope — reorder within `review.html` (fixes the 3 review-page
   confirm flows only) vs **move to `base.html`** (covers every page, including the
   requirement dossier, which loads no page script of its own). Chose `base.html`.
3. Recording — **record the overhaul** as accepted hardening (close the PDR-015 gap) vs
   leave it unrecorded.
4. Release posture — publish 1.2 now vs **hold**. Owner explicitly held publish.

## The call

- **Both a11y findings accepted and fixed** (`a15adb1`):
  - *Visited primary anchors:* the global `a:visited` rule (specificity 0,1,1) outspecified
    `.btn--primary` (0,1,0), flipping the "New requirement" link's text to `--link` on the
    brass fill (~1.7:1 — a WCAG AA failure) once visited. Re-asserted `--text-on-accent` for
    anchor primaries at higher specificity. Plain `<button>` primaries are unaffected (no
    `:visited` state).
  - *Stuck success toast:* the auto-dismiss timer lived inside `review.html`'s `.qi-actions`
    focus guard, so the confirm-step queue flows (drifted-accept, reject, draft-approve) and
    the requirement dossier left the toast on screen indefinitely. Moved the dismiss to
    `base.html` so it fires on any page when `#toast` is filled; `review.html` keeps only its
    focus management.
- **The operator web UI UX + a11y overhaul (`9f00ae0`) is recorded here as accepted
  hardening of the PDR-013 bet** — not a new bet, no roadmap horizon change.
- **The whole branch merged to `origin/main` via PR #5** (owner-directed push): web overhaul
  + design-review docs + peer-facts CLI-parity checkpoint (PDR-015) + these a11y fixes. This
  **resolves the standing "push `main`" escalation** carried since PDR-013.
- **1.2 stays unreleased.** No separate CHANGELOG entry for the a11y fixes (consistent with
  the overhaul carrying none); CHANGELOG version/date finalization + the PyPI publish remain
  owner-gated.

`make ci` green at merge: ruff + mypy `--strict`, **378 tests, 91.14% coverage**; CI gate
passed (37s).

## Rationale

The a11y fixes **restore a WCAG AA guardrail** (interactive-control contrast) on a ratified
human-facing surface — the no-silent-degradation discipline applied to the UI. Verifying the
findings before acting kept a plausible-but-wrong review from driving a change; the
discipline is the point even though both findings held. `base.html` for the toast is the
structurally complete fix. Recording the overhaul closes the PDR-015 provenance gap. The push
was outward-facing but **owner-directed in-session**, so it is authorized — explicitly
distinguished by the owner from publication, which was held.

## Reversal trigger

- If a future a11y audit (axe / WCAG AA) on the operator UI flags a new contrast / focus /
  target-size failure, or the visited-link / toast-dismiss fixes regress under a later change,
  reopen as a UI-hardening item (tie to the interactive-control-contrast guardrail in
  `metrics.md`).
- The standing PDR-013 trigger still governs the bet itself: if the operator web UI attracts
  no operator use within a window once real users exist, reopen as kill / shrink.
- Publication stays gated: reconsidering the held 1.2 publish is an owner call (PDR-002 /
  PDR-012), not reversed here.
