# Charter Agentic DOORS Replacement Roadmap

## Purpose

This document captures what is still missing for Charter to become a
first-class agentic replacement for DOORS-style requirements management.

Current state: Charter local core is installed on `main`. It can store
repo-local requirements, drafts, immutable approved versions, acceptance
criteria, local trace links, append-only events, named locked baselines,
verification methods, evidence records, computed verification status, and JSON
CLI envelopes. That is enough to start storing requirements and verification
state. It is not yet enough to replace a mature requirements-management system.

The replacement bar is not "copy DOORS." The bar is:

- requirements and versions are authoritative and auditable;
- agents can safely read, draft, propose, and report without fabricating
  accepted truth;
- baselines, verification status, and impact are first-class;
- integrations compose with Loom peers without taking over their authority;
- humans can review, approve, export, and audit the resulting state.

## Installed On Main

Installed capabilities are available in the integrated `main` branch:

- **v0.1 local core**: `charter init`, `charter doctor`, local
  `.charter/charter.db`, requirement drafts, immutable approved versions,
  acceptance criteria, proposed/accepted/rejected/stale/orphaned trace links,
  append-only events, JSON envelopes, CLI contract fixtures, and state tests.
- **Baseline core**: locked named baselines of current approved/deprecated
  requirement versions, baseline member listing, baseline list/show/diff CLI
  commands, immutable baseline storage, and baseline contract fixtures.
- **Verification and status core**: verification methods, append-only evidence
  records, method/evidence authority rules, status categories `satisfied`,
  `unsatisfied`, `unverified`, `stale`, `unknown`, and `waived`, machine-readable
  reason codes, `verify` CLI commands, `status` CLI commands, and verification
  contract fixtures.

Installed command groups:

```text
charter init
charter doctor
charter req add|edit|show|search|approve|supersede|deprecate|reject
charter criterion add|list
charter trace propose|accept|reject|list
charter baseline create|show|list|diff
charter verify method add
charter verify evidence record
charter verify status
charter status requirement|unverified|stale
```

## Remaining Work

Highest-priority remaining work:

- **P0 Requirement dossiers**: one dense agent-safe object per requirement,
  combining requirement version, criteria, traces, verification, gaps, peer
  facts, and next actions without calling live peers.
- **P0 MCP read/query surface**: read-only MCP tools for requirement search/show,
  dossiers, baselines, verification status, and traces, using the same stable
  JSON contracts as the CLI.

P1 operational work still deferred:

- impact analysis;
- durable gap tracking;
- MCP mutation surface;
- review queues and approval policy;
- import/export and migration.

P2/P3 adoption work still deferred:

- Clarion, Filigree, Wardline, and Legis federation integrations;
- human review UI/TUI;
- collaboration and governance hardening;
- scale/performance validation;
- ReqIF and enterprise ALM adapters.

## Product Gaps

| Gap | Why it matters | Current state | Priority |
|---|---|---|---|
| Baselines and release snapshots | Auditors and release decisions need a frozen set of approved requirement versions. | Installed on `main`. | P0 |
| Verification methods and evidence records | A requirement store is not enough; Charter must answer how satisfaction is known. | Installed on `main`. | P0 |
| Requirement satisfaction and freshness | Agents need current, stale, missing, and unknown status without scraping prose. | Installed on `main`. | P0 |
| Requirement dossiers | Agents need one dense object per requirement: text, criteria, traces, evidence, gaps, and next actions. | Deferred. | P0 |
| MCP read/query surface | Agentic use should not require shelling out to CLI for every read. | Deferred except inert contract fixture. | P0 |
| Impact analysis | The main product value is "what obligations does this change touch?" | Deferred. | P1 |
| Gap tracking | Missing or stale evidence must become durable work candidates. | Deferred. | P1 |
| MCP mutation surface | Agents should propose requirements, links, evidence, and gaps with actor attribution and idempotency. | Deferred. | P1 |
| Human review queues and approval policy | Proposed facts must not silently become accepted truth. | Minimal local approval only. | P1 |
| Import/export and migration | A replacement must ingest and emit requirements data in usable formats. | Deferred. | P1 |
| Federation integrations | Clarion, Filigree, Wardline, and Legis make Charter agentically useful across code, work, trust, and governance. | Deferred except local opaque trace kinds. | P2 |
| Reporting and UI/TUI | Humans need browse, diff, review, and audit views beyond raw JSON. | Deferred. | P2 |
| Collaboration and governance hardening | Multi-user workflows need stronger roles, signatures, conflict handling, and audit controls. | Local filesystem boundary only. | P2 |
| Scale and performance validation | Large projects need confidence with thousands of requirements and links. | Deferred. | P3 |
| ReqIF and enterprise ALM adapters | Enterprise replacement/migration often requires ReqIF and adapter behavior. | Deferred. | P3 |

