from __future__ import annotations

import re
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from .config import APP_NAME
from . import main as main_module
from .architecture_api import router as architecture_router
from .opening_api import router as opening_router
from .interior_api import router as interior_router
from .presentation_api import router as presentation_router
from .storage import ACTIVE_FOLDERS, UploadStorageError
from .services.rendering_v15 import blender_render as detailed_blender_render
from .services.strict_geometry import (
    add_room_guarded,
    analyze_floorplan_strict,
    update_room_geometry_guarded,
)


APP_VERSION = "2.0.0"
SAFE_ROUTE_TOKEN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")
app = main_module.app
app.version = APP_VERSION
main_module.APP_VERSION = APP_VERSION
main_module.blender_render = detailed_blender_render
main_module.analyze_floorplan = analyze_floorplan_strict
main_module.add_room = add_room_guarded
main_module.update_room_geometry = update_room_geometry_guarded


def _has_route(path: str) -> bool:
    return any(getattr(route, "path", None) == path for route in app.routes)


def _invalid_token(value: str) -> bool:
    return not SAFE_ROUTE_TOKEN.fullmatch(value) or ".." in value


# Replace the legacy health route so development and packaged builds report the same release.
app.router.routes = [route for route in app.routes if getattr(route, "path", None) != "/health"]


@app.middleware("http")
async def local_path_guard(request: Request, call_next):
    segments = [segment for segment in request.url.path.split("/") if segment]
    if len(segments) >= 4 and segments[:3] == ["api", "v1", "projects"]:
        project_id = segments[3]
        if _invalid_token(project_id):
            return JSONResponse(status_code=400, content={"detail": "Invalid project identifier"})

        if len(segments) >= 7 and segments[4] in {"assets", "interior-assets"}:
            category, slot = segments[5], segments[6]
            if _invalid_token(category) or _invalid_token(slot):
                return JSONResponse(status_code=400, content={"detail": "Invalid asset category or slot"})

        if len(segments) >= 6 and segments[4] == "files":
            root_folder = segments[5]
            if root_folder not in ACTIVE_FOLDERS:
                return JSONResponse(status_code=404, content={"detail": "Project file not found"})

    return await call_next(request)


@app.exception_handler(UploadStorageError)
async def upload_storage_error(_request: Request, exc: UploadStorageError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(FileNotFoundError)
async def local_resource_not_found(_request: Request, _exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Project or local resource not found"})


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": APP_NAME, "version": APP_VERSION}


if not _has_route("/api/v1/projects/{project_id}/compile-architecture"):
    app.include_router(architecture_router)
if not _has_route("/api/v1/projects/{project_id}/openings"):
    app.include_router(opening_router)
if not _has_route("/api/v1/projects/{project_id}/furniture"):
    app.include_router(interior_router)
if not _has_route("/api/v1/projects/{project_id}/presentation-renders"):
    app.include_router(presentation_router)
