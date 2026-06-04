# Charter Verification And Status Design

## Purpose

This spec defines the next P0 Charter slice after baseline core: local
verification methods, evidence records, and computed requirement satisfaction
status. The slice makes Charter answer how an approved requirement is known to
be satisfied without implementing dossiers, MCP tools, impact analysis, gaps,
or federation integrations.

## Scope

Implement local, SQLite-backed verification state for approved requirement
versions:

- verification methods that declare how a requirement version can be checked;
- evidence records tied to a method and the requirement version current when
  the evidence was recorded;
- status computation for the current requirement version;
- JSON CLI contracts for method creation, evidence recording, and status
  listing;
- roadmap and Filigree updates after review and gates pass.

## Out Of Scope

This slice does not implement requirement dossiers, MCP read tools, gap
records, impact analysis, peer-tool calls, UI/TUI, import/export, or automatic
test execution. Evidence references are local strings such as test selectors,
artifact paths, URLs, or manual attestation identifiers; Charter stores them
as facts but does not dereference them.

## Storage

Add two tables:

```text
verification_methods(
  method_id primary key,
  requirement_id references requirements(requirement_id),
  requirement_version,
  method_type,
  target,
  status,
  created_by,
  created_at
)

verification_evidence(
  evidence_id primary key,
  method_id references verification_methods(method_id),
  requirement_id references requirements(requirement_id),
  requirement_version,
  status,
  evidence_ref,
  authority,
  freshness,
  recorded_by,
  recorded_at,
  payload_json
)
```

Methods are created only for requirements with an approved or deprecated
current version. Evidence records are append-only. Superseding a requirement
does not rewrite previous evidence; status computation marks old-version
evidence as stale.

## Authority Rules

Supported method types are `test`, `analysis`, `inspection`, and `manual`.
Supported evidence statuses are `passing`, `failing`, `inconclusive`, and
`waived`.

Evidence authority is derived from method type and actor:

- `test_derived` for `test` methods;
- `human_attested` for human-recorded `analysis`, `inspection`, or `manual`
  evidence;
- `agent_reported` for agent-recorded `analysis` or `inspection` evidence;
- `waiver` for human-recorded waived evidence.

Agents may record test-derived evidence. Agents may not record `manual`
evidence or waived evidence, because those would create accepted manual
attestations without human authority.

## Status Semantics

`verify status REQ_ID` and `status requirement REQ_ID` return a
`requirement_verification_status.v1` object with:

- requirement identity and current version;
- computed status;
- machine-readable reason objects;
- current evidence references;
- stale evidence references.

Status values:

- `unverified`: approved/deprecated requirement has no verification method or
  no current evidence;
- `satisfied`: at least one current evidence record is `passing` and no current
  evidence record is `failing`;
- `unsatisfied`: at least one current evidence record is `failing`;
- `stale`: methods or evidence exist, but all evidence is for an older
  requirement version;
- `unknown`: latest current evidence is inconclusive or the requirement is not
  approved/deprecated;
- `waived`: current human waiver evidence exists and no current failing
  evidence exists.

Reason codes are stable strings such as `no_verification_method`,
`no_current_evidence`, `passing_evidence`, `failing_evidence`,
`stale_evidence`, `inconclusive_evidence`, `human_waiver`, and
`requirement_not_approved`.

## CLI

Add:

```text
charter verify method add REQ_ID --method test --target TARGET --actor ACTOR --json
charter verify evidence record METHOD_ID --status passing --evidence-ref REF --actor ACTOR --json
charter verify status REQ_ID --json
charter status requirement REQ_ID --json
charter status unverified --json
charter status stale --json
```

The `verify status` and `status requirement` commands return the same schema.
List commands use existing list envelopes.

## Contracts And Tests

Add fixture contracts:

- `tests/fixtures/contracts/verification/verification-method.json`
- `tests/fixtures/contracts/verification/verification-evidence.json`
- `tests/fixtures/contracts/verification/requirement-verification-status.json`
- CLI fixtures for method add, evidence record, verify status, status
  requirement, status unverified, and status stale.

Tests cover:

- migrations create tables and run twice;
- method creation rejects draft/rejected requirements;
- approved requirements can be unverified;
- passing evidence satisfies the current version;
- failing evidence makes the requirement unsatisfied;
- superseding a requirement makes prior evidence stale;
- human waiver behavior is distinct from passing evidence;
- agents cannot record manual or waiver attestations;
- CLI JSON output matches fixtures by shape.

## Review Gates

Before completion, review for:

- evidence records are append-only;
- evidence stays tied to immutable requirement versions;
- supersede does not mutate old evidence;
- manual/waiver authority is not available to agents;
- status is computed from accepted requirement state plus evidence, not issue
  closure or prose;
- schemas are stable and agent-safe.
