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


def approve_requirement(service: PlainweaveService, title: str, statement: str, key: str) -> str:
    draft = service.create_requirement(title, statement, "human:john")
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key=key)
    return draft.id


def test_create_empty_baseline_records_locked_snapshot_and_event(tmp_path: Path) -> None:
    service = service_for(tmp_path)

    baseline = service.create_baseline("Release 1.0 requirements", actor="human:john")

    assert baseline.id == "BASELINE-0001"
    assert baseline.name == "Release 1.0 requirements"
    assert baseline.description == ""
    assert baseline.locked is True
    assert baseline.created_by == "human:john"
    assert baseline.members == []
    assert event_count(service) == 1


def test_baseline_includes_only_current_approved_versions(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    approved_id = approve_requirement(
        service,
        "Reject expired bearer tokens",
        "The API shall reject expired bearer tokens.",
        "approve-1",
    )
    service.create_requirement("Draft only", "This draft is not approved.", "human:john")
    rejected = service.create_requirement("Rejected", "This draft is rejected.", "human:john")
    service.reject_requirement(rejected.id, actor="human:john", expected_version=0, reason="out of scope")

    baseline = service.create_baseline("Release 1.0 requirements", actor="human:john")

    assert [member.id for member in baseline.members] == [approved_id]
    assert baseline.members[0].version == 1
    assert baseline.members[0].status_at_baseline == "approved"


def test_baseline_includes_deprecated_current_versions(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(
        service,
        "Reject expired bearer tokens",
        "The API shall reject expired bearer tokens.",
        "approve-1",
    )
    service.deprecate_requirement(requirement_id, actor="human:john", expected_version=1, idempotency_key="dep-1")

    baseline = service.create_baseline("Deprecated requirements", actor="human:john")

    assert [member.id for member in baseline.members] == [requirement_id]
    assert baseline.members[0].status_at_baseline == "deprecated"


def test_show_and_list_baselines_return_snapshot_members(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    approve_requirement(
        service,
        "Reject expired bearer tokens",
        "The API shall reject expired bearer tokens.",
        "approve-1",
    )
    created = service.create_baseline(
        "Release 1.0 requirements",
        actor="human:john",
        description="Approved requirements for release 1.0.",
    )

    shown = service.show_baseline(created.id)
    listed = service.list_baselines()

    assert shown == created
    assert listed == [created]
    assert shown.members[0].statement_hash.startswith("sha256:")


def test_baseline_snapshot_does_not_change_after_supersede(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(
        service,
        "Reject expired bearer tokens",
        "The API shall reject expired bearer tokens.",
        "approve-1",
    )
    baseline = service.create_baseline("Release 1.0 requirements", actor="human:john")
    original_hash = baseline.members[0].statement_hash

    service.supersede_requirement(
        requirement_id,
        title="Reject invalid bearer tokens",
        statement="The API shall reject expired or malformed bearer tokens.",
        actor="human:john",
        expected_version=1,
        idempotency_key="supersede-1",
    )

    shown = service.show_baseline(baseline.id)
    assert shown.members[0].version == 1
    assert shown.members[0].statement_hash == original_hash


def test_baseline_diff_reports_superseded_and_new_requirements(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(
        service,
        "Reject expired bearer tokens",
        "The API shall reject expired bearer tokens.",
        "approve-1",
    )
    baseline = service.create_baseline("Release 1.0 requirements", actor="human:john")
    service.supersede_requirement(
        requirement_id,
        title="Reject invalid bearer tokens",
        statement="The API shall reject expired or malformed bearer tokens.",
        actor="human:john",
        expected_version=1,
        idempotency_key="supersede-1",
    )
    approve_requirement(service, "Log token failures", "The API shall log token failures.", "approve-2")

    diff = service.diff_baseline(baseline.id)

    assert diff.baseline_id == baseline.id
    assert diff.summary == {
        "unchanged": 0,
        "changed": 0,
        "missing_current": 0,
        "new_since_baseline": 1,
        "superseded_since_baseline": 1,
    }
    assert [item.status for item in diff.items] == ["superseded_since_baseline", "new_since_baseline"]
    assert diff.items[0].baseline_version == 1
    assert diff.items[0].current_version == 2
    assert diff.items[1].baseline_version is None
    assert diff.items[1].current_version == 1


def test_baseline_diff_reports_missing_current_version(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    requirement_id = approve_requirement(
        service,
        "Reject expired bearer tokens",
        "The API shall reject expired bearer tokens.",
        "approve-1",
    )
    baseline = service.create_baseline("Release 1.0 requirements", actor="human:john")
    with connect(service.db_path) as connection:
        requirement_row = connection.execute(
            "select requirement_id from requirements where display_id = ?",
            (requirement_id,),
        ).fetchone()
        connection.execute(
            "update requirements set current_version = ? where requirement_id = ?",
            (99, requirement_row["requirement_id"]),
        )
        connection.commit()

    diff = service.diff_baseline(baseline.id)

    assert diff.summary["missing_current"] == 1
    assert diff.items[0].status == "missing_current"
    assert diff.items[0].current_version == 99
    assert diff.items[0].current_statement_hash is None


def test_baseline_creation_requires_actor(tmp_path: Path) -> None:
    service = service_for(tmp_path)

    with pytest.raises(PlainweaveError) as exc_info:
        service.create_baseline("Release 1.0 requirements", actor="")

    assert exc_info.value.code == ErrorCode.VALIDATION


def test_missing_baseline_returns_not_found(tmp_path: Path) -> None:
    service = service_for(tmp_path)

    with pytest.raises(PlainweaveError) as exc_info:
        service.show_baseline("BASELINE-9999")

    assert exc_info.value.code == ErrorCode.NOT_FOUND
