# Plainweave peer facts: Wardline findings + Warpline requirements enrichment

Status: APPROVED (design forks ratified by owner 2026-06-27) — pending spec review.
Author: Plainweave product owner session.
Supersedes: nothing. Extends the peer-adapter pattern established by the Loomweave
catalog adapter and the Legis preflight-facts producer.

## 1. Problem & context

The agent verdict on Plainweave names five production blockers: **live peer
adapters, explicit degraded-state behavior, Loomweave-owned identity resolution,
Legis fact emission, and Warpline/Wardline/Filigree contract tests.** This bid
retires three of them by shipping two new local-first, advisory peer producers and
their frozen contracts:

1. **Wardline peer facts** — `weft.plainweave.wardline_peer_facts.v1`. Surface
   Wardline findings (active / waived / baselined / judged / resolved-or-unseen /
   non-defect) as advisory context. Plainweave consumes Wardline's local findings
   output; it never runs a scan, never judges, never gates.
2. **Warpline requirements enrichment** — `weft.plainweave.requirements_enrichment.v1`.
   Warpline's frozen contract reserves an `enrichment.requirements` slot that
   **Plainweave is the owning producer for** (Plainweave owns requirements; Warpline
   only re-derives risk as an ordering signal). Build the Plainweave-side producer +
   contract so Warpline can later consume it and stamp `present | absent | unavailable`.

Both are local-only (`live_peer_calls: false`), advisory (zero verdict vocabulary,
machine-enforced by the shared no-verdict validator), and explicit about degraded
state (no silent-clean).

## 2. Authority boundary (the spine)

- **Today is Plainweave-side only**: both producers, their frozen `.v1` contracts,
  and tests, inside this repo. In-grant — Plainweave reads peer local state (like the
  Loomweave catalog adapter) and produces facts about its own requirements.
- **Owner-gated sibling follow-on (NOT today)**: the Warpline-repo wiring (Warpline
  calling the Plainweave producer and stamping `enrichment.requirements`); any
  Wardline-repo change; and ratification of the proposed item-level schema for the
  reserved Warpline slot. These are handed off as **peer implementation prompts**
  (§7), never done unilaterally.
- **No verdict, ever**: neither producer emits allow/block/deny/approved/verdict/gate
  tokens. The shared structural validator (mirroring `tests/preflight_contract.py`)
  rejects them across keys, severity values, and string tokens.

## 3. Non-goals (YAGNI)

- No running of `wardline scan` (read existing `.wardline/` output only; no live call).
- No interpretation of Wardline severity as a gate; severity is surfaced verbatim as
  advisory context. Wardline owns trust policy.
- No Warpline-repo or Wardline-repo edits this session.
- No new auth, no multi-project fan-out, no caching layer.

## 4. The cardinal invariant: no-silent-clean

`metrics.md` makes "Zero silent-clean results when peer context is absent or stale" a
machine-enforced guardrail; PDR-009's review caught a silent-clean regression
("I-can't-tell" encoded as a clean number). Every degraded condition in both
producers MUST be reported in-band as `absent`/`unavailable`/`degraded[]` — never as
an empty-but-ok result that reads as "nothing here." Three specific places this bites
(all addressed below): Wardline resolved/unseen across differently-scoped snapshots;
the Warpline `unresolved → unavailable` mapping; and the contract tests, which the
real `.wardline/` data cannot exercise.

## 5. Item 1 — Wardline peer facts

### 5.1 Source & adapter

`src/plainweave/wardline_adapter.py`, class `WardlineAdapter(root)`, mirroring
`LoomweaveAdapter`: `health()` + `list_peer_facts(...)`. Source = the **most recent
`.wardline/*-findings.jsonl`** (timestamp-sorted), read-only, local-first. No
mutation, no scan, no network.

