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
from plainweave.web.context import RequestContext, csrf_ok, new_csrf_token
from plainweave.web.errors import error_to_status

_HERE = Path(__file__).parent
_CSRF_COOKIE = "pw_csrf"


def create_app(*, actor: str | None, root: Path | None) -> Starlette:
    templates = Jinja2Templates(directory=str(_HERE / "templates"))

    def ctx_factory() -> RequestContext:
        return RequestContext.from_root(root, actor=actor)

    async def healthz(request: Request) -> Response:
        return PlainTextResponse("ok")

    async def on_error(request: Request, exc: Exception) -> Response:
        if isinstance(exc, PlainweaveError):
            status = error_to_status(exc.code)
            return templates.TemplateResponse(
                request,
                "_partials/error.html",
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
