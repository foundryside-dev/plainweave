# Charter: Local-first requirements and verification authority for Loom

## 1. Product intent

Charter is a local-first, agent-native requirements and verification authority for the Loom federation.

Charter answers:

> What must be true, how do we know it is true, what code or work claims to satisfy it, and what requirements are impacted by this change?

Charter is not an enterprise ALM clone. It is a lightweight, repo-local requirements system intended for developers and coding agents who need more structure than tasks and epics, but less ceremony than DOORS, Polarion, Jama, or Codebeamer.

Charter fits between product truth, code identity, work state, and governance:

```text
Charter owns obligations.
Clarion owns code identity and structure.
Filigree owns work state and issue lifecycle.
Wardline owns trust-boundary analysis.
Legis owns git/CI governance and attestations.
```

> The authoritative federation roster and per-member authority split are owned
> by the Loom hub at `~/loom/doctrine.md`. The split above mirrors it; if they
> ever disagree, the hub wins.

The primary design goal is to make requirements traceability cheap enough that agents can maintain it during ordinary development.

## 2. Authority boundary

### 2.1 Charter owns

Charter is authoritative for:

* requirements;
* requirement versions;
* requirement decomposition;
* acceptance criteria;
* verification methods;
* verification evidence records;
* requirement baselines;
* requirement-to-requirement links;
* requirement-to-test links;
* requirement-to-code-entity links;
* requirement-to-issue links;
* satisfaction status;
* requirement impact analysis;
* stale trace detection;
* local requirements dossiers exposed over MCP.

### 2.2 Charter does not own

Charter does not own:

* source-code identity, call graphs, or structural code relationships;
* task assignment, claims, issue state, or sprint planning;
* static security or trust-boundary analysis;
* commit refusal, CI policy enforcement, or human sign-off;
* external ALM authority when Charter is operating as an adapter.

Those remain owned by Clarion, Filigree, Wardline, Legis, or an external ALM system.

## 3. Operating model

Charter follows the Loom federation model (the federation axiom and composition
law are authoritative in `~/loom/doctrine.md`; what follows is Charter's
restatement of it):

```text
Each tool owns one kind of truth.
Each tool remains useful alone.
When peers are present, facts compose.
No tool silently assumes another tool's authority.
Missing peers degrade honestly.
```

Charter can be installed by itself, but its highest value appears when paired with Clarion and Legis.

### 3.1 Standalone mode

Charter can operate without other Loom tools.

In standalone mode it provides:

* requirements database;
* baselines;
* verification records;
* manual trace links;
* CLI and MCP access;
* markdown or JSON import/export;
* impact reports limited to changed files and manually declared links.

### 3.2 Federated mode

When peers are installed, Charter gains richer capabilities:

| Peer     | Combination capability                                                                                                                                                                        |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Clarion  | Requirement links can bind to Stable Entity Identity rather than fragile file paths. Impact analysis can include touched entities, callers, callees, subsystems, and rename-resilient traces. |
| Filigree | Requirements can be connected to work items, defects, implementation tasks, review tasks, and verification tasks.                                                                             |
| Wardline | Trust findings can be mapped to security or safety requirements. Requirement satisfaction can depend on absence, presence, or disposition of specific Wardline findings.                      |
| Legis    | Requirement and verification state can participate in commit preflight, policy decisions, override trails, sign-offs, and CI gates.                                                           |

## 4. Core concepts

### 4.1 Requirement

A requirement is a versioned statement of something that must be true.

Example:

```yaml
id: REQ-AUTH-017
title: Reject expired bearer tokens
type: security
criticality: high
status: approved
statement: >
  The API shall reject bearer tokens whose expiry time is earlier than the
  request evaluation time.
rationale: >
  Expired credentials must not grant access to protected resources.
```

A requirement may be high-level, decomposed, implementation-level, security-focused, safety-focused, interface-focused, operational, or non-functional.

### 4.2 Acceptance criterion

An acceptance criterion is a concrete condition that clarifies when a requirement is satisfied.

Example:

```yaml
id: AC-AUTH-017-1
requirement: REQ-AUTH-017
statement: >
  A request with an expired token receives HTTP 401 and does not call the
  protected handler.
```

Acceptance criteria are optional for small projects but recommended for approved requirements.

