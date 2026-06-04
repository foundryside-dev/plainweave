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


def test_add_acceptance_criterion_to_active_draft(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )

    criterion = service.add_acceptance_criterion(draft.id, "Expired tokens return 401.", actor="human:john")

    assert criterion.id == "AC-0001"
    assert criterion.requirement_id == draft.requirement_id
    assert criterion.draft_id == draft.draft_id
    assert criterion.version is None
    assert criterion.position == 1
    assert criterion.text == "Expired tokens return 401."
    assert criterion.created_at
    assert service.list_acceptance_criteria(draft.id) == [criterion]


def test_approval_associates_draft_criteria_with_approved_version(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )
    service.add_acceptance_criterion(draft.id, "Expired tokens return 401.", actor="human:john")

    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")

    criteria = service.list_acceptance_criteria(draft.id, version=1)
    assert len(criteria) == 1
    assert criteria[0].version == 1
    assert criteria[0].draft_id == draft.draft_id


def test_adding_criterion_to_approved_requirement_without_draft_requires_policy(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")

    with pytest.raises(CharterError) as exc_info:
        service.add_acceptance_criterion(draft.id, "Expired tokens return 401.", actor="human:john")

    assert exc_info.value.code == ErrorCode.POLICY_REQUIRED


def test_criteria_listing_preserves_approved_history(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )
    first = service.add_acceptance_criterion(draft.id, "Expired tokens return 401.", actor="human:john")
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")

    version_one_criteria = service.list_acceptance_criteria(draft.id, version=1)

    assert version_one_criteria == [first.with_version(1)]
