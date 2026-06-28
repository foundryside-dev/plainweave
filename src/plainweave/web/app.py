from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qsl

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from plainweave.errors import PlainweaveError
from plainweave.web import views
from plainweave.web.context import RequestContext, csrf_ok, new_csrf_token, request_ctx
from plainweave.web.errors import error_to_status

_HERE = Path(__file__).parent
_CSRF_COOKIE = "pw_csrf"


def _global_context(request: Request) -> dict[str, object]:
    """Inject the operator identity and the global pending-review count into every
    full-page render so the nav "Review N" badge is populated on EVERY page (M6).

    HTMX swaps return base-less fragments that never read these values, so the
    expensive ``pending_items`` walk is skipped for them.

    This runs on the error path too (``error.html`` extends ``base.html``), so it
    must never itself raise: if the error being rendered was raised *during*
    ``RequestContext`` construction (e.g. a launch-time ``POLICY_REQUIRED`` operator
    or a DB-open failure), re-building the context here would raise a second time and
    collapse the actionable error page into an opaque 500. Failable work is therefore
    guarded and degrades to chrome-only defaults so the helpful message still renders.
    """
    if request.headers.get("HX-Request"):
        return {}
    try:
        ctx = request_ctx(request)
        return {
            "operator": ctx.operator,
            "pending_count": len(views.pending_items(ctx.service)),
        }
    except Exception:  # noqa: BLE001 — last-resort render path; must never double-fault.
        # A successful route caches its ctx on request.state *before* the template
        # renders, so the only renders that reach an uncached (failable) build here are
        # the error page and ctx-less routes — never a healthy page whose error we'd mask.
        return {"operator": None, "pending_count": 0}


def create_app(*, actor: str | None, root: Path | None) -> Starlette:
    templates = Jinja2Templates(directory=str(_HERE / "templates"), context_processors=[_global_context])

    def ctx_factory() -> RequestContext:
        return RequestContext.from_root(root, actor=actor)

    async def healthz(request: Request) -> Response:
        return PlainTextResponse("ok")

    async def on_error(request: Request, exc: Exception) -> Response:
        if isinstance(exc, PlainweaveError):
            status = error_to_status(exc.code)
            # HTMX swaps a bare fragment into the live page; a normal navigation
            # gets a full, navigable page with the nav + stylesheet chrome (M2).
            template = "_partials/error.html" if request.headers.get("HX-Request") else "error.html"
            return templates.TemplateResponse(
                request,
                template,
                {"code": exc.code.value, "message": exc.message, "hint": exc.hint},
                status_code=status,
            )
        raise exc

    async def csrf_mw(request: Request, call_next: RequestResponseEndpoint) -> Response:
        cookie_token = request.cookies.get(_CSRF_COOKIE)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            # Read via .body() so Starlette's _CachedRequest can replay the raw
            # bytes to downstream handlers — calling .form() here would consume
            # the body stream, leaving downstream request.form() empty.
            body = await request.body()
            fields = dict(parse_qsl(body.decode("utf-8")))
            if not csrf_ok(cookie_token, fields.get("_csrf")):
                return PlainTextResponse("CSRF check failed", status_code=403)
        # Mint the token for THIS render before calling the handler so the template
        # can embed a real token even on the very first (cold) request, when there
        # is no cookie yet.  scope["state"] is shared into the handler via
        # BaseHTTPMiddleware, making request.state.csrf_token visible there.
        token = cookie_token or new_csrf_token()
        request.state.csrf_token = token
        response = await call_next(request)
        if cookie_token is None:
            response.set_cookie(_CSRF_COOKIE, token, httponly=True, samesite="strict")
        return response

    routes = [
        Route("/healthz", healthz),
        Mount("/static", app=StaticFiles(directory=str(_HERE / "static")), name="static"),
    ]
    app = Starlette(
        routes=routes,
        middleware=[Middleware(BaseHTTPMiddleware, dispatch=csrf_mw)],
        exception_handlers={PlainweaveError: on_error},
    )
    app.state.templates = templates
    app.state.ctx_factory = ctx_factory
    app.state.csrf_cookie = _CSRF_COOKIE

    from plainweave.web.routes import register_all

    register_all(app)
    return app