### 4.3 Verification

A verification record describes how satisfaction is shown.

Verification methods:

* test;
* analysis;
* inspection;
* demonstration;
* review;
* external evidence;
* manual attestation.

Example:

```yaml
id: VER-AUTH-017-1
requirement: REQ-AUTH-017
method: test
evidence_ref: tests/test_auth.py::test_expired_token_rejected
status: passing
freshness: current
last_verified_commit: abc123
```

### 4.4 Trace link

A trace link connects a requirement to another requirement, acceptance criterion, verification record, code entity, issue, evidence item, or external reference.

Trace relations include:

* decomposes;
* refines;
* constrains;
* satisfies;
* verifies;
* implements;
* tests;
* depends_on;
* supersedes;
* conflicts_with;
* mitigates;
* derived_from;
* documented_by.

Trace links carry authority metadata:

```yaml
authority: human_accepted | agent_proposed | imported | inferred | test_derived
confidence: 0.0-1.0
freshness: current | stale | unknown
```

Agent-proposed links must be distinguishable from accepted links.

### 4.5 Baseline

A baseline is a named snapshot of approved requirements and their versions.

Baselines answer:

* what requirements were in force at a point in time;
* which requirements changed since the baseline;
* which verification records are stale against the baseline;
* whether a release can claim conformance to a baseline.

Example:

```yaml
id: BASELINE-1.0
title: Release 1.0 approved requirements
created_at: 2026-06-04T10:00:00+10:00
includes:
  - REQ-AUTH-017@3
  - REQ-LOG-004@1
  - REQ-API-012@2
```

### 4.6 Dossier

A dossier is a single, agent-facing summary of what is known about a requirement.

A requirement dossier includes:

* current statement;
* status;
* version;
* parent and child requirements;
* acceptance criteria;
* verification methods and freshness;
* linked code entities;
* linked Filigree issues;
* linked Wardline findings;
* relevant Legis attestations;
* open gaps;
* suggested next actions.

## 5. Model architecture

### 5.1 System components

Charter consists of five main components:

```text
charter-cli
  Human and script interface.

charter-store
  Local SQLite storage, migrations, baseline snapshots, event log.

charter-core
  Requirement model, trace model, verification model, impact engine.

charter-mcp
  Agent-facing MCP server exposing structured tools.

charter-federation
  Optional adapters for Clarion, Filigree, Wardline, Legis, and external ALM.
```

### 5.2 Local storage

Each project gets a repo-local directory:

```text
.charter/
  charter.db
  charter.yaml
  baselines/
  exports/
  context.md
  events.jsonl
```

The default store is SQLite.

Storage requirements:

* no mandatory cloud service;
* no mandatory account;
* deterministic local operation;
* schema migrations;
* append-only event stream for audit and agent resumption;
* export to JSONL and Markdown;
* import from Markdown, CSV, JSON, and simple YAML;
* safe degraded operation when peers are absent.

### 5.3 Data model

Core tables:

```text
requirements
  id
  stable_id
  version
  title
  statement
  rationale
  type
  criticality
  status
  owner
  source
  created_at
  updated_at
  superseded_by

acceptance_criteria
  id
  requirement_id
  requirement_version
  statement
  status

verification_records
  id
  requirement_id
  requirement_version
  method
  evidence_ref
  evidence_type
  status
  freshness
  last_verified_at
  last_verified_commit
  verifier
  notes

trace_links
  id
  from_kind
  from_id
  to_kind
  to_id
  relation
  authority
  confidence
  freshness
  created_by
  created_at
  accepted_by
  accepted_at

baselines
  id
  title
  description
  created_at
  created_by

baseline_members
  baseline_id
  requirement_id
  requirement_version

events
  id
  timestamp
  actor
  event_type
  subject_kind
  subject_id
  before_json
  after_json
```

### 5.4 Identity model

Charter has two levels of identity:

1. Charter-native requirement identity.
2. Federated code identity supplied by Clarion.

Requirement IDs are human-readable and durable:

```text
REQ-AUTH-017
REQ-SEC-004
REQ-API-012
```

Requirement versions are immutable once approved.

Code-entity links should prefer Clarion SEI when available:

```yaml
to_kind: clarion_entity
to_id: sei:01HX...
relation: satisfies
```

