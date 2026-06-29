from __future__ import annotations

from starlette.applications import Starlette
from starlette.datastructures import FormData
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.models import RequirementRecord
from plainweave.service import PlainweaveService
from plainweave.web import views
from plainweave.web.context import request_ctx


def _require_str(form: FormData, field: str) -> str:
    """Return form[field] as a non-empty str, or raise a 400-mapped PlainweaveError."""
    raw = form.get(field)
    if raw is None:
        raise PlainweaveError(
            ErrorCode.VALIDATION,
            f"missing required field: {field!r}",
            recoverable=True,
            hint=f"provide a value for {field!r}",
        )
    return str(raw)


def _optional_int(form: FormData, field: str, default: int = 0) -> int:
    """Return form[field] as int (default if absent), or raise a 400-mapped PlainweaveError."""
    raw = form.get(field)
    if raw is None:
        return default
    try:
        return int(str(raw))
    except ValueError as exc:
        raise PlainweaveError(
            ErrorCode.VALIDATION,
            f"field {field!r} must be an integer, got {raw!r}",
            recoverable=True,
            hint=f"provide a valid integer value for {field!r}",
        ) from exc


def _resolve_titles(svc: PlainweaveService, records: list[RequirementRecord]) -> dict[str, str]:
    """Resolve a display title for each requirement.

    For approved requirements the approved-version title is used.  For draft-only
    requirements the active draft title is sourced via ``requirement_dossier`` so
    the displayed title matches what the author typed, not just the display-id
    fallback.  Falls back to the display-id when neither exists.
    """
    titles: dict[str, str] = {}
    for rec in records:
        if rec.current_version_record is not None:
            titles[rec.requirement_id] = rec.current_version_record.title
        else:
            # Draft-only: fetch the active draft title from the dossier.
            dossier = svc.requirement_dossier(rec.requirement_id)
            draft = dossier.requirement.active_draft
            titles[rec.requirement_id] = draft.title if draft is not None else rec.id
    return titles


async def corpus(request: Request) -> Response:
    ctx = request_ctx(request)
    q = request.query_params.get("q", "")
    status = request.query_params.get("status", "")
    orphan = request.query_params.get("orphan", "")
    records = ctx.service.search_requirements()
    titles = _resolve_titles(ctx.service, records)
    rows = views.build_corpus_rows(ctx.service.intent_corpus(), records, titles)
    rows = views.filter_rows(rows, q=q, status=status, orphan=orphan)
    template = "_partials/corpus_rows.html" if request.headers.get("HX-Request") else "corpus.html"
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        template,
        {
            "rows": rows,
            "filters": {"q": q, "status": status, "orphan": orphan},
            "operator": ctx.operator,
            "active_page": "corpus",
        },
    )


async def req_inline(request: Request) -> Response:
    ctx = request_ctx(request)
    req_id = request.path_params["req_id"]
    dossier = ctx.service.requirement_dossier(req_id)
    section = dossier.requirement
    statement = (
        section.active_draft.statement
        if section.active_draft
        else (section.current_version.statement if section.current_version else "")
    )
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "_partials/req_inline.html",
        {"req_id": req_id, "statement": statement, "status": dossier.requirement.record.status},
    )


async def req_inline_collapsed(request: Request) -> Response:
    return HTMLResponse("")


async def req_detail(request: Request) -> Response:
    ctx = request_ctx(request)
    req_id = request.path_params["req_id"]
    dossier = ctx.service.requirement_dossier(req_id)
    goals = ctx.service.list_goals()
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "requirement_detail.html",
        {"dossier": dossier, "req_id": req_id, "operator": ctx.operator, "active_page": "corpus", "goals": goals},
    )


async def req_new_get(request: Request) -> Response:
    ctx = request_ctx(request)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "requirement_form.html",
        {
            "req_id": None,
            "title": "",
            "statement": "",
            "expected_draft_revision": None,
            "operator": ctx.operator,
            "active_page": "corpus",
        },
    )


async def req_new_post(request: Request) -> Response:
    ctx = request_ctx(request)
    form = await request.form()
    title = _require_str(form, "title")
    statement = _require_str(form, "statement")
    ctx.service.create_requirement(title, statement, actor=ctx.operator.actor_id)
    return RedirectResponse("/", status_code=303)


async def req_edit_get(request: Request) -> Response:
    ctx = request_ctx(request)
    req_id = request.path_params["req_id"]
    draft = ctx.service.requirement_dossier(req_id).requirement.active_draft
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "requirement_form.html",
        {
            "req_id": req_id,
            "title": draft.title if draft is not None else "",
            "statement": draft.statement if draft is not None else "",
            "expected_draft_revision": draft.draft_revision if draft is not None else None,
            "operator": ctx.operator,
            "active_page": "corpus",
        },
    )


async def req_edit_post(request: Request) -> Response:
    ctx = request_ctx(request)
    req_id = request.path_params["req_id"]
    form = await request.form()
    title = _require_str(form, "title")
    statement = _require_str(form, "statement")
    expected = _optional_int(form, "expected_draft_revision", default=0)
    try:
        ctx.service.update_draft(
            req_id,
            actor=ctx.operator.actor_id,
            title=title,
            statement=statement,
            expected_draft_revision=expected,
        )
        return RedirectResponse(f"/req/{req_id}", status_code=303)
    except PlainweaveError as exc:
        if exc.code is not ErrorCode.CONFLICT:
            raise  # falls through to the global handler
        # Local catch: HTMX only swaps 2xx; return 200 with both texts preserved.
        draft = ctx.service.requirement_dossier(req_id).requirement.active_draft
        templates: Jinja2Templates = request.app.state.templates
        return templates.TemplateResponse(
            request,
            "_partials/edit_conflict.html",
            {
                "req_id": req_id,
                "submitted_title": title,
                "submitted_statement": statement,
                "current_title": draft.title if draft is not None else "",
                "current_statement": draft.statement if draft is not None else "",
                "fresh_revision": draft.draft_revision if draft is not None else 0,
            },
            status_code=200,
        )


def register(app: Starlette) -> None:
    app.router.routes.append(Route("/", corpus, name="corpus"))
    # /req/new MUST precede /req/{req_id} — Starlette matches in registration order;
    # a literal "new" segment would otherwise be captured as req_id.
    app.router.routes.append(Route("/req/new", req_new_get, name="req_new"))
    app.router.routes.append(Route("/req/new", req_new_post, methods=["POST"]))
    app.router.routes.append(Route("/req/{req_id}", req_detail, name="req_detail"))
    app.router.routes.append(Route("/req/{req_id}/inline", req_inline, name="req_inline"))
    app.router.routes.append(Route("/req/{req_id}/inline/collapsed", req_inline_collapsed, name="req_inline_collapsed"))
    app.router.routes.append(Route("/req/{req_id}/edit", req_edit_get, name="req_edit"))
    app.router.routes.append(Route("/req/{req_id}/edit", req_edit_post, methods=["POST"]))
