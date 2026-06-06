from __future__ import annotations

from pathlib import Path

import pytest

from charter.errors import CharterError, ErrorCode
from charter.service import CharterService
from charter.store import connect, migrate


def service_for(tmp_path: Path) -> CharterService:
    db_path = tmp_path / ".charter" / "charter.db"
    migrate(db_path, project_key="AUTH")
    return CharterService(db_path)


def approve_requirement(service: CharterService, title: str = "Reject expired bearer tokens") -> str:
    draft = service.create_requirement(title, "The API shall reject expired bearer tokens.", "human:john")
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key=f"approve-{draft.id}")
    return draft.id


def manual_method(service: CharterService, requirement_id: str) -> str:
    method = service.add_verification_method(
        requirement_id,
        method="manual",
        target="manual:operator-attestation",
        actor="human:john",
    )
    return method.id


def analysis_method(service: CharterService, requirement_id: str) -> str:
    method = service.add_verification_method(
        requirement_id,
        method="analysis",
        target="analysis:static-review",
        actor="human:john",
    )
    return method.id


def event_types(service: CharterService) -> list[str]:
    with connect(service.db_path) as connection:
        rows = connection.execute("select event_type from events order by created_at, event_id").fetchall()
    return [str(row["event_type"]) for row in rows]


# --- The spoofing holes (D1): authority must derive from the registry, not a string prefix ---


