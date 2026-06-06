# Charter Contract Fixture Plan

## Purpose

This plan defines the contract fixtures required before and during the v0.1
implementation. Fixtures are shape references, not byte-for-byte output
promises. Tests should validate key sets, value types, enum closure, schema
versions, status/envelope pairing, and semantic invariants.

## Fixture Layout

```text
tests/fixtures/contracts/
  envelopes/
    success.json
    error-validation.json
    error-conflict.json
    list.json
    batch.json
  requirements/
    requirement-draft.json
    requirement-version-approved.json
    requirement-version-superseded.json
  traces/
    trace-link-proposed.json
    trace-link-accepted.json
    trace-link-stale.json
    trace-link-orphaned.json
  mcp/
    side-effect-metadata.json
  cli/
    req-add-json.json
    req-show-json.json
    req-approve-json.json
    criterion-add-json.json
    trace-propose-json.json
    trace-accept-json.json
    trace-reject-json.json
    trace-list-json.json
    error-validation-json.json
    error-conflict-json.json
```

Federation fixtures are defined now but implemented in later slices:

```text
tests/fixtures/contracts/federation/
  clarion-sei-link.json
  filigree-gap-to-work.json
  wardline-finding-link.json
  legis-preflight-facts.json
```

## Fixture Contracts

### Success Envelope

Required keys:

```json
{
  "schema": "weft.charter.<object>.v1",
  "ok": true,
  "data": {},
  "warnings": [],
  "meta": {
    "producer": {"tool": "charter", "version": "0.1.0"},
    "generated_at": "2026-06-04T10:00:00+10:00",
    "project": "AUTH"
  }
}
```

Semantic invariants:

- `ok` is `true`.
- `schema` starts with `weft.charter.` and ends with `.v1`.
- `warnings` is always present and is always a list.
- `meta.producer.tool` is `charter`.

### Error Envelope

Required keys:

```json
{
  "schema": "weft.charter.error.v1",
  "ok": false,
  "error": {
    "code": "VALIDATION",
    "message": "requirement_id is required",
    "recoverable": true,
    "hint": "Pass a requirement id such as REQ-AUTH-017.",
    "details": {}
  },
  "warnings": [],
  "meta": {
    "producer": {"tool": "charter", "version": "0.1.0"},
    "generated_at": "2026-06-04T10:00:00+10:00",
    "project": "AUTH"
  }
}
```

Enum closure:

- `VALIDATION`
- `NOT_FOUND`
- `CONFLICT`
- `POLICY_REQUIRED`
- `PEER_ABSENT`
- `PEER_STALE`
- `PEER_CONTRACT`
- `LOCKED`
- `UNSUPPORTED`
- `INTERNAL`

### Requirement Version

Required keys:

```json
{
  "schema": "weft.charter.requirement_version.v1",
  "id": "REQ-AUTH-017",
  "stable_id": "charter:req:AUTH:017",
  "version": 1,
  "title": "Reject expired bearer tokens",
  "statement": "The API shall reject expired bearer tokens.",
  "statement_hash": "sha256:...",
  "status": "approved",
  "approved_by": "human:john",
  "approved_at": "2026-06-04T10:00:00+10:00"
}
```

Semantic invariants:

- Approved version content is immutable.
- `statement_hash` changes if `statement` changes.
- `version` increases monotonically per requirement.

### Trace Link

Required keys:

```json
{
  "schema": "weft.charter.trace_link.v1",
  "id": "LINK-0001",
  "state": "proposed",
  "from": {"kind": "test_selector", "id": "tests/test_auth.py::test_expired"},
  "relation": "provides_evidence_for",
  "to": {"kind": "verification_method", "id": "VERM-0001"},
  "authority": "agent_proposed",
  "freshness": "current",
  "confidence": 0.82,
  "created_by": "agent:codex",
  "accepted_by": null,
  "target_snapshot": {}
}
```

Enum closure:

- `state`: `proposed`, `accepted`, `rejected`, `stale`, `orphaned`
- `authority`: `accepted`, `agent_proposed`, `human_proposed`, `inferred`, `imported`, `test_derived`, `peer_reported`
- `freshness`: `current`, `stale`, `unknown`, `orphaned`, `not_applicable`

### MCP Side-Effect Metadata

Required keys per tool:

```json
{
  "name": "trace_link_propose",
  "mutates": true,
  "idempotent": true,
  "requires_actor": true,
  "requires_human_acceptance": "later",
  "supports_dry_run": true,
  "peer_side_effects": [],
  "retry_contract": "same idempotency_key returns original result"
}
```

Semantic invariants:

- Every mutating tool sets `requires_actor: true`.
- Every peer-mutating tool lists `peer_side_effects`.
- `supports_dry_run` is true for local mutations and peer mutations.

### CLI JSON Output

Each CLI `--json` fixture wraps the command-specific object in the standard
success/error envelope. Human output is covered by smoke tests only.

Required v0.1 command fixture coverage:

- `charter req add --json`
- `charter req show --json`
- `charter req approve --json`
- `charter criterion add --json`
- `charter trace propose --json`
- `charter trace accept --json`
- `charter trace reject --json`
- `charter trace list --json`
- representative `VALIDATION` error
- representative `CONFLICT` error

## Contract Test Rules

- Contract tests validate parsed JSON, not raw bytes.
- Field ordering is not significant.
- Extra fields are forbidden in v0.1 fixtures unless explicitly allowed by the fixture's `shape_decl`.
- Missing required fields fail the test.
- Unknown enum values fail the test.
- Human-readable output is not a machine contract.
