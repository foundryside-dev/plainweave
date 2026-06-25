from __future__ import annotations

from plainweave.errors import ErrorCode
from plainweave.web.errors import error_to_status


def test_error_status_mapping() -> None:
    assert error_to_status(ErrorCode.VALIDATION) == 400
    assert error_to_status(ErrorCode.NOT_FOUND) == 404
    assert error_to_status(ErrorCode.CONFLICT) == 409
    assert error_to_status(ErrorCode.POLICY_REQUIRED) == 409
    assert error_to_status(ErrorCode.INTERNAL) == 500
