from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

from plainweave.intent_graph import IntentLevel
from plainweave.web import views
from plainweave.web.context import request_ctx


async def intent_dashboard(request: Request) -> Response:
    ctx = request_ctx(request)
    cov = ctx.service.intent_coverage()
    orphans = {
        level.value: ctx.service.intent_orphans(level)
        for level in (IntentLevel.CODE, IntentLevel.REQUIREMENT, IntentLevel.GOAL)
    }
    # Resolve human titles so orphans read as titles, not raw node ids (M7). Only the
    # draft-only requirement orphans need a dossier lookup; approved ones carry a title
    # on the record and goal titles come from the goal list.
    records_by_id = {r.requirement_id: r for r in ctx.service.search_requirements()}
    req_titles: dict[str, str] = {}
    for node in orphans[IntentLevel.REQUIREMENT.value]:
        rec = records_by_id.get(node.node_id)
        if rec is None:
            continue
        if rec.current_version_record is not None:
            req_titles[node.node_id] = rec.current_version_record.title
        else:
            draft = ctx.service.requirement_dossier(node.node_id).requirement.active_draft
            req_titles[node.node_id] = draft.title if draft is not None else rec.id
    goal_titles = {g.goal_id: g.title for g in ctx.service.list_goals()}
    orphan_sections = views.build_orphan_sections(orphans, req_titles, goal_titles)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "intent.html",
        {
            "cov": cov,
            "banner": views.coverage_banner(cov),
            "orphan_sections": orphan_sections,
            "operator": ctx.operator,
            "active_page": "intent",
        },
    )


def register(app: Starlette) -> None:
    app.router.routes.append(Route("/intent", intent_dashboard, name="intent"))