## Prioritized Roadmap

### P0: Make Charter Trustworthy For Agentic Requirements Use

P0 work turns Charter from a local requirement store into a requirements
authority that agents can query safely.

#### 1. Baseline Core

Deliver:

- named baselines of approved requirement versions;
- immutable locked baselines;
- baseline member listing;
- baseline diff against current approved versions;
- JSON CLI fixtures and state tests.

Minimum commands:

```text
charter baseline create --name NAME --actor ACTOR --json
charter baseline show BASELINE_ID --json
charter baseline diff BASELINE_ID --json
charter baseline list --json
```

Definition of done:

- locked baselines cannot mutate;
- baselines store requirement version identity, not mutable requirement rows;
- superseded requirements appear in baseline diff;
- missing current verification can be reported against a baseline once
  verification lands.

#### 2. Verification Core

Deliver:

- verification methods;
- verification evidence records;
- evidence status and freshness;
- method/evidence lifecycle tests;
- JSON CLI fixtures.

Minimum commands:

```text
charter verify method add REQ_ID --method test --target TARGET --actor ACTOR --json
charter verify evidence record METHOD_ID --status passing --evidence-ref REF --actor ACTOR --json
charter verify status REQ_ID --json
```

Definition of done:

- requirements can be approved but unverified;
- evidence is tied to a requirement version;
- superseding a requirement makes prior evidence stale unless explicitly
  carried forward;
- manual attestations are distinguishable from test-derived evidence;
- agents cannot fabricate external/manual attestation authority.

#### 3. Satisfaction Status And Freshness

Deliver:

- computed status for each requirement version;
- status categories: `satisfied`, `unsatisfied`, `unverified`, `stale`,
  `unknown`, `waived`;
- clear reason objects explaining each status;
- list/report commands for missing and stale verification.

Minimum commands:

```text
charter status requirement REQ_ID --json
charter status unverified --json
charter status stale --json
```

Definition of done:

- status is derived from accepted requirements, criteria, traces, and evidence;
- issue closure is not treated as satisfaction;
- stale evidence remains visible and useful;
- JSON output includes machine-readable reason codes.

#### 4. Requirement Dossiers

Deliver:

- one-call requirement dossier JSON;
- compact human dossier output;
- included sections for requirement version, criteria, traces, verification,
  gaps, peer facts, and next actions;
- contract fixture for `requirement_dossier.v1`.

Minimum commands:

```text
charter dossier REQ_ID --json
charter dossier REQ_ID
```

Definition of done:

- an agent can answer "what do I need to know before editing this area?" from
  one dossier call;
- proposed, accepted, stale, imported, and inferred facts remain separate;
- dossier output does not call live peers until federation capability is
  explicitly implemented.

#### 5. MCP Read Surface

Deliver:

- MCP server exposing read-only local Charter facts;
- tools for requirement search, show, dossier, baseline show/diff, verification
  status, and trace listing;
- stable JSON schemas shared with CLI envelopes;
- no mutation tools in the first MCP slice.

Definition of done:

- agents can use Charter without shelling out to CLI for read workflows;
- read tools never mutate state;
- tool descriptions state authority boundaries and freshness semantics;
- MCP tests validate schemas and error envelopes.

### P1: Make Charter Operationally Useful During Development

P1 work makes Charter useful while code changes are being planned and executed.

#### 6. Impact Analysis

Deliver:

- impact reports for requirement ID, file path, diff/range, and trace target;
- upstream/downstream trace traversal;
- stale evidence and affected baseline reporting;
- `impact_report.v1` fixture.

Minimum commands:

```text
charter impact requirement REQ_ID --json
charter impact path PATH --json
charter impact diff BASE..HEAD --json
```

Definition of done:

- report separates direct, transitive, and inferred impacts;
- report identifies evidence that will become stale;
- report can run with no peers using local trace links;
- report can later enrich from Clarion without changing the base schema.

#### 7. Gap Tracking

Deliver:

- durable gap records for missing evidence, stale links, unaccepted proposals,
  and unsatisfied criteria;
- gap lifecycle: `open -> linked_to_work -> resolved/waived`;
- JSON CLI fixtures and state tests.

Minimum commands:

```text
charter gap list --json
charter gap create --requirement REQ_ID --kind missing_verification --actor ACTOR --json
charter gap resolve GAP_ID --actor ACTOR --evidence-ref REF --json
```

Definition of done:

- gaps are distinct from Filigree issues;
- resolving a gap requires evidence, waiver, or explicit accepted rationale;
- waived gaps remain visible in status and dossiers.

#### 8. MCP Mutation Surface

Deliver:

- mutation tools for creating draft requirements, editing drafts, proposing
  trace links, recording evidence, and creating gaps;
- dry-run support;
- idempotency keys and actor attribution;
- policy metadata declaring which tools can create accepted facts.

Definition of done:

- agent-created facts are proposed or draft by default;
- all mutations write append-only events;
- same idempotency key with different payload fails closed;
- high-risk acceptance requires explicit policy or human action.

#### 9. Review Queues And Approval Policy

Deliver:

- listable review queues for draft requirements, proposed links, proposed
  methods, evidence needing acceptance, and waivers;
- policy configuration for low-risk auto-acceptance versus human acceptance;
- audit trail for approvals and rejections.

Definition of done:

- proposals have clear owner, reason, confidence, and evidence;
- accepting a proposal changes authority state without losing provenance;
- policy defaults are conservative.

#### 10. Import And Export

Deliver:

- Markdown, JSON, YAML, and CSV import/export;
- static report export for baselines, dossiers, and verification status;
- validation mode before import;
- stable ID mapping report.

Definition of done:

- import never overwrites approved versions in place;
- import produces explicit draft/proposed facts unless trusted mode is selected;
- export is deterministic enough for review diffs.

### P2: Make Charter Federated And Human-Comfortable

P2 work turns Charter into a strong member of the Loom federation and improves
human review ergonomics.

#### 11. Clarion Integration

Deliver:

- SEI-backed trace targets;
- code entity freshness checks;
- rename/move resilient impact enrichment;
- degraded behavior when Clarion is absent or stale.

Definition of done:

- Charter consumes Clarion identity; it does not derive code identity;
- stale or missing Clarion facts are explicit;
- local manual links still work without Clarion.

#### 12. Filigree Integration

Deliver:

- create work from Charter gaps;
- link gaps and requirements to Filigree issues;
- show issue status in dossiers without owning issue lifecycle.

Definition of done:

- Charter can create candidate work but does not claim, transition, or close
  Filigree issues except through explicit user/tool action;
- issue closure is never treated as requirement satisfaction by itself.

#### 13. Wardline Integration

Deliver:

- link findings to security/safety requirements and acceptance criteria;
- show active, waived, suppressed, and resolved findings distinctly;
- incorporate finding state into satisfaction and risk posture.

Definition of done:

- Charter does not own trust-boundary analysis;
- waived findings remain visible;
- dossiers explain how findings affect satisfaction.

#### 14. Legis Integration

Deliver:

- preflight fact envelope for requirement, verification, gap, and impact state;
- no direct commit blocking inside Charter;
- support for Chill-mode advisory reports and stricter policy modes in Legis.

Definition of done:

- Charter provides facts, not governance decisions;
- Legis can consume one structured envelope for commit/release checks;
- absence/staleness of Charter data is explicit.

#### 15. Human Review UI/TUI

Deliver:

- dense browse/search for requirements;
- baseline diff view;
- dossier view;
- proposal review queue;
- trace graph or tree view.

Definition of done:

- common review workflows do not require reading raw JSON;
- output remains compact and engineering-focused;
- UI never hides authority/freshness state.

### P3: Make Charter Enterprise-Migration Ready

P3 work is important for larger adoption but should not block the first
agentic product loop.

#### 16. Collaboration And Governance Hardening

Deliver:

- role and permission model;
- stronger approval provenance;
- optional signing/attestation support;
- conflict handling for concurrent actors;
- audit export.

