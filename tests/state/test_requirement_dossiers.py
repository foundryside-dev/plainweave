from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Protocol

import pytest

from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.models import DossierNextAction, TraceRef
from plainweave.service import PlainweaveService
from plainweave.store import connect, migrate


def service_for(tmp_path: Path) -> PlainweaveService:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")
    return PlainweaveService(db_path)


def approve_requirement(
    service: PlainweaveService,
    *,
    title: str = "Reject expired bearer tokens",
    statement: str = "The API shall reject expired bearer tokens.",
    criterion: str | None = "Expired tokens return 401.",
    key: str = "approve-1",
) -> str:
    draft = service.create_requirement(title, statement, "human:john")
    if criterion is not None:
        service.add_acceptance_criterion(draft.id, criterion, actor="human:john")
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key=key)
    return draft.id


def open_draft(service: PlainweaveService, requirement_id: str) -> str:
    with connect(service.db_path) as connection:
        requirement = connection.execute(
            "select requirement_id, current_version from requirements where display_id = ?",
            (requirement_id,),
        ).fetchone()
        draft_id = "DRAFT-9999"
        connection.execute(
            """
            insert into requirement_drafts(
              draft_id, requirement_id, base_version, title, statement,
              draft_revision, created_by, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                draft_id,
                requirement["requirement_id"],
                requirement["current_version"],
                "Reject expired or malformed bearer tokens",
                "The API shall reject expired or malformed bearer tokens.",
                1,
                "human:john",
                "2026-06-05T00:00:00+00:00",
                "2026-06-05T00:00:00+00:00",
            ),
        )
        connection.execute(
            "update requirements set active_draft_id = ? where requirement_id = ?",
            (draft_id, requirement["requirement_id"]),
        )
        connection.commit()
    return draft_id


class HasCode(Protocol):
    @property
    def code(self) -> str: ...


class HasAction(Protocol):
    @property
    def action(self) -> str: ...


def codes(items: Iterable[HasCode]) -> list[str]:
    return [item.code for item in items]


def actions(items: Iterable[HasAction]) -> list[str]:
    return [item.action for item in items]


def action_by(items: Sequence[DossierNextAction], action: str) -> DossierNextAction:
    return next(item for item in items if item.action == action)


def test_approved_requirement_dossier_includes_identity_authority_current_sections_and_verification(
    tmp_path: Path,
) -> None:
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

    assert dossier.identity == {
        "requirement_id": "req-1",
        "id": requirement_id,
        "stable_id": "plainweave:req:AUTH:0001",
        "current_version": 1,
    }
    assert dossier.authority_summary.status == "approved"
    assert dossier.authority_summary.current_approved_version == 1
    current_version = dossier.requirement.current_version
    assert current_version is not None
    assert dossier.authority_summary.current_statement_hash == current_version.statement_hash
    assert dossier.authority_summary.has_active_draft is False
    assert dossier.authority_summary.active_draft_id is None
    assert dossier.authority_summary.verification_status == "satisfied"
    assert dossier.authority_summary.baseline_count == 0
    assert dossier.requirement.record.id == requirement_id
    assert current_version.version == 1
    assert dossier.requirement.active_draft is None
    assert [item.text for item in dossier.acceptance_criteria.current_version] == ["Expired tokens return 401."]
    assert dossier.acceptance_criteria.active_draft == []
    assert dossier.verification.status == "satisfied"
    assert codes(dossier.verification.reasons) == ["passing_evidence"]
    assert [item.id for item in dossier.verification.current_evidence] == [evidence.id]
    assert dossier.peer_facts.live_peer_calls is False
    assert dossier.peer_facts.sources == []
    assert dossier.peer_facts.notes == ["Dossier is computed from the local Plainweave store only."]


def test_active_draft_and_draft_criteria_remain_separate_from_approved_current_sections(
    tmp_path: Path,
) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service, criterion="Expired tokens return 401.")
    open_draft(service, requirement_id)
    draft_criterion = service.add_acceptance_criterion(
        requirement_id,
        "Malformed tokens return 401.",
        actor="human:john",
    )

    dossier = service.requirement_dossier(requirement_id)

    assert dossier.requirement.current_version is not None
    assert dossier.requirement.current_version.title == "Reject expired bearer tokens"
    assert dossier.requirement.active_draft is not None
    assert dossier.requirement.active_draft.title == "Reject expired or malformed bearer tokens"
    assert [item.text for item in dossier.acceptance_criteria.current_version] == ["Expired tokens return 401."]
    assert dossier.acceptance_criteria.active_draft == [draft_criterion]
    assert dossier.authority_summary.has_active_draft is True
    assert dossier.authority_summary.active_draft_id == "DRAFT-9999"
    assert "active_draft_pending_review" in codes(dossier.computed_gaps)
    assert "approve_or_reject_draft" in actions(dossier.next_actions)
    assert (
        action_by(dossier.next_actions, "approve_or_reject_draft").command
        == f"plainweave req approve {requirement_id} --actor human:reviewer --expected-version 1 --json"
    )


def test_traces_are_grouped_by_direction_state_and_relation_while_preserving_states(
    tmp_path: Path,
) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    accepted = service.create_trace_link(
        TraceRef("file_ref", "src/auth.py"),
        "fragile_satisfies",
        TraceRef("requirement_version", f"{requirement_id}@1"),
        actor="human:john",
        authority="accepted",
    )
    proposed = service.propose_trace_link(
        TraceRef("loomweave_entity", "sei:token-validator"),
        "satisfies",
        TraceRef("requirement_version", f"{requirement_id}@1"),
        actor="agent:codex",
        confidence=0.81,
    )
    stale = service.create_trace_link(
        TraceRef("file_ref", "src/legacy_auth.py"),
        "fragile_satisfies",
        TraceRef("requirement_version", f"{requirement_id}@1"),
        actor="human:john",
        authority="accepted",
    )
    stale = service.mark_trace_stale(stale.id, actor="agent:codex", reason="content changed")
    outgoing = service.propose_trace_link(
        TraceRef("filigree_issue", requirement_id),
        "resolves_gap",
        TraceRef("gap", "GAP-0001"),
        actor="agent:codex",
    )

    dossier = service.requirement_dossier(requirement_id)

    assert [item.id for item in dossier.traces.incoming] == [accepted.id, proposed.id, stale.id]
    assert [item.id for item in dossier.traces.outgoing] == [outgoing.id]
    assert dossier.traces.by_state == {"accepted": 1, "proposed": 2, "stale": 1}
    assert dossier.traces.by_relation == {"fragile_satisfies": 2, "resolves_gap": 1, "satisfies": 1}
    assert [item.id for item in dossier.traces.items] == [accepted.id, proposed.id, stale.id, outgoing.id]
    assert [item.state for item in dossier.traces.incoming] == ["accepted", "proposed", "stale"]
    assert "proposed_trace_pending_review" in codes(dossier.computed_gaps)
    assert "stale_or_orphaned_trace" in codes(dossier.computed_gaps)
    assert "review_proposed_traces" in actions(dossier.next_actions)
    assert "repair_stale_or_orphaned_traces" in actions(dossier.next_actions)


def test_traces_include_links_attached_to_requirement_owned_verification_methods(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method = service.add_verification_method(
        requirement_id,
        method="test",
        target="tests/test_auth.py::test_expired",
        actor="human:john",
    )
    link = service.create_trace_link(
        TraceRef("test_selector", "tests/test_auth.py::test_expired"),
        "provides_evidence_for",
        TraceRef("verification_method", method.id),
        actor="human:john",
        authority="accepted",
    )

    dossier = service.requirement_dossier(requirement_id)

    assert [item.id for item in dossier.traces.items] == [link.id]
    assert [item.id for item in dossier.traces.incoming] == [link.id]
    assert dossier.traces.outgoing == []
    assert dossier.traces.by_state == {"accepted": 1}
    assert dossier.traces.by_relation == {"provides_evidence_for": 1}


def test_version_like_non_requirement_endpoint_does_not_make_trace_requirement_owned(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    first_id = approve_requirement(service, key="approve-1")
    second_id = approve_requirement(
        service,
        title="Log token failures",
        statement="The API shall log token validation failures.",
        criterion="Token failures are logged.",
        key="approve-2",
    )
    link = service.create_trace_link(
        TraceRef("file_ref", f"{first_id}@fixture"),
        "fragile_satisfies",
        TraceRef("requirement_version", f"{second_id}@1"),
        actor="human:john",
        authority="accepted",
    )

    first_dossier = service.requirement_dossier(first_id)
    second_dossier = service.requirement_dossier(second_id)

    assert link.id not in [item.id for item in first_dossier.traces.items]
    assert link.id not in [item.id for item in first_dossier.traces.outgoing]
    assert [item.id for item in second_dossier.traces.incoming] == [link.id]


def test_baseline_exposure_shows_containing_baseline_and_superseded_since_baseline(
    tmp_path: Path,
) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    baseline = service.create_baseline("Release 1.0 requirements", actor="human:john")

    service.supersede_requirement(
        requirement_id,
        title="Reject invalid bearer tokens",
        statement="The API shall reject expired or malformed bearer tokens.",
        actor="human:john",
        expected_version=1,
        idempotency_key="supersede-1",
    )
    dossier = service.requirement_dossier(requirement_id)

    assert dossier.baseline_exposure.summary == {
        "current": 0,
        "changed": 0,
        "missing_current": 0,
        "superseded_since_baseline": 1,
    }
    assert len(dossier.baseline_exposure.items) == 1
    item = dossier.baseline_exposure.items[0]
    assert item.baseline_id == baseline.id
    assert item.name == baseline.name
    assert item.locked is True
    assert item.baseline_version == 1
    assert item.current_version == 2
    assert item.state == "superseded_since_baseline"
    assert item.baseline_statement_hash != item.current_statement_hash
    assert "baseline_version_drift" in codes(dossier.computed_gaps)
    assert "run_impact_analysis_when_available" in actions(dossier.next_actions)


def test_gaps_and_next_actions_include_missing_criteria_method_and_do_not_treat_as_satisfied(
    tmp_path: Path,
) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service, criterion=None)

    dossier = service.requirement_dossier(requirement_id)

    assert codes(dossier.computed_gaps) == ["no_acceptance_criteria", "no_verification_method"]
    assert actions(dossier.next_actions) == [
        "add_acceptance_criteria",
        "add_verification_method",
        "do_not_treat_as_satisfied",
    ]
    assert action_by(dossier.next_actions, "add_acceptance_criteria").command is None
    assert (
        action_by(dossier.next_actions, "add_verification_method").command
        == f"plainweave verify method add {requirement_id} --method test --target tests/path.py::test_behavior "
        "--actor human:reviewer --json"
    )
    assert dossier.next_actions[-1].command is None
    assert dossier.next_actions[-1].blocked_by == ["no_acceptance_criteria", "no_verification_method"]


def test_method_without_current_evidence_emits_gap_and_record_current_evidence_action(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    service.add_verification_method(
        requirement_id,
        method="test",
        target="tests/test_auth.py::test_expired",
        actor="human:john",
    )

    dossier = service.requirement_dossier(requirement_id)

    assert codes(dossier.verification.reasons) == ["no_current_evidence"]
    assert "no_current_evidence" in codes(dossier.computed_gaps)
    assert "record_current_evidence" in actions(dossier.next_actions)
    assert action_by(dossier.next_actions, "record_current_evidence").command is None


def test_draft_only_requirement_dossier_reports_no_approved_version_without_peer_calls(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement("Draft only", "This requirement is not approved.", "human:john")

    dossier = service.requirement_dossier(draft.id)

    assert dossier.identity["current_version"] == 0
    assert dossier.requirement.current_version is None
    assert dossier.verification.status == "unknown"
    assert codes(dossier.verification.reasons) == ["requirement_not_approved"]
    assert codes(dossier.computed_gaps) == ["no_approved_version", "active_draft_pending_review"]
    assert dossier.peer_facts.live_peer_calls is False
    assert dossier.peer_facts.sources == []
    assert actions(dossier.next_actions) == ["approve_or_reject_draft"]
    assert (
        action_by(dossier.next_actions, "approve_or_reject_draft").command
        == f"plainweave req approve {draft.id} --actor human:reviewer --expected-version 0 --json"
    )


def test_current_failing_evidence_emits_gap_and_investigation_action(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method = service.add_verification_method(
        requirement_id,
        method="test",
        target="tests/test_auth.py::test_expired",
        actor="human:john",
    )
    service.record_verification_evidence(
        method.id,
        status="failing",
        evidence_ref="pytest:tests/test_auth.py::test_expired",
        actor="agent:codex",
    )

    dossier = service.requirement_dossier(requirement_id)

    assert dossier.verification.status == "unsatisfied"
    assert codes(dossier.verification.reasons) == ["failing_evidence"]
    assert "failing_evidence" in codes(dossier.computed_gaps)
    assert "investigate_failing_evidence" in actions(dossier.next_actions)


def test_stale_evidence_after_supersede_emits_gap_and_refresh_action(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method = service.add_verification_method(
        requirement_id,
        method="test",
        target="tests/test_auth.py::test_expired",
        actor="human:john",
    )
    service.record_verification_evidence(
        method.id,
        status="passing",
        evidence_ref="pytest:tests/test_auth.py::test_expired",
        actor="agent:codex",
    )
    service.supersede_requirement(
        requirement_id,
        title="Reject invalid bearer tokens",
        statement="The API shall reject expired or malformed bearer tokens.",
        actor="human:john",
        expected_version=1,
        idempotency_key="supersede-for-stale-evidence",
    )

    dossier = service.requirement_dossier(requirement_id)

    assert dossier.verification.status == "stale"
    assert codes(dossier.verification.reasons) == ["stale_evidence"]
    assert "stale_evidence" in codes(dossier.computed_gaps)
    assert "refresh_stale_evidence" in actions(dossier.next_actions)


def test_current_waiver_evidence_emits_review_waiver_action(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method = service.add_verification_method(
        requirement_id,
        method="manual",
        target="waiver:release-manager",
        actor="human:john",
    )
    service.register_actor("human:john", kind="human", actor="human:john")
    service.record_verification_evidence(
        method.id,
        status="waived",
        evidence_ref="waiver:release-manager:2026-06-05",
        actor="human:john",
    )

    dossier = service.requirement_dossier(requirement_id)

    assert dossier.verification.status == "waived"
    assert codes(dossier.verification.reasons) == ["human_waiver"]
    assert "review_waiver" in actions(dossier.next_actions)


def test_missing_requirement_raises_not_found(tmp_path: Path) -> None:
    service = service_for(tmp_path)

    with pytest.raises(PlainweaveError) as exc_info:
        service.requirement_dossier("REQ-AUTH-9999")

    assert exc_info.value.code == ErrorCode.NOT_FOUND