When Clarion is unavailable, Charter may link to files, symbols, or line ranges, but these links must be marked as fragile.

### 5.5 Event model

Every mutation emits an event.

Examples:

```text
requirement.created
requirement.updated
requirement.approved
requirement.superseded
criterion.added
verification.recorded
verification.marked_stale
trace.proposed
trace.accepted
trace.rejected
baseline.created
import.completed
```

Events enable:

* agent session resumption;
* change summaries;
* audit trails;
* generated context;
* future synchronisation or federation.

## 6. Feature set

### 6.1 Requirements authoring

Charter must support creating, editing, approving, superseding, and deprecating requirements.

Required features:

* create requirement;
* edit draft requirement;
* approve requirement;
* supersede requirement;
* deprecate requirement;
* assign type and criticality;
* add rationale;
* add source reference;
* add acceptance criteria;
* view requirement history;
* compare requirement versions.

CLI examples:

```bash
charter add "Reject expired bearer tokens" --type security --criticality high
charter approve REQ-AUTH-017
charter supersede REQ-AUTH-017 --statement-file req.md
charter show REQ-AUTH-017
charter history REQ-AUTH-017
```

### 6.2 Traceability

Charter must support explicit trace links between requirements, code, tests, issues, evidence, and external references.

Required features:

* link requirement to requirement;
* link requirement to acceptance criterion;
* link requirement to test;
* link requirement to Clarion entity;
* link requirement to Filigree issue;
* link requirement to Wardline finding;
* link requirement to external URL or imported ALM object;
* propose trace links from agent analysis;
* accept or reject proposed trace links;
* mark links stale;
* show forward and backward trace.

CLI examples:

```bash
charter link REQ-AUTH-017 --test tests/test_auth.py::test_expired_token_rejected
charter link REQ-AUTH-017 --entity auth.validate_token
charter trace REQ-AUTH-017
charter accept-link LINK-42
```

### 6.3 Verification

Charter must distinguish requirement existence from requirement satisfaction.

Required features:

* define verification method;
* attach verification evidence;
* record passing, failing, missing, stale, waived, or unknown verification state;
* bind verification to commit;
* mark verification stale when linked code or requirement changes;
* list unverified approved requirements;
* list stale verification records;
* support verification by test, analysis, inspection, demonstration, review, or external evidence.

CLI examples:

```bash
charter verify REQ-AUTH-017 --method test --evidence tests/test_auth.py::test_expired_token_rejected
charter verification stale
charter verification missing
charter verify-run --from-junit test-results.xml
```

### 6.4 Baselines

Charter must support requirement baselines.

Required features:

* create named baseline;
* include approved requirements in baseline;
* compare current requirements to baseline;
* show changed requirements since baseline;
* show verification state against baseline;
* export baseline;
* lock baseline against mutation.

CLI examples:

```bash
charter baseline create release-1.0
charter baseline diff release-1.0
charter baseline verify release-1.0
```

### 6.5 Impact analysis

Charter must provide impact analysis for requirements and diffs.

Required features:

* identify requirements touched by pending git diff;
* identify requirements touched by commit range;
* identify requirements linked to changed entities;
* identify requirements near changed entities through Clarion neighbourhoods;
* identify stale verification caused by code changes;
* identify requirements changed without linked work;
* identify code touched without requirements when policy expects traceability;
* produce agent-readable impact report.

CLI examples:

```bash
charter impact
charter impact --since main
charter impact --requirement REQ-AUTH-017
```

Example output:

```text
Requirement impact for pending diff

In this change:
  REQ-AUTH-017
    touched entity: auth.validate_token
    verification: stale
    evidence: tests/test_auth.py::test_expired_token_rejected not run on current commit

Around this change:
  REQ-AUTH-014
    caller chain depends on modified entity
    verification: current

Gaps:
  REQ-AUTH-017 has no accepted trace to implementation after rename.
```

### 6.6 Agent context

Charter must generate compact context for agents.

Required features:

* project requirement summary;
* open verification gaps;
* requirements touched by active work;
* changed requirements since last session;
* unresolved proposed links;
* stale verification records;
* baseline status.

Generated file:

```text
.charter/context.md
```

This file is regenerated after mutations and may be injected into agent sessions by install hooks.

