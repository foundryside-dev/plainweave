# Plainweave Verification And Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Plainweave P0 verification methods, evidence records, and computed requirement satisfaction/freshness status.

**Architecture:** Extend the local SQLite schema with method and evidence tables, then expose focused dataclasses and service methods. The CLI remains a thin envelope layer over service behavior, and tests pin both state semantics and JSON contracts.

**Tech Stack:** Python 3.13, SQLite, argparse CLI, pytest, uv, ruff, mypy.

---

## File Structure

- Modify `src/plainweave/store.py`: add verification tables, append-only evidence triggers, and idempotent migration behavior.
- Modify `src/plainweave/models.py`: add verification method, evidence, reason, and status dataclasses.
- Modify `src/plainweave/service.py`: add method/evidence creation, authority validation, status computation, and list helpers.
- Modify `src/plainweave/cli_commands.py`: register `verify` and `status` command trees and serializers.
- Modify `tests/test_store_migrations.py`: verify schema, idempotency, and evidence append-only behavior.
- Create `tests/state/test_verification_status.py`: service-level lifecycle and status tests.
- Create `tests/test_cli_verification.py`: CLI behavior and error tests.
- Modify `tests/contracts/test_contract_fixtures.py`: add fixture requirements and schema validators.
- Modify `tests/contracts/test_cli_contract_outputs.py`: add parsed CLI contract parity tests.
- Create `tests/fixtures/contracts/verification/*.json` and `tests/fixtures/contracts/cli/*verify*.json`: fixture contracts.
- Modify `docs/agentic-doors-replacement-roadmap.md`: mark Package B and the two P0 rows implemented after final gates.

### Task 1: Contracts First

**Files:**
- Modify: `tests/contracts/test_contract_fixtures.py`
- Add: `tests/fixtures/contracts/verification/verification-method.json`
- Add: `tests/fixtures/contracts/verification/verification-evidence.json`
- Add: `tests/fixtures/contracts/verification/requirement-verification-status.json`

- [ ] **Step 1: Write failing contract fixture tests**

Add fixture paths to `REQUIRED_FIXTURES`:

```python
"verification/verification-method.json",
"verification/verification-evidence.json",
"verification/requirement-verification-status.json",
```

Add validators asserting:

```python
def test_verification_method_fixture_contract() -> None:
    fixture = load_fixture("verification/verification-method.json")
    assert set(fixture) == {
        "schema", "id", "requirement_id", "requirement_version",
        "method", "target", "status", "created_by", "created_at",
    }
    assert fixture["schema"] == "weft.plainweave.verification_method.v1"
    assert fixture["id"].startswith("VERM-")
    assert fixture["method"] in {"test", "analysis", "inspection", "manual"}
    assert fixture["status"] == "active"


def test_verification_evidence_fixture_contract() -> None:
    fixture = load_fixture("verification/verification-evidence.json")
    assert set(fixture) == {
        "schema", "id", "method_id", "requirement_id",
        "requirement_version", "status", "evidence_ref", "authority",
        "freshness", "recorded_by", "recorded_at", "payload",
    }
    assert fixture["schema"] == "weft.plainweave.verification_evidence.v1"
    assert fixture["id"].startswith("EVID-")
    assert fixture["status"] in {"passing", "failing", "inconclusive", "waived"}
    assert fixture["authority"] in {"test_derived", "human_attested", "agent_reported", "waiver"}
    assert fixture["freshness"] in {"current", "stale"}


def test_requirement_verification_status_fixture_contract() -> None:
    fixture = load_fixture("verification/requirement-verification-status.json")
    assert set(fixture) == {
        "schema", "requirement_id", "id", "stable_id", "current_version",
        "status", "reasons", "current_evidence", "stale_evidence",
    }
    assert fixture["schema"] == "weft.plainweave.requirement_verification_status.v1"
    assert fixture["status"] in {"satisfied", "unsatisfied", "unverified", "stale", "unknown", "waived"}
    assert isinstance(fixture["reasons"], list)
```