Finding record shape (observed, frozen by Wardline upstream — Plainweave consumes
opaquely): `fingerprint`, `kind` (`defect | metric | fact | classification |
suggestion`), `location {path, line_start, line_end, col_start, col_end}`,
`maturity`, `message`, `properties`, `qualname`, `related_entities`, `rule_id`,
`severity` (`CRITICAL | ERROR | WARN | INFO | NONE`), `suggestion`,
`suppression_reason`, `suppression_state` (`active | waived | baselined | judged`).

### 5.2 States surfaced (advisory)

- **Suppression state** — verbatim from `suppression_state`: `active | waived |
  baselined | judged`. `suppression_reason` carried alongside when present.
- **Non-defect** — `kind ∈ {metric, fact, classification, suggestion}` is surfaced
  and tagged `non_defect: true` (the bid explicitly requires non-defect findings stay
  visible). `kind == defect` → `non_defect: false`. The synthetic engine record
  (`location.path == "<engine>"` / `rule_id` starting `WLN-ENGINE-METRICS`) is
  surfaced separately as run-metrics, NOT as an entity-anchored finding, and is
  excluded from the resolved/unseen diff (§5.3).
- **Resolved/unseen** — computed by snapshot diff under the honest rule in §5.3.

### 5.3 Resolved/unseen — the no-silent-clean algorithm

A finding is `resolved/unseen` when its `fingerprint` was in an earlier snapshot but
is gone from the latest — BUT only if the latest scan actually re-covered its
surface. The JSONL carries **no scan-scope manifest** (verified: keys are
findings-only; the engine-metrics record holds only perf counters). So the scanned
surface is approximated by the **set of `location.path` values present in the latest
snapshot** (`latest_paths`).

```
latest, prior = two most-recent snapshots (by timestamp in filename)
latest_fps  = { r.fingerprint for r in latest }
latest_paths = { r.location.path for r in latest
                 if path not in (None, "<engine>") }

for each prior record p with p.fingerprint not in latest_fps:
    if p.location.path in latest_paths:
        -> resolved_or_unseen      # path re-scanned, finding gone: honest resolved
    else:
        -> indeterminate           # path NOT re-scanned: cannot say resolved
                                    # counted under degraded[], reported unavailable
```

Degrade rules (all in-band, never silent):

- **< 2 snapshots** → resolved/unseen = `unavailable`; `degraded[]` carries
  `wardline_single_snapshot`.
- **Any prior fingerprint whose path is not in `latest_paths`** → that count is
  reported as `indeterminate` (not resolved); `degraded[]` carries
  `wardline_scope_mismatch` with the jaccard overlap of the two path-sets, so a thin
  comparison looks thin.
- **No `.wardline/` directory / no findings file** → `freshness: unavailable`,
  `degraded[]` carries `wardline_findings_absent`; the result is explicitly empty-as-
  unavailable, never empty-as-clean.

Unobservable caveat (documented, not maskable): without a scan manifest we cannot
confirm the two snapshots used the same ruleset/config; this is stated in-band in the
envelope `notes`. The Wardline peer prompt (§7) asks upstream to emit scan-identity
metadata so this heuristic can be replaced by an exact scope check.

### 5.4 Envelope `weft.plainweave.wardline_peer_facts.v1`

House success-envelope (`envelopes.py` conventions): `schema`, `ok`, `data`,
`warnings`, `meta {producer, generated_at, project}`. `data` carries:

```
{
  "source": {"snapshot": "<filename>", "snapshot_count": N, "prior": "<filename|null>"},
  "freshness": "current | stale | unavailable",
  "facts": [
    {
      "fingerprint": "...", "rule_id": "...", "kind": "...",
      "non_defect": bool, "severity": "...", "suppression_state": "...",
      "suppression_reason": "... | null",
      "location": {"path": "...", "line_start": N, ...},
      "qualname": "... | null", "message": "..."
    }
  ],
  "resolved_or_unseen": [ {"fingerprint": "...", "rule_id": "...", "location": {...}} ],
  "engine_metrics": [ {...} ],          // the synthetic run-metric records, surfaced apart
  "summary": {
    "by_suppression_state": {"active": N, "waived": N, "baselined": N, "judged": N},
    "by_kind": {...}, "defect": N, "non_defect": N,
    "resolved_or_unseen": N, "indeterminate": N
  },
  "degraded": [ {"code": "...", "message": "...", "detail": {...}} ],
  "authority_boundary": {"local_only": true, "live_peer_calls": false,
                          "governance_verdicts": false, "trust_policy_owner": "wardline"},
  "notes": ["scan-identity metadata absent; resolved/unseen bounded by latest path-set", ...]
}
```

