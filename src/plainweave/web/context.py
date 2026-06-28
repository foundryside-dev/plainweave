from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

from starlette.requests import Request

from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.paths import plainweave_db_path
from plainweave.service import PlainweaveService

DEFAULT_OPERATOR_ID = "human:operator"


@dataclass(frozen=True)
class OperatorIdentity:
    actor_id: str
    display_name: str
    kind: str


class RequestContext:
    def __init__(self, service: PlainweaveService, operator: OperatorIdentity) -> None:
        self.service = service
        self.operator = operator

    @classmethod
    def from_root(cls, root: Path | None, *, actor: str | None) -> RequestContext:
        service = PlainweaveService(plainweave_db_path(root), root=root)
        actor_id = actor or DEFAULT_OPERATOR_ID
        display = actor_id.split(":", 1)[-1] or actor_id
        operator = cls._ensure_operator(service, actor_id, display)
        return cls(service, operator)

    @staticmethod
    def _ensure_operator(service: PlainweaveService, actor_id: str, display: str) -> OperatorIdentity:
        # Register the operator as a human actor. At genesis (no attester yet) this
        # self-registration is permitted; once an attester exists, only an existing
        # attester may (re)register a human — surface that clearly rather than crashing.
        try:
            service.register_actor(actor_id, kind="human", display_name=display, actor=actor_id)
        except PlainweaveError as exc:
            if exc.code is ErrorCode.POLICY_REQUIRED:
                raise PlainweaveError(
                    ErrorCode.POLICY_REQUIRED,
                    f"operator actor {actor_id!r} is not a registered human and cannot self-register "
                    "(an attester already exists). Register it via the CLI before launching the web UI.",
                    recoverable=False,
                    hint="plainweave actor register --id <id> --kind human --actor <existing-attester>",
                ) from exc
            raise
        return OperatorIdentity(actor_id=actor_id, display_name=display, kind="human")


def request_ctx(request: Request) -> RequestContext:
    """Return a per-request :class:`RequestContext`, building it once and caching it
    on ``request.state``.

    Routes and the global Jinja context processor both reach for the context within a
    single request; memoising on ``request.state`` keeps the work to one
    ``PlainweaveService`` construction (and one operator self-registration) per request
    instead of one per call site.
    """
    cached = getattr(request.state, "ctx", None)
    if isinstance(cached, RequestContext):
        return cached
    ctx: RequestContext = request.app.state.ctx_factory()
    request.state.ctx = ctx
    return ctx


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_ok(cookie_token: str | None, form_token: str | None) -> bool:
    if not cookie_token or not form_token:
        return False
    return secrets.compare_digest(cookie_token, form_token)
