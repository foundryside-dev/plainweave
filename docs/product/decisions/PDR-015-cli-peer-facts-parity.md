# PDR-015: CLI/MCP parity for the peer-facts producers + Lacuna tour regression demos

Date: 2026-06-28   Status: accepted   Author: agent (ultracode, subagent-driven)   Owner sign-off: EXPLICIT (owner approved the design spec; selected the full resolved/unseen scenario; authorized "ultracode")
Related: PDR-014 (peer facts delivered — the producers this exposes), PDR-010-lacuna-intent-regression-harness (the Lacuna tour-leg pattern extended here), PDR-009 (no-silent-clean / no-vanity-metric)

## Context

PDR-014 shipped two local-first, advisory peer-facts producers with frozen `.v1`
contracts — `weft.plainweave.wardline_peer_facts.v1` and
`weft.plainweave.requirements_enrichment.v1` — but **MCP-only**. The Lacuna cross-member
tour (PDR-010 pattern) exercised the Plainweave intent leg over the CLI but did **not**
exercise either peer-facts producer, so two shipped capabilities had no cross-member
regression guard and no CLI surface. This is a harness-completeness / regression bet, not
a correctness fix, and explicitly **not a release blocker**.

## Options considered (the design forks, owner-approved)

1. Tour drive path — **add real CLI subcommands** (close the product parity gap, keep the
   tour leg uniform over the CLI) vs. drive the producers over Lacuna's MCP-attachment path
   (`tour/mcp_attachment.py`) with zero Plainweave change.
2. CLI reuse — **call `PlainweaveMcpSurface` verbatim** vs. extract a new service method.
3. Wardline demo depth — **full resolved/unseen** (two snapshots + scan-identity manifests,
   honest scope-mismatch) vs. a first-cut (active/non-defect + absent→unavailable only).

## The call

CLI parity via the surface; full resolved/unseen demo.

- **Two new CLI subcommands** (`plainweave wardline-peer-facts`,
  `plainweave requirements-enrichment <ref>...`) emit the producers' full `.v1` envelopes
  via `--json`, **reusing `PlainweaveMcpSurface`** through a local import inside each
  handler (dodging the `cli_commands`↔`mcp_surface` cycle). The envelope is passed through
  unchanged, so `authority_boundary`-inside-`data` and the zero-verdict invariant are
  automatic. New CLI tests run the existing no-verdict structural validators over the CLI
  output (the `test_cli_intent_coverage` precedent).
- **Lacuna tour** gains `plainweave+warpline` and `plainweave+wardline` cells driven by two
  new leg demos: `pw-requirements-enrichment` (covered→present, orphan→absent,
  identity-gap→unavailable — never a silent `absent`) and `pw-wardline-peer-facts` (a
  frozen tour-time two-snapshot fixture: active + non-defect findings surface; an in-scope
  finding resolves; an out-of-scope prior finding is honestly flagged
  `wardline_scope_mismatch`; an absent `.wardline/` is `unavailable`, never clean).
- Recorded Lacuna-side as **PDR-0015** (sibling repo; handed off, not unilateral).

`make ci` green (mypy --strict, ruff, coverage ≥90); `wardline scan` clean.

**No-silent-clean preserved end to end** (PDR-009 regression class): the demos *assert*
the degraded states, not just happy paths — `unresolved`/identity-gap → `unavailable`
(never `absent`); absent `.wardline/` → `unavailable` (never clean); out-of-scope prior
finding → `indeterminate` + `wardline_scope_mismatch` (never a silent "resolved").

## Folded-in adjacent changes (provenance: sibling product contract)

Two small, already-tested Plainweave changes landed in the working tree as part of another
product's contract work and ship here by owner decision:
1. `requirements_enrichment` drops `state == "rejected"` traces before building the view
   (a reviewed-and-rejected binding is not coverage) — this *strengthens* the new
   enrichment demo.
2. `_doctor_wardline_check` remediation is root-aware.

## Rationale

Closing the CLI parity gap is a genuine product improvement (the producers were
MCP-only); driving the tour over the CLI keeps the Plainweave leg uniform and avoids
coupling the regression demos to MCP transport. Frozen contract + the cross-member tour
are the durable guards. Version bump/release deferred — additive, not a release blocker
(CHANGELOG `[Unreleased]`).

## Reversal trigger

If the `requirements_enrichment` item shape reopens (PDR-014's Warpline interface-lock
trigger), the enrichment CLI surface and the Lacuna `pw-requirements-enrichment` demo
follow it — they assert status semantics, not byte-pinned item shapes, so they survive a
structure-pinned change. If a future Wardline scan-identity contract changes the
`scan_manifest` record shape, the Lacuna wardline fixture is updated in lockstep (it is a
frozen test fixture, not a wire contract).