- [ ] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/contracts/test_contract_fixtures.py -q
```

Expected: fails because the verification fixture files do not exist.

- [ ] **Step 3: Add fixture JSON**

Create fixtures matching the validators, using `REQ-AUTH-0001`, `VERM-0001`,
and `EVID-0001`.

- [ ] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/contracts/test_contract_fixtures.py -q
```

Expected: passes.

- [ ] **Step 5: Commit**

```bash
git add tests/contracts/test_contract_fixtures.py tests/fixtures/contracts/verification
git commit -m "test: add verification contract fixtures"
```

### Task 2: SQLite Schema And Models

**Files:**
- Modify: `src/plainweave/store.py`
- Modify: `src/plainweave/models.py`
- Modify: `tests/test_store_migrations.py`

- [ ] **Step 1: Write failing migration tests**

Add tests for table existence, idempotent migration, and evidence append-only:

```python
def test_verification_tables_are_created(tmp_path: Path) -> None:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")
    migrate(db_path, project_key="AUTH")
    with connect(db_path) as connection:
        assert columns(connection, "verification_methods") == {
            "method_id", "requirement_id", "requirement_version", "method_type",
            "target", "status", "created_by", "created_at",
        }
        assert columns(connection, "verification_evidence") == {
            "evidence_id", "method_id", "requirement_id", "requirement_version",
            "status", "evidence_ref", "authority", "freshness",
            "recorded_by", "recorded_at", "payload_json",
        }
```

- [ ] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_store_migrations.py -q
```

Expected: fails because tables are absent.

- [ ] **Step 3: Implement schema and dataclasses**

Add the two tables and evidence update/delete triggers in `store.py`. Add
frozen dataclasses `VerificationMethod`, `VerificationEvidence`,
`VerificationReason`, and `RequirementVerificationStatus` in `models.py`.

- [ ] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_store_migrations.py -q
```

Expected: passes.

- [ ] **Step 5: Commit**

```bash
git add src/plainweave/store.py src/plainweave/models.py tests/test_store_migrations.py
git commit -m "feat: add verification storage"
```

### Task 3: Service Behavior

**Files:**
- Modify: `src/plainweave/service.py`
- Add: `tests/state/test_verification_status.py`

- [ ] **Step 1: Write failing service tests**

Create tests with these exact names and assertions:

- `test_approved_requirement_without_evidence_is_unverified`: approve a
  requirement, call `verification_status`, assert `status == "unverified"` and
  reason code `no_verification_method`.
- `test_add_method_requires_approved_requirement`: create a draft requirement,
  call `add_verification_method`, assert `ErrorCode.POLICY_REQUIRED`.
- `test_passing_test_evidence_satisfies_current_version`: add a `test` method,
  record `passing` evidence, assert `status == "satisfied"` and one current
  evidence record.
- `test_failing_evidence_makes_requirement_unsatisfied`: add a `test` method,
  record `failing` evidence, assert `status == "unsatisfied"` and reason code
  `failing_evidence`.
- `test_supersede_makes_prior_evidence_stale`: record passing evidence for
  version 1, supersede to version 2, assert `status == "stale"` and the
  version 1 evidence appears in `stale_evidence`.
- `test_human_waiver_is_distinct_status`: add a `manual` method as a human,
  record `waived` evidence as a human, assert `status == "waived"` and
  authority `waiver`.
- `test_agent_cannot_record_manual_or_waiver_attestation`: assert agent
  recording against `manual` method or `waived` status raises
  `ErrorCode.POLICY_REQUIRED`.
- `test_status_lists_unverified_and_stale_requirements`: create one unverified
  approved requirement and one superseded stale requirement, then assert the
  list helpers return the expected IDs.

