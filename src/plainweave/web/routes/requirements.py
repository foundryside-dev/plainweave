from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
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


def register(app: Starlette) -> None:
    app.router.routes.append(Route("/", corpus, name="corpus"))