### 6.7 MCP tools

Charter must expose MCP tools for consult-mode and action-mode agents.

Initial MCP tool set:

```text
requirement_get(id)
requirement_search(query, status?, type?, criticality?)
requirement_create(...)
requirement_update(...)
requirement_approve(id)
requirement_supersede(id, ...)
requirement_deprecate(id)

trace_link_create(...)
trace_link_propose(...)
trace_link_accept(id)
trace_link_reject(id)
trace_for(id)
trace_gaps(scope?)

verification_record(...)
verification_status(requirement_id)
verification_missing(scope?)
verification_stale(scope?)
verification_import_junit(path)

baseline_create(name)
baseline_diff(name)
baseline_status(name)

impact_pending_diff()
impact_commit_range(base, head)
dossier_requirement(id)
session_context()
```

Action tools that mutate state must accept an actor parameter or infer actor from the MCP session.

### 6.8 Imports and exports

Charter must not trap users.

Required import formats:

* Markdown;
* YAML;
* JSON;
* CSV;
* simple table import.

Desirable import adapters:

* DOORS Next via OSLC or exported CSV;
* Polarion export;
* Jama export;
* Jira/Confluence pages;
* GitHub Issues labels;
* existing project markdown.

Required export formats:

* Markdown;
* JSONL;
* CSV;
* SARIF-adjacent evidence summary where useful;
* static HTML report.

### 6.9 External ALM adapter mode

Charter may operate in adapter mode where an external system remains the requirements authority.

In adapter mode:

* external requirement IDs remain canonical;
* Charter caches requirement metadata;
* Charter stores local trace links and verification facts unless the external system supports writing them;
* Charter marks imported facts with source and freshness;
* Charter never pretends imported stale data is current;
* Charter can produce local impact reports over imported requirements.

Supported external systems are post-v1.0 scope.

## 7. Federation requirements

### 7.1 Clarion integration

When Clarion is present, Charter must:

* resolve entity names to SEI;
* link requirements to SEI;
* request affected entities for pending diff;
* request neighbourhoods around touched entities;
* survive rename and move events through Clarion identity;
* degrade honestly if SEI capability is absent.

Charter must not mint or reinterpret SEI.

### 7.2 Filigree integration

When Filigree is present, Charter must:

* link requirements to issues;
* show open work for a requirement;
* create implementation or verification tasks from requirement gaps;
* attach requirement impact to issue context;
* expose requirement gaps as candidate work;
* avoid taking ownership of issue lifecycle.

Example:

```bash
charter gap create-work REQ-AUTH-017 --type verification
```

### 7.3 Wardline integration

When Wardline is present, Charter must:

* link Wardline findings to security or trust requirements;
* show Wardline findings in requirement dossiers;
* mark a requirement unsatisfied if an active finding violates a linked acceptance criterion;
* allow Wardline findings to generate proposed requirement links;
* avoid duplicating Wardline analysis authority.

Example:

```text
REQ-SEC-004 requires external request bodies to be validated before persistence.
Wardline finding PY-WL-101 violates REQ-SEC-004.
```

### 7.4 Legis integration

When Legis is present, Charter must:

* contribute requirement impact to commit preflight;
* provide verification freshness facts;
* provide baseline conformance facts;
* provide traceability gaps;
* allow Legis to enforce policies using Charter facts;
* receive governance attestations or sign-off references from Legis;
* avoid deciding whether a commit may proceed.

Example Chill-mode contribution:

```text
Requirements:
  WARN  REQ-AUTH-017 touched; verification stale.
  INFO  REQ-AUTH-014 nearby through caller chain; verification current.
```

Example Structured-mode contribution:

```text
BLOCK  Safety-critical requirement REQ-SAFE-003 touched without fresh verification.
```

## 8. Policy model

Charter itself should not be a general policy engine. It should expose facts that Legis can govern.

However, Charter should support local advisory rules:

```yaml
rules:
  require_verification_for_approved: true
  require_acceptance_criteria_for_high_criticality: true
  mark_verification_stale_on_requirement_change: true
  mark_verification_stale_on_linked_entity_change: true
  require_human_acceptance_for_agent_links: true
```

Rules produce Charter findings, not commit decisions.

Commit decisions belong to Legis.

