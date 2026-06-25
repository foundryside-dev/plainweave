# Plainweave webUX MVP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first, operator-facing web app that lets a human browse the code-grounded intent corpus, author requirements, and ratify agent-proposed drafts and trace links.

**Architecture:** A thin Starlette + Jinja2 + HTMX web tier under `src/plainweave/web/`, sitting on the existing `PlainweaveService`. Handlers translate HTTP ↔ one service call and render; all business logic stays in the service. Shipped as an optional `plainweave[web]` extra so the core install stays one-dep.

**Tech Stack:** Python 3.12, Starlette, uvicorn, Jinja2, HTMX ≥ 1.9 (vendored), pytest, mypy (strict), ruff.

**Design spec:** `docs/superpowers/specs/2026-06-25-plainweave-webux-design.md` (read §4.1 and §12 before starting — they fix the cross-cutting HTMX/accessibility contracts every task must honor).

## Global Constraints

- **Thin web tier:** handlers call exactly one `service` method and render. No business logic, no direct SQLite access from the web tier.
- **HTMX ≥ 1.9** vendored as one file at `src/plainweave/web/static/htmx.min.js`. No JS build, no node, no framework. The only JS we author is one small inline focus script (Task 16).
- **Controls:** every interactive control is a real `<button>`; links (`<a>`) GET, mutations POST; every mutating `<form>` carries a CSRF hidden field.
- **HTMX needs 2xx to swap:** validation/conflict states that must re-render in place are caught locally in the handler and returned as **200** with an inline-error partial. Exactly three such local catches exist (edit conflict, approve conflict, reject empty-reason); everything else falls through to the global `PlainweaveError` exception handler.
- **All writes attributed to the operator actor** (`kind="human"`), resolved once at startup.
- **WCAG 2.2 AA** target; the live-region/focus/aria contracts in §4.1 of the spec are mandatory, not optional.
- **Gate:** `make ci` must stay green — ruff clean, **mypy --strict**, pytest with **≥ 90% coverage**. Run it before every commit that touches `src/`.
- **`ErrorCode` values** (verbatim, from `src/plainweave/errors.py`): `VALIDATION, NOT_FOUND, CONFLICT, POLICY_REQUIRED, PEER_ABSENT, PEER_STALE, PEER_CONTRACT, LOCKED, UNSUPPORTED, INTERNAL`.

---

## File Structure

**Create:**
- `src/plainweave/web/__init__.py` — marks the subpackage; no runtime imports of starlette at module top (lazy).
- `src/plainweave/web/server.py` — `run_web(...)` (uvicorn launch + open browser), the missing-extra guard, and `add_web_subcommand(subparsers)` for the CLI.
- `src/plainweave/web/context.py` — `RequestContext`: service wiring, operator-actor resolution/registration, CSRF helpers.
- `src/plainweave/web/app.py` — `create_app(...)` Starlette factory: routes, Jinja env, static mount, exception handler, CSRF middleware.
- `src/plainweave/web/errors.py` — `error_to_response(...)`: `PlainweaveError`/`ErrorCode` → HTTP status + rendered error page.
- `src/plainweave/web/views.py` — pure view-model builders (corpus rows, dossier sections, coverage banner, queue items). Keeps handlers thin and gives unit-testable functions.
- `src/plainweave/web/routes/__init__.py`
- `src/plainweave/web/routes/requirements.py` — corpus, detail, inline expand, new/edit.
- `src/plainweave/web/routes/review.py` — review queue, approve, accept/reject, drift confirm.
- `src/plainweave/web/routes/intent.py` — coverage + orphans dashboard.
- `src/plainweave/web/routes/goals.py` — goals list/create, ladder.
- `src/plainweave/web/templates/…` — `base.html`, page templates, `_partials/…`.
- `src/plainweave/web/static/htmx.min.js`, `src/plainweave/web/static/app.css`.
- `tests/web/…` — one test module per route module + `test_context.py`, `test_errors.py`, `test_server.py`, `conftest.py` (fixtures).

**Modify:**
- `pyproject.toml` — add `[project.optional-dependencies] web`, the Jinja2 template package-data, and `web` to the wheel.
- `src/plainweave/cli.py` — call `add_web_subcommand(subparsers)` (lazy; no web import at parse time).

---

## Phase 0 — Foundation

### Task 1: Packaging extra + lazy `plainweave web` CLI

**Files:**
- Modify: `pyproject.toml`
- Create: `src/plainweave/web/__init__.py`, `src/plainweave/web/server.py`
- Modify: `src/plainweave/cli.py:14-19`
- Test: `tests/web/__init__.py`, `tests/web/test_server.py`

**Interfaces:**
- Produces: `add_web_subcommand(subparsers: argparse._SubParsersAction) -> None`; `run_web(*, host: str, port: int, actor: str | None, open_browser: bool, root: Path | None = None) -> int`; `WEB_EXTRA_HINT: str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_server.py
from __future__ import annotations

import argparse

from plainweave.web import server


def test_web_subcommand_parses_defaults():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    server.add_web_subcommand(sub)
    args = parser.parse_args(["web"])
    assert args.command == "web"
    assert args.host == "127.0.0.1"
    assert args.port == 8765
    assert args.open_browser is True
    assert callable(args.handler)


def test_run_web_without_starlette_prints_hint(monkeypatch, capsys):
    # Simulate the optional extra being absent.
    def boom() -> None:
        raise ModuleNotFoundError("No module named 'starlette'")

    monkeypatch.setattr(server, "_serve", boom)
    rc = server.run_web(host="127.0.0.1", port=8765, actor=None, open_browser=False)
    out = capsys.readouterr().out
    assert rc == 1
    assert "pip install plainweave[web]" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/web/test_server.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plainweave.web'`.

- [ ] **Step 3: Create the package + server stub**

```python
# src/plainweave/web/__init__.py
"""Optional operator-facing web tier (the plainweave[web] extra)."""
```

```python
# src/plainweave/web/server.py
from __future__ import annotations

import argparse
from pathlib import Path

WEB_EXTRA_HINT = (
    "The web UI needs the optional 'web' extra. Install it with:\n"
    "    pip install plainweave[web]\n"
    "(or: uv pip install 'plainweave[web]')"
)


def add_web_subcommand(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("web", help="Run the operator-facing web UI (needs plainweave[web]).")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765).")
    parser.add_argument("--actor", default=None, help="Operator actor id (default: from config / first-run).")
    parser.add_argument(
        "--no-open",
        dest="open_browser",
        action="store_false",
        help="Do not open a browser on start.",
    )
    parser.set_defaults(open_browser=True, handler=_handle)


def _handle(args: argparse.Namespace) -> int:
    return run_web(host=args.host, port=args.port, actor=args.actor, open_browser=args.open_browser)


def run_web(*, host: str, port: int, actor: str | None, open_browser: bool, root: Path | None = None) -> int:
    try:
        return _serve(host=host, port=port, actor=actor, open_browser=open_browser, root=root)
    except ModuleNotFoundError:
        print(WEB_EXTRA_HINT)
        return 1


def _serve(*, host: str, port: int, actor: str | None, open_browser: bool, root: Path | None = None) -> int:
    # Lazy import: only touches starlette/uvicorn when the extra is installed.
    import uvicorn  # noqa: PLC0415

    from plainweave.web.app import create_app  # noqa: PLC0415

    app = create_app(actor=actor, root=root)
    if open_browser:
        _open_browser_later(host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def _open_browser_later(host: str, port: int) -> None:
    import threading
    import webbrowser

    url = f"http://{host}:{port}/"
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
```

- [ ] **Step 4: Wire the CLI subcommand (lazy)**

In `src/plainweave/cli.py`, change `build_parser` to register the web subcommand without importing the web tier at module load:

```python
# src/plainweave/cli.py  (build_parser body, after register_commands(subparsers))
    register_commands(subparsers)
    from plainweave.web.server import add_web_subcommand  # local import keeps web optional

    add_web_subcommand(subparsers)
    return parser
```

- [ ] **Step 5: Add the optional extra + package data to pyproject.toml**

```toml
# pyproject.toml — add under [project]
[project.optional-dependencies]
web = [
    "starlette>=0.37",
    "uvicorn>=0.30",
    "jinja2>=3.1",
]
```

```toml
# pyproject.toml — ensure templates/static ship in the wheel
[tool.hatch.build.targets.wheel]
packages = ["src/plainweave"]

[tool.hatch.build.targets.wheel.force-include]
"src/plainweave/web/templates" = "plainweave/web/templates"
"src/plainweave/web/static" = "plainweave/web/static"
```

- [ ] **Step 6: Run tests + gate**

Run: `pytest tests/web/test_server.py -v && make ci`
Expected: PASS; ruff/mypy/coverage green.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/plainweave/web/__init__.py src/plainweave/web/server.py src/plainweave/cli.py tests/web/
git commit -m "feat(web): add plainweave[web] extra and lazy 'plainweave web' CLI"
```

---

### Task 2: Request context — operator actor + CSRF

**Files:**
- Create: `src/plainweave/web/context.py`
- Test: `tests/web/conftest.py`, `tests/web/test_context.py`

**Interfaces:**
- Consumes: `plainweave.service.PlainweaveService`, `plainweave.paths.plainweave_db_path`, `plainweave.store` init.
- Produces:
  - `OperatorIdentity(actor_id: str, display_name: str, kind: str)`
  - `RequestContext.from_root(root: Path | None, *, actor: str | None) -> RequestContext`
  - `RequestContext.service -> PlainweaveService`, `.operator -> OperatorIdentity`
  - `new_csrf_token() -> str`, `csrf_ok(cookie_token: str | None, form_token: str | None) -> bool`
  - `DEFAULT_OPERATOR_ID = "human:operator"`

- [ ] **Step 1: Write the failing tests**

```python
# tests/web/conftest.py
from __future__ import annotations

from pathlib import Path

import pytest

from plainweave.paths import plainweave_db_path
from plainweave.store import init_store  # existing store initializer


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    # Initialize a fresh local store under a temp root.
    init_store(plainweave_db_path(tmp_path))
    return tmp_path
```

```python
# tests/web/test_context.py
from __future__ import annotations

from plainweave.web import context as ctx


