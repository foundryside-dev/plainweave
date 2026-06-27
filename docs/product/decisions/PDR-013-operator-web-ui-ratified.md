# PDR-013: Operator web UI ratified as a standing product bet

Date: 2026-06-27   Status: accepted   Author: agent:claude-product-owner   Owner sign-off: EXPLICIT (owner answered "Ratify the direction" during the /own-product RESUME this session)
Related: PDR-002 (publication owner-gated), PDR-012 (1.0 released; web UI explicitly NOT part of 1.0)

## Context

PDR-012 and the brainstorm doc left the operator web UI "owner-gated at the vision
level, NOT approved." This session's `/own-product` RESUME found reality had moved far
past that record, all dated 2026-06-26 and none checkpointed:

- the operator web UI fully **built and merged to `main`** (PR #1, 35 files under
  `src/plainweave/web/`, `plainweave[web]` extra, 16 TDD tasks);
- a public site **`plainweave.foundryside.dev` deployed and LIVE** (PR #3; HTTP 200);
- a **1.1.0 release cut** (`release/1.1.0`, PR #2 OPEN; PyPI still 1.0.0).

No PDR recorded owner ratification — a decision-without-provenance gap. Authorship is
under the shared `tachyon-beep` push account, so git/GH attribution does **not** confirm
a human ratify. PR #1 itself flagged "adopting the human-facing surface remains the
owner's call." Surfaced to the owner as drift, not silently resolved.

## Options considered

1. **Ratify** — adopt the web UI into the roadmap as an accepted standing bet.
2. **Keep, hold ratification** — leave it on `main` as a shipped-but-unratified MVP.
3. **Shelve / revert** — back the direction out (close PR #2, revert, take site down).

## The call

Option 1 — **the operator web UI is an accepted standing product bet.** The owner
ratified explicitly. The 1.1.0 publish proceeds as a deliberate, separate step; the live
site stays up. `roadmap.md` moves "Operator web UI" out of *Later (owner-gated, NOT
approved)* into the shipped/Now band.

## Rationale

The owner made the call directly. The work is high-quality and self-aware (it named its
own gate; `make ci` green at delivery). The **soft-launch / RC posture** (published, no
users yet — owner-stated this session) makes adopting a new human-facing surface
low-risk to reverse if it underperforms.

## Reversal trigger

If the operator web UI attracts no operator use within a defined window after real users
exist, or accrues maintenance cost without value, reopen as kill/shrink (tie to a usage
metric once one exists). Note: `vision.md` "Serves" still does **not** name human
operators — adding it is a separate vision edit, owner-gated, and is flagged, not made
here. The authority grant was confirmed AS WRITTEN this session (no metadata added —
carried). The **1.1.0 PyPI publish** and **pushing `main`** remain outward-facing,
owner-gated steps — flagged in this checkpoint, not executed.