## 9. User workflows

### 9.1 Lightweight solo workflow

```bash
charter init
charter add "Users can reset their password" --type functional
charter approve REQ-USER-001
charter link REQ-USER-001 --entity users.reset_password
charter verify REQ-USER-001 --method test --evidence tests/test_password_reset.py
charter impact
```

### 9.2 Agent-driven implementation workflow

1. Agent starts session.
2. Filigree provides active issue context.
3. Charter provides linked requirements.
4. Clarion identifies affected entities.
5. Agent modifies code.
6. Wardline scans trust boundaries.
7. Charter marks verification stale or records new evidence.
8. Legis preflight reports commit-boundary obligations.

### 9.3 Requirement change workflow

1. Requirement is updated in draft.
2. Agent requests impact analysis.
3. Charter lists affected child requirements, entities, tests, issues, and verification records.
4. Filigree tasks are created for required updates.
5. Baseline diff shows what changed.
6. Legis may require sign-off if protected requirements are affected.

### 9.4 DOORS-lite import workflow

1. User imports CSV or exported requirements.
2. Charter creates imported requirements.
3. Agent proposes links to Clarion entities and tests.
4. Human accepts high-confidence links.
5. Charter creates baseline.
6. Future diffs can report requirement impact.

## 10. CLI surface

Minimum CLI:

```text
charter init
charter install
charter doctor

charter add
charter edit
charter approve
charter supersede
charter deprecate
charter show
charter search
charter history

charter criterion add
charter criterion list

charter link
charter unlink
charter trace
charter gaps
charter accept-link
charter reject-link

charter verify
charter verification status
charter verification missing
charter verification stale
charter verify-run

charter baseline create
charter baseline list
charter baseline diff
charter baseline verify
charter baseline export

charter impact
charter dossier
charter context
charter export
charter import
charter mcp
```

## 11. Configuration

Project config lives at:

```text
charter.yaml
```

Example:

```yaml
project:
  key: AUTH
  requirement_prefix: REQ

storage:
  path: .charter/charter.db

federation:
  clarion: auto
  filigree: auto
  wardline: auto
  legis: auto

verification:
  stale_on_requirement_change: true
  stale_on_linked_entity_change: true
  require_current_for_criticality:
    - high
    - safety
    - security

traceability:
  allow_agent_proposed_links: true
  require_human_acceptance_for:
    - safety
    - security
    - high

baselines:
  require_approved_only: true
```

## 12. Requirements

### Functional requirements

#### FR-1: Requirement management

Charter shall allow users and agents to create, update, approve, supersede, deprecate, search, and view requirements.

#### FR-2: Requirement versioning

Charter shall preserve immutable approved requirement versions.

#### FR-3: Acceptance criteria

Charter shall support one or more acceptance criteria per requirement.

#### FR-4: Verification records

Charter shall support verification records linked to requirements and requirement versions.

#### FR-5: Verification freshness

Charter shall mark verification records stale when linked requirements or linked implementation entities change.

#### FR-6: Trace links

Charter shall support typed trace links between requirements, acceptance criteria, verification records, tests, code entities, issues, findings, external references, and baselines.

#### FR-7: Agent-proposed trace links

Charter shall allow agents to propose trace links without treating them as accepted truth.

#### FR-8: Trace acceptance

Charter shall allow proposed trace links to be accepted or rejected.

#### FR-9: Baselines

Charter shall support named baselines of approved requirement versions.

#### FR-10: Baseline comparison

Charter shall compare the current requirement set to a baseline.

#### FR-11: Impact analysis

Charter shall report requirements affected by a pending diff or commit range.

#### FR-12: Requirement dossier

Charter shall provide a single structured dossier for a requirement.

#### FR-13: Session context

Charter shall generate an agent-readable project context summary.

#### FR-14: CLI

Charter shall provide a CLI for all core operations.

#### FR-15: MCP server

Charter shall expose core operations through an MCP-over-stdio server.

#### FR-16: Import

Charter shall import requirements from at least Markdown, CSV, YAML, and JSON.

#### FR-17: Export

Charter shall export requirements, traces, baselines, and verification records to Markdown, CSV, JSONL, and static report formats.

#### FR-18: Clarion federation

When Clarion is present, Charter shall link requirements to Clarion SEI rather than only files or line ranges.