def test_operator_self_registers_at_genesis(project_root):
    rc = ctx.RequestContext.from_root(project_root, actor="human:alice")
    assert rc.operator.actor_id == "human:alice"
    assert rc.operator.kind == "human"
    # The actor is now a registered human in the store.
    actors = {a.actor_id: a for a in rc.service.list_actors()}
    assert actors["human:alice"].kind == "human"


def test_default_operator_used_when_actor_omitted(project_root):
    rc = ctx.RequestContext.from_root(project_root, actor=None)
    assert rc.operator.actor_id == ctx.DEFAULT_OPERATOR_ID


def test_csrf_roundtrip():
    token = ctx.new_csrf_token()
    assert ctx.csrf_ok(token, token) is True
    assert ctx.csrf_ok(token, "other") is False
    assert ctx.csrf_ok(None, token) is False
```

> **Note:** confirm the store initializer name (`init_store`) and `service.list_actors()` exist; if the actual names differ (e.g. `read_schema_meta`/a migration entrypoint, or no `list_actors`), adapt the fixture and assertion to the real API discovered in `store.py`/`service.py`. The behavior under test does not change.

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/web/test_context.py -v`
Expected: FAIL — `plainweave.web.context` missing.

- [ ] **Step 3: Implement the context**

```python
# src/plainweave/web/context.py
from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.paths import plainweave_db_path
from plainweave.service import PlainweaveService

DEFAULT_OPERATOR_ID = "human:operator"


@dataclass(frozen=True)
class OperatorIdentity:
    actor_id: str
    display_name: str
    kind: str


class RequestContext:
    def __init__(self, service: PlainweaveService, operator: OperatorIdentity) -> None:
        self.service = service
        self.operator = operator

    @classmethod
    def from_root(cls, root: Path | None, *, actor: str | None) -> RequestContext:
        service = PlainweaveService(plainweave_db_path(root), root=root)
        actor_id = actor or DEFAULT_OPERATOR_ID
        display = actor_id.split(":", 1)[-1] or actor_id
        operator = cls._ensure_operator(service, actor_id, display)
        return cls(service, operator)

    @staticmethod
    def _ensure_operator(service: PlainweaveService, actor_id: str, display: str) -> OperatorIdentity:
        # Register the operator as a human actor. At genesis (no attester yet) this
        # self-registration is permitted; once an attester exists, only an existing
        # attester may (re)register a human — surface that clearly rather than crashing.
        try:
            service.register_actor(actor_id, kind="human", display_name=display, actor=actor_id)
        except PlainweaveError as exc:
            if exc.code is ErrorCode.POLICY_REQUIRED:
                raise PlainweaveError(
                    ErrorCode.POLICY_REQUIRED,
                    f"operator actor {actor_id!r} is not a registered human and cannot self-register "
                    "(an attester already exists). Register it via the CLI before launching the web UI.",
                    recoverable=False,
                    hint="plainweave actor register --id <id> --kind human --actor <existing-attester>",
                ) from exc
            raise
        return OperatorIdentity(actor_id=actor_id, display_name=display, kind="human")


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_ok(cookie_token: str | None, form_token: str | None) -> bool:
    if not cookie_token or not form_token:
        return False
    return secrets.compare_digest(cookie_token, form_token)
```

- [ ] **Step 4: Run tests + gate**

Run: `pytest tests/web/test_context.py -v && make ci`
Expected: PASS; gate green.

- [ ] **Step 5: Commit**

```bash
git add src/plainweave/web/context.py tests/web/conftest.py tests/web/test_context.py
git commit -m "feat(web): request context with operator-actor resolution and CSRF helpers"
```

---

### Task 3: Error mapping + app factory + base layout

**Files:**
- Create: `src/plainweave/web/errors.py`, `src/plainweave/web/app.py`, `src/plainweave/web/templates/base.html`, `src/plainweave/web/templates/_partials/error.html`, `src/plainweave/web/static/app.css`, `src/plainweave/web/static/htmx.min.js` (vendor ≥1.9)
- Test: `tests/web/test_errors.py`, `tests/web/test_app.py`

**Interfaces:**
- Consumes: `RequestContext`, `new_csrf_token`, `csrf_ok`.
- Produces: `error_to_status(code: ErrorCode) -> int`; `create_app(*, actor: str | None, root: Path | None) -> Starlette`; the app exposes `app.state.ctx_factory` returning a `RequestContext`; a CSRF cookie named `pw_csrf`; templates env at `app.state.templates`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/web/test_errors.py
from __future__ import annotations

from plainweave.errors import ErrorCode
from plainweave.web.errors import error_to_status


def test_error_status_mapping():
    assert error_to_status(ErrorCode.VALIDATION) == 400
    assert error_to_status(ErrorCode.NOT_FOUND) == 404
    assert error_to_status(ErrorCode.CONFLICT) == 409
    assert error_to_status(ErrorCode.INVALID_TRANSITION) == 409 if hasattr(ErrorCode, "INVALID_TRANSITION") else True
    assert error_to_status(ErrorCode.POLICY_REQUIRED) == 409
    assert error_to_status(ErrorCode.INTERNAL) == 500
```

```python
# tests/web/test_app.py
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from plainweave.web.app import create_app


@pytest.fixture
def client(project_root):
    app = create_app(actor="human:alice", root=project_root)
    return TestClient(app)


