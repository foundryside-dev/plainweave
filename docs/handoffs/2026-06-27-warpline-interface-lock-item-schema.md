# Peer prompt — Warpline interface-lock owner: ratify the requirements item schema

**To:** the owner of the frozen Warpline interface lock
(`/home/john/weft/pm/2026-06-13-warpline-interface-lock.md`).
**From:** Plainweave (sibling handoff, 2026-06-27).
**Decision requested:** ratify, amend, or reject a proposed item-level schema.

## Context

The frozen Warpline contract reserves `enrichment.requirements` with the closed status
vocab `present | absent | unavailable` and shows the item array empty (`[]`) in the
worked example. The **item shape was never specified**. Plainweave is the owning
producer of requirements facts and has shipped a producer
(`weft.plainweave.requirements_enrichment.v1`); to byte-pin its wire-golden, the item
shape needs an agreed contract, not a unilateral one.

## Proposed item schema (advisory only — no verdict tokens)

```json
{
  "requirement_id": "req-N",
  "stable_id": "plainweave:req:<...>",
  "version": 1,
  "type": "functional | nonfunctional | constraint | ...",
  "criticality": "low | medium | high | critical",
  "binding": {
    "relation": "satisfies | verifies | derives | ...",
    "actor_kind": "agent | human",
    "freshness": "current | stale | orphaned | unknown"
  }
}
```

Rationale per field:
- `stable_id` / `version` — opaque stable identity + version so Warpline can key/dedupe
  without parsing.
- `criticality` — an **ordering/triage signal only**, consistent with how Warpline uses
  `risk`. It is explicitly NOT a gate input.
- `binding.actor_kind` — provenance: an `agent`-authored binding is a proposal, not
  accepted human truth. Consumers must not present `agent` bindings as ratified.
- `binding.freshness` — so a stale/orphaned binding looks stale, not authoritative.

## Invariants the schema must preserve

- No allow/block/deny/approved/verdict/gate tokens anywhere (Plainweave's shared
  validator rejects them; Warpline should too).
- Closed status vocab unchanged: `present | absent | unavailable`, where `unavailable`
  is "could not determine," never an implied clean state.

## Decision

- **Ratify** → Plainweave byte-pins the producer wire-golden to this shape and the
  Warpline consumer prompt (`2026-06-27-warpline-requirements-enrichment-consumer.md`)
  proceeds.
- **Amend** → return field changes; Plainweave updates the producer + golden before pin.
- **Reject** → Plainweave keeps the producer structurally validated but unpinned and
  the seam stays proposal-only.

## References

- Plainweave spec: `docs/superpowers/specs/2026-06-27-peer-facts-wardline-warpline-design.md` §6.3.
- Warpline frozen contract + enrichment vocab as cited above.
