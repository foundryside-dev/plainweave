from __future__ import annotations

from plainweave.errors import ErrorCode

_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION: 400,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.POLICY_REQUIRED: 409,
    ErrorCode.LOCKED: 409,
    ErrorCode.PEER_ABSENT: 503,
    ErrorCode.PEER_STALE: 503,
    ErrorCode.PEER_CONTRACT: 502,
    ErrorCode.UNSUPPORTED: 400,
    ErrorCode.INTERNAL: 500,
}


def error_to_status(code: ErrorCode) -> int:
    return _STATUS.get(code, 500)
