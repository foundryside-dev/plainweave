# Charter Requirement Dossiers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local, agent-first requirement dossier command and JSON contract that summarizes one requirement's authority, criteria, traces, verification, baseline exposure, computed gaps, peer-call status, and next actions.

**Architecture:** Implement dossiers as read-only computed service objects over existing Charter SQLite state. The service returns immutable dataclasses, the CLI serializes them with existing envelope helpers, and contract tests pin the agent-facing JSON shape.

**Tech Stack:** Python 3.12, SQLite, argparse, dataclasses, pytest, uv, existing Charter CLI/envelope/store/service patterns.

---

## File Structure

- Create `tests/fixtures/contracts/dossiers/requirement-dossier.json`: canonical data fixture for `loom.charter.requirement_dossier.v1`.
- Create `tests/fixtures/contracts/cli/dossier-json.json`: canonical CLI envelope fixture for `charter dossier REQ-AUTH-0001 --json`.
- Modify `tests/contracts/test_contract_fixtures.py`: register dossier fixtures and validate dossier section shapes.
- Modify `tests/contracts/test_cli_contract_outputs.py`: add parsed-shape CLI parity test for dossier JSON output.
- Modify `src/charter/models.py`: add frozen dataclasses for `RequirementDossier`, `DossierAuthoritySummary`, `DossierRequirementSection`, `DossierAcceptanceCriteriaSection`, `DossierTraceSection`, `DossierBaselineExposure`, `DossierBaselineExposureItem`, `DossierComputedGap`, `DossierPeerFacts`, and `DossierNextAction`.
- Modify `src/charter/service.py`: add `CharterService.requirement_dossier(requirement_id)` and private helpers for draft lookup, criteria split, trace grouping, baseline exposure, computed gaps, and next actions.
- Modify `src/charter/cli_commands.py`: register `charter dossier REQ_ID`, add handler and serializers, reuse `success_envelope`.
- Create `tests/state/test_requirement_dossiers.py`: service behavior tests for approved, draft, trace, verification, baseline, and gap scenarios.
- Create `tests/test_cli_dossier.py`: CLI behavior tests for JSON, human output, and not-found errors.
- Modify `docs/agentic-doors-replacement-roadmap.md`: after implementation and gates, mark local requirement dossiers as installed and keep MCP read as the next sequencing item.

## Contract Decisions

The dossier data object has this top-level shape:

```json
{
  "identity": {},
  "authority_summary": {},
  "requirement": {},
  "acceptance_criteria": {},
  "traces": {},
  "verification": {},
  "baseline_exposure": {},
  "computed_gaps": [],
  "peer_facts": {},
  "next_actions": []
}
```

The CLI envelope uses:

```json
{
  "schema": "loom.charter.requirement_dossier.v1",
  "ok": true,
  "data": {
    "identity": {},
    "authority_summary": {},
    "requirement": {},
    "acceptance_criteria": {},
    "traces": {},
    "verification": {},
    "baseline_exposure": {},
    "computed_gaps": [],
    "peer_facts": {},
    "next_actions": []
  },
  "warnings": [],
  "meta": {}
}
```

No task in this plan may add migrations, tables, peer calls, durable gap rows, or MCP tools.

### Task 1: Add Dossier Contract Fixtures

**Files:**
- Modify: `tests/contracts/test_contract_fixtures.py`
- Create: `tests/fixtures/contracts/dossiers/requirement-dossier.json`

- [ ] **Step 1: Write the failing fixture registration**

Add these entries to `REQUIRED_FIXTURES` in `tests/contracts/test_contract_fixtures.py`:

```python
    "dossiers/requirement-dossier.json",
```

Add this test to the same file:

```python
def test_requirement_dossier_fixture_contract() -> None:
    fixture = load_fixture("dossiers/requirement-dossier.json")

    assert set(fixture) == {
        "schema",
        "identity",
        "authority_summary",
        "requirement",
        "acceptance_criteria",
        "traces",
        "verification",
        "baseline_exposure",
        "computed_gaps",
        "peer_facts",
        "next_actions",
    }
    assert fixture["schema"] == "loom.charter.requirement_dossier.v1"
    assert set(fixture["identity"]) == {"requirement_id", "id", "stable_id", "current_version"}
    assert set(fixture["authority_summary"]) == {
        "status",
        "current_approved_version",
        "current_statement_hash",
        "has_active_draft",
        "active_draft_id",
        "verification_status",
        "baseline_count",
    }
    assert set(fixture["requirement"]) == {"record", "current_version", "active_draft"}
    assert set(fixture["acceptance_criteria"]) == {"current_version", "active_draft"}
    assert set(fixture["traces"]) == {"incoming", "outgoing", "by_state", "by_relation", "items"}
    assert set(fixture["verification"]) == {"status", "reasons", "current_evidence", "stale_evidence"}
    assert set(fixture["baseline_exposure"]) == {"summary", "items"}
    assert set(fixture["peer_facts"]) == {"live_peer_calls", "sources", "notes"}
    assert fixture["peer_facts"]["live_peer_calls"] is False
    assert isinstance(fixture["computed_gaps"], list)
    assert isinstance(fixture["next_actions"], list)
    for gap in fixture["computed_gaps"]:
        assert set(gap) == {"code", "severity", "message", "source"}
    for action in fixture["next_actions"]:
        assert set(action) == {"action", "priority", "reason", "command", "blocked_by"}
```

- [ ] **Step 2: Run the contract test and verify RED**

Run:

```bash
uv run pytest tests/contracts/test_contract_fixtures.py::test_required_fixture_plan_files_exist tests/contracts/test_contract_fixtures.py::test_requirement_dossier_fixture_contract -q
```

Expected: FAIL because `tests/fixtures/contracts/dossiers/requirement-dossier.json` does not exist or the new contract test cannot load it.

- [ ] **Step 3: Add the canonical dossier fixture**

Create `tests/fixtures/contracts/dossiers/requirement-dossier.json`:

```json
{
  "schema": "loom.charter.requirement_dossier.v1",
  "identity": {
    "requirement_id": "req_auth_0001",
    "id": "REQ-AUTH-0001",
    "stable_id": "charter:req:AUTH:0001",
    "current_version": 1
  },
  "authority_summary": {
    "status": "approved",
    "current_approved_version": 1,
    "current_statement_hash": "sha256:4d9674f0b947daeb092a02fa2b2d0d9c7b501c2385d59a468b181dc3a09d2f3f",
    "has_active_draft": false,
    "active_draft_id": null,
    "verification_status": "satisfied",
    "baseline_count": 1
  },
  "requirement": {
    "record": {
      "requirement_id": "req_auth_0001",
      "id": "REQ-AUTH-0001",
      "stable_id": "charter:req:AUTH:0001",
      "current_version": 1,
      "active_draft_id": null,
      "status": "approved",
      "current_version_record": {
        "requirement_id": "req_auth_0001",
        "id": "REQ-AUTH-0001",
        "stable_id": "charter:req:AUTH:0001",
        "version": 1,
        "title": "Reject expired bearer tokens",
        "statement": "The API shall reject expired bearer tokens.",
        "statement_hash": "sha256:4d9674f0b947daeb092a02fa2b2d0d9c7b501c2385d59a468b181dc3a09d2f3f",
        "status": "approved",
        "approved_by": "human:john",
        "approved_at": "2026-06-05T00:00:00Z"
      }
    },
    "current_version": {
      "requirement_id": "req_auth_0001",
      "id": "REQ-AUTH-0001",
      "stable_id": "charter:req:AUTH:0001",
      "version": 1,
      "title": "Reject expired bearer tokens",
      "statement": "The API shall reject expired bearer tokens.",
      "statement_hash": "sha256:4d9674f0b947daeb092a02fa2b2d0d9c7b501c2385d59a468b181dc3a09d2f3f",
      "status": "approved",
      "approved_by": "human:john",
      "approved_at": "2026-06-05T00:00:00Z"
    },
    "active_draft": null
  },
  "acceptance_criteria": {
    "current_version": [
      {
        "id": "AC-0001",
        "requirement_id": "REQ-AUTH-0001",
        "draft_id": null,
        "version": 1,
        "position": 1,
        "text": "Expired tokens return 401.",
        "status": "approved",
        "created_by": "human:john",
        "created_at": "2026-06-05T00:00:00Z"
      }
    ],
    "active_draft": []
  },
  "traces": {
    "incoming": [
      {
        "id": "LINK-0001",
        "state": "accepted",
        "from": {"kind": "test_selector", "id": "tests/test_auth.py::test_expired"},
        "relation": "provides_evidence_for",
        "to": {"kind": "requirement_version", "id": "REQ-AUTH-0001@1"},
        "authority": "accepted",
        "freshness": "current",
        "confidence": 0.82,
        "created_by": "agent:codex",
        "accepted_by": "human:john",
        "target_snapshot": {}
      }
    ],
    "outgoing": [],
    "by_state": {"accepted": 1},
    "by_relation": {"provides_evidence_for": 1},
    "items": [
      {
        "id": "LINK-0001",
        "state": "accepted",
        "from": {"kind": "test_selector", "id": "tests/test_auth.py::test_expired"},
        "relation": "provides_evidence_for",
        "to": {"kind": "requirement_version", "id": "REQ-AUTH-0001@1"},
        "authority": "accepted",
        "freshness": "current",
        "confidence": 0.82,
        "created_by": "agent:codex",
        "accepted_by": "human:john",
        "target_snapshot": {}
      }
    ]
  },
  "verification": {
    "status": "satisfied",
    "reasons": [
      {"code": "passing_evidence", "message": "Current passing evidence exists.", "evidence_id": "EVID-0001"}
    ],
    "current_evidence": [
      {
        "id": "EVID-0001",
        "method_id": "VERM-0001",
        "status": "passing",
        "authority": "test_derived",
        "freshness": "current",
        "evidence_ref": "pytest:tests/test_auth.py::test_expired"
      }
    ],
    "stale_evidence": []
  },
  "baseline_exposure": {
    "summary": {
      "current": 1,
      "changed": 0,
      "missing_current": 0,
      "superseded_since_baseline": 0
    },
    "items": [
      {
        "baseline_id": "BASELINE-0001",
        "name": "Release 1.0 requirements",
        "locked": true,
        "created_by": "human:john",
        "created_at": "2026-06-05T00:00:00Z",
        "baseline_version": 1,
        "baseline_statement_hash": "sha256:4d9674f0b947daeb092a02fa2b2d0d9c7b501c2385d59a468b181dc3a09d2f3f",
        "current_version": 1,
        "current_statement_hash": "sha256:4d9674f0b947daeb092a02fa2b2d0d9c7b501c2385d59a468b181dc3a09d2f3f",
        "state": "current"
      }
    ]
  },
  "computed_gaps": [],
  "peer_facts": {
    "live_peer_calls": false,
    "sources": [],
    "notes": ["Dossier is computed from the local Charter store only."]
  },
  "next_actions": [
    {
      "action": "record_current_evidence",
      "priority": 2,
      "reason": "Keep verification evidence fresh before release.",
      "command": "charter verify evidence record VERM-0001 --status passing --evidence-ref pytest:tests/test_auth.py::test_expired --actor agent:codex --json",
      "blocked_by": []
    }
  ]
}
```

- [ ] **Step 4: Run the contract test and verify GREEN**

Run:

```bash
uv run pytest tests/contracts/test_contract_fixtures.py::test_required_fixture_plan_files_exist tests/contracts/test_contract_fixtures.py::test_requirement_dossier_fixture_contract -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add tests/contracts/test_contract_fixtures.py tests/fixtures/contracts/dossiers/requirement-dossier.json
git commit -m "test: add requirement dossier contract fixture"
```

### Task 2: Add Service Models and Dossier Computation

