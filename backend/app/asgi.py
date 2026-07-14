from __future__ import annotations

from typing import Any

from .config import APP_NAME
from . import main as main_module
from .architecture_api import router as architecture_router
from .opening_api import router as opening_router
from .interior_api import router as interior_router
from .stability_api import router as stability_router
from .services.rendering_v15 import blender_render as detailed_blender_render
from .services.strict_geometry import (
    add_room_guarded,
    analyze_floorplan_strict,
    update_room_geometry_guarded,
)

APP_VERSION = "1.5.6"
app = main_module.app
app.version = APP_VERSION
main_module.APP_VERSION = APP_VERSION
main_module.blender_render = detailed_blender_render
main_module.analyze_floorplan = analyze_floorplan_strict
main_module.add_room = add_room_guarded
main_module.update_room_geometry = update_room_geometry_guarded


def _has_route(path: str) -> bool:
    return any(getattr(route, "path", None) == path for route in app.routes)


# Remove obsolete handlers whose request/response models pre-date the 1.5.x
# storage schema. The canonical stability router below owns these routes.
_replaced_paths = {
    "/health",
    "/api/v1/projects/{project_id}/floorplan",
    "/api/v1/projects/{project_id}/assets/{category}/{slot}",
    "/api/v1/projects/{project_id}/building-model",
    "/api/v1/projects/{project_id}/save-slots/{slot_id}/restore",
}
app.router.routes = [
    route for route in app.router.routes
    if getattr(route, "path", None) not in _replaced_paths
]


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": APP_NAME, "version": APP_VERSION}


app.include_router(stability_router)
if not _has_route("/api/v1/projects/{project_id}/compile-architecture"):
    app.include_router(architecture_router)
if not _has_route("/api/v1/projects/{project_id}/openings"):
    app.include_router(opening_router)
if not _has_route("/api/v1/projects/{project_id}/furniture"):
    app.include_router(interior_router)