No-verdict validator runs over the whole envelope.

## 6. Item 2 — Warpline requirements enrichment

### 6.1 Producer

Reuse the existing `entity_intent_context` resolution
(`mcp_surface.py:_entity_intent_context_item`, states `resolved |
resolved_no_binding | unresolved`, plus `peer_resolution`). New surface method
`plainweave_requirements_enrichment_get(entity_refs)` → envelope
`weft.plainweave.requirements_enrichment.v1`.

### 6.2 Status mapping (no-silent-clean corrected)

Per entity, the closed Warpline vocab is derived as:

| Plainweave resolution | enrichment.requirements | meaning |
|---|---|---|
| `resolved` (≥1 alive requirement binding) | `present` | peer present, fact attached |
| `resolved_no_binding` (entity in catalog, no requirement bound) | `absent` | peer present, definitively no requirement fact |
| `unresolved` (identity not resolvable) | `unavailable` | **cannot determine — NOT "no requirements"** |
| store error / Plainweave unreachable | `unavailable` | producer could not answer |

The `unresolved → unavailable` split is the load-bearing correction: an identity gap
is "I can't tell," never "absent."

### 6.3 Item-level shape (Plainweave proposes; sibling ratifies)

Warpline froze only the slot key + status vocab; the item array is Plainweave's to
define (in-grant — Plainweave owns requirement facts). Proposed item (advisory, no
verdict tokens):

```
{
  "requirement_id": "req-N",
  "stable_id": "plainweave:req:<...>",
  "version": 1,
  "type": "functional | nonfunctional | constraint | ...",
  "criticality": "low | medium | high | critical",   // advisory ordering signal, NOT a gate
  "binding": {
    "relation": "satisfies | verifies | derives | ...",
    "actor_kind": "agent | human",                    // provenance: agent != accepted human truth
    "freshness": "current | stale | orphaned | unknown"
  }
}
```

`status: present` carries a non-empty `items` array; `absent`/`unavailable` carry
`items: []` plus the reason. This proposed schema is sent to the Warpline
interface-lock owner for ratification (§7) before the wire-golden is byte-pinned.

### 6.4 Envelope `weft.plainweave.requirements_enrichment.v1`

```
{
  "schema": "weft.plainweave.requirements_enrichment.v1", "ok": true,
  "data": {
    "items": [
      {"entity_ref": "loomweave:eid:<...> | <locator>",
       "status": "present | absent | unavailable",
       "requirements": [ <item shape §6.3> ],
       "reason": "... | null",
       "freshness": "current | stale | orphaned | unknown | unavailable"}
    ],
    "summary": {"present": N, "absent": N, "unavailable": N}
  },
  "warnings": [...],
  "authority_boundary": {"local_only": true, "live_peer_calls": false,
                          "governance_verdicts": false, "requirements_owner": "plainweave"},
  "meta": {...}
}
```

## 7. Deliverable: peer implementation prompts (handoff briefs)

Owner directive: produce prompts for peers who must implement the sibling-side
functionality. Written to `docs/handoffs/`, each self-sufficient (contract ref, exact
shapes, acceptance criteria, no-silent-clean invariants):

1. **`2026-06-27-warpline-requirements-enrichment-consumer.md`** — for the Warpline
   team/agent. Consume `weft.plainweave.requirements_enrichment.v1`; map status into
   `enrichment.requirements` (`present|absent|unavailable`, never an implied clean
   state); populate the item array; `unavailable` when Plainweave is unreachable.
   Acceptance: a reverify worklist item shows `enrichment.requirements: present` with
   a populated array when Plainweave has bindings, `absent` when it has none, and
   `unavailable` when Plainweave is down — proven by a contract test against the
   frozen Plainweave golden.
