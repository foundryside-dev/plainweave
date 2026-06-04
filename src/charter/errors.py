from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    VALIDATION = "VALIDATION"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    POLICY_REQUIRED = "POLICY_REQUIRED"
    PEER_ABSENT = "PEER_ABSENT"
    PEER_STALE = "PEER_STALE"
    PEER_CONTRACT = "PEER_CONTRACT"
    LOCKED = "LOCKED"
    UNSUPPORTED = "UNSUPPORTED"
    INTERNAL = "INTERNAL"


class CharterError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        recoverable: bool,
        hint: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.recoverable = recoverable
        self.hint = hint
        self.details = details or {}
