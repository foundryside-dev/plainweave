from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
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


async def goals_new(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    form = await request.form()
    ctx.service.create_goal(str(form["title"]), str(form["statement"]), actor=ctx.operator.actor_id)
    return RedirectResponse("/goals", status_code=303)


async def req_ladder(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    req_id = request.path_params["req_id"]
    form = await request.form()
    ctx.service.link_goal_to_requirement(str(form["goal_id"]), req_id, actor=ctx.operator.actor_id)
    return RedirectResponse(f"/req/{req_id}", status_code=303)


def register(app: Starlette) -> None:
    app.router.routes.append(Route("/goals", goals_page, name="goals"))
    app.router.routes.append(Route("/goals/new", goals_new, methods=["POST"]))
    app.router.routes.append(Route("/req/{req_id}/ladder", req_ladder, methods=["POST"]))
