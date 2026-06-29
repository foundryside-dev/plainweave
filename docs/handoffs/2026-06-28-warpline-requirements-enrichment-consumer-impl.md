# Peer prompt — Warpline: wire the Plainweave requirements-enrichment consumer

**To:** the Warpline maintainer / implementing agent.
**From:** Plainweave (owner-gated sibling handoff).
**Date:** 2026-06-28 (implementation-grounded refresh of `2026-06-27-warpline-requirements-enrichment-consumer.md`; that doc states the contract, this one states *how to build it against the warpline you have today*).
**Precondition (soft, see end):** the item schema is proposed but not yet ratified in the
interface lock (sibling prompt `2026-06-27-warpline-interface-lock-item-schema.md`). Because
warpline consumes peer facts **opaquely**, you can build this in parallel and land the
byte-pinned contract test when ratification completes — see "On the schema dependency".

## Goal (one line)

`requirements` is the **one federation member warpline never wired**. Wire Plainweave as a
4th member of the `consult_federation` hard seam — structurally identical to how `risk`
(wardline) and `governance` (legis) already work — so `warpline_reverify_worklist_get(...,
include_federation=True)` reports honest per-entity requirement facts and a real
`enrichment.requirements` scalar + reason instead of the reserved `disabled` default.

## Where warpline is today (anchors, all confirmed)

- `src/warpline/envelope.py:18` — `requirements` is already in the **frozen** `ENRICHMENT_VOCAB`
  (`present|absent|unavailable`); `:29` defaults it to `unavailable`; `:78` injects
  `requirements_reason()` as the default reason triple.
- `src/warpline/_enrichment.py:82-103` — `requirements_reason()` is a static **reserved /
  `disabled`** triple ("no requirements-trace transport is wired in warpline yet"). This is the
  honest placeholder you are replacing. `sei_reason()` at `:106-146` is the **template** to copy:
  a status→reason-triple mapper (`clean` / `unresolved_input` / `unreachable`).
- `src/warpline/federation.py` — the `consult_federation` hard seam (PDR-0023):
  `FEDERATION_MEMBERS = ("filigree","wardline","legis")` (`:44`); per-member `_consult_*`
  functions return `(by_locator, weft_reason)`; `LegisGovernanceClient` (`:129-202`) +
  `_consult_legis` (`:285-318`) are the **exact template** — a capability-gated CLI client
  (`.available()` `--help` probe at `:148-168`), `clean` on facts, `unreachable` on raise,
  `disabled` when no client. `federation_transport_blockers` (`:373-418`) declares the missing
  member to the strike.
- `src/warpline/reverify.py:18` — `_empty_enrichment()` already includes `"requirements": []`
  per item; today only `work` is filled inline.
- `src/warpline/commands.py:972-1078` — the reverify assembly: `consult_federation(...)` →
  `_merge_federation_enrichment(items, federation)` (merges per-entity facts onto
  `item.enrichment.{risk,governance}` and returns the scalars) → `_member_scalar(federation, ...)`
  → `build_envelope(enrichment=enrichment_state(... risk=risk_state, governance=gov_state),
  enrichment_reasons={...})`. **`requirements` is simply absent from every one of these calls.**
- `src/warpline/cop.py:366-376` composes the same consults — mirror the requirements member there too.

## What Plainweave gives you (the producer — shipped, stable)

- **CLI (use this — matches your `wardline dossier` / `legis governance-read` transport):**
  `plainweave requirements-enrichment <entity_ref>... --json`
  (`entity_ref` is `nargs="+"`; pass a SEI `loomweave:eid:<32hex>` or a dotted locator; batch
  refs in one call). Defined at `plainweave/src/plainweave/cli_commands.py:137-143,1113-1121`.
  There is an MCP equivalent (`plainweave_requirements_enrichment_get(entity_refs)`) but the CLI
  is the right fit for warpline's subprocess pattern.
- **Envelope:** `weft.plainweave.requirements_enrichment.v1`.
- **Frozen golden (implement-to; do NOT edit it):**
  `plainweave/tests/fixtures/contracts/warpline/requirements-enrichment.json`. Shape:
  ```json
  {
    "schema": "weft.plainweave.requirements_enrichment.v1",
    "items": [
      {"entity_ref": "...", "status": "present|absent|unavailable",
       "requirements": [ {requirement_id, stable_id, version, type, criticality,
                          binding:{relation, actor_kind, freshness}} ],
       "reason": "...|null", "freshness": "current|stale|orphaned|unknown|unavailable"}
    ],
    "summary": {"present": N, "absent": N, "unavailable": N},
    "authority_boundary": {"local_only": true, "live_peer_calls": false,
                           "governance_verdicts": false, "requirements_owner": "plainweave"}
  }
  ```
- **Per-entity status (already mapped Plainweave-side — pass through, do NOT re-interpret):**
  `present` = ≥1 alive requirement bound (`requirements` non-empty); `absent` = entity known,
  none bound (definitive "none here"); `unavailable` = could not determine (identity unresolved /
  store error) — **"I can't tell", never "no requirements"**.

## Build steps (mirror the legis member end to end)

