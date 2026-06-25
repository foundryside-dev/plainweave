from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

from plainweave.intent_graph import IntentLevel


async def goals_page(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    goals = ctx.service.list_goals()
    orphan_goal_ids = {n.node_id for n in ctx.service.intent_orphans(IntentLevel.GOAL)}
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "goals.html",
        {"goals": goals, "orphan_goal_ids": orphan_goal_ids, "operator": ctx.operator, "active_page": "goals"},
    )


def register(app: Starlette) -> None:
    app.router.routes.append(Route("/goals", goals_page, name="goals"))
