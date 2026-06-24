# PDR-005: Beta-Candidate Golden-Vector Gate Met on Plainweave Self-Dogfood

Date: 2026-06-24   Status: accepted   Author: agent:claude-product-owner   Owner sign-off: n/a (within grant)
Related: beta-charter.md (Beta-candidate gate), metrics.md (north-star), PDR-001

## Context

The beta vertical slice (intent-graph model, SEI binding, read primitives, write
surface) shipped and closed 2026-06-21, but no metric had ever been read — the
acceptance gap was open. The beta-charter's beta-candidate gate requires a golden
vector demonstrated *first on Plainweave itself*. Accepting against criteria is
autonomous under the confirmed grant.

## Options considered

1. Accept the gate from shipped code + green CI alone — fast, but tests prove the
   code runs, not that the product answers "why does this exist?"; leaves the gap open.
2. Run the golden vector live on Plainweave's own public surfaces and judge against
   the charter acceptance bar — closes the gap with real data; only as good as the
   catalog's surface enumeration.
3. Defer until the sibling-peer dogfood — one combined run, but leaves the charter's
   Plainweave-first gate unmet and the bet unproven longer.

## The call

Option 2. Initialized the local store and ran the vector on the two genuinely-public
entry points (`plainweave.cli.main`, `plainweave.mcp_server.main`):
record → goal → goal↔requirement link → SEI bind → orphans/trace/corpus. All green;
`orphans` empty at all three levels; `trace(cli.main)` → `[req-1, goal-1]`; `corpus`
returned two rows each carrying goal + code context. Every charter acceptance-bar line
met. **Beta-candidate gate: PASS on Plainweave self-dogfood.**

## Rationale

Only a live corpus proves the product delivers value; CI cannot. Option 2 is the
cheapest real test of the riskiest assumption and satisfies the charter's
Plainweave-first gate. PDR-001's reversal trigger explicitly did NOT fire — useful
answers were produced for representative surfaces without duplicating Loomweave/Legis
authority — so the bet holds.

## Reversal trigger

Reopen if (a) a re-run after corpus growth breaks orphans/trace/corpus or yields
dishonest results, or (b) the sibling-peer dogfood (next bet) fails to reproduce the
end-to-end answer on a peer. Bind to metrics.md "corpus rows with both goal and code
context" and the orphan counts.