def test_unregistered_human_prefix_cannot_record_waiver(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method_id = manual_method(service, requirement_id)

    with pytest.raises(CharterError) as exc:
        service.record_verification_evidence(
            method_id,
            status="waived",
            evidence_ref="waiver:spoofed",
            actor="human:fake",
        )
    assert exc.value.code == ErrorCode.POLICY_REQUIRED


def test_unregistered_human_prefix_cannot_mint_human_attested(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method_id = analysis_method(service, requirement_id)

    evidence = service.record_verification_evidence(
        method_id,
        status="passing",
        evidence_ref="analysis:spoofed",
        actor="human:fake",
    )
    assert evidence.authority == "agent_reported"


def test_unregistered_human_prefix_cannot_manual_attest(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method_id = manual_method(service, requirement_id)

    with pytest.raises(CharterError) as exc:
        service.record_verification_evidence(
            method_id,
            status="passing",
            evidence_ref="manual:spoofed",
            actor="human:fake",
        )
    assert exc.value.code == ErrorCode.POLICY_REQUIRED


def test_bare_actor_cannot_record_waiver(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method_id = manual_method(service, requirement_id)

    with pytest.raises(CharterError) as exc:
        service.record_verification_evidence(
            method_id,
            status="waived",
            evidence_ref="waiver:bare",
            actor="codex",
        )
    assert exc.value.code == ErrorCode.POLICY_REQUIRED


def test_bare_actor_cannot_manual_attest(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method_id = manual_method(service, requirement_id)

    with pytest.raises(CharterError) as exc:
        service.record_verification_evidence(
            method_id,
            status="passing",
            evidence_ref="manual:bare",
            actor="codex",
        )
    assert exc.value.code == ErrorCode.POLICY_REQUIRED


# --- The legitimate human path still works once the actor is registered ---


def test_registered_human_records_waiver(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method_id = manual_method(service, requirement_id)
    service.register_actor("human:john", kind="human", actor="human:john")

    evidence = service.record_verification_evidence(
        method_id,
        status="waived",
        evidence_ref="waiver:release-manager:2026-06-05",
        actor="human:john",
    )
    assert evidence.authority == "waiver"
    assert service.verification_status(requirement_id).status == "waived"


def test_registered_human_mints_human_attested(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method_id = analysis_method(service, requirement_id)
    service.register_actor("human:john", kind="human", actor="human:john")

    evidence = service.record_verification_evidence(
        method_id,
        status="passing",
        evidence_ref="analysis:operator",
        actor="human:john",
    )
    assert evidence.authority == "human_attested"


def test_registered_attester_kind_may_attest(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method_id = manual_method(service, requirement_id)
    service.register_actor("release-manager", kind="attester", display_name="Release Manager", actor="human:john")

    evidence = service.record_verification_evidence(
        method_id,
        status="waived",
        evidence_ref="waiver:release-manager",
        actor="release-manager",
    )
    assert evidence.authority == "waiver"


def test_registered_agent_cannot_attest(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method_id = manual_method(service, requirement_id)
    service.register_actor("agent:codex", kind="agent", actor="human:john")

    with pytest.raises(CharterError) as exc:
        service.record_verification_evidence(
            method_id,
            status="waived",
            evidence_ref="waiver:agent",
            actor="agent:codex",
        )
    assert exc.value.code == ErrorCode.POLICY_REQUIRED


# --- Registration mechanics ---


def test_register_actor_persists_and_logs_event(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    actor = service.register_actor("human:john", kind="human", display_name="John", actor="human:john")

    assert actor.actor_id == "human:john"
    assert actor.kind == "human"
    assert actor.display_name == "John"
    with connect(service.db_path) as connection:
        row = connection.execute(
            "select kind, display_name from actors where actor_id = ?", ("human:john",)
        ).fetchone()
    assert row is not None
    assert str(row["kind"]) == "human"
    assert "actor_registered" in event_types(service)


def test_register_actor_rejects_unknown_kind(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    with pytest.raises(CharterError) as exc:
        service.register_actor("human:john", kind="robot", actor="human:john")
    assert exc.value.code == ErrorCode.VALIDATION


def test_register_actor_requires_actor_id(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    with pytest.raises(CharterError) as exc:
        service.register_actor("", kind="human", actor="human:john")
    assert exc.value.code == ErrorCode.VALIDATION


# --- Genesis-gated registration: the CLI must not mint attester authority in one hop ---


def test_first_attester_registration_is_open_genesis(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    # Empty registry: the first human/attester may be registered by anyone (bootstrap).
    actor = service.register_actor("human:john", kind="human", actor="human:john")
    assert actor.kind == "human"


def test_agent_cannot_register_attester_after_genesis(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.register_actor("human:john", kind="human", actor="human:john")  # genesis attester exists

    with pytest.raises(CharterError) as exc:
        service.register_actor("human:fake", kind="human", actor="agent:codex")
    assert exc.value.code == ErrorCode.POLICY_REQUIRED


def test_registered_attester_can_register_another_attester(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.register_actor("human:john", kind="human", actor="human:john")  # genesis

    jane = service.register_actor("human:jane", kind="attester", actor="human:john")
    assert jane.kind == "attester"


def test_agent_kind_registration_stays_open(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.register_actor("human:john", kind="human", actor="human:john")  # attester exists

    # Registering a least-privileged agent is not a privilege grant: stays open.
    agent = service.register_actor("agent:codex", kind="agent", actor="agent:orchestrator")
    assert agent.kind == "agent"


def test_agent_cannot_self_upgrade_to_attester(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.register_actor("human:john", kind="human", actor="human:john")  # genesis
    service.register_actor("agent:codex", kind="agent", actor="human:john")

    with pytest.raises(CharterError) as exc:
        service.register_actor("agent:codex", kind="human", actor="agent:codex")
    assert exc.value.code == ErrorCode.POLICY_REQUIRED


def test_agent_cannot_downgrade_existing_attester(tmp_path: Path) -> None:
    # Re-registering an existing attester (even to a non-privileged kind) is a
    # privileged operation: an agent must not be able to neuter an attester.
    service = service_for(tmp_path)
    service.register_actor("human:john", kind="human", actor="human:john")  # genesis

    with pytest.raises(CharterError) as exc:
        service.register_actor("human:john", kind="agent", actor="agent:codex")
    assert exc.value.code == ErrorCode.POLICY_REQUIRED


def test_attester_may_re_register_an_existing_attester(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.register_actor("human:john", kind="human", actor="human:john")  # genesis

    updated = service.register_actor(
        "human:john", kind="human", display_name="John Q.", actor="human:john"
    )
    assert updated.display_name == "John Q."


def test_agent_cannot_fabricate_waiver_via_registration(tmp_path: Path) -> None:
    # The P1 DoD, asserted directly: once a real attester exists, an agent using
    # only the service API cannot obtain waiver authority — not even by trying to
    # register a fake human first.
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    method_id = manual_method(service, requirement_id)
    service.register_actor("human:john", kind="human", actor="human:john")  # genesis attester

    with pytest.raises(CharterError) as register_exc:
        service.register_actor("human:fake", kind="human", actor="agent:codex")
    assert register_exc.value.code == ErrorCode.POLICY_REQUIRED

    with pytest.raises(CharterError) as waive_exc:
        service.record_verification_evidence(
            method_id,
            status="waived",
            evidence_ref="waiver:fabricated",
            actor="agent:codex",
        )
    assert waive_exc.value.code == ErrorCode.POLICY_REQUIRED
