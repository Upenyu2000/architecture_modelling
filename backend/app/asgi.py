from __future__ import annotations

from .main import app
from .architecture_api import router as architecture_router
from .opening_api import router as opening_router
from .interior_api import router as interior_router


def _has_route(path: str) -> bool:
    return any(getattr(route, "path", None) == path for route in app.routes)


if not _has_route("/api/v1/projects/{project_id}/compile-architecture"):
    app.include_router(architecture_router)
if not _has_route("/api/v1/projects/{project_id}/openings"):
    app.include_router(opening_router)
if not _has_route("/api/v1/projects/{project_id}/furniture"):
    app.include_router(interior_router)
