from __future__ import annotations

from typing import Any

from .config import APP_NAME
from . import main as main_module
from .architecture_api import router as architecture_router
from .opening_api import router as opening_router
from .interior_api import router as interior_router
from .services.rendering_v15 import blender_render as detailed_blender_render


APP_VERSION = "1.5.1"
app = main_module.app
app.version = APP_VERSION
main_module.APP_VERSION = APP_VERSION
main_module.blender_render = detailed_blender_render


def _has_route(path: str) -> bool:
    return any(getattr(route, "path", None) == path for route in app.routes)


# Replace the legacy health route so the packaged ASGI application and UI always report the release version.
app.router.routes = [route for route in app.router.routes if getattr(route, "path", None) != "/health"]


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": APP_NAME, "version": APP_VERSION}


if not _has_route("/api/v1/projects/{project_id}/compile-architecture"):
    app.include_router(architecture_router)
if not _has_route("/api/v1/projects/{project_id}/openings"):
    app.include_router(opening_router)
if not _has_route("/api/v1/projects/{project_id}/furniture"):
    app.include_router(interior_router)
