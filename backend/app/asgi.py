from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import APP_NAME
from . import main as main_module
from .architecture_api import router as architecture_router
from .opening_api import router as opening_router
from .interior_api import router as interior_router
from .presentation_api import router as presentation_router
from .services.rendering_v15 import blender_render as detailed_blender_render
from .services.strict_geometry import (
    add_room_guarded,
    analyze_floorplan_strict,
    update_room_geometry_guarded,
)


APP_VERSION = "2.1.0"
app = main_module.app
app.version = APP_VERSION
main_module.APP_VERSION = APP_VERSION
main_module.blender_render = detailed_blender_render
main_module.analyze_floorplan = analyze_floorplan_strict
main_module.add_room = add_room_guarded
main_module.update_room_geometry = update_room_geometry_guarded

# Capacitor serves the bundled Android app from https://localhost. This outer CORS
# layer keeps the existing desktop origins while allowing the native WebView.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "capacitor://localhost",
        "https://localhost",
        "http://localhost",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "null",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def optional_mobile_api_token(request: Request, call_next):
    """Require a bearer token only when DREAMHOME_API_TOKEN is configured.

    File and image URLs may also carry access_token because image elements in a
    Capacitor WebView cannot attach an Authorization header.
    """
    expected = os.getenv("DREAMHOME_API_TOKEN", "").strip()
    if not expected or request.method == "OPTIONS" or request.url.path == "/health":
        return await call_next(request)

    authorization = request.headers.get("authorization", "")
    bearer = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    supplied = bearer or request.query_params.get("access_token", "")
    if not supplied or not secrets.compare_digest(supplied, expected):
        return JSONResponse(
            status_code=401,
            content={"detail": "A valid Roomify API token is required."},
        )
    return await call_next(request)


def _has_route(path: str) -> bool:
    return any(getattr(route, "path", None) == path for route in app.routes)


# Replace the legacy health route so development and packaged builds report the same release.
app.router.routes = [route for route in app.routes if getattr(route, "path", None) != "/health"]


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": APP_NAME, "version": APP_VERSION, "android_client": True}


if not _has_route("/api/v1/projects/{project_id}/compile-architecture"):
    app.include_router(architecture_router)
if not _has_route("/api/v1/projects/{project_id}/openings"):
    app.include_router(opening_router)
if not _has_route("/api/v1/projects/{project_id}/furniture"):
    app.include_router(interior_router)
if not _has_route("/api/v1/projects/{project_id}/presentation-renders"):
    app.include_router(presentation_router)