**Files:**
- Modify: `src/charter/models.py`
- Modify: `src/charter/service.py`
- Create: `tests/state/test_requirement_dossiers.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/state/test_requirement_dossiers.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from charter.errors import CharterError, ErrorCode
from charter.service import CharterService
from charter.store import migrate


def service_for(tmp_path: Path) -> CharterService:
    db_path = tmp_path / ".charter" / "charter.db"
    migrate(db_path, project_key="AUTH")
    return CharterService(db_path)


def approve_requirement(service: CharterService) -> str:
    draft = service.create_requirement(
        "Reject expired bearer tokens",
        "The API shall reject expired bearer tokens.",
        "human:john",
    )
    service.add_acceptance_criterion(draft.id, "Expired tokens return 401.", actor="human:john")
    service.approve_requirement(
        draft.id,
        actor="human:john",
        expected_version=0,
        idempotency_key="approve-1",
    )
    return draft.id


def gap_codes(dossier: object) -> list[str]:
    return [gap.code for gap in dossier.computed_gaps]  # type: ignore[attr-defined]


def action_names(dossier: object) -> list[str]:
    return [action.action for action in dossier.next_actions]  # type: ignore[attr-defined]


def test_dossier_for_approved_requirement_splits_core_sections(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method = service.add_verification_method(
        requirement_id,
        method="test",
        target="tests/test_auth.py::test_expired",
        actor="human:john",
    )
    evidence = service.record_verification_evidence(
        method.id,
        status="passing",
        evidence_ref="pytest:tests/test_auth.py::test_expired",
        actor="agent:codex",
    )

    dossier = service.requirement_dossier(requirement_id)

    assert dossier.identity["id"] == "REQ-AUTH-0001"
    assert dossier.authority_summary.status == "approved"
    assert dossier.authority_summary.current_approved_version == 1
    assert dossier.authority_summary.has_active_draft is False
    assert dossier.requirement.current_version is not None
    assert dossier.requirement.active_draft is None
    assert [criterion.id for criterion in dossier.acceptance_criteria.current_version] == ["AC-0001"]
    assert dossier.acceptance_criteria.active_draft == []
    assert dossier.verification.status == "satisfied"
    assert [item.id for item in dossier.verification.current_evidence] == [evidence.id]
    assert dossier.peer_facts.live_peer_calls is False


def test_dossier_keeps_active_draft_and_draft_criteria_separate(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    service.edit_requirement(
        requirement_id,
        title="Reject invalid bearer tokens",
        statement="The API shall reject expired or malformed bearer tokens.",
        actor="human:john",
        expected_draft_revision=None,
    )
    service.add_acceptance_criterion(requirement_id, "Malformed tokens return 401.", actor="human:john")

    dossier = service.requirement_dossier(requirement_id)

    assert dossier.authority_summary.has_active_draft is True
    assert dossier.requirement.current_version is not None
    assert dossier.requirement.current_version.title == "Reject expired bearer tokens"
    assert dossier.requirement.active_draft is not None
    assert dossier.requirement.active_draft.title == "Reject invalid bearer tokens"
    assert [criterion.text for criterion in dossier.acceptance_criteria.current_version] == [
        "Expired tokens return 401."
    ]
    assert [criterion.text for criterion in dossier.acceptance_criteria.active_draft] == [
        "Malformed tokens return 401."
    ]
    assert "approve_or_reject_draft" in action_names(dossier)


def test_dossier_groups_traces_by_direction_state_and_relation(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    incoming = service.propose_trace_link(
        from_kind="test_selector",
        from_id="tests/test_auth.py::test_expired",
        relation="provides_evidence_for",
        to_kind="requirement_version",
        to_id="REQ-AUTH-0001@1",
        actor="agent:codex",
        confidence=0.82,
    )
    service.accept_trace_link(incoming.id, actor="human:john")
    service.propose_trace_link(
        from_kind="requirement_version",
        from_id="REQ-AUTH-0001@1",
        relation="depends_on",
        to_kind="requirement_version",
        to_id="REQ-AUTH-0002@1",
        actor="agent:codex",
        confidence=0.6,
    )

    dossier = service.requirement_dossier(requirement_id)

    assert [link.id for link in dossier.traces.incoming] == ["LINK-0001"]
    assert [link.id for link in dossier.traces.outgoing] == ["LINK-0002"]
    assert dossier.traces.by_state == {"accepted": 1, "proposed": 1}
    assert dossier.traces.by_relation == {"depends_on": 1, "provides_evidence_for": 1}
    assert "review_proposed_traces" in action_names(dossier)


def test_dossier_reports_baseline_exposure_and_drift(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    baseline = service.create_baseline(
        "Release 1.0 requirements",
        actor="human:john",
        description="Approved requirements for release 1.0.",
    )
    service.supersede_requirement(
        requirement_id,
        title="Reject invalid bearer tokens",
        statement="The API shall reject expired or malformed bearer tokens.",
        actor="human:john",
        expected_version=1,
        idempotency_key="supersede-1",
    )

    dossier = service.requirement_dossier(requirement_id)

    assert dossier.authority_summary.baseline_count == 1
    assert dossier.baseline_exposure.items[0].baseline_id == baseline.id
    assert dossier.baseline_exposure.items[0].baseline_version == 1
    assert dossier.baseline_exposure.items[0].current_version == 2
    assert dossier.baseline_exposure.items[0].state == "superseded_since_baseline"
    assert dossier.baseline_exposure.summary["superseded_since_baseline"] == 1
    assert "baseline_version_drift" in gap_codes(dossier)


def test_dossier_computes_verification_and_criteria_gaps(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement("Unspecified audit log", "The API shall log token failures.", "human:john")
    service.approve_requirement(
        draft.id,
        actor="human:john",
        expected_version=0,
        idempotency_key="approve-gap",
    )

    dossier = service.requirement_dossier(draft.id)

    assert dossier.verification.status == "unverified"
    assert {"no_acceptance_criteria", "no_verification_method"}.issubset(set(gap_codes(dossier)))
    assert "add_acceptance_criteria" in action_names(dossier)
    assert "add_verification_method" in action_names(dossier)
    assert "do_not_treat_as_satisfied" in action_names(dossier)


def test_dossier_missing_requirement_raises_not_found(tmp_path: Path) -> None:
    service = service_for(tmp_path)

    with pytest.raises(CharterError) as exc_info:
        service.requirement_dossier("REQ-AUTH-9999")

    assert exc_info.value.code == ErrorCode.NOT_FOUND
```

- [ ] **Step 2: Run service tests and verify RED**

Run:

```bash
uv run pytest tests/state/test_requirement_dossiers.py -q
```

Expected: FAIL with `AttributeError: 'CharterService' object has no attribute 'requirement_dossier'`.

