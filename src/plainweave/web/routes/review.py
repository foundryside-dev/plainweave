from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

from plainweave.web import views


async def review(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    items = views.pending_items(ctx.service)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "items": items,
            "pending_count": len(items),
            "operator": ctx.operator,
            "active_page": "review",
        },
    )


def register(app: Starlette) -> None:
    app.router.routes.append(Route("/review", review, name="review"))
