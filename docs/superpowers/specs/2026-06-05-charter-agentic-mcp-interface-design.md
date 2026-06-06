# Charter Agentic MCP Interface Design

## Purpose

Design the P0 read-only MCP surface for Charter as an agent-first interface over
installed local requirements facts. The goal is not to mirror the CLI one command
at a time. The goal is to give agents the facts they need before editing,
reviewing, or preparing release evidence, while preserving Charter's authority
boundaries.

This design closes the brainstorming phase for the remaining Package C work. It
does not close Package C by itself. Package C closes after the read-only MCP
surface is implemented, tested, reviewed, and the roadmap marks MCP read tools as
installed on `main`.

## Current Context

Installed on `main`:

- v0.1 local core for requirements, drafts, approved versions, criteria, trace
  links, append-only events, JSON envelopes, and contract fixtures.
- Baseline core for locked named baselines, baseline members, baseline
  list/show/diff, and baseline fixtures.
- Verification and status core for methods, evidence, derived status,
  unverified/stale reporting, and verification fixtures.
- Local requirement dossiers with `charter dossier REQ_ID --json`,
  `weft.charter.requirement_dossier.v1`, compact human output, and CLI contract
  parity.

Remaining P0 work:

- Read-only MCP tools and resources over the installed local contracts.

## Agent Persona Findings

Three agent-user personas were interrogated:

- implementation coding agent;
- reviewer/auditor agent;
- requirements/release curator agent.

They converged on the same needs:

- start with project context before trusting any result;
- search requirements without scraping text;
- fetch one dense requirement dossier before acting;
- inspect traces with explicit authority and freshness;
- inspect verification status and broad stale/unverified lists;
- inspect baselines and baseline diffs for release risk;
- keep all outputs schema-versioned, timestamped, and project-scoped;
- exclude mutation, live peer calls, release verdicts, and policy decisions from
  the first MCP slice.

## Design Principle

Use whatever MCP primitives agents require.

For P0 this means:

- tools answer live local questions;
- resources explain stable contracts and authority rules;
- no live peer enrichment;
- no state mutation;
- no governance verdicts.

This is an agent task surface, not a CRUD mirror.

## P0 Tool Inventory

### `charter_project_context_get`

Parameters:

```json
{
  "include_contracts": false
}
```

Returns local project and capability context. It maps to the useful parts of
`charter doctor --json` plus MCP capability metadata.

Required facts:

- project key;
- initialized state;
- producer tool/version;
- schema/database health;
- read-only capability list;
- authority boundary summary;
- optional contract/resource references when `include_contracts` is true.

Every P0 capability entry must declare:

- `mutates: false`;
- `local_only: true`;
- `peer_side_effects: []`;
- `authority_boundary`.

### `charter_requirement_search`

Parameters:

```json
{
  "query": null,
  "status_filter": null,
  "limit": 25,
  "offset": 0
}
```

Returns a paginated requirement list using the same shape as the CLI requirement
search contract. Agents use this for discovery, not for complete authority over a
single requirement.

Required behavior:

- include `items`, `has_more`, and `next_offset`;
- never imply an unpaginated result is exhaustive when more rows exist;
- keep approved/draft/rejected/deprecated status visible.

### `charter_requirement_get`

Parameters:

```json
{
  "requirement_id": "REQ-AUTH-0001"
}
```

Returns the local requirement record using the existing requirement show
contract. Agents use this when they need the requirement row without the full
dossier.

Required facts:

- display ID and internal `requirement_id`;
- `stable_id`;
- current approved version;
- active draft identity when present;
- statement hash;
- approval metadata when present.

### `charter_requirement_dossier_get`

Parameters:

```json
{
  "requirement_id": "REQ-AUTH-0001"
}
```

Returns `weft.charter.requirement_dossier.v1`. This is the preferred one-call
context object before an agent edits, reviews, or plans around a requirement.

Required sections:

- identity;
- authority summary;
- requirement record, current version, and active draft;
- acceptance criteria split into current version and active draft;
- trace summaries and items;
- verification status, current evidence, and stale evidence;
- baseline exposure;
- computed local gaps;
- peer facts;
- next actions.

Authority requirements:

- active drafts are never current approved truth;
- proposed traces are never accepted traceability;
- stale verification remains visible but is not current satisfaction;
- `peer_facts.live_peer_calls` must be false in P0.

### `charter_trace_link_list`

Parameters:

```json
{
  "requirement_id": null,
  "state_filter": null,
  "relation_filter": null,
  "direction": "both",
  "limit": 50,
  "offset": 0
}
```

Returns local trace links with pagination and explicit state. Agents use this
when the dossier trace summary is not enough.

Required facts:

- `from`, `relation`, and `to`;
- trace `state`;
- authority and freshness when available;
- creator/acceptor metadata when available;
- target snapshot when available.

### `charter_baseline_list`

Parameters:

```json
{
  "limit": 25,
  "offset": 0
}
```

Returns paginated local baselines.

Required facts:

- baseline ID;
- name and description;
- locked state;
- creator and creation time.

### `charter_baseline_get`

Parameters:

```json
{
  "baseline_id": "BASELINE-0001"
}
```

Returns `weft.charter.baseline.v1`.

Required facts:

- baseline metadata;
- locked state;
- member requirement IDs;
- member versions;
- display IDs and stable IDs;
- statement hashes captured at baseline time;
- status at baseline.

### `charter_baseline_diff`

Parameters:

```json
{
  "baseline_id": "BASELINE-0001"
}
```

Returns `weft.charter.baseline_diff.v1`.

Required statuses:

- `unchanged`;
- `changed`;
- `missing_current`;
- `new_since_baseline`;
- `superseded_since_baseline`.

This is release-risk input, not a release decision.

