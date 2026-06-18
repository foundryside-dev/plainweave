from __future__ import annotations

from pathlib import Path

import pytest

from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.service import PlainweaveService
from plainweave.store import connect, migrate


def service_for(tmp_path: Path) -> PlainweaveService:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")
    return PlainweaveService(db_path)


def approve_requirement(service: PlainweaveService, title: str = "Reject expired bearer tokens") -> str:
    draft = service.create_requirement(title, "The API shall reject expired bearer tokens.", "human:john")
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key=f"approve-{draft.id}")
    return draft.id


def event_types(service: PlainweaveService) -> list[str]:
    with connect(service.db_path) as connection:
        rows = connection.execute("select event_type from events order by created_at, event_id").fetchall()
    return [str(row["event_type"]) for row in rows]


def reason_codes(status: object) -> list[str]:
    return [reason.code for reason in status.reasons]  # type: ignore[attr-defined]


def test_approved_requirement_without_evidence_is_unverified(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)

    status = service.verification_status(requirement_id)

    assert status.id == requirement_id
    assert status.current_version == 1
    assert status.status == "unverified"
    assert reason_codes(status) == ["no_verification_method"]
    assert status.current_evidence == []
    assert status.stale_evidence == []


def test_add_method_requires_approved_requirement(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement("Draft only", "This requirement is not approved.", "human:john")

    with pytest.raises(PlainweaveError) as exc_info:
        service.add_verification_method(
            draft.id,
            method="test",
            target="tests/test_auth.py::test_expired",
            actor="human:john",
        )

    assert exc_info.value.code == ErrorCode.POLICY_REQUIRED


def test_passing_test_evidence_satisfies_current_version(tmp_path: Path) -> None:
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
        payload={"runner": "pytest", "exit_code": 0},
    )
    verification = service.verification_status(requirement_id)

    assert method.id == "VERM-0001"
    assert evidence.id == "EVID-0001"
    assert evidence.requirement_version == 1
    assert evidence.authority == "test_derived"
    assert verification.status == "satisfied"
    assert reason_codes(verification) == ["passing_evidence"]
    assert [item.id for item in verification.current_evidence] == [evidence.id]
    assert "verification_method_added" in event_types(service)
    assert "verification_evidence_recorded" in event_types(service)


def test_failing_evidence_makes_requirement_unsatisfied(tmp_path: Path) -> None:
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

    status = service.verification_status(requirement_id)
    assert status.status == "unsatisfied"
    assert reason_codes(status) == ["failing_evidence"]


def test_supersede_makes_prior_evidence_stale(tmp_path: Path) -> None:
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

    service.supersede_requirement(
        requirement_id,
        title="Reject invalid bearer tokens",
        statement="The API shall reject expired or malformed bearer tokens.",
        actor="human:john",
        expected_version=1,
        idempotency_key="supersede-1",
    )
    status = service.verification_status(requirement_id)

    assert status.current_version == 2
    assert status.status == "stale"
    assert reason_codes(status) == ["stale_evidence"]
    assert status.current_evidence == []
    assert [item.id for item in status.stale_evidence] == [evidence.id]
    assert status.stale_evidence[0].freshness == "stale"


def test_human_waiver_is_distinct_status(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method = service.add_verification_method(
        requirement_id,
        method="manual",
        target="waiver:release-manager",
        actor="human:john",
    )
    service.register_actor("human:john", kind="human", actor="human:john")

    evidence = service.record_verification_evidence(
        method.id,
        status="waived",
        evidence_ref="waiver:release-manager:2026-06-05",
        actor="human:john",
    )
    status = service.verification_status(requirement_id)

    assert evidence.authority == "waiver"
    assert status.status == "waived"
    assert reason_codes(status) == ["human_waiver"]


def test_agent_cannot_record_manual_or_waiver_attestation(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    manual = service.add_verification_method(
        requirement_id,
        method="manual",
        target="manual:operator-attestation",
        actor="human:john",
    )
    test_method = service.add_verification_method(
        requirement_id,
        method="test",
        target="tests/test_auth.py::test_expired",
        actor="human:john",
    )

    with pytest.raises(PlainweaveError) as manual_exc:
        service.record_verification_evidence(
            manual.id,
            status="passing",
            evidence_ref="manual:agent-claim",
            actor="agent:codex",
        )
    with pytest.raises(PlainweaveError) as waiver_exc:
        service.record_verification_evidence(
            test_method.id,
            status="waived",
            evidence_ref="waiver:agent-claim",
            actor="agent:codex",
        )

    assert manual_exc.value.code == ErrorCode.POLICY_REQUIRED
    assert waiver_exc.value.code == ErrorCode.POLICY_REQUIRED


def test_status_lists_unverified_and_stale_requirements(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    unverified_id = approve_requirement(service, "Unverified requirement")
    stale_id = approve_requirement(service, "Stale requirement")
    method = service.add_verification_method(
        stale_id,
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
        stale_id,
        title="Stale requirement updated",
        statement="The API shall reject expired or malformed bearer tokens.",
        actor="human:john",
        expected_version=1,
        idempotency_key="supersede-1",
    )

    assert [item.id for item in service.list_unverified_requirements()] == [unverified_id]
    assert [item.id for item in service.list_stale_requirements()] == [stale_id]
