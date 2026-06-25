from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

from plainweave.intent_graph import IntentLevel
from plainweave.web import views


async def intent_dashboard(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    cov = ctx.service.intent_coverage()
    orphans = {
        level.value: ctx.service.intent_orphans(level)
        for level in (IntentLevel.CODE, IntentLevel.REQUIREMENT, IntentLevel.GOAL)
    }
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "intent.html",
        {
            "cov": cov,
            "banner": views.coverage_banner(cov),
            "orphans": orphans,
            "operator": ctx.operator,
            "active_page": "intent",
        },
    )


def register(app: Starlette) -> None:
    app.router.routes.append(Route("/intent", intent_dashboard, name="intent"))