### `charter_verification_status_get`

Parameters:

```json
{
  "requirement_id": "REQ-AUTH-0001"
}
```

Returns `weft.charter.requirement_verification_status.v1`.

Required facts:

- status category;
- reason codes;
- current evidence summaries;
- stale evidence summaries;
- requirement version;
- evidence references and authority/freshness where available.

### `charter_verification_status_list`

Parameters:

```json
{
  "status_filter": "unverified",
  "limit": 25,
  "offset": 0
}
```

Supported P0 `status_filter` values:

- `unverified`;
- `stale`.

This unified MCP tool wraps the installed `status unverified` and `status stale`
CLI behavior. It must preserve the list envelope shape.

## P0 Resource Inventory

### `charter://project/context`

Stable project context and authority summary. This may duplicate
`charter_project_context_get` for hosts that prefer attaching project context as
a resource.

### `charter://contracts/weft.charter.error.v1`

Error envelope contract and recovery expectations.

### `charter://contracts/weft.charter.requirement_dossier.v1`

Requirement dossier contract.

### `charter://contracts/weft.charter.baseline.v1`

Baseline contract.

### `charter://contracts/weft.charter.baseline_diff.v1`

Baseline diff contract.

### `charter://contracts/weft.charter.requirement_verification_status.v1`

Verification status contract.

Resources are for stable schema/context discovery. They must not smuggle live
facts that belong behind tools.

## Output Contract

Every successful tool returns the existing Charter envelope:

```json
{
  "schema": "weft.charter.<contract>.v1",
  "ok": true,
  "data": {},
  "warnings": [],
  "meta": {
    "producer": {
      "tool": "charter",
      "version": "..."
    },
    "generated_at": "...",
    "project": "..."
  }
}
```

Every list tool returns:

```json
{
  "items": [],
  "has_more": false,
  "next_offset": null
}
```

The MCP server must reuse existing serializers and envelope helpers rather than
creating a parallel MCP-only truth shape.

## Error Contract

Errors return `weft.charter.error.v1`:

```json
{
  "schema": "weft.charter.error.v1",
  "ok": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "...",
    "recoverable": true,
    "hint": "...",
    "details": {}
  },
  "warnings": [],
  "meta": {
    "producer": {
      "tool": "charter",
      "version": "..."
    },
    "generated_at": "...",
    "project": "..."
  }
}
```

Agents must be able to recover from errors by switching on `error.code`, not by
parsing message text.

## Agent Workflows

### Pre-Edit Workflow

1. `charter_project_context_get`
2. `charter_requirement_search`
3. `charter_requirement_dossier_get`
4. Optional `charter_trace_link_list`
5. Optional `charter_verification_status_get`

The agent gets accepted requirement text, active draft separation, acceptance
criteria, trace authority/freshness, verification status, stale evidence,
baseline exposure, computed local gaps, and next actions before editing code.

### Review Workflow

1. `charter_project_context_get`
2. `charter_requirement_search`
3. `charter_requirement_dossier_get`
4. `charter_verification_status_list`
5. Optional `charter_trace_link_list`

The reviewer checks blockers without treating proposed links, active drafts, or
stale evidence as accepted truth.

### Release/Baseline Workflow

1. `charter_project_context_get`
2. `charter_baseline_list`
3. `charter_baseline_diff`
4. `charter_verification_status_list` with `unverified`
5. `charter_verification_status_list` with `stale`

The agent reports facts, not verdicts. There is no P0 `release_ready` tool.

## Explicit Exclusions

P0 excludes:

- requirement add/edit/approve/supersede/deprecate/reject;
- criterion add;
- trace propose/accept/reject;
- baseline create;
- verification method add;
- evidence record;
- durable gap lifecycle;
- review queues and approval policy;
- impact analysis;
- import/export;
- live Clarion, Filigree, Wardline, or Legis calls;
- release-readiness verdicts;
- Git, CI, shell, or test execution;
- any tool that treats issue closure as requirement satisfaction;
- any tool that infers peer authority from local opaque IDs.

## Implementation Shape

Implementation should preserve the current architecture:

- add a small MCP module that calls `CharterService` directly;
- reuse existing CLI serializers and envelope helpers;
- keep tool handlers thin;
- validate parameters at the MCP boundary;
- add no migrations;
- add no new persistent state;
- add no peer integrations;
- add no mutation/idempotency-key behavior beyond read-only metadata.

The MCP dependency and transport choice are deferred to implementation planning.
The decision should prefer the smallest maintained Python MCP server dependency
that fits the Loom ecosystem.

## Test Strategy

Tests must prove agent safety, not only happy paths.

Required tests:

- MCP tool output contract fixtures aligned with CLI fixture shapes;
- tool inventory metadata test for `mutates: false`, `local_only: true`, and
  `peer_side_effects: []`;
- no-mutation test showing every P0 MCP tool leaves Charter state unchanged;
- validation and not-found error-envelope tests;
- pagination shape tests for every list/search tool;
- dossier parity test against the CLI dossier contract shape;
- scope audit proving no live peer calls, no subprocess shelling to `charter`,
  and no mutation handlers.

Final gates should include the existing project gates plus the new MCP contract
tests.

## Package C Closure Criteria

Package C closes when all of these are true on `main`:

- local requirement dossiers remain installed and tested;
- read-only MCP tools and resources from this design are implemented;
- MCP outputs preserve the installed Charter envelope and contract shapes;
- all P0 tools declare and satisfy read-only/local-only behavior;
- no live peer calls or mutations exist in the P0 MCP surface;
- MCP contract, error, pagination, no-mutation, and dossier parity tests pass;
- the replacement roadmap marks MCP read/query surface installed on `main`;
- Filigree Package C work is closed with verification evidence.