- [ ] **Step 3: Add dossier dataclasses**

Append these dataclasses to `src/charter/models.py` after `RequirementVerificationStatus`:

```python
@dataclass(frozen=True)
class DossierAuthoritySummary:
    status: str
    current_approved_version: int | None
    current_statement_hash: str | None
    has_active_draft: bool
    active_draft_id: str | None
    verification_status: str
    baseline_count: int


@dataclass(frozen=True)
class DossierRequirementSection:
    record: RequirementRecord
    current_version: RequirementVersion | None
    active_draft: RequirementDraft | None


@dataclass(frozen=True)
class DossierAcceptanceCriteriaSection:
    current_version: list[AcceptanceCriterion]
    active_draft: list[AcceptanceCriterion]


@dataclass(frozen=True)
class DossierTraceSection:
    incoming: list[TraceLink]
    outgoing: list[TraceLink]
    by_state: dict[str, int]
    by_relation: dict[str, int]
    items: list[TraceLink]


@dataclass(frozen=True)
class DossierBaselineExposureItem:
    baseline_id: str
    name: str
    locked: bool
    created_by: str
    created_at: str
    baseline_version: int
    baseline_statement_hash: str
    current_version: int | None
    current_statement_hash: str | None
    state: str


@dataclass(frozen=True)
class DossierBaselineExposure:
    summary: dict[str, int]
    items: list[DossierBaselineExposureItem]


@dataclass(frozen=True)
class DossierComputedGap:
    code: str
    severity: str
    message: str
    source: str


@dataclass(frozen=True)
class DossierPeerFacts:
    live_peer_calls: bool
    sources: list[str]
    notes: list[str]


@dataclass(frozen=True)
class DossierNextAction:
    action: str
    priority: int
    reason: str
    command: str | None
    blocked_by: list[str]


@dataclass(frozen=True)
class RequirementDossier:
    identity: dict[str, object]
    authority_summary: DossierAuthoritySummary
    requirement: DossierRequirementSection
    acceptance_criteria: DossierAcceptanceCriteriaSection
    traces: DossierTraceSection
    verification: RequirementVerificationStatus
    baseline_exposure: DossierBaselineExposure
    computed_gaps: list[DossierComputedGap]
    peer_facts: DossierPeerFacts
    next_actions: list[DossierNextAction]
```

- [ ] **Step 4: Import the new models in service**

Add these names to the `from charter.models import (` block in `src/charter/service.py`:

```python
    DossierAcceptanceCriteriaSection,
    DossierAuthoritySummary,
    DossierBaselineExposure,
    DossierBaselineExposureItem,
    DossierComputedGap,
    DossierNextAction,
    DossierPeerFacts,
    DossierRequirementSection,
    DossierTraceSection,
    RequirementDossier,
    RequirementDraft,
```

If `RequirementDraft` is already imported, keep one import entry only.

- [ ] **Step 5: Add service helper methods**

Add these private helpers in `src/charter/service.py` near the other requirement read helpers:

```python
    def _active_draft_for_requirement(
        self,
        connection: sqlite3.Connection,
        record: RequirementRecord,
    ) -> RequirementDraft | None:
        if record.active_draft_id is None:
            return None
        row = connection.execute(
            """
            select *
            from requirement_drafts
            where requirement_id = ? and draft_id = ?
            """,
            (record.requirement_id, record.active_draft_id),
        ).fetchone()
        if row is None:
            return None
        return self._draft_from_row(row)

    def _criteria_for_dossier(
        self,
        connection: sqlite3.Connection,
        record: RequirementRecord,
    ) -> DossierAcceptanceCriteriaSection:
        current = []
        if record.current_version > 0:
            current = self._criteria_for_requirement(connection, record.requirement_id, version=record.current_version)
        draft = []
        if record.active_draft_id is not None:
            draft = self._criteria_for_draft(connection, record.requirement_id, record.active_draft_id)
        return DossierAcceptanceCriteriaSection(current_version=current, active_draft=draft)

    def _criteria_for_draft(
        self,
        connection: sqlite3.Connection,
        requirement_id: str,
        draft_id: str,
    ) -> list[AcceptanceCriterion]:
        rows = connection.execute(
            """
            select *
            from acceptance_criteria
            where requirement_id = ? and draft_id = ?
            order by position, criterion_id
            """,
            (requirement_id, draft_id),
        ).fetchall()
        return [self._criterion_from_row(row) for row in rows]

    def _trace_section_for_dossier(self, links: list[TraceLink], requirement_id: str) -> DossierTraceSection:
        incoming = [
            link
            for link in links
            if link.to_ref.id == requirement_id or link.to_ref.id.startswith(f"{requirement_id}@")
        ]
        outgoing = [
            link
            for link in links
            if link.from_ref.id == requirement_id or link.from_ref.id.startswith(f"{requirement_id}@")
        ]
        by_state = self._count_by([link.state for link in links])
        by_relation = self._count_by([link.relation for link in links])
        return DossierTraceSection(
            incoming=incoming,
            outgoing=outgoing,
            by_state=by_state,
            by_relation=by_relation,
            items=links,
        )

    def _count_by(self, values: list[str]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for value in sorted(values):
            counts[value] = counts.get(value, 0) + 1
        return counts
```

- [ ] **Step 6: Add baseline exposure helper**

Add this helper in `src/charter/service.py`:

