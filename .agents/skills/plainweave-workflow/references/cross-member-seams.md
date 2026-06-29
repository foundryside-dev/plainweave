# Cross-member seams

How Plainweave consumes from and produces facts for its Weft siblings. The unifying
rule: **enrich-only, opaque identity, no silent-clean, no verdicts.**

## Loomweave — identity & catalog (Plainweave consumes)

Plainweave never mints code identity. It consumes Loomweave **SEIs**
(`loomweave:eid:<32hex>`) opaquely:

- `plainweave catalog record` registers a public entity discovered by a sibling
  catalog tool. The SEI is stored verbatim; Plainweave does not parse or synthesise it.
- `plainweave bind sei <entity_id> <requirement_id>` ties a requirement to that
  identity. `--content-hash` captures the entity's hash at attach time so a consumer
  can later detect drift.
- The Loomweave catalog adapter has a **frozen degraded-state contract**
  (`weft.plainweave.loomweave_catalog.v1`): when the adapter is `unavailable` it
  returns an explicit unavailable envelope routed through the same oracle as live
  output — it never returns a clean-empty page that would read as "no entities."

If Loomweave is absent, Plainweave degrades to manual file/symbol references; the
graph still works, identity is just less precise.

## Legis — the git/CI boundary (Plainweave's facts ride out)

Plainweave emits **no enforcement of its own**. Coverage facts cross the git/CI
boundary *through Legis* ("this change adds N public entities bound to no
requirement"). Advisory by default; a repo that wants teeth dials it up through
Legis's policy cells. The preflight advisory cell
(`plainweave_preflight_facts_get`) supplies the facts; Legis decides whether they gate.

## Warpline — requirements enrichment (Plainweave produces, Warpline consumes live)

`plainweave requirements-enrichment <entity_ref>... --json` is the Plainweave-owned
producer (`weft.plainweave.requirements_enrichment.v1`) for Warpline's reserved
`enrichment.requirements` slot. Warpline's `consult_federation` wires it as the
**4th federation member** (alongside filigree/wardline/legis), capability-gated on
the verb being advertised.

Per-entity `status` semantics — **mapped Plainweave-side; consumers pass through, never re-interpret**:

| status | meaning |
|---|---|
| `present` | ≥1 alive requirement bound (the `requirements` array is non-empty) |
| `absent` | entity known, none bound — a definitive "none here" |
| `unavailable` | could not determine (identity unresolved / store error) — **"I can't tell," never "no requirements"** |

The `unavailable` ≠ `absent` distinction is load-bearing and fault-injection-tested:
collapsing `unavailable` to `absent` (or to a clean-empty) would violate no-silent-clean
and let a "can't tell" masquerade as "verified none." Requirement item bodies and SEIs
are **opaque** to the consumer — surfaced, never parsed.

Operational note: a consumer that execs bare `plainweave` from `PATH` runs the
installed uv-tool snapshot, which can lag the dev tree. If the verb isn't advertised,
the consumer reads the member `disabled` even though the code is correct — keep the
installed tool current (`uv tool install --force` / an editable install).

## Wardline — findings as peer facts (Plainweave produces)

`plainweave wardline-peer-facts --json` (`weft.plainweave.wardline_peer_facts.v1`)
surfaces Wardline findings (active / waived / baselined / judged; defect /
non-defect) plus resolved-or-unseen, computed against the **actually re-scanned
scope** — scan-identity manifest primary, with a path-set heuristic fallback that
flags itself in-band. An absent `.wardline/` reports `freshness: unavailable`, never
a clean empty page.

## The freshness / status vocabulary

Across the producers, degraded state is **explicit and distinct** — these are not
interchangeable, and none of them is a silent clean:

- `present` — facts found and returned.
- `absent` — definitively none (the authority looked and there are none).
- `unavailable` — could not determine (peer/store/identity gap). The honest "I can't tell."
- `stale` — facts exist but the thing they describe has moved on.

Surface the exact one; never round `unavailable`/`stale` down to `absent` or up to a clean result.
