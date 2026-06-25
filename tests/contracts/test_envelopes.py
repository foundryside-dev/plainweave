from __future__ import annotations

from typing import Any, cast

import pytest

from plainweave import __version__
from plainweave.envelopes import batch_envelope, error_envelope, list_envelope, success_envelope
from plainweave.errors import ErrorCode

GENERATED_AT = "2026-06-04T10:00:00+10:00"


def test_success_envelope_has_standard_shape() -> None:
    envelope = success_envelope(
        "weft.plainweave.requirement_version.v1",
        {"id": "REQ-AUTH-001"},
        project="AUTH",
        generated_at=GENERATED_AT,
    )

    assert envelope == {
        "schema": "weft.plainweave.requirement_version.v1",
        "ok": True,
        "data": {"id": "REQ-AUTH-001"},
        "warnings": [],
        "meta": {
            "producer": {"tool": "plainweave", "version": __version__},
            "generated_at": GENERATED_AT,
            "project": "AUTH",
        },
    }


def test_error_envelope_has_recovery_fields_and_closed_code() -> None:
    envelope = error_envelope(
        ErrorCode.VALIDATION,
        "requirement_id is required",
        recoverable=True,
        hint="Pass a requirement id such as REQ-AUTH-017.",
        details={"field": "requirement_id"},
        project="AUTH",
        generated_at=GENERATED_AT,
    )

    assert envelope == {
        "schema": "weft.plainweave.error.v1",
        "ok": False,
        "error": {
            "code": "VALIDATION",
            "message": "requirement_id is required",
            "recoverable": True,
            "hint": "Pass a requirement id such as REQ-AUTH-017.",
            "details": {"field": "requirement_id"},
        },
        "warnings": [],
        "meta": {
            "producer": {"tool": "plainweave", "version": __version__},
            "generated_at": GENERATED_AT,
            "project": "AUTH",
        },
    }


def test_error_envelope_rejects_unknown_error_codes() -> None:
    with pytest.raises(ValueError, match="unknown Plainweave error code"):
        error_envelope(
            "NOT_A_CODE",
            "bad",
            recoverable=False,
            hint="Use a known error code.",
            generated_at=GENERATED_AT,
        )


def test_list_envelope_wraps_items_and_pagination() -> None:
    envelope = list_envelope(
        "weft.plainweave.requirement_list.v1",
        [{"id": "REQ-AUTH-001"}],
        has_more=True,
        next_offset=25,
        project="AUTH",
        generated_at=GENERATED_AT,
    )

    assert envelope["ok"] is True
    data = cast(dict[str, Any], envelope["data"])
    assert data == {
        "items": [{"id": "REQ-AUTH-001"}],
        "has_more": True,
        "next_offset": 25,
    }
    meta = cast(dict[str, Any], envelope["meta"])
    assert meta["project"] == "AUTH"


def test_batch_envelope_wraps_succeeded_and_failed_items() -> None:
    envelope = batch_envelope(
        "weft.plainweave.batch.v1",
        succeeded=[{"id": "REQ-AUTH-001"}],
        failed=[{"id": "REQ-AUTH-002", "error": {"code": "CONFLICT"}}],
        generated_at=GENERATED_AT,
    )

    assert envelope["ok"] is True
    assert envelope["data"] == {
        "succeeded": [{"id": "REQ-AUTH-001"}],
        "failed": [{"id": "REQ-AUTH-002", "error": {"code": "CONFLICT"}}],
    }
    assert envelope["warnings"] == []


def test_error_code_enum_is_closed_for_v0_1() -> None:
    assert {code.value for code in ErrorCode} == {
        "VALIDATION",
        "NOT_FOUND",
        "CONFLICT",
        "POLICY_REQUIRED",
        "PEER_ABSENT",
        "PEER_STALE",
        "PEER_CONTRACT",
        "LOCKED",
        "UNSUPPORTED",
        "INTERNAL",
    }
