# MCP Read Surface First-Principles Review

## Scope

Review the implemented P0 Package C MCP read surface against:

- `docs/superpowers/specs/2026-06-05-charter-agentic-mcp-interface-design.md`;
- `docs/agentic-doors-replacement-roadmap.md`;
- the user requirement to implement the plan and understand what is delivered.

This review evaluates current code and tests, not implementation intent.

## Delivered

### Agent Task Surface

Delivered.

Evidence:

- `src/charter/mcp_surface.py` defines the required ten P0 read tools:
  `charter_project_context_get`, `charter_requirement_search`,
  `charter_requirement_get`, `charter_requirement_dossier_get`,
  `charter_trace_link_list`, `charter_baseline_list`, `charter_baseline_get`,
  `charter_baseline_diff`, `charter_verification_status_get`, and
  `charter_verification_status_list`.
- `src/charter/mcp_server.py` registers those tools with FastMCP.
- `tests/test_mcp_read_surface.py` verifies the tool inventory.
- `tests/test_mcp_server.py` verifies FastMCP catalog registration.

### MCP Resources

Delivered.

Evidence:

- `src/charter/mcp_surface.py` defines `MCP_RESOURCE_URIS` for project context
  and the P0 contract resources.
- `src/charter/mcp_server.py` registers those URIs as FastMCP resources.
- `tests/test_mcp_read_surface.py` verifies internal resource reads.
- `tests/test_mcp_server.py` verifies server resource registration.

### Existing Charter Envelope Discipline

Delivered.

Evidence:

- `src/charter/mcp_surface.py` uses `success_envelope` and `error_envelope`
  from `src/charter/envelopes.py`.
- Tool methods return existing schema names such as
  `weft.charter.requirement_dossier.v1`,
  `weft.charter.baseline.v1`,
  `weft.charter.baseline_diff.v1`, and
  `weft.charter.requirement_verification_status.v1`.
- `tests/test_mcp_read_surface.py` asserts schema, `ok`, warnings, producer,
  and project metadata on successful envelopes.
- Error tests assert `weft.charter.error.v1`, closed error code, recoverability,
  and recovery hint.

### Read-Only And Local-Only Behavior

Delivered.

Evidence:

- Every entry in `MCP_TOOL_METADATA` declares `mutates: false`,
  `local_only: true`, and `peer_side_effects: []`.
- `tests/test_mcp_read_surface.py` snapshots all SQLite tables before and after
  representative MCP reads and asserts state equality.
- Scope audit found no calls from `src/charter/mcp_surface.py` or
  `src/charter/mcp_server.py` to Charter mutation service methods such as
  requirement create/edit/approve, trace mutation, baseline creation, or
  evidence recording.
- Scope audit found no live Clarion, Filigree, Wardline, or Legis calls in the
  MCP implementation.

### Agent-Safe Discovery And Pagination

Delivered.

Evidence:

- `charter_project_context_get` returns initialized state, schema/database
  context, capability metadata, and authority boundary summary.
- `charter_requirement_search`, `charter_trace_link_list`,
  `charter_baseline_list`, and `charter_verification_status_list` return
  `items`, `has_more`, and `next_offset`.
- `tests/test_mcp_read_surface.py` verifies pagination and filter behavior.
- Invalid enum-like filters return validation error envelopes instead of silent
  empty results.

### Dossier And Verification Authority Boundaries

Delivered.

Evidence:

- `charter_requirement_dossier_get` returns the installed local dossier contract
  and keeps `peer_facts.live_peer_calls` false.
- Dossier output continues to preserve approved/current sections, active drafts,
  trace states, verification status, stale evidence, baseline exposure, computed
  gaps, and next actions.
- `charter_verification_status_get` and `charter_verification_status_list` expose
  reason-coded status rather than prose verdicts.

### Runnable MCP Server

Delivered.

Evidence:

- `pyproject.toml` adds the `charter-mcp` script.
- `pyproject.toml` and `uv.lock` add the official Python MCP SDK dependency.
- `.mcp.json` registers a local `charter` stdio server using `uv run
  charter-mcp`.
- A direct FastMCP catalog check verifies registered tools/resources.

### Roadmap And Package C Status

Delivered.

Evidence:

- `docs/agentic-doors-replacement-roadmap.md` marks the MCP read/query surface
  installed on `main`.
- Package C status now says installed on `main`.
- Remaining work begins at P1 operational depth: impact analysis, durable gaps,
  MCP mutation, review queues, and import/export.
- Filigree issue `charter-ca64aed01f` is closed as `delivered` with final gate
  evidence.

## Not Delivered

These exclusions match the P0 design:

- MCP mutation tools.
- Live Clarion, Filigree, Wardline, or Legis federation calls.
- Impact analysis.
- Durable gap lifecycle.
- Review queues and approval policy.
- Import/export.
- Release-readiness verdict tools.
- UI/TUI.
- ReqIF or ALM adapters.

## Residual Risks

- The MCP surface intentionally reuses CLI serializer helpers, including private
  helper functions. This keeps JSON shapes aligned, but the coupling should be
  revisited if CLI rendering and MCP serialization begin to diverge.
- The project context resources are compact contract summaries, not full JSON
  Schema documents. Current tests pin the shape and authority text, but a later
  schema-publication slice may need richer machine-readable schemas.
- P0 is local-process scoped. It does not add authentication, multi-user
  isolation, signing, or cross-project authorization.

## Verification Evidence

Commands run:

- `uv run pytest tests/test_mcp_read_surface.py tests/test_mcp_server.py -q`
- `uv run pytest tests/test_mcp_read_surface.py tests/test_mcp_server.py tests/contracts/test_contract_fixtures.py -q`
- `make lint`
- `make typecheck`
- `make test`
- `uv run pytest tests/contracts -q`
- `uv run pytest tests/state -q`
- `make ci`
- scope audit over `src/charter/mcp_surface.py` and `src/charter/mcp_server.py`
  for subprocess, mutation-service calls, peer tool names, impact/gap/release
  verdict leakage, and live peer behavior.

Result:

- `make test`: 139 passed.
- `tests/contracts`: 36 passed.
- `tests/state`: 58 passed.
- `make ci`: 139 passed with 92.73% total coverage.

## Review Verdict

The implementation satisfies the P0 Package C read-only MCP requirements. It
delivers a first-class local agent read surface over Charter's installed
requirements, dossier, trace, baseline, and verification facts while preserving
authority boundaries and leaving P1/P2 work explicitly deferred.
