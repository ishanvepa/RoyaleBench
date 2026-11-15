"""The FastAPI application: JSON API under /api, and the built React app (web/dist) at /."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .context import AppContext, build_context
from .errors import body, not_found, register_error_handlers
from .routers import assets, evals, legacy, legacy_play
from .schemas.common import HealthOut
from .settings import Settings

log = logging.getLogger("rb_server")
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
CLIENT_HEADER = "x-rb-client"  # every state-changing request must carry it; cross-site pages cannot send it unprompted
LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]", "::1", "testserver")
NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>RoyaleBench</title>
<body style="font:16px system-ui;max-width:42rem;margin:4rem auto;padding:0 1rem">
<h1>The web app is not built yet</h1>
<p>The API is running. Build the frontend once with <code>cd web &amp;&amp; npm install &amp;&amp; npm run build</code> and reload,
or start the Vite dev server with <code>cd web &amp;&amp; npm run dev</code> and open <a href="http://127.0.0.1:5173">http://127.0.0.1:5173</a>.</p>
<p>API docs: <a href="/api/docs">/api/docs</a></p></body>"""


class SPAStaticFiles(StaticFiles):
    """Serves web/dist; any path that is not a file falls back to index.html so client-side routes work on reload."""

    async def get_response(self, path: str, scope):
        route = path.replace("\\", "/")  # Starlette joins path parts with os.sep, so this is "api\\x" on Windows
        if route == "api" or route.startswith("api/"):
            raise StarletteHTTPException(404, "Not found")
        try:
            response = await super().get_response(path, scope)
            missing = response.status_code == 404
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            missing = True
        if missing:
            response = await super().get_response("index.html", scope)
        if missing or route in ("", ".", "index.html"):
            response.headers["Cache-Control"] = "no-cache"  # hashed assets are cacheable; the HTML shell is not
        return response


def create_app(settings: Settings | None = None, *, ctx: AppContext | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    ctx = ctx or build_context(settings)
    from contextlib import asynccontextmanager
    from rb_evals.archive import ArchiveWorker
    from rb_evals.valkyrie import Valkyrie
    from .cost_refresh import CostRefresher

    @asynccontextmanager
    async def lifespan(app):
        worker = ArchiveWorker(ctx.valkyrie).start() if isinstance(ctx.valkyrie, Valkyrie) and not ctx.fake else None
        costs = CostRefresher(ctx).start() if isinstance(ctx.valkyrie, Valkyrie) and not ctx.fake else None
        try:
            yield
        finally:
            if costs:
                costs.close()
            if worker:
                worker.close()

    app = FastAPI(title="RoyaleBench API", version="1.0.0", docs_url="/api/docs", redoc_url=None,
                  openapi_url="/api/openapi.json", lifespan=lifespan)
    app.state.ctx = ctx
    register_error_handlers(app)

    # A local server that can spend credits must not answer a page on another origin (DNS rebinding) ...
    hosts = list(LOCAL_HOSTS) if settings.host in ("127.0.0.1", "localhost", "::1") else ["*"]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        # ... or fire a state-changing request at it from a form or a no-cors fetch (CSRF).
        if request.method not in SAFE_METHODS and request.url.path.startswith("/api/") and request.headers.get(CLIENT_HEADER) != "web":
            return JSONResponse(body("forbidden", f"Missing {CLIENT_HEADER}: web header"), status_code=403)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    @app.get("/api/health", tags=["meta"], response_model=HealthOut)
    def health() -> HealthOut:
        return HealthOut(read_only=ctx.cfg.read_only, fake=ctx.fake)

    app.include_router(evals.router)
    app.include_router(legacy.router, prefix="/api/legacy")
    app.include_router(legacy_play.router, prefix="/api/legacy")
    app.include_router(assets.router, prefix="/api/assets")

    if settings.static_dir.is_dir() and (settings.static_dir / "index.html").is_file():
        app.mount("/", SPAStaticFiles(directory=settings.static_dir, html=True), name="web")
    else:
        @app.get("/{path:path}", include_in_schema=False)
        def not_built(path: str):
            if path == "api" or path.startswith("api/"):
                raise not_found("Not found")
            return HTMLResponse(NOT_BUILT, status_code=503)

    return app
