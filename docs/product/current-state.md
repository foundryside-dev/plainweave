# Plainweave Current State        Checkpoint: 2026-07-01 (PDR-019, PDR-020) · branch main

## The bet right now

**Harden + build out under the soft-launch posture** (owner-stated: published, no users yet, so
iteration is cheap). This session **cleared the long-standing publication escalation**: the full
1.2 line is now **live on PyPI (1.2.0 → 1.2.1)**, owner-directed. Active theme is
production-readiness + agent-adoption legibility. Metric: production-readiness (surface parity +
regression + a11y + error-honesty guardrails); north-star (coverage completeness) unchanged —
owner-/sibling-gated.

## In flight

- **1.2.x shipped + live.** `pip install plainweave` → 1.2.1 (wheel+sdist); PyPI `[1.0.0, 1.2.0,
  1.2.1]` (1.1.0 never published — its build had failed on the wheel bug, now fixed). The global
  uv-tool is reverted off editable to the published `plainweave[web]==1.2.1`, so siblings consume
  the released package (`[[weft-tools-editable-installs]]`).
- **Idempotency-hint precision** — `plainweave-de4ced60cf` (P3): the idempotency-key CONFLICT
  sites ride the honest CONFLICT default (improved, not perfect — could name "use a fresh key").
- **Coverage-completeness** (carried, the most pressing north-star mover) — the Rust public
  surface is untagged upstream on Loomweave; Plainweave surfaces the gap (`present_plugins`).
  Owner-gated (sibling obligation).
- **Lacuna tour clean-tree regen** — now **unblocked** (the packaging bug that blocked
  `uv tool install` is fixed + published); `docs/tour.md` still wants a clean-tree `make tour`.
- **Sibling handoffs** — the Warpline requirements consumer is BUILT + accepted (Warpline
  PDR-0008) and the producer is gated-live (PDR-017/019), so that handoff is effectively closed.
  Remaining owner-gated: Wardline scan-identity metadata; Warpline interface-lock item-schema
  ratification (then byte-pin the contract test); Filigree `open_linked_work`
  (`docs/handoffs/2026-06-29-filigree-linked-work-facts.md`).
- **Deferred perf/hint** (unchanged, acceptable at pre-alpha scale): `plainweave-706d80dc8e`,
  `plainweave-3edcd19943` (P3); semantic-similarity hint `plainweave-02376962ab` (PDR-003).

## Open questions / blocked-on-owner (escalations)

- **Publication is no longer a standing escalation for 1.2.x** — done this session, owner-directed.
  Future releases still gate (`vision.md` Authority Grant).
- **Carried `vision.md` edits (owner-gated):** authority-grant metadata still absent; "Serves"
  still does not name human operators (PDR-013); publishing a headline north-star number remains
  owner-gated (PDR-002/009). `vision.md` not touched this session.
- **Cross-member coverage completeness** — Rust public surface untagged upstream on Loomweave;
  owner-gated (do not file a Loomweave ticket unilaterally).
- **Dispatch the remaining sibling handoffs** (Wardline / Warpline interface-lock / Filigree) —
  owner-gated.

## What this checkpoint did (this session)

- **Released 1.2.0 then 1.2.1 to PyPI** (owner-directed) via Trusted Publishing, verified live on
  the PyPI JSON API; created both GitHub Releases; reconciled the release branches. Cleared the
  publication escalation held across the last three checkpoints (PDR-019, PDR-020).
- **Delivered the `plainweave-workflow` skill pack** (Later → Done) — federation-standard,
  in-package + dogfooded — and resolved two clean-room **error-legibility (say-what-you-know)**
  dogfood findings via an ultracode sweep→implement→adversarial-verify workflow, extended inline
  to the sibling draft-revision guard (`make ci` 400 passed / 91.32%).
- **Reconciled tracker + install:** reverted the uv tool to published 1.2.1; dismissed the
  resolved wheel-build observation (`plainweave-obs-6a7255ffbe`); filed the idempotency-hint
  follow-up (`plainweave-de4ced60cf`).

## Next session, start here

**Pivot to coverage-completeness** if the owner wants north-star movement (the Rust-surface gap is
the mover, owner-gated) — otherwise the cheap wins are the **idempotency-hint precision**
(`plainweave-de4ced60cf`) and the now-unblocked **Lacuna-tour clean regen**. Watch for
**real-agent adoption feedback** on the new error legibility — PDR-020's reversal trigger fires on
a hint that still misdirects, and there is no adoption input-metric yet to quantify it.
