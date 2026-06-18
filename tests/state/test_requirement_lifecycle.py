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


def event_count(service: PlainweaveService) -> int:
    with connect(service.db_path) as connection:
        return int(connection.execute("select count(*) from events").fetchone()[0])


def test_create_requirement_creates_mutable_draft_and_event(tmp_path: Path) -> None:
    service = service_for(tmp_path)

    draft = service.create_requirement(
        title="Reject expired bearer tokens",
        statement="The API shall reject expired bearer tokens.",
        actor="human:john",
    )

    assert draft.id == "REQ-AUTH-0001"
    assert draft.stable_id == "plainweave:req:AUTH:0001"
    assert draft.draft_id == "DRAFT-0001"
    assert draft.status == "draft"
    assert draft.draft_revision == 1
    assert event_count(service) == 1


def test_approve_requirement_creates_immutable_version(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )

    version = service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")

    assert version.id == draft.id
    assert version.version == 1
    assert version.status == "approved"
    assert version.statement_hash.startswith("sha256:")
    assert version.approved_by == "human:john"
    assert event_count(service) == 2

    with (
        connect(service.db_path) as connection,
        pytest.raises(Exception, match="requirement version text is immutable"),
    ):
        connection.execute(
            """
            update requirement_versions
            set statement = ?, statement_hash = ?
            where requirement_id = ? and version = ?
            """,
            ("Changed.", "sha256:new", version.requirement_id, 1),
        )


def test_repeated_approval_with_same_idempotency_key_returns_original_version(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )

    first = service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")
    second = service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")

    assert second == first
    assert event_count(service) == 2