- [ ] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/state/test_verification_status.py -q
```

Expected: fails because service methods do not exist.

- [ ] **Step 3: Implement service methods**

Implement:

```python
add_verification_method(requirement_id, *, method, target, actor)
record_verification_evidence(method_id, *, status, evidence_ref, actor, payload=None)
verification_status(requirement_id)
list_unverified_requirements()
list_stale_requirements()
```

Use deterministic IDs `VERM-0001` and `EVID-0001`, version evidence against the
requirement current version at recording time, and compute status from current
and stale evidence.

- [ ] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/state/test_verification_status.py -q
```

Expected: passes.

- [ ] **Step 5: Commit**

```bash
git add src/plainweave/service.py tests/state/test_verification_status.py
git commit -m "feat: add verification service"
```

### Task 4: CLI And Contract Parity

**Files:**
- Modify: `src/plainweave/cli_commands.py`
- Add: `tests/test_cli_verification.py`
- Modify: `tests/contracts/test_cli_contract_outputs.py`
- Add: `tests/fixtures/contracts/cli/verify-method-add-json.json`
- Add: `tests/fixtures/contracts/cli/verify-evidence-record-json.json`
- Add: `tests/fixtures/contracts/cli/verify-status-json.json`
- Add: `tests/fixtures/contracts/cli/status-requirement-json.json`
- Add: `tests/fixtures/contracts/cli/status-unverified-json.json`
- Add: `tests/fixtures/contracts/cli/status-stale-json.json`

- [ ] **Step 1: Write failing CLI tests**

Test create/status/list commands and representative validation/not-found errors.

- [ ] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_cli_verification.py tests/contracts/test_cli_contract_outputs.py -q
```

Expected: fails because `verify` and `status` commands are not registered.

- [ ] **Step 3: Implement CLI commands and serializers**

Register `verify method add`, `verify evidence record`, `verify status`,
`status requirement`, `status unverified`, and `status stale`. Return schemas
`weft.plainweave.verification_method.v1`,
`weft.plainweave.verification_evidence.v1`, and
`weft.plainweave.requirement_verification_status.v1`.

- [ ] **Step 4: Add CLI fixtures and parity assertions**

Update `REQUIRED_FIXTURES` and parsed-shape fixture tests. Timestamp fields are
shape-checked, not byte-compared.

- [ ] **Step 5: Run GREEN**

Run:

```bash
uv run pytest tests/test_cli_verification.py tests/contracts/test_cli_contract_outputs.py -q
```

Expected: passes.

- [ ] **Step 6: Commit**

```bash
git add src/plainweave/cli_commands.py tests/test_cli_verification.py tests/contracts/test_cli_contract_outputs.py tests/contracts/test_contract_fixtures.py tests/fixtures/contracts/cli
git commit -m "feat: add verification CLI contracts"
```

### Task 5: Review, Roadmap, And Gates

**Files:**
- Modify: `docs/agentic-doors-replacement-roadmap.md`

- [ ] **Step 1: Run review checklist**

Check:

```text
evidence records are append-only
evidence remains tied to requirement versions
supersede does not mutate previous evidence
agents cannot record manual or waiver authority
status never depends on issue closure
schemas are stable and agent-safe
```

- [ ] **Step 2: Fix review findings**

Add failing tests first for any Critical or Important finding, then fix.

- [ ] **Step 3: Run final gates**

Run:

```bash
make lint
make typecheck
make test
uv run pytest tests/contracts -q
uv run pytest tests/state -q
make ci
rg -n "impact|loomweave|filigree|wardline|legis|mcp" src tests
```

Expected: all commands pass; scope audit shows only existing inert/deferred
references and no new peer/MCP/impact implementation.

- [ ] **Step 4: Update roadmap**

Mark verification methods/evidence and requirement satisfaction/freshness rows
as implemented in `codex/verification-core`. Mark Package B exit criteria
complete with commit/reference and verification evidence.

- [ ] **Step 5: Commit docs**

```bash
git add docs/agentic-doors-replacement-roadmap.md
git commit -m "docs: update verification roadmap status"
```
