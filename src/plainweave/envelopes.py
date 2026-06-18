from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from plainweave import __version__
from plainweave.errors import ErrorCode

JsonObject = dict[str, object]


def _generated_at(value: str | None) -> str:
    return value if value is not None else datetime.now(UTC).isoformat()


def _meta(*, project: str | None = None, generated_at: str | None = None) -> JsonObject:
    return {
        "producer": {"tool": "plainweave", "version": __version__},
        "generated_at": _generated_at(generated_at),
        "project": project,
    }


def _warnings(warnings: Sequence[object]) -> list[object]:
    return list(warnings)


def _error_code(code: ErrorCode | str) -> ErrorCode:
    if isinstance(code, ErrorCode):
        return code
    try:
        return ErrorCode(code)
    except ValueError:
        raise ValueError(f"unknown Plainweave error code: {code}") from None


def success_envelope(
    schema: str,
    data: JsonObject,
    *,
    warnings: Sequence[object] = (),
    project: str | None = None,
    generated_at: str | None = None,
) -> JsonObject:
    return {
        "schema": schema,
        "ok": True,
        "data": data,
        "warnings": _warnings(warnings),
        "meta": _meta(project=project, generated_at=generated_at),
    }


def error_envelope(
    code: ErrorCode | str,
    message: str,
    *,
    recoverable: bool,
    hint: str,
    details: JsonObject | None = None,
    warnings: Sequence[object] = (),
    project: str | None = None,
    generated_at: str | None = None,
) -> JsonObject:
    error_code = _error_code(code)
    return {
        "schema": "weft.plainweave.error.v1",
        "ok": False,
        "error": {
            "code": error_code.value,
            "message": message,
            "recoverable": recoverable,
            "hint": hint,
            "details": details or {},
        },
        "warnings": _warnings(warnings),
        "meta": _meta(project=project, generated_at=generated_at),
    }


def list_envelope(
    schema: str,
    items: Sequence[object],
    *,
    has_more: bool = False,
    next_offset: int | None = None,
    warnings: Sequence[object] = (),
    project: str | None = None,
    generated_at: str | None = None,
) -> JsonObject:
    return success_envelope(
        schema,
        {"items": list(items), "has_more": has_more, "next_offset": next_offset},
        warnings=warnings,
        project=project,
        generated_at=generated_at,
    )


def batch_envelope(
    schema: str,
    succeeded: Sequence[object],
    failed: Sequence[object],
    *,
    warnings: Sequence[object] = (),
    project: str | None = None,
    generated_at: str | None = None,
) -> JsonObject:
    return success_envelope(
        schema,
        {"succeeded": list(succeeded), "failed": list(failed)},
        warnings=warnings,
        project=project,
        generated_at=generated_at,
    )