def test_approval_same_idempotency_key_with_different_expected_version_conflicts(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")

    with pytest.raises(PlainweaveError) as exc_info:
        service.approve_requirement(draft.id, actor="human:john", expected_version=1, idempotency_key="approve-1")

    assert exc_info.value.code == ErrorCode.CONFLICT


def test_same_idempotency_key_cannot_replay_across_operations(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="same")

    with pytest.raises(PlainweaveError) as exc_info:
        service.supersede_requirement(
            draft.id,
            title="Reject invalid bearer tokens",
            statement="The API shall reject expired or malformed bearer tokens.",
            actor="human:john",
            expected_version=1,
            idempotency_key="same",
        )

    assert exc_info.value.code == ErrorCode.CONFLICT


def test_same_idempotency_key_cannot_replay_across_requirements(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    first = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )
    second = service.create_requirement(
        "Log token failures", "The API shall log token validation failures.", "human:john"
    )
    service.approve_requirement(first.id, actor="human:john", expected_version=0, idempotency_key="same")

    with pytest.raises(PlainweaveError) as exc_info:
        service.approve_requirement(second.id, actor="human:john", expected_version=0, idempotency_key="same")

    assert exc_info.value.code == ErrorCode.CONFLICT


def test_same_idempotency_key_with_different_supersede_payload_conflicts(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")
    first = service.supersede_requirement(
        draft.id,
        title="Reject invalid bearer tokens",
        statement="The API shall reject expired or malformed bearer tokens.",
        actor="human:john",
        expected_version=1,
        idempotency_key="same",
    )

    with pytest.raises(PlainweaveError) as exc_info:
        service.supersede_requirement(
            draft.id,
            title="Reject malformed bearer tokens",
            statement="The API shall reject malformed bearer tokens.",
            actor="human:john",
            expected_version=1,
            idempotency_key="same",
        )

    assert first.title == "Reject invalid bearer tokens"
    assert exc_info.value.code == ErrorCode.CONFLICT


def test_legacy_idempotency_row_without_request_hash_fails_closed(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")
    service.supersede_requirement(
        draft.id,
        title="Reject invalid bearer tokens",
        statement="The API shall reject expired or malformed bearer tokens.",
        actor="human:john",
        expected_version=1,
        idempotency_key="same",
    )
    with connect(service.db_path) as connection:
        connection.execute("update idempotency_keys set request_hash = null where key = ?", ("same",))
        connection.commit()

    with pytest.raises(PlainweaveError) as exc_info:
        service.supersede_requirement(
            draft.id,
            title="Reject invalid bearer tokens",
            statement="The API shall reject expired or malformed bearer tokens.",
            actor="human:john",
            expected_version=1,
            idempotency_key="same",
        )

    assert exc_info.value.code == ErrorCode.CONFLICT


def test_stale_expected_version_returns_conflict(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")

    with pytest.raises(PlainweaveError) as exc_info:
        service.deprecate_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="deprecate-1")

    assert exc_info.value.code == ErrorCode.CONFLICT


def test_supersede_creates_new_version_and_marks_previous_superseded(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")

    version = service.supersede_requirement(
        draft.id,
        title="Reject invalid bearer tokens",
        statement="The API shall reject expired or malformed bearer tokens.",
        actor="human:john",
        expected_version=1,
        idempotency_key="supersede-1",
    )

    assert version.version == 2
    assert version.title == "Reject invalid bearer tokens"
    assert service.get_requirement(draft.id).current_version == 2
    assert service.get_requirement(draft.id).status == "approved"
    with connect(service.db_path) as connection:
        previous_status = connection.execute(
            "select status, superseded_by_version from requirement_versions where requirement_id = ? and version = ?",
            (version.requirement_id, 1),
        ).fetchone()
    assert tuple(previous_status) == ("superseded", 2)


def test_deprecate_preserves_current_version_text(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )
    approved = service.approve_requirement(
        draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1"
    )

    deprecated = service.deprecate_requirement(
        draft.id, actor="human:john", expected_version=1, idempotency_key="dep-1"
    )

    assert deprecated.status == "deprecated"
    assert deprecated.current_version == 1
    version = service.get_requirement(draft.id).current_version_record
    assert version is not None
    assert version.statement == approved.statement


def test_update_draft_increments_revision_and_records_event(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )

    updated = service.update_draft(
        draft.id,
        title="Reject stale bearer tokens",
        actor="human:john",
        expected_draft_revision=1,
    )

    assert updated.title == "Reject stale bearer tokens"
    assert updated.statement == draft.statement
    assert updated.draft_revision == 2
    assert event_count(service) == 2


def test_update_draft_stale_revision_returns_conflict(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )

    with pytest.raises(PlainweaveError) as exc_info:
        service.update_draft(draft.id, statement="Changed.", actor="human:john", expected_draft_revision=99)

    assert exc_info.value.code == ErrorCode.CONFLICT


def test_reject_draft_marks_requirement_rejected_and_records_event(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )

    rejected = service.reject_requirement(draft.id, actor="human:john", expected_version=0, reason="out of scope")

    assert rejected.id == draft.id
    assert rejected.status == "rejected"
    assert rejected.current_version == 0
    assert rejected.active_draft_id is None
    assert event_count(service) == 2


def test_reject_draft_requires_active_draft(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")

    with pytest.raises(PlainweaveError) as exc_info:
        service.reject_requirement(draft.id, actor="human:john", expected_version=1, reason="too late")

    assert exc_info.value.code == ErrorCode.POLICY_REQUIRED


def test_search_and_missing_requirement_errors(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    service.create_requirement("Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john")
    service.create_requirement("Log token failures", "The API shall log token validation failures.", "human:john")

    assert [record.id for record in service.search_requirements("Log")] == ["REQ-AUTH-0002"]
    assert [record.id for record in service.search_requirements()] == ["REQ-AUTH-0001", "REQ-AUTH-0002"]

    with pytest.raises(PlainweaveError) as exc_info:
        service.get_requirement("REQ-AUTH-9999")

    assert exc_info.value.code == ErrorCode.NOT_FOUND


def test_actor_is_required_for_mutations(tmp_path: Path) -> None:
    service = service_for(tmp_path)

    with pytest.raises(PlainweaveError) as exc_info:
        service.create_requirement("Reject expired bearer tokens", "The API shall reject expired tokens.", "")

    assert exc_info.value.code == ErrorCode.VALIDATION


def test_deprecate_with_same_idempotency_key_returns_original_record(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")

    first = service.deprecate_requirement(draft.id, actor="human:john", expected_version=1, idempotency_key="dep-1")
    second = service.deprecate_requirement(draft.id, actor="human:john", expected_version=1, idempotency_key="dep-1")

    assert second == first
    assert event_count(service) == 3