def test_app_boots_and_sets_csrf_cookie(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert "pw_csrf" in resp.cookies


def test_unknown_path_404(client):
    assert client.get("/no-such-page").status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/web/test_errors.py tests/web/test_app.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement the error mapper**

```python
# src/plainweave/web/errors.py
from __future__ import annotations

from plainweave.errors import ErrorCode

_STATUS = {
    ErrorCode.VALIDATION: 400,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.POLICY_REQUIRED: 409,
    ErrorCode.LOCKED: 409,
    ErrorCode.PEER_ABSENT: 503,
    ErrorCode.PEER_STALE: 503,
    ErrorCode.PEER_CONTRACT: 502,
    ErrorCode.UNSUPPORTED: 400,
    ErrorCode.INTERNAL: 500,
}


def error_to_status(code: ErrorCode) -> int:
    return _STATUS.get(code, 500)
```

> If `ErrorCode` has no `INVALID_TRANSITION` member (it does not in the current enum), drop that assertion line from `test_errors.py`.

- [ ] **Step 4: Implement the app factory**

```python
# src/plainweave/web/app.py
from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
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

    async def csrf_mw(request: Request, call_next):
        token = request.cookies.get(_CSRF_COOKIE)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            form = await request.form()
            if not csrf_ok(token, form.get("_csrf")):
                return PlainTextResponse("CSRF check failed", status_code=403)
        response = await call_next(request)
        if token is None:
            token = new_csrf_token()
            response.set_cookie(_CSRF_COOKIE, token, httponly=True, samesite="strict")
        return response

    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware

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
    # Routers added in later tasks call app.router.routes.append(...) via register_*(app).
    from plainweave.web.routes import register_all

    register_all(app)
    return app
```

```python
# src/plainweave/web/routes/__init__.py
from __future__ import annotations

from starlette.applications import Starlette


def register_all(app: Starlette) -> None:
    # Each route module appends its routes; populated as tasks land.
    from plainweave.web.routes import goals, intent, requirements, review

    requirements.register(app)
    intent.register(app)
    review.register(app)
    goals.register(app)
```

> Until later tasks add the route modules, create minimal `register(app: Starlette) -> None: ...` stubs in each `routes/*.py` so the import resolves. Each subsequent task replaces its stub.

- [ ] **Step 5: Create base layout + error partial + static**

```html
{# src/plainweave/web/templates/base.html #}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Plainweave{% endblock %}</title>
  <link rel="stylesheet" href="/static/app.css">
  <script src="/static/htmx.min.js" defer></script>
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to content</a>

  <nav aria-label="Main navigation" class="topnav">
    <a href="/" {% if active_page == 'corpus' %}aria-current="page"{% endif %}>Corpus</a>
    <a href="/review" {% if active_page == 'review' %}aria-current="page"{% endif %}>
      Review
      <span id="review-badge" class="nav-badge">{% if pending_count %}{{ pending_count }}{% endif %}</span>
    </a>
    <a href="/intent" {% if active_page == 'intent' %}aria-current="page"{% endif %}>Intent</a>
    <a href="/goals" {% if active_page == 'goals' %}aria-current="page"{% endif %}>Goals</a>
    <span class="operator">operator: {{ operator.display_name }} · {{ operator.kind }}</span>
  </nav>

  {# Permanent SR status live region — NEVER replaced via outerHTML; innerHTML-OOB only. #}
  <div id="sr-status" role="status" aria-live="polite" aria-atomic="true" class="visually-hidden"></div>
  {# Decorative global loader; status comes from #sr-status, so this is aria-hidden. #}
  <div id="global-loader" class="htmx-indicator" aria-hidden="true"><span class="loader-spinner"></span></div>

  <main id="main-content">
    {% block main %}{% endblock %}
  </main>
</body>
</html>
```

```html
{# src/plainweave/web/templates/_partials/error.html #}
<main id="main-content" class="error-page">
  <h1>Something went wrong</h1>
  <p class="error-code">{{ code }}</p>
  <p>{{ message }}</p>
  {% if hint %}<p class="error-hint">{{ hint }}</p>{% endif %}
  <p><a href="/">Back to corpus</a></p>
</main>
```

```css
/* src/plainweave/web/static/app.css */
:root { --amber: #c47b1a; --warn-bg: #fdf3e3; --line: #d9d9d9; }
body { font-family: system-ui, sans-serif; margin: 0; color: #1c1c1c; font-size: 16px; }
.visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
.skip-link { position: absolute; left: -999px; }
.skip-link:focus { left: 1rem; top: 0.5rem; background: #fff; padding: 0.5rem; }
.topnav { display: flex; gap: 1rem; align-items: center; padding: 0.6rem 1rem; border-bottom: 1px solid var(--line); }
.topnav a[aria-current="page"] { font-weight: 700; text-decoration: underline; }
.nav-badge:not(:empty) { background: #b00; color: #fff; border-radius: 8px; padding: 0 6px; font-size: 0.75rem; }
.operator { margin-left: auto; opacity: 0.7; font-size: 0.85rem; }
main { padding: 1rem; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { text-align: left; padding: 6px 8px; border-top: 1px solid var(--line); }
.htmx-indicator { opacity: 0; transition: opacity 0.1s; }
.htmx-request .htmx-indicator, .htmx-indicator.htmx-request { opacity: 1; }
.queue-item--drifted { border: 1px solid var(--amber); border-left-width: 4px; background: var(--warn-bg); padding: 0.6rem; }
.drift-badge { display: inline-block; background: var(--amber); color: #fff; font-size: 0.7rem; font-weight: 700; padding: 1px 7px; border-radius: 4px; }
.toggle-btn { border: 1px solid var(--line); border-radius: 4px; padding: 3px 9px; font-size: 0.8rem; }
.toggle-btn--active { border-width: 2px; font-weight: 700; }
.toggle-btn--active::before { content: "✓ "; }
```

Vendor HTMX: download `htmx.min.js` (≥1.9) into `src/plainweave/web/static/htmx.min.js`.

Run: `curl -sL https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js -o src/plainweave/web/static/htmx.min.js`
Expected: a ~40KB file; verify the first line contains the version banner.

- [ ] **Step 6: Run tests + gate**

Run: `pytest tests/web/ -v && make ci`
Expected: PASS; gate green.

- [ ] **Step 7: Commit**

```bash
git add src/plainweave/web/ tests/web/test_errors.py tests/web/test_app.py
git commit -m "feat(web): app factory, PlainweaveError->HTTP mapping, base layout, CSRF middleware"
```

---

## Phase 1 — Read surfaces

### Task 4: Corpus browse + search/status/orphan filters

**Files:**
- Create: `src/plainweave/web/templates/corpus.html`, `src/plainweave/web/templates/_partials/corpus_rows.html`, `src/plainweave/web/templates/_partials/corpus_filter.html`
- Modify: `src/plainweave/web/views.py` (create), `src/plainweave/web/routes/requirements.py`
- Test: `tests/web/test_requirements.py`

**Interfaces:**
- Consumes: `service.intent_corpus()` → `list[CorpusEntry]` (each entry has `.requirement.node_id`, `.goals` tuple, `.code` tuple); `service.search_requirements()` → `list[RequirementRecord]` (has `.requirement_id`, `.id` display, `.status`, `.current_version_record.title` or active draft title).
- Produces: `views.CorpusRow(req_id, display_id, title, status, goal_count, code_count)`; `views.build_corpus_rows(corpus, records) -> list[CorpusRow]`; `views.filter_rows(rows, *, q, status, orphan) -> list[CorpusRow]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_requirements.py
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from plainweave.web.app import create_app


@pytest.fixture
def client(project_root):
    return TestClient(create_app(actor="human:alice", root=project_root))


def _mint(client, title, statement):
    # Author a draft requirement through the (later) new-req route; for this test
    # seed via the service directly to keep the test focused on rendering.
    ctx = client.app.state.ctx_factory()
    return ctx.service.create_requirement(title, statement, actor="human:alice")


def test_corpus_lists_requirements(client):
    _mint(client, "Coverage is self-computable", "answers why this exists")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Coverage is self-computable" in resp.text


def test_corpus_orphan_filter_no_goal(client):
    _mint(client, "Orphan req", "no goal yet")
    resp = client.get("/", params={"orphan": "no-goal"})
    assert "Orphan req" in resp.text
    # status filter excludes it
    resp2 = client.get("/", params={"status": "approved"})
    assert "Orphan req" not in resp2.text
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/web/test_requirements.py -v`
Expected: FAIL — route `/` returns 404 (stub) / view missing.

- [ ] **Step 3: Add view models**

```python
# src/plainweave/web/views.py
from __future__ import annotations

from dataclasses import dataclass

from plainweave.intent_graph import CorpusEntry
from plainweave.models import RequirementRecord


@dataclass(frozen=True)
class CorpusRow:
    req_id: str
    display_id: str
    title: str
    status: str
    goal_count: int
    code_count: int


def _title_of(record: RequirementRecord) -> str:
    cur = record.current_version_record
    return cur.title if cur is not None else record.id


def build_corpus_rows(corpus: list[CorpusEntry], records: list[RequirementRecord]) -> list[CorpusRow]:
    by_id = {r.requirement_id: r for r in records}
    rows: list[CorpusRow] = []
    for entry in corpus:
        rid = entry.requirement.node_id
        rec = by_id.get(rid)
        if rec is None:
            continue
        rows.append(
            CorpusRow(
                req_id=rid,
                display_id=rec.id,
                title=_title_of(rec),
                status=rec.status,
                goal_count=len(entry.goals),
                code_count=len(entry.code),
            )
        )
    return rows


def filter_rows(rows: list[CorpusRow], *, q: str, status: str, orphan: str) -> list[CorpusRow]:
    out = rows
    if q:
        needle = q.lower()
        out = [r for r in out if needle in r.title.lower() or needle in r.display_id.lower()]
    if status:
        out = [r for r in out if r.status == status]
    if orphan == "no-goal":
        out = [r for r in out if r.goal_count == 0]
    elif orphan == "no-code":
        out = [r for r in out if r.code_count == 0]
    elif orphan == "both":
        out = [r for r in out if r.goal_count == 0 and r.code_count == 0]
    return out
```

- [ ] **Step 4: Add the route + templates**

```python
# src/plainweave/web/routes/requirements.py
from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from plainweave.web import views


async def corpus(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    q = request.query_params.get("q", "")
    status = request.query_params.get("status", "")
    orphan = request.query_params.get("orphan", "")
    rows = views.build_corpus_rows(ctx.service.intent_corpus(), ctx.service.search_requirements())
    rows = views.filter_rows(rows, q=q, status=status, orphan=orphan)
    template = "_partials/corpus_rows.html" if request.headers.get("HX-Request") else "corpus.html"
    return request.app.state.templates.TemplateResponse(
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
```

```html
{# src/plainweave/web/templates/corpus.html #}
{% extends "base.html" %}
{% set active_page = "corpus" %}
{% block title %}Corpus · Plainweave{% endblock %}
{% block main %}
<h1>Corpus</h1>
{% include "_partials/corpus_filter.html" %}
<table>
  <thead>
    <tr><th scope="col">Requirement</th><th scope="col">Status</th><th scope="col">Goal</th><th scope="col">Code links</th></tr>
  </thead>
  <tbody id="corpus-rows">
    {% include "_partials/corpus_rows.html" %}
  </tbody>
</table>
{% endblock %}
```

```html
{# src/plainweave/web/templates/_partials/corpus_filter.html #}
<search aria-label="Corpus requirements">
  <form hx-get="/" hx-target="#corpus-rows" hx-swap="innerHTML"
        hx-indicator="#global-loader"
        hx-trigger="change, input changed delay:300ms from:#req-search">
    <label for="req-search">Search requirements</label>
    <input id="req-search" type="search" name="q" value="{{ filters.q }}"
           placeholder="keyword or ID" autocomplete="off">

    <fieldset class="filter-toggles">
      <legend>Status</legend>
      {% for value, label in [("", "All"), ("approved", "Approved"), ("draft", "Draft"), ("deprecated", "Deprecated")] %}
      <label class="toggle-btn{% if filters.status == value %} toggle-btn--active{% endif %}">
        <input class="visually-hidden" type="radio" name="status" value="{{ value }}" {% if filters.status == value %}checked{% endif %}>{{ label }}
      </label>
      {% endfor %}
    </fieldset>

    <fieldset class="filter-toggles">
      <legend>Orphans</legend>
      {% for value, label in [("", "Any"), ("no-goal", "No goal"), ("no-code", "No code"), ("both", "Both")] %}
      <label class="toggle-btn{% if filters.orphan == value %} toggle-btn--active{% endif %}">
        <input class="visually-hidden" type="radio" name="orphan" value="{{ value }}" {% if filters.orphan == value %}checked{% endif %}>{{ label }}
      </label>
      {% endfor %}
    </fieldset>
  </form>
</search>
```

```html
{# src/plainweave/web/templates/_partials/corpus_rows.html #}
{% for row in rows %}
<tr class="corpus-row" hx-get="/req/{{ row.req_id }}/inline" hx-target="#req-detail-{{ row.req_id }}" hx-swap="innerHTML" style="cursor:pointer">
  <td>{{ row.title }} <span class="muted">{{ row.display_id }}</span></td>
  <td>{{ row.status }}</td>
  <td>{% if row.goal_count %}{{ row.goal_count }}{% else %}<span class="warn">none</span>{% endif %}</td>
  <td>{% if row.code_count %}{{ row.code_count }}{% else %}<span class="warn">none</span>{% endif %}</td>
</tr>
<tr class="corpus-row-detail"><td colspan="4"><div id="req-detail-{{ row.req_id }}"></div></td></tr>
{% else %}
<tr><td colspan="4">No requirements match the current filters.</td></tr>
{% endfor %}
```

- [ ] **Step 5: Run tests + gate**

Run: `pytest tests/web/test_requirements.py -v && make ci`
Expected: PASS; gate green.

- [ ] **Step 6: Commit**

```bash
git add src/plainweave/web/views.py src/plainweave/web/routes/requirements.py src/plainweave/web/templates/corpus.html src/plainweave/web/templates/_partials/corpus_filter.html src/plainweave/web/templates/_partials/corpus_rows.html tests/web/test_requirements.py
git commit -m "feat(web): corpus browse with search/status/orphan filters"
```

---

### Task 5: Corpus inline multi-row expand

**Files:**
- Modify: `src/plainweave/web/routes/requirements.py`
- Create: `src/plainweave/web/templates/_partials/req_inline.html`
- Test: extend `tests/web/test_requirements.py`

**Interfaces:**
- Consumes: `service.get_requirement(req_id)`, `service.requirement_dossier(req_id)` (for statement).
- Produces: routes `GET /req/{req_id}/inline`, `GET /req/{req_id}/inline/collapsed`.

- [ ] **Step 1: Write the failing test**

```python
def test_inline_expand_independent_targets(client):
    a = _mint(client, "Alpha req", "alpha statement body")
    b = _mint(client, "Beta req", "beta statement body")
    ra = client.get(f"/req/{a.requirement_id}/inline")
    assert ra.status_code == 200
    assert "alpha statement body" in ra.text
    assert f'id="req-detail-{a.requirement_id}"' not in ra.text  # partial targets the existing row div, not nested
    rb = client.get(f"/req/{b.requirement_id}/inline")
    assert "beta statement body" in rb.text
    # collapse returns empty
    rc = client.get(f"/req/{a.requirement_id}/inline/collapsed")
    assert rc.status_code == 200
    assert rc.text.strip() == ""
```

- [ ] **Step 2: Run to verify failure** — Run: `pytest tests/web/test_requirements.py::test_inline_expand_independent_targets -v` · Expected: FAIL (404).

- [ ] **Step 3: Add handlers + partial**

```python
# add to src/plainweave/web/routes/requirements.py
async def req_inline(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    req_id = request.path_params["req_id"]
    dossier = ctx.service.requirement_dossier(req_id)
    section = dossier.requirement
    statement = (
        section.active_draft.statement if section.active_draft
        else (section.current_version.statement if section.current_version else "")
    )
    return request.app.state.templates.TemplateResponse(
        request, "_partials/req_inline.html",
        {"req_id": req_id, "statement": statement, "status": dossier.requirement.record.status},
    )


async def req_inline_collapsed(request: Request) -> Response:
    from starlette.responses import HTMLResponse
    return HTMLResponse("")
```

Append to `register(app)`:

```python
    app.router.routes.append(Route("/req/{req_id}/inline", req_inline, name="req_inline"))
    app.router.routes.append(Route("/req/{req_id}/inline/collapsed", req_inline_collapsed, name="req_inline_collapsed"))
```

```html
{# src/plainweave/web/templates/_partials/req_inline.html #}
<div class="req-inline">
  <p class="req-inline__statement">{{ statement }}</p>
  <div class="req-inline__actions">
    <a href="/req/{{ req_id }}">Full dossier →</a>
    <button type="button" hx-get="/req/{{ req_id }}/inline/collapsed" hx-target="#req-detail-{{ req_id }}" hx-swap="innerHTML">▲ Collapse</button>
  </div>
</div>
```

> Confirm `requirement_dossier(...).requirement` exposes `.record.status`, `.current_version`, `.active_draft` (per `DossierRequirementSection` in `models.py`). Adjust attribute access to the real dataclass if names differ.

- [ ] **Step 4: Run + gate** — Run: `pytest tests/web/test_requirements.py -v && make ci` · Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/plainweave/web/routes/requirements.py src/plainweave/web/templates/_partials/req_inline.html tests/web/test_requirements.py
git commit -m "feat(web): corpus inline expand with independent per-row targets"
```

---

### Task 6: Requirement detail (current vs draft)

**Files:** Modify `routes/requirements.py`; Create `templates/requirement_detail.html`; Test extends `test_requirements.py`.

**Interfaces:** Consumes `service.requirement_dossier(req_id) -> RequirementDossier`. Produces route `GET /req/{req_id}`.

- [ ] **Step 1: Failing test**

```python
def test_requirement_detail_renders_statement(client):
    r = _mint(client, "Detail req", "the full detail statement")
    resp = client.get(f"/req/{r.requirement_id}")
    assert resp.status_code == 200
    assert "Detail req" in resp.text
    assert "the full detail statement" in resp.text
```

- [ ] **Step 2: Run to verify failure** — Expected: 404.

- [ ] **Step 3: Handler + template**

```python
# add to routes/requirements.py
async def req_detail(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    req_id = request.path_params["req_id"]
    dossier = ctx.service.requirement_dossier(req_id)
    return request.app.state.templates.TemplateResponse(
        request, "requirement_detail.html",
        {"dossier": dossier, "req_id": req_id, "operator": ctx.operator, "active_page": "corpus"},
    )
```

Append route (place BEFORE `/req/{req_id}/inline`? No — Starlette matches in order; `/req/{req_id}` and `/req/{req_id}/inline` are distinct paths, order-independent):

```python
    app.router.routes.append(Route("/req/{req_id}", req_detail, name="req_detail"))
```

```html
{# src/plainweave/web/templates/requirement_detail.html #}
{% extends "base.html" %}
{% set active_page = "corpus" %}
{% set section = dossier.requirement %}
{% block title %}{{ section.record.id }} · Plainweave{% endblock %}
{% block main %}
<h1>{% if section.current_version %}{{ section.current_version.title }}{% elif section.active_draft %}{{ section.active_draft.title }}{% endif %}
  <span class="muted">{{ section.record.id }} · {{ section.record.status }}</span></h1>

{% if section.current_version %}
<section><h2>Current approved — v{{ section.current_version.version }}</h2>
  <p>{{ section.current_version.statement }}</p></section>
{% endif %}
{% if section.active_draft %}
<section class="draft"><h2>Draft{% if section.current_version %} (proposed changes){% else %} (new — no approved version yet){% endif %}</h2>
  <p>{{ section.active_draft.statement }}</p>
  <p><a href="/req/{{ req_id }}/edit">Edit draft</a></p>
  <div id="dossier-approve-slot">
    <button type="button" hx-get="/req/{{ req_id }}/approve-confirm" hx-target="#dossier-approve-slot" hx-swap="innerHTML">Approve this draft</button>
  </div>
</section>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Run + gate** — Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add src/plainweave/web/routes/requirements.py src/plainweave/web/templates/requirement_detail.html tests/web/test_requirements.py
git commit -m "feat(web): requirement detail showing current vs draft side by side"
```

---

### Task 7: Intent dashboard (coverage + orphans + degraded banner)

**Files:** Create `routes/intent.py`, `templates/intent.html`; Modify `views.py`; Test `tests/web/test_intent.py`.

**Interfaces:** Consumes `service.intent_coverage()` → `IntentCoverage` (`.numerator`, `.denominator`, `.ratio`, `.denominator_complete`, `.adapter_degraded`, `.coverage`); `service.intent_orphans(level)` → `list[IntentNode]`. Produces `views.coverage_banner(cov) -> str | None`; route `GET /intent`.

- [ ] **Step 1: Failing test**

```python
# tests/web/test_intent.py
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from plainweave.web.app import create_app
from plainweave.web import views


@pytest.fixture
def client(project_root):
    return TestClient(create_app(actor="human:alice", root=project_root))


def test_intent_dashboard_renders(client):
    resp = client.get("/intent")
    assert resp.status_code == 200
    assert "Coverage" in resp.text


def test_degraded_banner_when_denominator_incomplete():
    class _Cov:
        denominator_complete = False
        adapter_degraded = ({"reason": "loomweave catalog stale"},)
    assert views.coverage_banner(_Cov()) is not None

    class _Ok:
        denominator_complete = True
        adapter_degraded = ()
    assert views.coverage_banner(_Ok()) is None
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL.

- [ ] **Step 3: View + route + template**

```python
# add to src/plainweave/web/views.py
def coverage_banner(cov) -> str | None:
    if getattr(cov, "denominator_complete", True) and not getattr(cov, "adapter_degraded", ()):
        return None
    return "Coverage denominator is incomplete — the Loomweave catalog is absent or stale. This number is partial."
```

```python
# src/plainweave/web/routes/intent.py
from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from plainweave.intent_graph import IntentLevel
from plainweave.web import views


async def intent_dashboard(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    cov = ctx.service.intent_coverage()
    orphans = {
        level.value: ctx.service.intent_orphans(level)
        for level in (IntentLevel.CODE, IntentLevel.REQUIREMENT, IntentLevel.GOAL)
    }
    return request.app.state.templates.TemplateResponse(
        request, "intent.html",
        {"cov": cov, "banner": views.coverage_banner(cov), "orphans": orphans,
         "operator": ctx.operator, "active_page": "intent"},
    )


def register(app: Starlette) -> None:
    app.router.routes.append(Route("/intent", intent_dashboard, name="intent"))
```

```html
{# src/plainweave/web/templates/intent.html #}
{% extends "base.html" %}
{% set active_page = "intent" %}
{% block title %}Intent · Plainweave{% endblock %}
{% block main %}
<h1>Intent coverage</h1>
{% if banner %}<p class="banner banner--warn" role="status">{{ banner }}</p>{% endif %}
<p class="big-number">
  {% if cov.ratio is not none %}{{ "%.0f%%"|format(cov.ratio * 100) }}{% else %}—{% endif %}
  <span class="muted">{{ cov.numerator }}/{{ cov.denominator }} public surfaces answer "why does this exist?"</span>
</p>
{% for level, nodes in orphans.items() %}
<section><h2>Orphans — {{ level }} ({{ nodes|length }})</h2>
  <ul>{% for n in nodes %}<li>{{ n.node_id }}</li>{% endfor %}</ul>
</section>
{% endfor %}
{% endblock %}
```

- [ ] **Step 4: Run + gate** — Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add src/plainweave/web/routes/intent.py src/plainweave/web/templates/intent.html src/plainweave/web/views.py tests/web/test_intent.py
git commit -m "feat(web): intent dashboard with coverage, orphans, and no-silent-clean banner"
```

---

### Task 8: Goals list (read)

**Files:** Create `routes/goals.py`, `templates/goals.html`; Test `tests/web/test_goals.py`.

**Interfaces:** Consumes a goals-list read (confirm exact verb in `service.py`; candidates: `list_goals()` / a goals query — discover and use the real one) and `service.intent_orphans(IntentLevel.GOAL)`. Produces route `GET /goals`.

- [ ] **Step 1: Failing test**

```python
# tests/web/test_goals.py
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from plainweave.web.app import create_app


@pytest.fixture
def client(project_root):
    return TestClient(create_app(actor="human:alice", root=project_root))


def test_goals_page_lists_created_goal(client):
    ctx = client.app.state.ctx_factory()
    ctx.service.create_goal("Be self-computable", "the north-star goal", actor="human:alice")
    resp = client.get("/goals")
    assert resp.status_code == 200
    assert "Be self-computable" in resp.text
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL.

- [ ] **Step 3: Route + template** — discover the goals-list read in `service.py` (search for `def list_goals` / a `intent_goals` query). If none exists, add a thin `list_goals() -> list[IntentGoal]` read to `service.py` mirroring `list_baselines()` (one task-local addition, justified: the goals page needs it).

```python
# src/plainweave/web/routes/goals.py
from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from plainweave.intent_graph import IntentLevel


async def goals_page(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    goals = ctx.service.list_goals()  # confirm/add this read
    orphan_goal_ids = {n.node_id for n in ctx.service.intent_orphans(IntentLevel.GOAL)}
    return request.app.state.templates.TemplateResponse(
        request, "goals.html",
        {"goals": goals, "orphan_goal_ids": orphan_goal_ids, "operator": ctx.operator, "active_page": "goals"},
    )


def register(app: Starlette) -> None:
    app.router.routes.append(Route("/goals", goals_page, name="goals"))
```

```html
{# src/plainweave/web/templates/goals.html #}
{% extends "base.html" %}
{% set active_page = "goals" %}
{% block title %}Goals · Plainweave{% endblock %}
{% block main %}
<h1>Goals</h1>
<ul>
{% for g in goals %}
  <li>{{ g.title }} <span class="muted">{{ g.id }}</span>{% if g.goal_id in orphan_goal_ids %} <span class="warn">— no requirements ladder here</span>{% endif %}</li>
{% else %}
  <li>No goals yet.</li>
{% endfor %}
</ul>
{% endblock %}
```

- [ ] **Step 4: Run + gate** — Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add src/plainweave/web/routes/goals.py src/plainweave/web/templates/goals.html tests/web/test_goals.py src/plainweave/service.py
git commit -m "feat(web): goals list page (with list_goals read if needed)"
```

---

## Phase 2 — Authoring & review (writes)

### Task 9: New / Edit requirement + conflict-preserves-text

**Files:** Modify `routes/requirements.py`; Create `templates/requirement_form.html`, `_partials/edit_conflict.html`, `_partials/csrf.html`; Test extends `test_requirements.py`.

**Interfaces:** Consumes `service.create_requirement(title, statement, actor)`, `service.update_draft(req_id, actor=, title=, statement=, expected_draft_revision=)` (raises `PlainweaveError(CONFLICT)`), `service.requirement_dossier(req_id)`. Produces routes `GET/POST /req/new`, `GET/POST /req/{req_id}/edit`.

- [ ] **Step 1: Failing tests**

```python
def test_create_requirement(client):
    token = client.get("/").cookies.get("pw_csrf")  # ensure cookie set
    resp = client.post("/req/new", data={"title": "Newborn", "statement": "fresh shell", "_csrf": token})
    assert resp.status_code in (200, 303)
    assert "Newborn" in client.get("/").text


def test_edit_conflict_preserves_text(client):
    r = _mint(client, "Editable", "v1 body")
    token = client.get("/").cookies.get("pw_csrf")
    # submit a stale revision (0 when the real draft_revision is 1)
    resp = client.post(
        f"/req/{r.requirement_id}/edit",
        data={"title": "Editable", "statement": "MY UNSAVED EDIT", "expected_draft_revision": "0", "_csrf": token},
    )
    assert resp.status_code == 200            # NOT 409 — HTMX must be able to swap
    assert "MY UNSAVED EDIT" in resp.text     # operator's text echoed back
    assert "v1 body" in resp.text             # current draft shown alongside
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL.

- [ ] **Step 3: CSRF partial + form template**

```html
{# src/plainweave/web/templates/_partials/csrf.html #}
<input type="hidden" name="_csrf" value="{{ request.cookies.get('pw_csrf', '') }}">
```

```html
{# src/plainweave/web/templates/requirement_form.html #}
{% extends "base.html" %}
{% set active_page = "corpus" %}
{% block main %}
<h1>{% if req_id %}Edit draft{% else %}New requirement{% endif %}</h1>
<form method="post" action="{% if req_id %}/req/{{ req_id }}/edit{% else %}/req/new{% endif %}">
  {% include "_partials/csrf.html" %}
  {% if expected_draft_revision is not none %}<input type="hidden" name="expected_draft_revision" value="{{ expected_draft_revision }}">{% endif %}
  <label>Title<input type="text" name="title" value="{{ title or '' }}" required></label>
  <label>Statement<textarea name="statement" rows="6" required>{{ statement or '' }}</textarea></label>
  <button type="submit">Save</button>
</form>
{% endblock %}
```

```html
{# src/plainweave/web/templates/_partials/edit_conflict.html #}
<div id="edit-form-{{ req_id }}" class="conflict-panel">
  <p class="banner banner--warn" role="alert">Draft modified while you were editing. Your text is on the left — not discarded.</p>
  <div class="conflict-columns">
    <form hx-post="/req/{{ req_id }}/edit" hx-target="#edit-form-{{ req_id }}" hx-swap="outerHTML">
      {% include "_partials/csrf.html" %}
      <input type="hidden" name="expected_draft_revision" value="{{ fresh_revision }}">
      <h3>Your edits (not saved)</h3>
      <label>Title<input type="text" name="title" value="{{ submitted_title }}"></label>
      <label>Statement<textarea name="statement" rows="6">{{ submitted_statement }}</textarea></label>
      <button type="submit">Save my edits</button>
    </form>
    <div><h3>Current draft</h3><p><strong>{{ current_title }}</strong></p><p>{{ current_statement }}</p>
      <a href="/req/{{ req_id }}/edit">Discard mine — start from current</a></div>
  </div>
</div>
```

- [ ] **Step 4: Handlers (note the local CONFLICT catch)**

```python
# add to routes/requirements.py
from starlette.responses import RedirectResponse


async def req_new_get(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    return request.app.state.templates.TemplateResponse(
        request, "requirement_form.html",
        {"req_id": None, "title": "", "statement": "", "expected_draft_revision": None,
         "operator": ctx.operator, "active_page": "corpus"},
    )


async def req_new_post(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    form = await request.form()
    ctx.service.create_requirement(str(form["title"]), str(form["statement"]), actor=ctx.operator.actor_id)
    return RedirectResponse("/", status_code=303)


async def req_edit_get(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    req_id = request.path_params["req_id"]
    draft = ctx.service.requirement_dossier(req_id).requirement.active_draft
    return request.app.state.templates.TemplateResponse(
        request, "requirement_form.html",
        {"req_id": req_id, "title": draft.title, "statement": draft.statement,
         "expected_draft_revision": draft.draft_revision, "operator": ctx.operator, "active_page": "corpus"},
    )


async def req_edit_post(request: Request) -> Response:
    from plainweave.errors import ErrorCode, PlainweaveError
    ctx = request.app.state.ctx_factory()
    req_id = request.path_params["req_id"]
    form = await request.form()
    title, statement = str(form["title"]), str(form["statement"])
    expected = int(str(form.get("expected_draft_revision", "0")))
    try:
        ctx.service.update_draft(req_id, actor=ctx.operator.actor_id, title=title, statement=statement,
                                 expected_draft_revision=expected)
        return RedirectResponse(f"/req/{req_id}", status_code=303)
    except PlainweaveError as exc:
        if exc.code is not ErrorCode.CONFLICT:
            raise  # falls through to the global handler
        # Local catch: HTMX only swaps 2xx; return 200 with both texts preserved.
        draft = ctx.service.requirement_dossier(req_id).requirement.active_draft
        return request.app.state.templates.TemplateResponse(
            request, "_partials/edit_conflict.html",
            {"req_id": req_id, "submitted_title": title, "submitted_statement": statement,
             "current_title": draft.title, "current_statement": draft.statement,
             "fresh_revision": draft.draft_revision},
            status_code=200,
        )
```

Append routes:

```python
    app.router.routes.append(Route("/req/new", req_new_get, name="req_new"))
    app.router.routes.append(Route("/req/new", req_new_post, methods=["POST"]))
    app.router.routes.append(Route("/req/{req_id}/edit", req_edit_get, name="req_edit"))
    app.router.routes.append(Route("/req/{req_id}/edit", req_edit_post, methods=["POST"]))
```

> **Route ordering:** register `/req/new` BEFORE `/req/{req_id}` so "new" is not captured as a `req_id`. Verify in `register()` order.

- [ ] **Step 5: Run + gate** — Expected: PASS.
- [ ] **Step 6: Commit**

```bash
git add src/plainweave/web/routes/requirements.py src/plainweave/web/templates/requirement_form.html src/plainweave/web/templates/_partials/edit_conflict.html src/plainweave/web/templates/_partials/csrf.html tests/web/test_requirements.py
git commit -m "feat(web): create/edit requirement with conflict-preserves-text UX"
```

---

### Task 10: Goals create + ladder requirement→goal

**Files:** Modify `routes/goals.py`, `templates/goals.html`; Test extends `test_goals.py`.

**Interfaces:** Consumes `service.create_goal(title, statement, actor)`, `service.link_goal_to_requirement(goal_id, requirement_id, actor)`. Produces `POST /goals/new`, `POST /req/{req_id}/ladder`.

- [ ] **Step 1: Failing test**

```python
def test_create_goal_and_ladder(client):
    token = client.get("/goals").cookies.get("pw_csrf")
    client.post("/goals/new", data={"title": "Ladder target", "statement": "g", "_csrf": token})
    ctx = client.app.state.ctx_factory()
    req = ctx.service.create_requirement("Ladders up", "body", actor="human:alice")
    goals = ctx.service.list_goals()
    gid = goals[0].goal_id
    resp = client.post(f"/req/{req.requirement_id}/ladder", data={"goal_id": gid, "_csrf": token})
    assert resp.status_code in (200, 303)
    # the requirement now ladders to a goal → no longer a requirement-orphan
    from plainweave.intent_graph import IntentLevel
    orphan_ids = {n.node_id for n in ctx.service.intent_orphans(IntentLevel.REQUIREMENT)}
    assert req.requirement_id not in orphan_ids
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL.

- [ ] **Step 3: Handlers + form**

```python
# add to routes/goals.py
from starlette.responses import RedirectResponse


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
```

Append:

```python
    app.router.routes.append(Route("/goals/new", goals_new, methods=["POST"]))
    app.router.routes.append(Route("/req/{req_id}/ladder", req_ladder, methods=["POST"]))
```

Add a create-goal form to `goals.html` (above the list):

```html
<form method="post" action="/goals/new">
  {% include "_partials/csrf.html" %}
  <label>Goal title<input name="title" required></label>
  <label>Statement<input name="statement" required></label>
  <button type="submit">Create goal</button>
</form>
```

Add a ladder form to `requirement_detail.html` (in the draft/current section), listing goals via a context var `goals` (extend `req_detail` handler to pass `ctx.service.list_goals()`).

- [ ] **Step 4: Run + gate** — Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add src/plainweave/web/routes/goals.py src/plainweave/web/routes/requirements.py src/plainweave/web/templates/goals.html src/plainweave/web/templates/requirement_detail.html tests/web/test_goals.py
git commit -m "feat(web): create goals and ladder requirements to goals"
```

---

### Task 11: Review queue list (unified, type-badged, empty state)

**Files:** Create `routes/review.py`, `templates/review.html`, `_partials/queue_item_draft.html`, `_partials/queue_item_link.html`, `_partials/queue_empty.html`; Modify `views.py`; Test `tests/web/test_review.py`.

**Interfaces:** Consumes `service.search_requirements()` (pending = records with `active_draft_id`), `service.trace_for(state="proposed")` → `list[TraceLink]` (each has `.id`, `.from_ref`, `.relation`, `.to_ref`, `.authority`, `.freshness`, `.confidence`, `.created_by`), `service.requirement_dossier(req_id)` for draft text. Produces `views.pending_items(service) -> list[QueueItem]`; route `GET /review`.

- [ ] **Step 1: Failing tests**

```python
# tests/web/test_review.py
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from plainweave.models import TraceRef
from plainweave.web.app import create_app


@pytest.fixture
def client(project_root):
    return TestClient(create_app(actor="human:alice", root=project_root))


def test_empty_queue_state(client):
    resp = client.get("/review")
    assert resp.status_code == 200
    assert "All caught up" in resp.text


def test_queue_shows_pending_draft_and_proposed_link(client):
    ctx = client.app.state.ctx_factory()
    req = ctx.service.create_requirement("Pending draft", "body", actor="human:alice")
    ctx.service.propose_trace_link(
        TraceRef("code", "loomweave:eid:abc"), "satisfies",
        TraceRef("requirement", req.requirement_id), actor="agent:claude", confidence=0.8,
    )
    resp = client.get("/review")
    assert "Pending draft" in resp.text       # the draft card
    assert "DRAFT" in resp.text and "LINK" in resp.text
    assert "agent:claude" in resp.text        # proposing agent shown
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL.

- [ ] **Step 3: View model + route + templates**

```python
# add to src/plainweave/web/views.py
from dataclasses import dataclass as _dc

from plainweave.models import TraceLink


@_dc(frozen=True)
class DraftItem:
    kind: str  # "draft"
    req_id: str
    display_id: str
    title: str
    statement: str
    current_version: int


@_dc(frozen=True)
class LinkItem:
    kind: str  # "link"
    link_id: str
    from_label: str
    relation: str
    to_label: str
    proposing_actor: str
    confidence: float | None
    drifted: bool


def pending_items(service) -> list:
    items: list = []
    for rec in service.search_requirements():
        if rec.active_draft_id is None:
            continue
        d = service.requirement_dossier(rec.requirement_id).requirement.active_draft
        if d is None:
            continue
        items.append(DraftItem("draft", rec.requirement_id, rec.id, d.title, d.statement, rec.current_version))
    for link in service.trace_for(state="proposed"):
        items.append(LinkItem(
            "link", link.id, link.from_ref.id, link.relation, link.to_ref.id,
            link.created_by, link.confidence, link.freshness != "current",
        ))
    return items
```

```python
# src/plainweave/web/routes/review.py
from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from plainweave.web import views


def _pending_count(service) -> int:
    return len(views.pending_items(service))


async def review(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    items = views.pending_items(ctx.service)
    return request.app.state.templates.TemplateResponse(
        request, "review.html",
        {"items": items, "pending_count": len(items), "operator": ctx.operator, "active_page": "review"},
    )


def register(app: Starlette) -> None:
    app.router.routes.append(Route("/review", review, name="review"))
```

```html
{# src/plainweave/web/templates/review.html #}
{% extends "base.html" %}
{% set active_page = "review" %}
{% block title %}Review · Plainweave{% endblock %}
{% block main %}
<h1 id="review-page-heading">Review queue</h1>
<div id="queue-list">
  {% if items %}
    {% for item in items %}
      {% if item.kind == 'draft' %}{% include "_partials/queue_item_draft.html" %}
      {% else %}{% include "_partials/queue_item_link.html" %}{% endif %}
    {% endfor %}
  {% else %}{% include "_partials/queue_empty.html" %}{% endif %}
</div>
<script>
(function () {
  document.body.addEventListener('htmx:afterSettle', function (evt) {
    var elt = evt.detail.requestConfig && evt.detail.requestConfig.elt;
    if (!elt || !elt.closest('.qi-actions')) return;
    var list = document.getElementById('queue-list');
    if (!list) return;
    var next = list.querySelector('.queue-action-primary');
    if (next) { next.focus(); return; }
    var empty = document.getElementById('empty-queue-heading');
    if (empty) empty.focus();
  });
}());
</script>
{% endblock %}
```

```html
{# src/plainweave/web/templates/_partials/queue_empty.html #}
<section class="empty-queue" aria-labelledby="empty-queue-heading">
  <h2 id="empty-queue-heading" tabindex="-1">All caught up</h2>
  <p>No pending drafts or trace links to review.</p>
</section>
```

```html
{# src/plainweave/web/templates/_partials/queue_item_draft.html #}
<article id="queue-item-{{ item.req_id }}" class="queue-item queue-item--draft" aria-labelledby="qi-title-{{ item.req_id }}">
  <header><span class="type-badge" aria-label="Item type: Draft">DRAFT</span>
    <h2 id="qi-title-{{ item.req_id }}">{{ item.title }} <span class="muted">{{ item.display_id }}</span></h2></header>
  <p>{{ item.statement | truncate(200) }}</p>
  <div class="qi-actions">
    <a href="/req/{{ item.req_id }}">View full draft →</a>
    <button type="button" class="queue-action-primary" hx-get="/req/{{ item.req_id }}/approve-confirm"
            hx-target="#queue-item-{{ item.req_id }}" hx-swap="outerHTML"
            aria-label="Approve draft: {{ item.title }}">Approve</button>
  </div>
</article>
```

```html
{# src/plainweave/web/templates/_partials/queue_item_link.html #}
<article id="queue-item-{{ item.link_id }}" class="queue-item queue-item--link{% if item.drifted %} queue-item--drifted{% endif %}" aria-labelledby="qi-title-{{ item.link_id }}">
  {% if item.drifted %}<span class="drift-badge" aria-hidden="true">CODE DRIFTED</span>
  <p id="drift-{{ item.link_id }}" class="drift-notice" role="note">Code changed since this link was proposed — verify before accepting.</p>{% endif %}
  <header><span class="type-badge" aria-label="Item type: Link">LINK</span>
    <h2 id="qi-title-{{ item.link_id }}"><code>{{ item.from_label }}</code> <span aria-label="{{ item.relation }}">—{{ item.relation }}→</span> <em>{{ item.to_label }}</em></h2></header>
  <p class="muted">{{ item.proposing_actor }}{% if item.confidence is not none %} · conf {{ item.confidence }}{% endif %}</p>
  <div class="qi-actions">
    {% if item.drifted %}
    <button type="button" class="queue-action-primary" hx-get="/trace/{{ item.link_id }}/accept-drifted-confirm"
            hx-target="#queue-item-{{ item.link_id }}" hx-swap="outerHTML"
            aria-label="Accept link: {{ item.from_label }} {{ item.relation }} {{ item.to_label }}"
            aria-describedby="drift-{{ item.link_id }}">Accept…</button>
    {% else %}
    <form hx-post="/trace/{{ item.link_id }}/accept" hx-target="#queue-item-{{ item.link_id }}" hx-swap="outerHTML">
      {% include "_partials/csrf.html" %}
      <button type="submit" class="queue-action-primary" aria-label="Accept link: {{ item.from_label }} {{ item.relation }} {{ item.to_label }}">Accept</button>
    </form>
    {% endif %}
    <button type="button" hx-get="/trace/{{ item.link_id }}/reject-form" hx-target="#queue-item-{{ item.link_id }}" hx-swap="outerHTML"
            aria-label="Reject link: {{ item.from_label }} {{ item.relation }} {{ item.to_label }}">Reject</button>
  </div>
</article>
```

- [ ] **Step 4: Run + gate** — Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add src/plainweave/web/routes/review.py src/plainweave/web/templates/review.html src/plainweave/web/templates/_partials/queue_item_draft.html src/plainweave/web/templates/_partials/queue_item_link.html src/plainweave/web/templates/_partials/queue_empty.html src/plainweave/web/views.py tests/web/test_review.py
git commit -m "feat(web): unified review queue (drafts + proposed links) with empty state and focus script"
```

---

### Task 12: Approve draft (two-step confirm + OOB result)

**Files:** Modify `routes/review.py`; Create `_partials/draft_approve_confirm.html`, `_partials/queue_action_result.html`, `_partials/draft_card.html`; Test extends `test_review.py`.

**Interfaces:** Consumes `service.approve_requirement(req_id, actor=, expected_version=)` (raises `CONFLICT`), `service.requirement_dossier(req_id)`, `views.pending_items`. Produces `GET /req/{req_id}/approve-confirm`, `POST /req/{req_id}/approve`, `GET /req/{req_id}/draft-card`.

- [ ] **Step 1: Failing tests**

```python
def test_approve_two_step(client):
    ctx = client.app.state.ctx_factory()
    req = ctx.service.create_requirement("To approve", "body", actor="human:alice")
    confirm = client.get(f"/req/{req.requirement_id}/approve-confirm")
    assert "approves version 1" in confirm.text.lower() or "version 1" in confirm.text
    token = client.get("/review").cookies.get("pw_csrf")
    done = client.post(f"/req/{req.requirement_id}/approve",
                       data={"expected_version": "0", "_csrf": token})
    assert done.status_code == 200
    assert 'hx-swap-oob="innerHTML:#sr-status"' in done.text  # announces outcome
    # the requirement is now approved
    assert ctx.service.get_requirement(req.requirement_id).status == "approved"
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL.

- [ ] **Step 3: OOB result partial (shared by 12/13/14)**

```html
{# src/plainweave/web/templates/_partials/queue_action_result.html #}
{# Primary target (the acted card) is replaced by NOTHING via outerHTML → card removed. #}
<div hx-swap-oob="innerHTML:#sr-status">
  {{ action_label }}: {{ item_desc }}.
  {% if remaining_count > 0 %}{{ remaining_count }} item{{ 's' if remaining_count != 1 }} remaining in queue.
  {% else %}Queue is now empty.{% endif %}
</div>
<span hx-swap-oob="innerHTML:#review-badge">{% if remaining_count > 0 %}{{ remaining_count }}{% endif %}</span>
{% if remaining_count == 0 %}
<div hx-swap-oob="innerHTML:#queue-list">{% include "_partials/queue_empty.html" %}</div>
{% endif %}
```

```html
{# src/plainweave/web/templates/_partials/draft_approve_confirm.html #}
<article id="queue-item-{{ req_id }}" class="queue-item queue-item--draft">
  {% if error %}<p class="banner banner--warn" role="alert">{{ error }}</p>{% endif %}
  <p>Approve <strong>{{ title }}</strong> as <strong>version {{ next_version }}</strong>? This cannot be undone — there is no un-approve.</p>
  <form hx-post="/req/{{ req_id }}/approve" hx-target="#queue-item-{{ req_id }}" hx-swap="outerHTML">
    {% include "_partials/csrf.html" %}
    <input type="hidden" name="expected_version" value="{{ current_version }}">
    <button type="submit" class="queue-action-primary">Confirm — approve v{{ next_version }}</button>
    <button type="button" hx-get="/req/{{ req_id }}/draft-card" hx-target="#queue-item-{{ req_id }}" hx-swap="outerHTML">Cancel</button>
  </form>
</article>
```

`_partials/draft_card.html` = the same markup as `_partials/queue_item_draft.html` but parameterized on a single `item`; reuse by extracting the card body into `draft_card.html` and `{% include %}`-ing it from both the queue and the cancel route. (Repeat the markup here to keep tasks independent.)

- [ ] **Step 4: Handlers**

```python
# add to routes/review.py
from plainweave.errors import ErrorCode, PlainweaveError
from starlette.responses import HTMLResponse


def _draft_ctx(service, req_id):
    rec = service.get_requirement(req_id)
    draft = service.requirement_dossier(req_id).requirement.active_draft
    return rec, draft


async def approve_confirm(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    req_id = request.path_params["req_id"]
    rec, draft = _draft_ctx(ctx.service, req_id)
    return request.app.state.templates.TemplateResponse(
        request, "_partials/draft_approve_confirm.html",
        {"req_id": req_id, "title": draft.title, "current_version": rec.current_version,
         "next_version": rec.current_version + 1, "error": None},
    )


async def approve_post(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    req_id = request.path_params["req_id"]
    form = await request.form()
    expected = int(str(form["expected_version"]))
    rec, draft = _draft_ctx(ctx.service, req_id)
    try:
        ctx.service.approve_requirement(req_id, actor=ctx.operator.actor_id, expected_version=expected)
    except PlainweaveError as exc:
        if exc.code is not ErrorCode.CONFLICT:
            raise
        return request.app.state.templates.TemplateResponse(
            request, "_partials/draft_approve_confirm.html",
            {"req_id": req_id, "title": draft.title, "current_version": rec.current_version,
             "next_version": rec.current_version + 1,
             "error": "Draft changed since you loaded this. Reopen to see the latest."},
            status_code=200,
        )
    remaining = _pending_count(ctx.service)
    return request.app.state.templates.TemplateResponse(
        request, "_partials/queue_action_result.html",
        {"action_label": "Approved", "item_desc": draft.title, "remaining_count": remaining},
    )


async def draft_card(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    req_id = request.path_params["req_id"]
    rec, draft = _draft_ctx(ctx.service, req_id)
    item = views.DraftItem("draft", req_id, rec.id, draft.title, draft.statement, rec.current_version)
    return request.app.state.templates.TemplateResponse(request, "_partials/draft_card.html", {"item": item})
```

Append routes:

```python
    app.router.routes.append(Route("/req/{req_id}/approve-confirm", approve_confirm))
    app.router.routes.append(Route("/req/{req_id}/approve", approve_post, methods=["POST"]))
    app.router.routes.append(Route("/req/{req_id}/draft-card", draft_card))
```

- [ ] **Step 5: Run + gate** — Expected: PASS.
- [ ] **Step 6: Commit**

```bash
git add src/plainweave/web/routes/review.py src/plainweave/web/templates/_partials/draft_approve_confirm.html src/plainweave/web/templates/_partials/queue_action_result.html src/plainweave/web/templates/_partials/draft_card.html tests/web/test_review.py
git commit -m "feat(web): two-step draft approval with OOB status/badge/empty-state result"
```

---

### Task 13: Accept / Reject trace link (reason form + local empty-reason catch)

**Files:** Modify `routes/review.py`; Create `_partials/link_reject_form.html`, `_partials/link_card.html`; Test extends `test_review.py`.

**Interfaces:** Consumes `service.accept_trace_link(lid, actor)`, `service.reject_trace_link(lid, actor, reason)`, `service.trace_for(...)` to refetch one link for the cancel card. Produces `POST /trace/{lid}/accept`, `GET /trace/{lid}/reject-form`, `POST /trace/{lid}/reject`, `GET /trace/{lid}/card`.

- [ ] **Step 1: Failing tests**

```python
def _propose(ctx, req_id):
    from plainweave.models import TraceRef
    return ctx.service.propose_trace_link(
        TraceRef("code", "loomweave:eid:x"), "satisfies",
        TraceRef("requirement", req_id), actor="agent:claude", confidence=0.7,
    )


def test_reject_requires_reason(client):
    ctx = client.app.state.ctx_factory()
    req = ctx.service.create_requirement("R", "b", actor="human:alice")
    link = _propose(ctx, req.requirement_id)
    token = client.get("/review").cookies.get("pw_csrf")
    # empty reason → 200 with inline error, link NOT rejected
    resp = client.post(f"/trace/{link.id}/reject", data={"reason": "", "_csrf": token})
    assert resp.status_code == 200
    assert "reason is required" in resp.text.lower()
    assert ctx.service.trace_for(state="proposed")  # still proposed


def test_accept_link(client):
    ctx = client.app.state.ctx_factory()
    req = ctx.service.create_requirement("R2", "b", actor="human:alice")
    link = _propose(ctx, req.requirement_id)
    token = client.get("/review").cookies.get("pw_csrf")
    resp = client.post(f"/trace/{link.id}/accept", data={"_csrf": token})
    assert resp.status_code == 200
    assert 'hx-swap-oob="innerHTML:#sr-status"' in resp.text
    assert not ctx.service.trace_for(state="proposed")  # no longer pending
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL.

- [ ] **Step 3: Templates**

```html
{# src/plainweave/web/templates/_partials/link_reject_form.html #}
<article id="queue-item-{{ link_id }}" class="queue-item queue-item--link">
  <form hx-post="/trace/{{ link_id }}/reject" hx-target="#queue-item-{{ link_id }}" hx-swap="outerHTML">
    {% include "_partials/csrf.html" %}
    <label for="reason-{{ link_id }}">Reason for rejection</label>
    <textarea id="reason-{{ link_id }}" name="reason" rows="3" required>{{ submitted_reason or "" }}</textarea>
    {% if error %}<p class="banner banner--warn" role="alert">{{ error }}</p>{% endif %}
    <button type="submit">Confirm reject</button>
    <button type="button" hx-get="/trace/{{ link_id }}/card" hx-target="#queue-item-{{ link_id }}" hx-swap="outerHTML">Cancel</button>
  </form>
</article>
```

`_partials/link_card.html` = the LINK card body (same markup as `queue_item_link.html`, parameterized on `item`) — used by the Cancel route to restore the original card. Repeat the markup here for task independence.

- [ ] **Step 4: Handlers + a helper to fetch one link as a `LinkItem`**

```python
# add to routes/review.py
def _link_item(service, link_id):
    for link in service.trace_for(state="proposed"):
        if link.id == link_id:
            return views.LinkItem("link", link.id, link.from_ref.id, link.relation, link.to_ref.id,
                                  link.created_by, link.confidence, link.freshness != "current")
    raise PlainweaveError(ErrorCode.NOT_FOUND, f"proposed link {link_id} not found",
                          recoverable=False, hint="It may have already been accepted or rejected.")


async def reject_form(request: Request) -> Response:
    request.path_params["link_id"]
    return request.app.state.templates.TemplateResponse(
        request, "_partials/link_reject_form.html",
        {"link_id": request.path_params["link_id"], "submitted_reason": "", "error": None},
    )


async def reject_post(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    link_id = request.path_params["link_id"]
    form = await request.form()
    reason = str(form.get("reason", "")).strip()
    if not reason:
        return request.app.state.templates.TemplateResponse(
            request, "_partials/link_reject_form.html",
            {"link_id": link_id, "submitted_reason": "", "error": "Reason is required — explain why this link should be rejected."},
            status_code=200,
        )
    item = _link_item(ctx.service, link_id)
    ctx.service.reject_trace_link(link_id, actor=ctx.operator.actor_id, reason=reason)
    remaining = _pending_count(ctx.service)
    return request.app.state.templates.TemplateResponse(
        request, "_partials/queue_action_result.html",
        {"action_label": "Rejected", "item_desc": f"{item.from_label} {item.relation} {item.to_label}", "remaining_count": remaining},
    )


async def accept_post(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    link_id = request.path_params["link_id"]
    item = _link_item(ctx.service, link_id)
    ctx.service.accept_trace_link(link_id, actor=ctx.operator.actor_id)
    remaining = _pending_count(ctx.service)
    return request.app.state.templates.TemplateResponse(
        request, "_partials/queue_action_result.html",
        {"action_label": "Accepted", "item_desc": f"{item.from_label} {item.relation} {item.to_label}", "remaining_count": remaining},
    )


async def link_card(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    item = _link_item(ctx.service, request.path_params["link_id"])
    return request.app.state.templates.TemplateResponse(request, "_partials/link_card.html", {"item": item})
```

Append routes:

```python
    app.router.routes.append(Route("/trace/{link_id}/accept", accept_post, methods=["POST"]))
    app.router.routes.append(Route("/trace/{link_id}/reject-form", reject_form))
    app.router.routes.append(Route("/trace/{link_id}/reject", reject_post, methods=["POST"]))
    app.router.routes.append(Route("/trace/{link_id}/card", link_card))
```

- [ ] **Step 5: Run + gate** — Expected: PASS.
- [ ] **Step 6: Commit**

```bash
git add src/plainweave/web/routes/review.py src/plainweave/web/templates/_partials/link_reject_form.html src/plainweave/web/templates/_partials/link_card.html tests/web/test_review.py
git commit -m "feat(web): accept/reject trace links with required-reason two-step and OOB result"
```

---

### Task 14: Drift confirm for accepting drifted links

**Files:** Modify `routes/review.py`; Create `_partials/link_accept_drifted_confirm.html`; Test extends `test_review.py`.

**Interfaces:** Consumes `service.accept_trace_link(lid, actor)`, `service.mark_trace_stale(lid, actor, reason)` (test-only, to fabricate a drifted link). Produces `GET /trace/{lid}/accept-drifted-confirm`.

- [ ] **Step 1: Failing test**

```python
def test_drifted_link_renders_warning_and_requires_extra_confirm(client):
    ctx = client.app.state.ctx_factory()
    req = ctx.service.create_requirement("R3", "b", actor="human:alice")
    link = _propose(ctx, req.requirement_id)
    # Fabricate drift: mark the proposed link stale (freshness != "current").
    ctx.service.mark_trace_stale(link.id, actor="human:alice", reason="code moved")
    # Note: mark_trace_stale moves state to "stale"; for the queue test we branch on
    # freshness. If the queue only lists state="proposed", confirm the drift fixture
    # path with the team — the assertion below targets the confirm route directly.
    confirm = client.get(f"/trace/{link.id}/accept-drifted-confirm")
    assert confirm.status_code == 200
    assert "drifted" in confirm.text.lower()
    assert 'name="drift_acknowledged"' in confirm.text
```

> **Confirm during this task:** the exact drift signal. The plan branches the queue card on `link.freshness != "current"`. If proposed links never carry a non-`current` freshness in practice (drift is computed elsewhere, spec §10.2), wire the queue's `drifted` flag to the real signal the team confirms, and keep this test targeting the confirm route directly.

- [ ] **Step 2: Run to verify failure** — Expected: FAIL.

- [ ] **Step 3: Template + handler**

```html
{# src/plainweave/web/templates/_partials/link_accept_drifted_confirm.html #}
<article id="queue-item-{{ link_id }}" class="queue-item queue-item--link queue-item--drifted">
  <span class="drift-badge" aria-hidden="true">CODE DRIFTED</span>
  <p class="banner banner--warn" role="alert">Accept anyway? This ratifies the link in its current <strong>drifted</strong> state — the code changed since it was proposed.</p>
  <form hx-post="/trace/{{ link_id }}/accept" hx-target="#queue-item-{{ link_id }}" hx-swap="outerHTML">
    {% include "_partials/csrf.html" %}
    <input type="hidden" name="drift_acknowledged" value="1">
    <button type="submit" class="queue-action-primary">Accept drifted link</button>
    <button type="button" hx-get="/trace/{{ link_id }}/card" hx-target="#queue-item-{{ link_id }}" hx-swap="outerHTML">Cancel</button>
  </form>
</article>
```

```python
# add to routes/review.py
async def accept_drifted_confirm(request: Request) -> Response:
    return request.app.state.templates.TemplateResponse(
        request, "_partials/link_accept_drifted_confirm.html",
        {"link_id": request.path_params["link_id"]},
    )
```

Append route:

```python
    app.router.routes.append(Route("/trace/{link_id}/accept-drifted-confirm", accept_drifted_confirm))
```

- [ ] **Step 4: Run + gate** — Expected: PASS.
- [ ] **Step 5: Commit**

```bash
git add src/plainweave/web/routes/review.py src/plainweave/web/templates/_partials/link_accept_drifted_confirm.html tests/web/test_review.py
git commit -m "feat(web): extra confirm step for accepting drifted trace links"
```

---

### Task 15: CSRF + degraded-peer + missing-extra integration tests; docs

**Files:** Test `tests/web/test_security.py`; Modify `README.md`.

**Interfaces:** none new — verifies cross-cutting guarantees.

- [ ] **Step 1: Write the tests**

```python
# tests/web/test_security.py
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from plainweave.web.app import create_app
from plainweave.web import server


@pytest.fixture
def client(project_root):
    return TestClient(create_app(actor="human:alice", root=project_root))


def test_forged_post_without_csrf_rejected(client):
    # No prior GET → no cookie; POST must be refused.
    fresh = TestClient(create_app(actor="human:alice", root=client.app.state.ctx_factory().service.root))
    resp = fresh.post("/req/new", data={"title": "x", "statement": "y", "_csrf": "bogus"})
    assert resp.status_code == 403


def test_missing_extra_prints_hint(monkeypatch, capsys):
    monkeypatch.setattr(server, "_serve", lambda **kw: (_ for _ in ()).throw(ModuleNotFoundError("starlette")))
    assert server.run_web(host="127.0.0.1", port=1, actor=None, open_browser=False) == 1
    assert "plainweave[web]" in capsys.readouterr().out
```

- [ ] **Step 2: Run to verify failure** — Expected: FAIL (or pass for the second, already covered — keep both for the security module).

- [ ] **Step 3: Make them pass** — these exercise existing behavior; fix any gaps surfaced (e.g. ensure the CSRF middleware refuses a POST when no cookie is present).

- [ ] **Step 4: Document** — add a short "Web UI (optional)" section to `README.md`:

```markdown
### Web UI (optional)

Install the extra and launch the operator console:

    pip install 'plainweave[web]'
    plainweave web --actor human:<you>

Browse the corpus, author requirements, and ratify agent-proposed drafts and
trace links. Local-first, single-operator; advisory only (no release verdicts).
```

- [ ] **Step 5: Run full gate** — Run: `make ci` · Expected: all green, coverage ≥ 90%.
- [ ] **Step 6: Commit**

```bash
git add tests/web/test_security.py README.md
git commit -m "test(web): CSRF + missing-extra guarantees; docs: web UI quickstart"
```

---

### Task 16: Accessibility pass — focus + live-region verification (AT gate)

**Files:** Test `tests/web/test_a11y_contracts.py` (structural assertions); a manual AT-gate checklist note.

**Interfaces:** none new — locks the §4.1 contracts structurally; the empirical screen-reader pass is a manual gate.

- [ ] **Step 1: Write structural a11y tests**

```python
# tests/web/test_a11y_contracts.py
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from plainweave.web.app import create_app


@pytest.fixture
def client(project_root):
    return TestClient(create_app(actor="human:alice", root=project_root))


def test_base_has_live_region_and_skip_link(client):
    html = client.get("/").text
    assert 'id="sr-status"' in html and 'role="status"' in html and 'aria-live="polite"' in html
    assert 'class="skip-link"' in html


def test_search_has_visible_label(client):
    html = client.get("/").text
    assert '<label for="req-search"' in html


def test_review_buttons_have_unique_aria_labels(client):
    ctx = client.app.state.ctx_factory()
    ctx.service.create_requirement("Aria draft one", "b", actor="human:alice")
    ctx.service.create_requirement("Aria draft two", "b", actor="human:alice")
    html = client.get("/review").text
    assert "Approve draft: Aria draft one" in html
    assert "Approve draft: Aria draft two" in html
```

- [ ] **Step 2: Run to verify failure / pass** — fix any structural gaps (missing label, missing live region) surfaced.

- [ ] **Step 3: Record the manual AT gate** — append to the README web section or a `docs/` note: *"Before shipping the review surface, run an NVDA (Windows) or VoiceOver (macOS) pass: approving/accepting/rejecting an item must (a) announce the outcome via the status region, (b) move focus to the next action button, and (c) on the last item, announce 'Queue is now empty' and focus the 'All caught up' heading."*

- [ ] **Step 4: Run full gate + commit**

```bash
git add tests/web/test_a11y_contracts.py README.md
git commit -m "test(web): structural accessibility contracts; record manual AT gate"
```

---

## Self-Review

**1. Spec coverage** — every spec section maps to a task:
- §3 operator identity → Task 2. §4 architecture/packaging → Tasks 1, 3. §4.1 HTMX/a11y contracts → Tasks 3 (live region/loader/base), 11 (focus script), 12–14 (two-step/OOB), 16 (structural a11y). §5① corpus/detail/new-edit → Tasks 4, 5, 6, 9. §5② review/approve/accept/reject/drift → Tasks 11, 12, 13, 14. §5③ intent/goals → Tasks 7, 8, 10. §6 routes/conflict → Tasks 9, 12, 13. §7 error mapping + local catches → Tasks 3, 9, 12, 13. §8 tests + AT gate → every task + Tasks 15, 16. §9 deps/CLI → Task 1. §12 firm checklist → Tasks 3, 11, 13, 14, 16.
- **Deferred (correctly absent):** SEI-binding detail panel, similarity hint, verification/baseline surfaces, multi-user/auth (spec §2/§11).

**2. Placeholder scan** — code is concrete throughout. The remaining *confirm-in-task* notes (store initializer name, `list_goals` existence, dossier attribute names, drift sentinel) are explicit verification steps against real code, not hand-waves; each names the fallback. These mirror the spec's §10 open questions and must be resolved when the task runs, not invented.

**3. Type consistency** — `RequestContext`/`OperatorIdentity` (Task 2) used consistently; `CorpusRow`/`DraftItem`/`LinkItem` (views) consistent across Tasks 4/11/12/13; service signatures match the verbatim ones read from `service.py` (`create_requirement`, `update_draft(expected_draft_revision=)`, `approve_requirement(expected_version=)`, `accept_trace_link`, `reject_trace_link(reason=)`, `propose_trace_link`, `link_goal_to_requirement`, `create_goal`, `intent_corpus/orphans/coverage`, `search_requirements`, `requirement_dossier`). The `queue_action_result.html` OOB contract is identical in Tasks 12/13/14.

**Open items the implementer must confirm against code on first touch (carried from spec §10):** store init entrypoint name; `service.list_actors()` / `list_goals()` existence (add the thin read if absent, justified); exact `DossierRequirementSection` attribute names; the drift signal source (`TraceLink.freshness` vs. a computed check). None blocks starting Task 1.
