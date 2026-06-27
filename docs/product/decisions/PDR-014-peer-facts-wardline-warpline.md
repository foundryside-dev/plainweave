# PDR-014: Peer facts delivered — Wardline peer facts + Warpline requirements enrichment

Date: 2026-06-27   Status: accepted   Author: agent:claude-product-owner   Owner sign-off: EXPLICIT (owner set the day's bid; authorized subagent-driven multi-agent delivery via "ultracode")
Related: PDR-004 (cross-member seam policy), PDR-008 (seam validated on live peers), PDR-011 (doctor federation parity), PDR-009 (no-silent-clean / no-vanity-metric)

## Context

The agent verdict named five production blockers: live peer adapters, explicit
degraded-state behaviour, Loomweave-owned identity resolution, Legis fact emission, and
Warpline/Wardline/Filigree contract tests. The owner steered today as **harden + build
out** under the soft-launch/RC posture, and set the bid: define **Wardline peer facts**
and complete **Warpline requirements enrichment** — Plainweave side first. (This
superseded an earlier same-session "federation operability / install surfaces" pick.)

## Options considered (the design forks, owner-approved)

1. Scope — **Plainweave-side only** vs also wiring the sibling repos.
2. Wardline resolved/unseen — **snapshot-diff (scope-bounded)** vs latest-snapshot only.
3. Warpline shape — **dedicated `requirements_enrichment.v1`** vs extend `entity_intent_context.v1`.

## The call

Plainweave-side only. Two new local-first, advisory producers + frozen `.v1` contracts,
delivered via brainstorm → spec → 17-task subagent-driven TDD workflow → consolidated fix
pass → opus whole-branch review, **merged to `main` (`bc37a24`)**:

- **`weft.plainweave.wardline_peer_facts.v1`** — surfaces `.wardline/*-findings.jsonl`
  findings (active/waived/baselined/judged, defect/non-defect) + resolved-or-unseen.
- **`weft.plainweave.requirements_enrichment.v1`** — Plainweave-owned producer for
  Warpline's reserved `enrichment.requirements` slot (`present|absent|unavailable`).

`make ci` green (355 tests, 90.94% cov, mypy --strict, ruff); `wardline scan` clean.
**Retires 3 of the 5 blockers**: live-data peer adapters, explicit degraded-state, and
Warpline/Wardline contract tests.

**No-silent-clean corrections baked in** (the bid's thesis; PDR-009 regression class):
resolved/unseen is bounded by the actually re-scanned scope (scan-identity manifest
PRIMARY + path-set heuristic FALLBACK — a "not re-scanned" finding is never reported
"resolved"); `unresolved` AND dead-binding both map to `unavailable`, never `absent` —
both now pinned by mutation-verified tests. The unemittable `stale` freshness was dropped
(no snapshot-age threshold defined; spec §5.4 reconciled).

## Rationale

Production-readiness hardening with **frozen contract tests as the durable guard**.
Consumer/producer-of-own-requirements is in-grant (the Loomweave-adapter pattern). The
sibling-side wiring stays handed-off, never unilateral.

## Sibling follow-on (OWNER-GATED — handed off, not done)

Three peer prompts under `docs/handoffs/`: (1) Warpline consumer of the new producer;
(2) Wardline scan-identity/scope metadata — owner is building this **in parallel** for
integration testing (it becomes the agreed `scan_manifest` contract); (3) Warpline
interface-lock owner ratifies the proposed enrichment item schema (§6.3).

## Reversal trigger

If the Warpline interface-lock owner **rejects** the proposed enrichment item schema, the
`requirements_enrichment` item shape reopens and its wire-golden stays structure-pinned
(not byte-pinned) — already the design posture (spec §11). If Wardline never emits
scan-identity metadata, resolved/unseen stays heuristic-bounded (honest, flagged
`wardline_scan_identity_absent`). Accepted minor debt: a few spec-inherited smells
(redundant `_read_manifest`, dead `_summary` engine_metrics param) left as-is; trivial.