```python
    def _baseline_exposure_for_dossier(
        self,
        connection: sqlite3.Connection,
        record: RequirementRecord,
    ) -> DossierBaselineExposure:
        rows = connection.execute(
            """
            select b.baseline_id, b.name, b.locked, b.created_by, b.created_at,
                   bm.version, bm.statement_hash
            from baseline_members bm
            join baselines b on b.baseline_id = bm.baseline_id
            where bm.requirement_id = ?
            order by b.baseline_id
            """,
            (record.requirement_id,),
        ).fetchall()
        summary = {
            "current": 0,
            "changed": 0,
            "missing_current": 0,
            "superseded_since_baseline": 0,
        }
        current_version = record.current_version if record.current_version > 0 else None
        current_hash = (
            record.current_version_record.statement_hash if record.current_version_record is not None else None
        )
        items: list[DossierBaselineExposureItem] = []
        for row in rows:
            state = self._baseline_member_state(
                baseline_version=int(row["version"]),
                baseline_hash=str(row["statement_hash"]),
                current_version=current_version,
                current_hash=current_hash,
            )
            summary[state] += 1
            items.append(
                DossierBaselineExposureItem(
                    baseline_id=str(row["baseline_id"]),
                    name=str(row["name"]),
                    locked=bool(row["locked"]),
                    created_by=str(row["created_by"]),
                    created_at=str(row["created_at"]),
                    baseline_version=int(row["version"]),
                    baseline_statement_hash=str(row["statement_hash"]),
                    current_version=current_version,
                    current_statement_hash=current_hash,
                    state=state,
                )
            )
        return DossierBaselineExposure(summary=summary, items=items)

    def _baseline_member_state(
        self,
        *,
        baseline_version: int,
        baseline_hash: str,
        current_version: int | None,
        current_hash: str | None,
    ) -> str:
        if current_version is None:
            return "missing_current"
        if baseline_version != current_version:
            return "superseded_since_baseline"
        if baseline_hash != current_hash:
            return "changed"
        return "current"
```

- [ ] **Step 7: Add computed gap and action helpers**

Add these helpers in `src/charter/service.py`:

```python
    def _computed_gaps_for_dossier(
        self,
        record: RequirementRecord,
        criteria: DossierAcceptanceCriteriaSection,
        traces: DossierTraceSection,
        verification: RequirementVerificationStatus,
        baseline_exposure: DossierBaselineExposure,
    ) -> list[DossierComputedGap]:
        gaps: list[DossierComputedGap] = []
        if record.current_version <= 0:
            gaps.append(self._gap("no_approved_version", "critical", "Requirement has no approved version.", "requirement"))
        if record.active_draft_id is not None:
            gaps.append(
                self._gap(
                    "active_draft_pending_review",
                    "high",
                    "Requirement has an active draft that is not approved.",
                    "requirement",
                )
            )
        if record.current_version > 0 and not criteria.current_version:
            gaps.append(
                self._gap(
                    "no_acceptance_criteria",
                    "high",
                    "Current approved version has no acceptance criteria.",
                    "acceptance_criteria",
                )
            )
        for reason in verification.reasons:
            if reason.code in {"no_verification_method", "failing_evidence", "stale_evidence"}:
                gaps.append(self._gap(reason.code, "high", reason.message, "verification"))
        if any(link.state == "proposed" for link in traces.items):
            gaps.append(
                self._gap("proposed_trace_pending_review", "medium", "One or more trace links await review.", "traces")
            )
        if any(link.state in {"stale", "orphaned"} for link in traces.items):
            gaps.append(
                self._gap(
                    "stale_or_orphaned_trace",
                    "medium",
                    "One or more trace links are stale or orphaned.",
                    "traces",
                )
            )
        if baseline_exposure.summary["changed"] or baseline_exposure.summary["superseded_since_baseline"]:
            gaps.append(
                self._gap(
                    "baseline_version_drift",
                    "medium",
                    "At least one baseline captures a different version or hash.",
                    "baseline_exposure",
                )
            )
        return gaps

    def _gap(self, code: str, severity: str, message: str, source: str) -> DossierComputedGap:
        return DossierComputedGap(code=code, severity=severity, message=message, source=source)

    def _next_actions_for_dossier(
        self,
        record: RequirementRecord,
        gaps: list[DossierComputedGap],
        traces: DossierTraceSection,
        verification: RequirementVerificationStatus,
    ) -> list[DossierNextAction]:
        gap_codes = {gap.code for gap in gaps}
        actions: list[DossierNextAction] = []
        if record.active_draft_id is not None:
            actions.append(
                self._action(
                    "approve_or_reject_draft",
                    1,
                    "Active draft must be reviewed before agents treat it as approved.",
                    f"charter req approve {record.id} --actor human:reviewer --expected-version {record.current_version} --json",
                )
            )
        if "no_acceptance_criteria" in gap_codes:
            actions.append(
                self._action(
                    "add_acceptance_criteria",
                    1,
                    "Current approved version has no acceptance criteria.",
                    f"charter criterion add {record.id} --text \"Expected observable behavior.\" --actor human:reviewer --json",
                )
            )
        if "no_verification_method" in gap_codes:
            actions.append(
                self._action(
                    "add_verification_method",
                    1,
                    "Requirement cannot be satisfied without a verification method.",
                    f"charter verify method add {record.id} --method test --target tests/path.py::test_behavior --actor human:reviewer --json",
                )
            )
        if "failing_evidence" in gap_codes:
            actions.append(
                self._action("investigate_failing_evidence", 1, "Current evidence is failing.", None)
            )
        if "stale_evidence" in gap_codes:
            actions.append(
                self._action("refresh_stale_evidence", 1, "Evidence exists for an older requirement version.", None)
            )
        if verification.status == "waived":
            actions.append(self._action("review_waiver", 2, "Requirement satisfaction depends on a waiver.", None))
        if any(link.state == "proposed" for link in traces.items):
            actions.append(self._action("review_proposed_traces", 2, "Proposed trace links need review.", None))
        if any(link.state in {"stale", "orphaned"} for link in traces.items):
            actions.append(
                self._action("repair_stale_or_orphaned_traces", 2, "Trace links need repair or rejection.", None)
            )
        if verification.status != "satisfied":
            actions.append(
                self._action("do_not_treat_as_satisfied", 1, "Requirement is not currently satisfied.", None)
            )
        if "baseline_version_drift" in gap_codes:
            actions.append(
                self._action(
                    "run_impact_analysis_when_available",
                    3,
                    "Baseline drift exists, but impact analysis is not implemented in this slice.",
                    None,
                    blocked_by=["impact_analysis"],
                )
            )
        return actions

    def _action(
        self,
        action: str,
        priority: int,
        reason: str,
        command: str | None,
        blocked_by: list[str] | None = None,
    ) -> DossierNextAction:
        return DossierNextAction(
            action=action,
            priority=priority,
            reason=reason,
            command=command,
            blocked_by=blocked_by or [],
        )
```

- [ ] **Step 8: Add the public service method**

Add this method near `verification_status` and read-only service methods in `src/charter/service.py`:

```python
    def requirement_dossier(self, requirement_id: str) -> RequirementDossier:
        with connect(self.db_path) as connection:
            record = self._get_requirement(connection, requirement_id)
            active_draft = self._active_draft_for_requirement(connection, record)
            criteria = self._criteria_for_dossier(connection, record)
            links = self.trace_for(requirement_id=record.id)
            traces = self._trace_section_for_dossier(links, record.id)
            verification = self._verification_status_for_row(
                connection,
                self._requirement_row(connection, record.requirement_id),
            )
            baseline_exposure = self._baseline_exposure_for_dossier(connection, record)
            gaps = self._computed_gaps_for_dossier(record, criteria, traces, verification, baseline_exposure)
            current_version = record.current_version_record
            return RequirementDossier(
                identity={
                    "requirement_id": record.requirement_id,
                    "id": record.id,
                    "stable_id": record.stable_id,
                    "current_version": record.current_version,
                },
                authority_summary=DossierAuthoritySummary(
                    status=record.status,
                    current_approved_version=record.current_version if record.current_version > 0 else None,
                    current_statement_hash=current_version.statement_hash if current_version is not None else None,
                    has_active_draft=active_draft is not None,
                    active_draft_id=active_draft.draft_id if active_draft is not None else None,
                    verification_status=verification.status,
                    baseline_count=len(baseline_exposure.items),
                ),
                requirement=DossierRequirementSection(
                    record=record,
                    current_version=current_version,
                    active_draft=active_draft,
                ),
                acceptance_criteria=criteria,
                traces=traces,
                verification=verification,
                baseline_exposure=baseline_exposure,
                computed_gaps=gaps,
                peer_facts=DossierPeerFacts(
                    live_peer_calls=False,
                    sources=[],
                    notes=["Dossier is computed from the local Charter store only."],
                ),
                next_actions=self._next_actions_for_dossier(record, gaps, traces, verification),
            )
```

- [ ] **Step 9: Run service tests and verify GREEN**

Run:

```bash
uv run pytest tests/state/test_requirement_dossiers.py -q
```

Expected: PASS.

- [ ] **Step 10: Run focused state regression tests**

Run:

```bash
uv run pytest tests/state/test_requirement_dossiers.py tests/state/test_baselines.py tests/state/test_verification_status.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit**

Run:

```bash
git add src/charter/models.py src/charter/service.py tests/state/test_requirement_dossiers.py
git commit -m "feat: add requirement dossier service"
```

### Task 3: Add Dossier CLI

**Files:**
- Modify: `src/charter/cli_commands.py`
- Create: `tests/test_cli_dossier.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_cli_dossier.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from charter.cli import main


def json_output(output: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(output))


def run_json(args: list[str], capsys: pytest.CaptureFixture[str], expected_status: int = 0) -> dict[str, Any]:
    assert main([*args, "--json"]) == expected_status
    return json_output(capsys.readouterr().out)


def init_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--project-key", "AUTH", "--json"]) == 0
    capsys.readouterr()


