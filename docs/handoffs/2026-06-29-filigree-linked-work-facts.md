# Peer prompt — Filigree: emit a local linked-work facts artifact for Plainweave

**To:** the Filigree maintainer / implementing agent.
**From:** Plainweave (owner-gated sibling handoff).
**Date:** 2026-06-29 (PDR-018, seam hardening).
**Status:** PROPOSED — owner-gated. Do **not** implement on the Plainweave side; this is
Filigree-side work plus a small Plainweave adapter once the artifact exists.

## Why

Plainweave's Legis preflight producer (`weft.plainweave.preflight_facts.v1`, ADR-006)
reserves an `open_linked_work` fact kind: "for a scoped requirement/gap, what Filigree
issues are open and linked?". Plainweave **cannot emit it today** and honestly reports the
gap in-band as the `linked_work_facts_unavailable` warning (no-silent-clean). It cannot be
emitted in-grant because:

- Plainweave never calls a sibling live: `authority_boundary.live_peer_calls = false`. The
  sanctioned `entity_association_list_by_entity` (ADR-029) is a live MCP/HTTP call, so it
  would break that boundary.
- `.filigree/` is a Filigree-owned SQLite DB. Direct reads would couple Plainweave to
  Filigree's internal schema — exactly the coupling the thin-member doctrine forbids.

Unlike Wardline (whose append-only `.wardline/*-findings.jsonl` Plainweave already adapts
in-grant), Filigree exposes **no local, boundary-clean facts artifact** Plainweave can read.

## The ask (Filigree-side)

Emit a **local, append-only or snapshot facts artifact** — mirroring `.wardline/*.jsonl` —
that Plainweave can read read-only with no live call. Suggested: `.filigree/linked-work.jsonl`
(or a documented export command) with, per row, the stable identity Plainweave keys on plus
the issue's open/closed lifecycle facts. Concretely, enough to answer "for requirement R /
gap G, which Filigree issues are open and link to it":

- the linked entity/requirement/gap identity (a SEI or the `filigree_issue` / `gap` ids
  Plainweave already stores as opaque trace refs — see `service.py` canonical relations
  `('filigree_issue','implements_work_for','requirement_version')` and
  `('filigree_issue','resolves_gap','gap')`),
- issue id, status/lifecycle (open vs closed/resolved), and a freshness/observed-at stamp.

Facts only — **no verdicts**. Filigree owns the work lifecycle; Plainweave only surfaces the
linkage as advisory context. Plainweave will **never** create or move Filigree work from
this seam (the `gap_create_work` write path stays unimplemented; it would mutate a sibling).

## Then (Plainweave-side, once the artifact exists — a separate owner-gated bid)

A `FiligreeAdapter` reading that artifact in-grant (the Wardline-adapter pattern), wiring real
`open_linked_work` facts into `preflight_facts.v1`, with the `linked_work_facts_unavailable`
warning degrading to a `filigree_linked_work_absent` code only when the artifact is genuinely
absent — and a frozen contract test (mirroring the wardline/warpline/loomweave contract tests
landed in PDR-018).

## Reversal trigger (recorded in ADR-006)

If this boundary-clean local artifact lands, `open_linked_work` becomes emittable in-grant and
the ADR-006 emission fork (PDR-018) reopens. Until then, the in-band
`linked_work_facts_unavailable` warning is the correct honest posture.
