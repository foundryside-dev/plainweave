# Peer prompt — Warpline: consume Plainweave requirements enrichment

**To:** the Warpline maintainer / implementing agent.
**From:** Plainweave (owner-gated sibling handoff, 2026-06-27).
**Status:** ready to implement once the item schema is ratified (see the sibling prompt
`2026-06-27-warpline-interface-lock-item-schema.md`).

## Context

Warpline's frozen contract reserves an `enrichment.requirements` slot
(`enrichment` keys: `sei, edges, work, risk, governance, requirements`; closed vocab
`present | absent | unavailable`). It is currently always empty (`requirements: []`).
**Plainweave is the owning producer of requirements facts** — Warpline re-derives
risk as an ordering signal but does not own requirements. Plainweave has now shipped a
local-first producer; this task wires Warpline to consume it.

## What Plainweave gives you

A local, read-only, advisory MCP tool + contract:

- Tool: `plainweave_requirements_enrichment_get(entity_refs: [str])`
- Envelope: `weft.plainweave.requirements_enrichment.v1`
- Frozen golden: `tests/fixtures/contracts/warpline/requirements-enrichment.json`
  in the Plainweave repo (implement-to this; do not edit it).

Per entity it returns:

```json
{
  "entity_ref": "loomweave:eid:<32hex> | <locator>",
  "status": "present | absent | unavailable",
  "requirements": [
    {"requirement_id": "req-N", "stable_id": "plainweave:req:<...>", "version": 1,
     "type": "functional", "criticality": "medium",
     "binding": {"relation": "satisfies", "actor_kind": "agent|human",
                 "freshness": "current|stale|orphaned|unknown"}}
  ],
  "reason": "... | null",
  "freshness": "current|stale|orphaned|unknown|unavailable"
}
```

Status semantics (already mapped Plainweave-side — do not re-interpret):
- `present` — entity resolves to ≥1 alive requirement binding; `requirements` is non-empty.
- `absent` — entity is known but has **no** requirement bound. Definitive "none here."
- `unavailable` — Plainweave could not determine (identity unresolved, store error,
  unreachable). **"I can't tell" — never "no requirements."**

## What to build (Warpline side)

1. Add a Plainweave enrichment client behind your existing enrichment-resolution path,
   keyed on `sei` (preferred) or `locator`, consistent with how you resolve the other
   enrichment keys (`work` from filigree, `risk` from wardline).
2. For each entity in a `warpline_impact_radius_get` / `warpline_reverify_worklist_get`
   response:
   - call the Plainweave tool (batch `entity_refs` where possible),
   - set envelope-level `enrichment.requirements` to the producer's status, and
   - populate the item-level `requirements: [...]` array from the producer items.
3. Degrade exactly per the closed vocab and the warpline degrade doc:
   - Plainweave present + data → `present`.
   - Plainweave present + no fact → `absent`.
   - Plainweave unreachable / errored → `unavailable` (NOT a transport error surfaced
     as clean; NOT `absent`).

## Hard invariants (do not violate)

- **Advisory, never gates.** Requirements enrichment is an ordering/context signal,
  exactly like `risk`. It must never produce or imply an allow/block/clean verdict.
- **No-silent-clean.** `absent` and `unavailable` are explicit and distinct;
  `unavailable` is never collapsed to `absent` or to an empty-clean state.
- **Opaque SEI.** Treat `loomweave:eid:...` and `plainweave:req:...` as opaque; never
  mint or parse them.
- **Local-only seam.** Plainweave's producer is `local_only: true,
  live_peer_calls: false`. Your client call to it is the only hop.

## Acceptance criteria

- A reverify-worklist item shows `enrichment.requirements: "present"` with a populated
  item array when Plainweave has bindings for the entity.
- Shows `"absent"` (empty array) when Plainweave knows the entity but has no requirement.
- Shows `"unavailable"` when Plainweave is unreachable — verified by a fault-injection
  test, and asserted to differ from `absent`.
- A Warpline-side contract test pins these against the frozen Plainweave golden
  `weft.plainweave.requirements_enrichment.v1`.

## References

- Plainweave spec: `docs/superpowers/specs/2026-06-27-peer-facts-wardline-warpline-design.md` §6.
- Warpline frozen contract: `/home/john/weft/pm/2026-06-13-warpline-interface-lock.md`.
- Degrade/enrichment vocab: warpline-workflow `references/degrade-and-federation.md`.