def approve_requirement(capsys: pytest.CaptureFixture[str]) -> None:
    run_json(
        [
            "req",
            "add",
            "--title",
            "Reject expired bearer tokens",
            "--statement",
            "The API shall reject expired bearer tokens.",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    run_json(
        [
            "criterion",
            "add",
            "REQ-AUTH-0001",
            "--text",
            "Expired tokens return 401.",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    run_json(
        [
            "req",
            "approve",
            "REQ-AUTH-0001",
            "--actor",
            "human:john",
            "--expected-version",
            "0",
            "--idempotency-key",
            "approve-dossier",
        ],
        capsys,
    )


def test_dossier_cli_json_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    approve_requirement(capsys)

    output = run_json(["dossier", "REQ-AUTH-0001"], capsys)

    assert output["schema"] == "loom.charter.requirement_dossier.v1"
    assert output["ok"] is True
    assert output["data"]["identity"]["id"] == "REQ-AUTH-0001"
    assert output["data"]["authority_summary"]["status"] == "approved"
    assert output["data"]["acceptance_criteria"]["current_version"][0]["text"] == "Expired tokens return 401."
    assert output["data"]["peer_facts"]["live_peer_calls"] is False


def test_dossier_cli_human_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    approve_requirement(capsys)

    assert main(["dossier", "REQ-AUTH-0001"]) == 0
    output = capsys.readouterr().out

    assert "REQ-AUTH-0001 v1 approved" in output
    assert "Verification: unverified" in output
    assert "Gaps:" in output
    assert "Next actions:" in output


def test_dossier_cli_missing_requirement_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)

    error = run_json(["dossier", "REQ-AUTH-9999"], capsys, expected_status=2)

    assert error["schema"] == "loom.charter.error.v1"
    assert error["error"]["code"] == "NOT_FOUND"
```

- [ ] **Step 2: Run CLI tests and verify RED**

Run:

```bash
uv run pytest tests/test_cli_dossier.py -q
```

Expected: FAIL because the `dossier` command is not registered.

- [ ] **Step 3: Import dossier model names in CLI**

Add these names to the `from charter.models import (` block in `src/charter/cli_commands.py`:

```python
    DossierAcceptanceCriteriaSection,
    DossierAuthoritySummary,
    DossierBaselineExposure,
    DossierBaselineExposureItem,
    DossierComputedGap,
    DossierNextAction,
    DossierPeerFacts,
    DossierRequirementSection,
    DossierTraceSection,
    RequirementDossier,
```

- [ ] **Step 4: Register the top-level dossier command**

In `register_commands`, after the `status` parser block, add:

```python
    dossier_parser = subparsers.add_parser("dossier", help="Show an agent-facing requirement dossier.")
    dossier_parser.add_argument("requirement_id")
    dossier_parser.add_argument("--json", action="store_true")
    dossier_parser.set_defaults(handler=handle_dossier)
```

- [ ] **Step 5: Add the CLI handler**

Add this handler near other `handle_*` functions in `src/charter/cli_commands.py`:

```python
def handle_dossier(args: argparse.Namespace) -> int:
    service = _service()
    dossier = service.requirement_dossier(str(args.requirement_id))
    if bool(args.json):
        print(json.dumps(success_envelope("loom.charter.requirement_dossier.v1", _dossier_dict(dossier))))
        return 0
    print(_dossier_human(dossier))
    return 0
```

- [ ] **Step 6: Add dossier serializers**

Add these serializers near the existing `_requirement_verification_status_dict` helper:

```python
def _authority_summary_dict(summary: DossierAuthoritySummary) -> dict[str, object]:
    return {
        "status": summary.status,
        "current_approved_version": summary.current_approved_version,
        "current_statement_hash": summary.current_statement_hash,
        "has_active_draft": summary.has_active_draft,
        "active_draft_id": summary.active_draft_id,
        "verification_status": summary.verification_status,
        "baseline_count": summary.baseline_count,
    }


def _requirement_section_dict(section: DossierRequirementSection) -> dict[str, object]:
    return {
        "record": _record_dict(section.record),
        "current_version": _version_dict(section.current_version) if section.current_version is not None else None,
        "active_draft": _draft_dict(section.active_draft) if section.active_draft is not None else None,
    }


def _acceptance_criteria_section_dict(section: DossierAcceptanceCriteriaSection) -> dict[str, object]:
    return {
        "current_version": [_criterion_dict(criterion) for criterion in section.current_version],
        "active_draft": [_criterion_dict(criterion) for criterion in section.active_draft],
    }


def _trace_section_dict(section: DossierTraceSection) -> dict[str, object]:
    return {
        "incoming": [_trace_dict(link) for link in section.incoming],
        "outgoing": [_trace_dict(link) for link in section.outgoing],
        "by_state": section.by_state,
        "by_relation": section.by_relation,
        "items": [_trace_dict(link) for link in section.items],
    }


def _baseline_exposure_item_dict(item: DossierBaselineExposureItem) -> dict[str, object]:
    return {
        "baseline_id": item.baseline_id,
        "name": item.name,
        "locked": item.locked,
        "created_by": item.created_by,
        "created_at": item.created_at,
        "baseline_version": item.baseline_version,
        "baseline_statement_hash": item.baseline_statement_hash,
        "current_version": item.current_version,
        "current_statement_hash": item.current_statement_hash,
        "state": item.state,
    }


def _baseline_exposure_dict(exposure: DossierBaselineExposure) -> dict[str, object]:
    return {
        "summary": exposure.summary,
        "items": [_baseline_exposure_item_dict(item) for item in exposure.items],
    }


def _computed_gap_dict(gap: DossierComputedGap) -> dict[str, object]:
    return {
        "code": gap.code,
        "severity": gap.severity,
        "message": gap.message,
        "source": gap.source,
    }


def _peer_facts_dict(peer_facts: DossierPeerFacts) -> dict[str, object]:
    return {
        "live_peer_calls": peer_facts.live_peer_calls,
        "sources": peer_facts.sources,
        "notes": peer_facts.notes,
    }


def _next_action_dict(action: DossierNextAction) -> dict[str, object]:
    return {
        "action": action.action,
        "priority": action.priority,
        "reason": action.reason,
        "command": action.command,
        "blocked_by": action.blocked_by,
    }


def _dossier_dict(dossier: RequirementDossier) -> dict[str, object]:
    return {
        "identity": dossier.identity,
        "authority_summary": _authority_summary_dict(dossier.authority_summary),
        "requirement": _requirement_section_dict(dossier.requirement),
        "acceptance_criteria": _acceptance_criteria_section_dict(dossier.acceptance_criteria),
        "traces": _trace_section_dict(dossier.traces),
        "verification": _requirement_verification_status_dict(dossier.verification),
        "baseline_exposure": _baseline_exposure_dict(dossier.baseline_exposure),
        "computed_gaps": [_computed_gap_dict(gap) for gap in dossier.computed_gaps],
        "peer_facts": _peer_facts_dict(dossier.peer_facts),
        "next_actions": [_next_action_dict(action) for action in dossier.next_actions],
    }
```

- [ ] **Step 7: Add compact human output**

Add this helper near other output helpers:

```python
def _dossier_human(dossier: RequirementDossier) -> str:
    identity = dossier.identity
    lines = [
        f"{identity['id']} v{identity['current_version']} {dossier.authority_summary.status}",
        f"Verification: {dossier.verification.status}",
        f"Baselines: {dossier.authority_summary.baseline_count}",
    ]
    if dossier.requirement.active_draft is not None:
        lines.append(f"Active draft: {dossier.requirement.active_draft.draft_id}")
    if dossier.computed_gaps:
        lines.append("Gaps:")
        lines.extend(f"- {gap.code}: {gap.message}" for gap in dossier.computed_gaps)
    else:
        lines.append("Gaps: none")
    if dossier.next_actions:
        lines.append("Next actions:")
        lines.extend(f"- P{action.priority} {action.action}: {action.reason}" for action in dossier.next_actions)
    else:
        lines.append("Next actions: none")
    return "\n".join(lines)
```

- [ ] **Step 8: Run CLI tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_cli_dossier.py -q
```

Expected: PASS.

- [ ] **Step 9: Run CLI regression tests**

Run:

```bash
uv run pytest tests/test_cli_dossier.py tests/test_cli_baseline.py tests/contracts/test_cli_contract_outputs.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

Run:

```bash
git add src/charter/cli_commands.py tests/test_cli_dossier.py
git commit -m "feat: add requirement dossier CLI"
```

### Task 4: Pin CLI Contract Parity

**Files:**
- Modify: `tests/contracts/test_contract_fixtures.py`
- Modify: `tests/contracts/test_cli_contract_outputs.py`
- Create: `tests/fixtures/contracts/cli/dossier-json.json`

- [ ] **Step 1: Register CLI fixture and write failing parity test**

Add this entry to `REQUIRED_FIXTURES` in `tests/contracts/test_contract_fixtures.py`:

```python
    "cli/dossier-json.json",
```

Add this test to `tests/contracts/test_cli_contract_outputs.py`:

```python
def test_dossier_cli_output_matches_contract_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    init_project(tmp_path, monkeypatch, capsys)
    run_json(
        [
            "req",
            "add",
            "--title",
            "Reject expired bearer tokens",
            "--statement",
            "The API shall reject expired bearer tokens.",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    run_json(
        [
            "criterion",
            "add",
            "REQ-AUTH-0001",
            "--text",
            "Expired tokens return 401.",
            "--actor",
            "human:john",
        ],
        capsys,
    )
    run_json(
        [
            "req",
            "approve",
            "REQ-AUTH-0001",
            "--actor",
            "human:john",
            "--expected-version",
            "0",
            "--idempotency-key",
            "approve-dossier-contract",
        ],
        capsys,
    )

    dossier = run_json(["dossier", "REQ-AUTH-0001"], capsys)
    assert_matches_fixture(dossier, load_fixture("cli/dossier-json.json"))
```

- [ ] **Step 2: Run CLI contract tests and verify RED**

Run:

```bash
uv run pytest tests/contracts/test_cli_contract_outputs.py::test_dossier_cli_output_matches_contract_fixture tests/contracts/test_contract_fixtures.py::test_required_fixture_plan_files_exist -q
```

Expected: FAIL because `tests/fixtures/contracts/cli/dossier-json.json` does not exist.

- [ ] **Step 3: Generate the actual CLI JSON once**

Run:

```bash
tmpdir="$(mktemp -d)"
cd "$tmpdir"
python -m charter.cli init --project-key AUTH --json >/dev/null
python -m charter.cli req add --title "Reject expired bearer tokens" --statement "The API shall reject expired bearer tokens." --actor human:john --json >/dev/null
python -m charter.cli criterion add REQ-AUTH-0001 --text "Expired tokens return 401." --actor human:john --json >/dev/null
python -m charter.cli req approve REQ-AUTH-0001 --actor human:john --expected-version 0 --idempotency-key approve-dossier-contract --json >/dev/null
python -m charter.cli dossier REQ-AUTH-0001 --json
```

Expected: a JSON envelope whose top-level `schema` is `loom.charter.requirement_dossier.v1`.

- [ ] **Step 4: Save and normalize the fixture**

Create `tests/fixtures/contracts/cli/dossier-json.json` from the generated output. Keep real generated IDs and hashes. Replace timestamp values only with stable non-empty strings that match the existing fixture style, because `assert_value_matches` shape-checks `generated_at`, `approved_at`, `created_at`, and `recorded_at`.

The fixture must include:

```json
{
  "schema": "loom.charter.requirement_dossier.v1",
  "ok": true,
  "data": {
    "identity": {
      "requirement_id": "req_auth_0001",
      "id": "REQ-AUTH-0001",
      "stable_id": "charter:req:AUTH:0001",
      "current_version": 1
    }
  },
  "warnings": [],
  "meta": {
    "producer": {"tool": "charter", "version": "0.1.0"},
    "project": "AUTH",
    "generated_at": "2026-06-05T00:00:00Z"
  }
}
```

The saved fixture must include the full `data` object emitted by the command, not only the `identity` fragment shown here.

- [ ] **Step 5: Run CLI contract tests and verify GREEN**

Run:

```bash
uv run pytest tests/contracts/test_cli_contract_outputs.py::test_dossier_cli_output_matches_contract_fixture tests/contracts/test_contract_fixtures.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add tests/contracts/test_contract_fixtures.py tests/contracts/test_cli_contract_outputs.py tests/fixtures/contracts/cli/dossier-json.json
git commit -m "test: pin dossier CLI contract"
```

### Task 5: Review, Gates, and Roadmap Update

**Files:**
- Modify: `docs/agentic-doors-replacement-roadmap.md`

- [ ] **Step 1: Run the focused dossier test set**

Run:

```bash
uv run pytest tests/contracts/test_contract_fixtures.py -q
uv run pytest tests/contracts/test_cli_contract_outputs.py -q
uv run pytest tests/state/test_requirement_dossiers.py -q
uv run pytest tests/test_cli_dossier.py -q
```

Expected: all commands PASS.

- [ ] **Step 2: Run full gates**

Run:

```bash
make lint
make typecheck
make test
uv run pytest tests/contracts -q
uv run pytest tests/state -q
make ci
```

Expected: all commands PASS.

- [ ] **Step 3: Run scope audit**

Run:

```bash
rg -n "impact|clarion|filigree|wardline|legis|mcp" src tests
```

Expected: no new live peer integrations, no MCP server code, and only allowed hits in inert contract text, fixtures, tests, help text, or explicit deferred markers.

- [ ] **Step 4: Perform implementation review**

Review the diff manually with this checklist:

```text
- No migration or new SQLite table was added.
- No external peer command, network call, MCP call, or subprocess call was added.
- Approved current requirement and active draft are serialized separately.
- Current-version criteria and active-draft criteria are serialized separately.
- Trace state, authority, freshness, confidence, and target_snapshot are preserved.
- Verification status reuses existing status semantics and preserves stale evidence.
- Computed gaps are not persisted.
- Next actions are deterministic objects, not prose-only advice.
- JSON keys match tests/fixtures/contracts/dossiers/requirement-dossier.json.
```

If any item fails, fix the code and rerun the focused tests plus the relevant full gate before continuing.

- [ ] **Step 5: Update roadmap**

Edit `docs/agentic-doors-replacement-roadmap.md`:

- Move "Requirement dossiers" from remaining work to installed local capability.
- Mark the installed command as `charter dossier REQ_ID --json`.
- State that dossiers are computed local read models with no new storage.
- Keep "read-only MCP wrapper for dossiers" as the next sequencing item before P1 durable gaps and impact analysis.
- Keep "MCP mutation" deferred until after P1 review policy and gap lifecycle work.

- [ ] **Step 6: Commit roadmap update**

Run:

```bash
git add docs/agentic-doors-replacement-roadmap.md
git commit -m "docs: update dossier roadmap status"
```

- [ ] **Step 7: Final verification**

Run:

```bash
git status --short --branch
git log --oneline -5
```

Expected: branch is `codex/requirement-dossiers`, worktree is clean, and the last commits are the dossier contract, service, CLI, CLI contract, and roadmap commits.

## Execution Notes

- Keep the branch based on `main`.
- Use TDD for each task: RED, GREEN, regression test, commit.
- Do not merge to `main` until all gates pass and the review checklist is clean.
- Do not create Filigree work unless the user asks for tracker updates for this slice.
- Preserve exact authority boundaries. Draft facts can guide agents, but approved facts drive release readiness.