1. **`federation.py` — add the member.**
   - `RequirementsClient` Protocol: `requirements_for_refs(self, refs: list[str]) -> dict[str, dict]`
     returning `{entity_ref: item}` from the producer's `items`.
   - `PlainweaveRequirementsClient` over the CLI (copy `LegisGovernanceClient`): run
     `plainweave requirements-enrichment <refs...> --json` with `cwd=repo`, parse the envelope,
     index `items` by `entity_ref`. Add a `.available()` `--help` probe for `requirements-enrichment`.
     Batch all refs in one subprocess call (the CLI takes `nargs="+"`) — cheaper than per-SEI.
   - `_consult_plainweave(items, requirements_client)` returning `(by_locator, weft_reason)`:
     `disabled` (no client / verb absent) → `unreachable` (subprocess/JSON raised) →
     else map each entity's producer `status`: `present` puts the item's `requirements` array in
     `by_locator[locator]`; `absent`/`unavailable` contribute no facts but **must still drive the
     scalar** (see step 3). Use `_seis()`/locator keying exactly as the other consults do.
   - Add `"plainweave"` to `FEDERATION_MEMBERS`; thread `requirements_client` through
     `consult_federation(...)` (params, `members["plainweave"]`, the per-entity `requirements`
     slot in `entities`), and add a `federation_transport_blockers` entry.

2. **`_enrichment.py` — replace the reserved reason with a real one.**
   Add `requirements_reason_for(status: str)` mirroring `sei_reason()`:
   `present`→`clean`; `absent`→`unresolved_input` (entity known, no binding — cause/fix);
   `unavailable`→`unreachable` (could not determine — cause/fix). Keep the static
   `requirements_reason()` as the `disabled` fallback for when the member isn't wired.

3. **`commands.py` (and `cop.py`) — light it up.**
   - Pass `requirements_client` into `consult_federation`.
   - Extend `_merge_federation_enrichment` to also fill `item.enrichment["requirements"]` from the
     federation `entities` (same merge it does for `risk`/`governance`) and return a `req_state`
     scalar via `_member_scalar(federation, "plainweave")`.
   - Add `requirements=req_state` to the `enrichment_state(...)` call (`commands.py:1073-1078`) and
     `"requirements": requirements_reason_for(req_state)` to `enrichment_reasons` so the envelope's
     reserved default is overridden.
   - Capability-gate the client in the MCP wiring (`mcp.py`) exactly like the legis verb gate.

## Status / scalar mapping (envelope-level, mirror `_member_scalar`)

| Plainweave result for the worklist | `enrichment.requirements` | reason_class |
|---|---|---|
| ≥1 entity `present` (facts returned) | `present` | `clean` |
| all known entities `absent`, none present | `absent` | `unresolved_input` |
| producer unreachable / errored / verb absent | `unavailable` | `unreachable` (down) / `disabled` (no verb) |

## Hard invariants (do not violate)

- **Advisory, never gates.** `requirements` (incl. `criticality`) is an ordering/context signal
  exactly like `risk`. Never produce or imply allow/block/clean/approved/verdict tokens —
  warpline's reason/envelope validators reject them; so does Plainweave's.
- **No-silent-clean.** `absent` and `unavailable` stay explicit and distinct; `unavailable` is
  never collapsed to `absent` or to an empty-clean — assert this with a fault-injection test.
- **Opaque identity & items.** Treat `loomweave:eid:...` / `plainweave:req:...` and the requirement
  item bodies as opaque (pass through, like wardline findings / legis records); never mint or parse.
- **Local-only seam.** The producer is `local_only:true, live_peer_calls:false`; your one CLI hop
  is the only call. Keep warpline's `meta.local_only` / `peer_side_effects: []` intact.
- **Member never omitted.** `plainweave` appears in the federation block with its own weft-reason on
  every `include_federation=True` run — `disabled` when unwired, never silently dropped.

## Acceptance criteria

- A reverify-worklist item shows `enrichment.requirements: "present"` with a populated per-item
  `requirements: [...]` array when Plainweave has bindings for the entity.
- Shows `"absent"` (empty array) when Plainweave knows the entity but has no requirement.
- Shows `"unavailable"` under producer fault — verified by a fault-injection test and asserted to
  differ from `absent`.
- `disabled` (with a transport_blocker) when the installed plainweave lacks the
  `requirements-enrichment` verb — never a faked-empty.
- A warpline-side **contract test pins the consumed shape to the frozen Plainweave golden**
  `weft.plainweave.requirements_enrichment.v1`.
- `plainweave` is present in `FEDERATION_MEMBERS` and the federation block on every federated run.

## On the schema dependency (sibling prompt #3)

Prompt #3 asks the Warpline interface-lock owner to ratify the requirement **item** shape
(`requirement_id, stable_id, version, type, criticality, binding{relation, actor_kind,
freshness}`). It is **not yet ratified**, and Plainweave's golden already uses that shape.
Because warpline consumes items **opaquely** (it surfaces them, it doesn't parse their
internals), you can build and ship the consumer now; only the *byte-pinned* contract test
depends on ratification. Recommended sequencing: ratify #3 → byte-pin the contract test. If you
proceed before ratification, assert **status semantics** (present/absent/unavailable + the
no-silent-clean distinction), not the item internals — a later amend to the item shape then
won't break the consumer.

## References

- Plainweave producer: `cli_commands.py:137-143,1113-1121`; golden
  `tests/fixtures/contracts/warpline/requirements-enrichment.json`; spec
  `docs/superpowers/specs/2026-06-27-peer-facts-wardline-warpline-design.md` §6.
- Warpline template to copy: `federation.py` (legis member end to end), `_enrichment.py:106` (`sei_reason`).
- Warpline frozen contract / enrichment vocab: `/home/john/weft/pm/2026-06-13-warpline-interface-lock.md`;
  warpline-workflow `references/degrade-and-federation.md`.