Definition of done:

- every accepted fact has attributable authority;
- conflicting edits are explicit and recoverable;
- audit artifacts can be reviewed outside Charter.

#### 17. Scale And Performance Validation

Deliver:

- synthetic project generator;
- performance tests for thousands of requirements and links;
- indexed query review;
- large baseline and impact benchmarks.

Definition of done:

- common queries have documented performance envelopes;
- migrations remain practical on large local databases;
- regressions are caught in CI or a dedicated perf gate.

#### 18. ReqIF And ALM Adapters

Deliver:

- ReqIF import/export investigation and prototype;
- adapter-mode authority policy;
- external ID mapping and round-trip diagnostics;
- migration validation report.

Definition of done:

- external ALM truth is not silently overwritten;
- imported requirements preserve provenance;
- round-trip gaps are reported before migration acceptance.

## Recommended Sequencing

The highest-leverage order is:

1. Baseline core.
2. Verification core.
3. Satisfaction status and freshness.
4. Requirement dossiers.
5. MCP read surface.
6. Impact analysis.
7. Gap tracking.
8. MCP mutation surface.
9. Review queues and approval policy.
10. Import/export.
11. Clarion, Filigree, Wardline, and Legis federation in that order.
12. Human review UI/TUI.
13. Collaboration hardening.
14. Scale validation.
15. ReqIF and enterprise ALM adapters.

This order keeps Charter useful at every step. It avoids building federation
or UI features before Charter can answer the core questions:

- What requirements are approved?
- Which baseline do they belong to?
- How do we know they are satisfied?
- What changed or went stale?
- What should an agent do next?

## First Three Implementation Packages

### Package A: Baselines

Goal: make approved requirement sets auditable.

Status: installed on `main`. Evidence includes immutable baseline storage,
`charter baseline create/show/list/diff`, baseline JSON fixtures, state tests,
CLI tests, and final local gates.

Suggested Filigree breakdown:

- design baseline schema and contract fixture;
- implement baseline store/service;
- implement baseline CLI JSON commands;
- implement baseline diff;
- add contract and state-machine tests;
- run scope review for immutable baseline semantics.

Exit criteria:

- Complete: a release can name and inspect a frozen requirement-version set.
- Complete: baseline diff is machine-readable.
- Complete: existing v0.1 tests still pass with the baseline suite included.

### Package B: Verification And Satisfaction

Goal: make Charter answer whether requirements are satisfied.

Status: installed on `main`. Evidence includes verification method/evidence
storage, append-only evidence records, `charter verify method add`,
`charter verify evidence record`, `charter verify status`,
`charter status requirement`, `charter status unverified`,
`charter status stale`, verification JSON fixtures, state tests, CLI tests, and
local gates.

Delivered Filigree breakdown:

- Complete: design verification method and evidence contracts;
- Complete: implement method/evidence store/service;
- Complete: implement evidence freshness when requirement versions change;
- Complete: implement `status requirement`, `status unverified`, and
  `status stale`;
- Complete: add contract, state-machine, and CLI tests;
- Complete: review authority rules for manual/external attestations.

Exit criteria:

- Complete: requirements can be approved, unverified, satisfied, stale, or
  unsatisfied.
- Complete: status output includes reason codes and evidence references.
- Complete: agents cannot create accepted manual attestations by default.

### Package C: Dossiers And MCP Read Tools

Goal: make Charter useful as an agent-facing requirements authority.

Suggested Filigree breakdown:

- design `requirement_dossier.v1`;
- implement local dossier computation;
- add CLI dossier command;
- add read-only MCP server skeleton;
- expose read tools for requirements, traces, status, baselines, and dossiers;
- add MCP contract tests and no-mutation safety tests.

Exit criteria:

- an agent can fetch a full requirement context in one tool call;
- MCP tools are read-only and schema-stable;
- dossier output preserves authority and freshness distinctions.

## Non-Negotiable Product Rules

- Never collapse proposed, inferred, imported, stale, and accepted facts.
- Never treat issue closure as requirement satisfaction.
- Never mutate approved requirement text or locked baselines.
- Never let an agent mark its own guess as accepted truth without policy.
- Never make Charter depend on peer tools for local requirements use.
- Never hide stale, waived, or orphaned facts; label them and explain the
  consequence.