#### FR-19: Filigree federation

When Filigree is present, Charter shall link requirements to issues and create work items from gaps.

#### FR-20: Wardline federation

When Wardline is present, Charter shall link trust findings to requirements and expose those findings in requirement dossiers.

#### FR-21: Legis federation

When Legis is present, Charter shall provide requirement impact, verification freshness, baseline status, and traceability gap facts to Legis preflight and enforcement surfaces.

### Non-functional requirements

#### NFR-1: Local-first

Charter shall operate without a cloud service or account.

#### NFR-2: Deterministic core

Charter’s core model and impact calculations shall be deterministic.

#### NFR-3: Agent-safe output

All CLI commands used by agents shall support structured JSON output.

#### NFR-4: Human-readable output

Charter shall also provide concise human-readable CLI output.

#### NFR-5: Low dependency weight

The base install shall have minimal dependencies.

#### NFR-6: No hidden authority

Charter shall not silently make governance decisions, infer code identity, or mutate peer-owned state without explicit integration contracts.

#### NFR-7: Freshness honesty

Imported, inferred, stale, or agent-proposed facts shall be labelled as such.

#### NFR-8: Auditability

All mutations shall produce event records.

#### NFR-9: Graceful degradation

Charter shall remain useful when Clarion, Filigree, Wardline, or Legis are absent.

#### NFR-10: Repository portability

A project’s Charter state shall live in a repo-local `.charter/` directory.

#### NFR-11: Performance

Charter shall support thousands of requirements and trace links on ordinary developer hardware.

#### NFR-12: Safety against false certainty

Charter shall distinguish accepted traceability from proposed or inferred traceability.

## 13. MVP scope

### MVP must include

* local SQLite store;
* `charter init`;
* create/edit/approve/deprecate requirements;
* requirement versions;
* acceptance criteria;
* manual trace links;
* verification records;
* stale verification detection for requirement changes;
* baselines;
* `charter impact` over manually linked files/tests;
* JSON output for agent use;
* MCP server with read/query/dossier tools;
* import/export to Markdown and JSON;
* generated `.charter/context.md`.

### MVP should include

* Clarion entity links if Clarion is installed;
* Filigree issue links if Filigree is installed;
* agent-proposed trace links;
* baseline diff;
* pending-diff impact report.

### MVP may defer

* external DOORS/Polarion/Jama import adapters;
* full OSLC support;
* rich web UI;
* multi-user sync;
* cryptographic attestations;
* deep test runner integration;
* automatic semantic requirement extraction;
* complex policy grammar.

## 14. v1.0 scope

v1.0 should include:

* robust requirement lifecycle;
* accepted/proposed/rejected trace links;
* requirement dossiers over MCP;
* Clarion federation using SEI;
* Filigree federation for requirement-linked work;
* Legis preflight contribution;
* Wardline finding links;
* baseline creation and comparison;
* verification freshness against requirement and linked entity changes;
* import/export;
* session context generation;
* documented integration contracts.

## 15. Post-v1.0 scope

Post-v1.0 candidates:

* DOORS Next OSLC adapter;
* Polarion adapter;
* Jama adapter;
* Codebeamer adapter;
* GitHub Issues import/export;
* Confluence/Jira import;
* generated trace-matrix reports;
* static HTML dashboard;
* Graph visualisation;
* richer requirement quality checks;
* LLM-assisted requirement decomposition;
* LLM-assisted test suggestion;
* requirement coverage heatmaps;
* safety case or assurance case support.

## 16. Product positioning

Charter is for users who have outgrown tasks and epics, but do not want enterprise ALM ceremony.

Use Charter when:

* requirements need to be explicit;
* verification matters;
* agents need structured obligations;
* change impact should include requirements;
* traceability should survive refactors;
* a lightweight local-first workflow is enough.

Do not use Charter when:

* the organisation requires a certified enterprise ALM system;
* requirements must be centrally managed across many teams;
* role-based access control is mandatory;
* external auditors require an approved system of record;
* requirements contain sensitive information that cannot live in local repo storage.

## 17. One-sentence description

Charter is a local-first requirements and verification authority for agentic development: it records what must be true, links it to code and work, tracks how it is verified, and tells agents what obligations a change touches.
