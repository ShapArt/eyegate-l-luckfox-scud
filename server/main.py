from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import base as db_base
from server import ws as ws_routes
from server.api import health as health_routes
from server.api.router import api_router
from server.deps import (
    get_camera_ingest,
    get_config,
    get_restream_service,
    start_gate_controller,
)
from server.errors import setup_exception_handlers

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR / "web" / "app" / "dist"
STATIC_DIR = BASE_DIR / "web" / "static"
TEMPLATES_DIR = BASE_DIR / "web" / "templates"
STREAMS_DIR = BASE_DIR / "data" / "streams"
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    cfg = get_config()

    app = FastAPI(
        title="EyeGate Mantrap SCUD",
        description="Учебный проект двухдверного шлюза на Luckfox Pico Ultra",
        version="0.1.0",
    )

    app.include_router(api_router, prefix="/api")
    app.include_router(health_routes.router)
    app.include_router(ws_routes.router)
    setup_exception_handlers(app)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    STREAMS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/streams", StaticFiles(directory=str(STREAMS_DIR)), name="streams")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @app.middleware("http")
    async def add_permissions_policy(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Permissions-Policy", "camera=()")
        return response

    index_path = FRONTEND_DIST / "index.html"
    if not index_path.exists():
        if getattr(cfg, "env", "dev") == "dev":
            logger.warning(
                "SPA build is missing (%s). Run `cd web/app && npm run dev` (port 5173) or build `npm run build`.",
                index_path,
            )
        else:
            logger.error("SPA build is missing: %s not found", index_path)

    if FRONTEND_DIST.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(FRONTEND_DIST / "assets")),
            name="assets",
        )

    @app.get("/legacy/{page}")
    async def legacy_page(page: str, request: Request):
        allowed = {
            "index",
            "kiosk",
            "monitor",
            "simulator",
            "sim",
            "admin",
            "login",
            "register",
        }
        if page not in allowed:
            return HTMLResponse(status_code=404, content="Legacy page not found")
        filename = "simulator.html" if page == "sim" else f"{page}.html"
        return templates.TemplateResponse(filename, {"request": request})

    def _spa_index_response() -> HTMLResponse | FileResponse:
        """
        Serve the SPA entrypoint from the built bundle, with a graceful fallback for dev.
        This prevents 404s when users hit deep links like /kiosk directly.
        """
        if index_path.exists():
            return FileResponse(index_path)
        return HTMLResponse(
            status_code=200,
            content=(
                "<!doctype html><html><body>"
                '<div id="root"></div>'
                '<pre style="padding:16px;font-family:ui-monospace,monospace">'
                "SPA build is missing.\\n\\n"
                "Dev (recommended):\\n"
                "  cd web/app && npm install && npm run dev\\n"
                "  open http://localhost:5173\\n\\n"
                "Prod-like:\\n"
                "  cd web/app && npm install && npm run build\\n"
                "  then open http://localhost:8000\\n"
                "</pre></body></html>"
            ),
        )

    @app.get("/{full_path:path}")
    async def spa_catch_all(full_path: str, request: Request):
        # Respect API/WS prefixes and avoid swallowing static asset misses.
        blocked_prefixes = ("api", "ws")
        static_like = ("assets", "static", "favicon.ico", "robots.txt")
        if full_path.startswith(blocked_prefixes):
            return HTMLResponse(status_code=404, content="Not found")
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        if full_path.startswith(static_like):
            return HTMLResponse(status_code=404, content="Not found")
        return _spa_index_response()

    if os.getenv("EYEGATE_SKIP_STARTUP", "0") != "1":

        @app.on_event("startup")
        async def _startup() -> None:
            await start_gate_controller()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        try:
            ingest = get_camera_ingest()
            if ingest is not None:
                ingest.stop()
        except Exception:
            pass
        try:
            restream = get_restream_service()
            if restream is not None:
                restream.stop()
        except Exception:
            pass
        try:
            db_base.close_all_connections()
        except Exception:
            pass

    return app


app = create_app()
