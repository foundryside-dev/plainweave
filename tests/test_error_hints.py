"""Anti-vacuous guards for the honest error-hint layer (functional honesty).

An error must SAY WHAT IT KNOWS. A hint that does not point at the real fix
actively misdirects, so these tests pin three properties that the frozen
``weft.plainweave.error.v1`` envelope must keep honouring additively:

1. Every :class:`ErrorCode` has a non-empty default hint, and VALIDATION /
   NOT_FOUND never inherit the stale-state "Refresh local Plainweave state and
   retry." blanket (their cause is bad input / a missing id, not staleness).
2. ``_error`` resolves an omitted hint from that map, threads an explicit hint
   verbatim, and always coerces ``details`` to a dict.
3. The two dogfood findings (CONFLICT version guard; missing-actor VALIDATION)
   emit precise, cause-appropriate hints and details end-to-end.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.service import _DEFAULT_ERROR_HINTS, PlainweaveService
from plainweave.store import migrate

_BLANKET_HINT = "Refresh local Plainweave state and retry."


def service_for(tmp_path: Path) -> PlainweaveService:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")
    return PlainweaveService(db_path)


def test_default_hint_map_covers_every_error_code_non_empty() -> None:
    for code in ErrorCode:
        assert code in _DEFAULT_ERROR_HINTS, f"missing default hint for {code}"
        hint = _DEFAULT_ERROR_HINTS[code]
        assert hint and hint.strip(), f"empty default hint for {code}"


def test_validation_and_not_found_defaults_are_never_stale_state_hints() -> None:
    for code in (ErrorCode.VALIDATION, ErrorCode.NOT_FOUND):
        hint = _DEFAULT_ERROR_HINTS[code].lower()
        assert _BLANKET_HINT.lower() not in hint
        # No refresh/refetch-local-state phrasing either: the cause is the input,
        # not local staleness. (CONFLICT may legitimately say "refetch".)
        assert "refresh" not in hint
        assert "refetch" not in hint


def test_error_resolves_default_hint_when_none(tmp_path: Path) -> None:
    service = service_for(tmp_path)

    error = service._error(ErrorCode.NOT_FOUND, "requirement not found: REQ-X")

    assert error.hint == _DEFAULT_ERROR_HINTS[ErrorCode.NOT_FOUND]
    assert error.hint
    assert error.details == {}


def test_error_threads_explicit_hint_and_details_verbatim(tmp_path: Path) -> None:
    service = service_for(tmp_path)

    error = service._error(
        ErrorCode.CONFLICT,
        "boom",
        hint="Retry with --expected-version 7.",
        details={"expected_version": 3, "current_version": 7},
    )

    assert error.hint == "Retry with --expected-version 7."
    assert error.details == {"expected_version": 3, "current_version": 7}
    assert isinstance(error.details, dict)


def test_conflict_version_guard_says_what_it_knows(tmp_path: Path) -> None:
    # add -> current version 0; approving with expected_version 1 trips the guard.
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )

    with pytest.raises(PlainweaveError) as exc_info:
        service.approve_requirement(draft.id, actor="human:john", expected_version=1, idempotency_key="approve-1")

    error = exc_info.value
    assert error.code == ErrorCode.CONFLICT
    assert error.details["current_version"] == 0
    assert error.details["expected_version"] == 1
    assert "current version 0" in error.message
    assert "--expected-version 0" in error.hint
    assert _BLANKET_HINT not in error.hint


def test_draft_revision_guard_says_what_it_knows(tmp_path: Path) -> None:
    # The same optimistic-concurrency defect as the requirement-version guard, on
    # a sibling field: updating a draft with a wrong expected_draft_revision must
    # disclose the actual revision (message + details + a --expected-draft-revision hint).
    service = service_for(tmp_path)
    draft = service.create_requirement(
        "Reject expired bearer tokens", "The API shall reject expired tokens.", "human:john"
    )

    with pytest.raises(PlainweaveError) as exc_info:
        service.update_draft(draft.id, actor="human:john", statement="revised", expected_draft_revision=99)

    error = exc_info.value
    assert error.code == ErrorCode.CONFLICT
    current = error.details["current_draft_revision"]
    assert error.details["expected_draft_revision"] == 99
    assert f"current draft revision {current}" in error.message
    assert f"--expected-draft-revision {current}" in error.hint
    assert _BLANKET_HINT not in error.hint


def test_missing_actor_error_points_at_actor_not_stale_state(tmp_path: Path) -> None:
    service = service_for(tmp_path)

    with pytest.raises(PlainweaveError) as exc_info:
        service.create_requirement("Reject expired bearer tokens", "The API shall reject expired tokens.", "")

    error = exc_info.value
    assert error.code == ErrorCode.VALIDATION
    assert "--actor" in error.hint
    assert _BLANKET_HINT not in error.hint
    # The missing-actor golden pins details:{}; enrichment must not silently grow it.
    assert error.details == {}


def _assert_validation_without_blanket_hint(exc_info: pytest.ExceptionInfo[PlainweaveError]) -> None:
    assert exc_info.value.code == ErrorCode.VALIDATION
    assert exc_info.value.hint != _BLANKET_HINT
    assert _BLANKET_HINT not in exc_info.value.hint


def test_no_service_path_validation_error_carries_the_blanket_hint(tmp_path: Path) -> None:
    """Guard: a VALIDATION error must never inherit the stale-state blanket hint."""
    service = service_for(tmp_path)

    with pytest.raises(PlainweaveError) as missing_actor:
        service.create_requirement("t", "s", "")
    _assert_validation_without_blanket_hint(missing_actor)

    with pytest.raises(PlainweaveError) as bad_method:
        service._validate_verification_method("nonsense")
    _assert_validation_without_blanket_hint(bad_method)

    with pytest.raises(PlainweaveError) as bad_status:
        service._validate_evidence_status("nonsense")
    _assert_validation_without_blanket_hint(bad_status)
