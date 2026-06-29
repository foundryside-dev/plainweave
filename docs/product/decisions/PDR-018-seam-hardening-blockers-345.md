# PDR-018: Seam hardening — production blockers #3/#4/#5 retired plainweave-side (contract tests + test-hardening)

Date: 2026-06-29   Status: accepted   Author: agent:claude-product-owner
Owner sign-off: EXPLICIT (owner set the bid — "do the seam hardening … then get it out the door" — and authorized subagent-driven multi-agent delivery via "ultracode"/"ultrathink")
Related: PDR-014 (peer facts; retired blockers 1/2 + Warpline/Wardline contract tests), PDR-009 (no-silent-clean / no-vanity-metric), PDR-011 (doctor federation parity), ADR-006 (Legis preflight fact envelope), ADR-005 (Loomweave SEI consumer contract)

## Context

PDR-014 retired 3 of the 5 named production blockers. This bid retires the remaining
three — (3) Loomweave-owned identity resolution, (4) Legis fact emission, (5) Filigree
contract tests — under the harden-and-ship posture. A scoping workflow (3 investigators +
adversarial challenge per blocker + contract-template auditor) established the **honest
size** of each: the seam BEHAVIOR was already built and tested for #3 and #4; the genuine
gaps were contract-test/parity artifacts and one zero-coverage fact kind. The adversarial
pass rejected two unsafe over-scopes (suppressing the Legis `*_unavailable` warnings — a
silent-clean hole; a dedicated Filigree validator module — Filigree emits no `.v1` payload).

## The call

**Plainweave-side, test-and-docs only — ZERO `src/` production changes** (the seam behavior
already exists; this freezes and pins it). Delivered via inline TDD with every new test
proven red-first against a transient producer mutation (anti-decorative), then reverted.

- **#5 Filigree contract tests — RETIRED.** New `tests/contracts/test_filigree_contract.py`
  pins: `open_linked_work` is never emitted by the local-only producer (absence is the
  in-band `linked_work_facts_unavailable` warning, never empty-but-ok); the `filigree_issue`
  `implements_work_for` relation (previously untested) is canonical and stored as an opaque
  pointer; a non-canonical filigree relation is a VALIDATION error; the dossier introduces no
  gate/decision/enforcement KEY. The scope-independent presence of `linked_work_facts_unavailable`
  on an EMPTY scope is pinned by an extension to the existing empty-scope preflight test.
  (Finding: the peer-facts value-token scanner does NOT apply to the dossier, which
  legitimately carries lifecycle `"approved"`/`"rejected"` VALUES — the meaningful invariant
  is the absence of a verdict KEY.)
- **#4 Legis fact emission — degraded-state already done; test-hardening landed; remaining
  kinds handed-off / superseded (NOT "all kinds flowing").** The producer's explicit
  degraded-state (`live_diff_resolution_unavailable`, `freshness: partial`, `requirement_nearby`
  basis) was already present and tested. Added the missing behavioral coverage for
  `orphaned_entity_link` (emitted but previously zero-coverage). Of ADR-006's 11 fact kinds the
  producer emits 8; the three unemitted are now PROVENANCED in ADR-006 (annotation): 
  `active_finding_linked`/`waived_finding_linked` are **superseded** by the dedicated
  `weft.plainweave.wardline_peer_facts.v1` producer (PDR-014) — wiring them into the preflight
  envelope is an owner-gated fork intentionally NOT taken; `open_linked_work` is **sibling-gated**
  (handed off, below). Fixed a stale doc claim (the Legis consumer now exists).
- **#3 Loomweave identity resolution — behavior already done+tested; PDR-014-parity contract
  landed.** The live HTTP resolve + capability probe + closed-vocab degraded codes + SEI §8
  oracle were already implemented and tested. Added the missing PRODUCER-side contract:
  `tests/loomweave_contract.py::validate_loomweave_catalog` + a degraded golden
  (`tests/fixtures/contracts/loomweave/catalog-degraded.json`), routing the committed golden
  AND live producer output through one validator so they cannot diverge. The cardinal
  invariant pinned: an `unavailable` adapter never returns a clean-empty page (empty `items`
  must carry a non-empty `degraded[]`).

## Evidence

`make ci` green: **390 tests** (up from 378), **91.18% coverage** (up from 91.14%), mypy
--strict + ruff clean. `wardline scan` clean (0 active). Cross-repo: legis's vendored preflight
oracle stays green (**28 passed**) — additive plainweave-side test/doc changes created no
legis obligation (legis pins the empty `commit_range` scenario; plainweave pins the populated
one). Every new test mutation-verified red-before-green. Zero `src/plainweave/*.py` changes.

## Scope explicitly NOT taken (honesty)

- The preflight wire-golden was NOT enriched with `orphaned_entity_link`/`requirement_nearby`;
  the behavioral test closes the coverage gap, and the wire-golden remains one representative
  scenario — avoiding a byte-pin re-vendor and any cross-repo churn for no added guarantee.
- No live Filigree join, no `gap_create_work` write path (would mutate a sibling; spine-prohibited).

## Sibling follow-on (OWNER-GATED — handed off, not done)

`docs/handoffs/2026-06-29-filigree-linked-work-facts.md`: a peer prompt asking Filigree to emit
a local, boundary-clean linked-work facts artifact (mirroring `.wardline/*.jsonl`) that
Plainweave could adapt in-grant to emit real `open_linked_work` facts.

## Reversal trigger

If a boundary-clean local Filigree facts artifact lands, `open_linked_work` becomes emittable
in-grant and the ADR-006 emission fork reopens (a `FiligreeAdapter` + its contract test, a
separate owner-gated bid). Recorded in ADR-006's emission-status annotation.