2. **`2026-06-27-wardline-scan-identity-metadata.md`** — for the Wardline team/agent.
   Emit scan-identity/scope metadata (covered path-set / scope selector, ruleset id,
   commit) in the findings JSONL (a manifest record or per-run header) so consumers
   compute resolved/unseen by exact scope rather than the latest-path-set heuristic.
   Acceptance: two snapshots are comparable by an explicit scope key; consumers can
   distinguish "resolved" from "not re-scanned" without guessing.
3. **`2026-06-27-warpline-interface-lock-item-schema.md`** — for the Warpline
   interface-lock owner. Ratify (or amend) the proposed item-level schema (§6.3) for
   the reserved `enrichment.requirements` slot, so Plainweave can byte-pin the
   producer wire-golden against an agreed shape.

## 8. Surfacing (service / CLI / MCP)

- **Service**: `PlainweaveService._wardline_adapter()` (on-demand, mirrors
  `_loomweave_adapter()`); a `requirements_enrichment` producer method reusing intent
  context.
- **MCP**: tools `plainweave_wardline_peer_facts_list` and
  `plainweave_requirements_enrichment_get`, each with `MCP_TOOL_METADATA`
  (`mutates: false`, `local_only: true`, `peer_side_effects: []`, authority_boundary)
  and `CONTRACT_RESOURCES` entries; both contract URIs added to `MCP_RESOURCE_URIS`.
- **CLI**: `plainweave doctor` gains a Wardline health line
  (`WardlineAdapter(root).health()`), report-only.

## 9. Contract-test discipline (and §4 fixtures)

Mirror the preflight wire-golden: byte-pinned golden fixture in
`tests/fixtures/contracts/{wardline,warpline}/` + structural validator
(`tests/{wardline,warpline}_contract.py` with no-verdict assertions) + two-layer
wire-golden test (`tests/contracts/test_*_wire_golden.py`: blob-pin + producer
recheck over a seeded project). Register both in `REQUIRED_FIXTURES`.

Because the real `.wardline/` is 100% `active`/non-defect/varying-scope, ship crafted
fixture snapshot sets under `tests/fixtures/wardline/`:

- **A — same-scope, a resolution**: ≥2 snapshots, identical path-set, one fingerprint
  dropped → `resolved_or_unseen` populated.
- **B — scope mismatch**: prior path absent from latest → that fingerprint is
  `indeterminate`/`unavailable`, NOT resolved; `wardline_scope_mismatch` degraded.
- **C — single snapshot**: resolved/unseen `unavailable`; `wardline_single_snapshot`.
- **D — full state matrix**: a snapshot carrying `waived`, `baselined`, `judged`,
  defect + non-defect → each surfaced with correct state/tag.

A contract test that never exercises the bid-named states does not retire the
blocker; these fixtures are mandatory.

## 10. Definition of done

- Both adapters/producers implemented TDD; both envelopes pass the no-verdict
  validator; both wire-goldens byte-pinned with producer recheck.
- Fixture scenarios A–D all green.
- `make ci` green (mypy --strict, ruff, full pytest, coverage not regressed) and
  `wardline scan . --fail-on ERROR` clean.
- Three peer prompts written under `docs/handoffs/`.
- Spec + prompts committed; PDR drafted at checkpoint recording the bet, the
  no-silent-clean corrections, and the owner-gated sibling follow-on.

## 11. Open caveats (carried in-band, not masked)

- Wardline scan-identity is unobservable until the §7.2 prompt lands; resolved/unseen
  is path-set-bounded and says so in `notes`.
- The Warpline item schema is *proposed* until the §7.3 ratification; the producer
  wire-golden is frozen only after agreement (until then the test pins structure, not
  bytes, to avoid an expensive re-freeze).
