# Charter Requirement Dossiers Design

## Decision

Build local, agent-first requirement dossiers before adding the read-only MCP surface. The dossier is a computed view over existing Charter state, exposed by a CLI command and JSON contract:

```bash
charter dossier REQ-AUTH-0001 --json
```

The JSON schema is `weft.charter.requirement_dossier.v1`.

## Product Intent

An agent should be able to ask one question, "what do I need to know about this requirement?", and receive enough structured context to make the next correct move without scraping several command outputs. The dossier is not a report for humans first. It is a stable, local authority packet for agentic planning, review, and execution.

This should make common agent workflows cheaper and safer:

- decide whether a requirement is usable for implementation;
- see whether there is an active draft that changes the approved requirement;
- inspect acceptance criteria without mixing approved and draft criteria;
- see trace authority, freshness, confidence, and state without flattening them;
- understand verification status and stale evidence;
- identify baseline exposure for release snapshots;
- receive machine-readable next actions.

## Scope

Included:

- `CharterService.requirement_dossier(requirement_id)`;
- immutable dataclasses for dossier sections;
- `charter dossier REQ_ID --json`;
- compact human output for `charter dossier REQ_ID`;
- contract fixture for `weft.charter.requirement_dossier.v1`;
- CLI contract fixture for dossier JSON output;
- state and CLI tests;
- roadmap update after implementation.

Excluded:

- no new SQLite tables;
- no live Clarion, Filigree, Wardline, Legis, or MCP peer calls;
- no durable gap records;
- no MCP server implementation;
- no impact-analysis engine;
- no issue closure as satisfaction evidence;
- no UI.

## Data Shape

Top-level dossier keys:

- `schema`: `weft.charter.requirement_dossier.v1`
- `identity`
- `authority_summary`
- `requirement`
- `acceptance_criteria`
- `traces`
- `verification`
- `baseline_exposure`
- `computed_gaps`
- `peer_facts`
- `next_actions`

### identity

Stable names and version coordinates:

- `requirement_id`
- `id`
- `stable_id`
- `current_version`

### authority_summary

Lifecycle summary for agent trust decisions:

- `status`
- `current_approved_version`
- `current_statement_hash`
- `has_active_draft`
- `active_draft_id`
- `verification_status`
- `baseline_count`

### requirement

Current record and requirement text:

- `record`: existing requirement record shape;
- `current_version`: existing version shape or `null`;
- `active_draft`: draft shape or `null`.

The approved current version remains distinct from an active draft. Agents must not silently use draft text as approved text.

### acceptance_criteria

Criteria are split by authority:

- `current_version`: criteria attached to the current approved version;
- `active_draft`: criteria attached to the active draft.

The split is intentional. Draft criteria may indicate upcoming intent, but they are not approved acceptance criteria.

### traces

Trace facts are grouped while preserving every authority bit:

- `incoming`
- `outgoing`
- `by_state`
- `by_relation`
- `items`

Each trace item uses the existing trace-link shape:

- `state`
- `authority`
- `freshness`
- `confidence`
- `target_snapshot`
- endpoint refs

Proposed, accepted, rejected, stale, orphaned, imported, inferred, and peer-reported facts must not be flattened into a single "trace exists" result.

### verification

Wrap the existing verification status model:

- `status`
- `reasons`
- `current_evidence`
- `stale_evidence`

This section must preserve stale evidence instead of hiding it, because stale evidence is often the most useful agent clue after a requirement changes.

### baseline_exposure

Local release-snapshot exposure:

- `items`: baselines containing this requirement;
- `summary`: counts by `current`, `changed`, `missing_current`, and `superseded_since_baseline`.

Each baseline item includes:

- baseline ID, name, locked flag, creator, creation time;
- requirement version and statement hash captured in the baseline;
- current requirement version and hash;
- local relation between the baseline member and current approved version.

### computed_gaps

Ephemeral gap hints computed from local state. These are not persisted and are not P1 gap records.

Examples:

- `no_approved_version`
- `active_draft_pending_review`
- `no_acceptance_criteria`
- `no_verification_method`
- `failing_evidence`
- `stale_evidence`
- `proposed_trace_pending_review`
- `stale_or_orphaned_trace`
- `baseline_version_drift`

Each gap has:

- `code`
- `severity`
- `message`
- `source`

### peer_facts

Explicit local-only marker:

```json
{
  "live_peer_calls": false,
  "sources": [],
  "notes": ["Dossier is computed from the local Charter store only."]
}
```

This keeps future MCP and federation behavior honest. The dossier may later include peer summaries, but this slice must not call peers.

### next_actions

Machine-readable action hints for agents:

- `approve_or_reject_draft`
- `add_acceptance_criteria`
- `add_verification_method`
- `record_current_evidence`
- `investigate_failing_evidence`
- `refresh_stale_evidence`
- `review_waiver`
- `review_proposed_traces`
- `repair_stale_or_orphaned_traces`
- `do_not_treat_as_satisfied`
- `run_impact_analysis_when_available`

Each action has:

- `action`
- `priority`
- `reason`
- `command`
- `blocked_by`

Commands are suggestions for existing Charter CLI surfaces. If an action requires a future feature, the command is `null` and the reason names the missing feature.

## Sequencing

Implement dossiers first. Then add a read-only MCP wrapper that returns this exact contract. After the MCP read surface exists, sequence the remaining P1 work, especially durable gap policy and impact analysis. MCP mutation should wait until Charter has stronger review policy and gap lifecycle behavior.

## Review Checklist

- The implementation adds no storage or migration.
- The dossier does not call peer tools or external processes.
- Approved and draft requirement facts stay separate.
- Current and draft acceptance criteria stay separate.
- Trace state, authority, freshness, confidence, and snapshot are preserved.
- Verification status wraps existing evidence and reason codes.
- Gaps are computed and ephemeral.
- Next actions are deterministic, machine-readable, and conservative.
