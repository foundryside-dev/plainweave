from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

from plainweave.models import RequirementRecord
from plainweave.service import PlainweaveService
from plainweave.web import views


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
    ctx = request.app.state.ctx_factory()
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
    ctx = request.app.state.ctx_factory()
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
    ctx = request.app.state.ctx_factory()
    req_id = request.path_params["req_id"]
    dossier = ctx.service.requirement_dossier(req_id)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "requirement_detail.html",
        {"dossier": dossier, "req_id": req_id, "operator": ctx.operator, "active_page": "corpus"},
    )


def register(app: Starlette) -> None:
    app.router.routes.append(Route("/", corpus, name="corpus"))
    app.router.routes.append(Route("/req/{req_id}", req_detail, name="req_detail"))
    app.router.routes.append(Route("/req/{req_id}/inline", req_inline, name="req_inline"))
    app.router.routes.append(Route("/req/{req_id}/inline/collapsed", req_inline_collapsed, name="req_inline_collapsed"))
