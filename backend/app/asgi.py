from __future__ import annotations

from typing import Any

from .config import APP_NAME
from .main import app
from .architecture_api import router as architecture_router
from .opening_api import router as opening_router
from .interior_api import router as interior_router


APP_VERSION = "1.5.0"
app.version = APP_VERSION


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
