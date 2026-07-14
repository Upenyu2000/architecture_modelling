from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import APP_NAME, PROJECTS_DIR, ensure_directories, load_settings, save_settings
from .models import (
    AnalyzeRequest, AssetFile, BuildingModelFile, CreateProjectRequest, DrawingRequest,
    FloorplanFile, Job, ManualLayoutRequest, Project, RenderRequest, RoomCreateRequest,
    RoomGeometryRequest, RoomUpdateRequest, SaveSlotRequest, SaveSlotSummary,
    SceneManifest, WalkthroughRequest,
)
from .storage import (
    create_project, create_save_slot, delete_save_slot, list_save_slots, load_project,
    project_dir, reset_project, restore_save_slot, save_project, save_upload, write_json,
)
from .services.drawings import generate_drawing_set
from .services.floorplan import analyze_floorplan, rasterize_floorplan
from .services.jobs import create_job, get_job, submit
from .services.layout import add_room, delete_room, update_room_geometry
from .services.providers import reconstruct_image_to_3d
from .services.rendering import blender_render, technical_render
from .services.scene import apply_assets

APP_VERSION = "1.5.6"
app = FastAPI(title=f"{APP_NAME} Local API", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "null"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
ensure_directories()


def project_or_404(project_id: str) -> Project:
    try:
        return load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


def persist_scene(project: Project, scene: SceneManifest, status: str = "layout_updated") -> SceneManifest:
    scene = apply_assets(scene, project.assets)
    project.scene = scene
    project.status = status
    write_json(project_dir(project.id) / "working" / "scene.json", scene.model_dump(mode="json"))
    save_project(project)
    return scene


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": APP_NAME, "version": APP_VERSION}


@app.get("/api/v1/settings")
def get_settings() -> dict[str, Any]:
    return load_settings().model_dump(mode="json")


@app.put("/api/v1/settings")
def put_settings(payload: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings().model_copy(update=payload)
    save_settings(settings)
    return settings.model_dump(mode="json")


@app.get("/api/v1/projects")
def get_projects() -> list[Project]:
    ensure_directories()
    projects: list[Project] = []
    for path in sorted(PROJECTS_DIR.iterdir() if PROJECTS_DIR.exists() else []):
        if not path.is_dir():
            continue
        try:
            projects.append(load_project(path.name))
        except (FileNotFoundError, ValueError):
            continue
    return projects


@app.post("/api/v1/projects")
def post_project(payload: CreateProjectRequest) -> Project:
    return create_project(payload.name)


@app.get("/api/v1/projects/{project_id}")
def get_project(project_id: str) -> Project:
    return project_or_404(project_id)


@app.delete("/api/v1/projects/{project_id}/reset")
def clear_project(project_id: str) -> Project:
    project_or_404(project_id)
    return reset_project(project_id)


@app.get("/api/v1/projects/{project_id}/save-slots")
def get_save_slots(project_id: str) -> list[SaveSlotSummary]:
    project_or_404(project_id)
    return list_save_slots(project_id)


@app.post("/api/v1/projects/{project_id}/save-slots")
def post_save_slot(project_id: str, payload: SaveSlotRequest) -> SaveSlotSummary:
    project_or_404(project_id)
    return create_save_slot(project_id, payload.name)


@app.post("/api/v1/projects/{project_id}/save-slots/{slot_id}/restore")
def post_restore_slot(project_id: str, slot_id: str) -> Project:
    project_or_404(project_id)
    try:
        return restore_save_slot(project_id, slot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Save slot not found") from exc


@app.delete("/api/v1/projects/{project_id}/save-slots/{slot_id}")
def remove_save_slot(project_id: str, slot_id: str) -> dict[str, bool]:
    project_or_404(project_id)
    try:
        delete_save_slot(project_id, slot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Save slot not found") from exc
    return {"deleted": True}


@app.post("/api/v1/projects/{project_id}/floorplan")
async def upload_floorplan(project_id: str, file: UploadFile = File(...)) -> Project:
    project = project_or_404(project_id)
    target = save_upload(project_id, file.filename or "floorplan", await file.read(), "floorplans")
    raster = rasterize_floorplan(target)
    project.floorplan = FloorplanFile(
        filename=target.name,
        path=str(target),
        mime_type=file.content_type or "application/octet-stream",
        width_px=raster.width,
        height_px=raster.height,
    )
    project.status = "floorplan_uploaded"
    save_project(project)
    return project


@app.post("/api/v1/projects/{project_id}/assets/{category}/{slot}")
async def upload_asset(project_id: str, category: str, slot: str, file: UploadFile = File(...)) -> Project:
    project = project_or_404(project_id)
    target = save_upload(project_id, file.filename or slot, await file.read(), f"assets/{category}")
    project.assets[f"{category}:{slot}"] = AssetFile(
        category=category,
        slot=slot,
        filename=target.name,
        path=str(target),
        mime_type=file.content_type or "application/octet-stream",
    )
    save_project(project)
    return project


@app.post("/api/v1/projects/{project_id}/building-model")
async def upload_building_model(project_id: str, file: UploadFile = File(...)) -> Project:
    project = project_or_404(project_id)
    target = save_upload(project_id, file.filename or "building-model", await file.read(), "building_models")
    project.building_model = BuildingModelFile(
        filename=target.name,
        path=str(target),
        mime_type=file.content_type or "application/octet-stream",
    )
    project.status = "building_model_uploaded"
    save_project(project)
    return project


@app.post("/api/v1/projects/{project_id}/analyze")
def analyze(project_id: str, payload: AnalyzeRequest) -> SceneManifest:
    project = project_or_404(project_id)
    scene = analyze_floorplan(project, payload)
    return persist_scene(project, scene, "analyzed")


@app.post("/api/v1/projects/{project_id}/manual-layout")
def manual_layout(project_id: str, payload: ManualLayoutRequest) -> SceneManifest:
    project = project_or_404(project_id)
    scene = SceneManifest.empty(
        width_m=payload.width_m,
        depth_m=max(payload.width_m * 0.7, 2.0),
        wall_height_m=payload.wall_height_m,
    )
    return persist_scene(project, scene, "manual_layout")


@app.post("/api/v1/projects/{project_id}/rooms")
def create_room(project_id: str, payload: RoomCreateRequest) -> SceneManifest:
    project = project_or_404(project_id)
    if project.scene is None:
        raise HTTPException(status_code=409, detail="Create a manual layout or analyze a floor plan first")
    scene = add_room(project.scene, payload)
    return persist_scene(project, scene)


@app.put("/api/v1/projects/{project_id}/rooms/{room_id}")
def update_room(project_id: str, room_id: str, payload: RoomUpdateRequest) -> SceneManifest:
    project = project_or_404(project_id)
    if project.scene is None:
        raise HTTPException(status_code=409, detail="No scene available")
    room = next((item for item in project.scene.rooms if item.id == room_id), None)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    room.name = payload.name
    return persist_scene(project, project.scene)


@app.put("/api/v1/projects/{project_id}/rooms/{room_id}/geometry")
def put_room_geometry(project_id: str, room_id: str, payload: RoomGeometryRequest) -> SceneManifest:
    project = project_or_404(project_id)
    if project.scene is None:
        raise HTTPException(status_code=409, detail="No scene available")
    try:
        scene = update_room_geometry(project.scene, room_id, payload.polygon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return persist_scene(project, scene)


@app.delete("/api/v1/projects/{project_id}/rooms/{room_id}")
def remove_room(project_id: str, room_id: str) -> SceneManifest:
    project = project_or_404(project_id)
    if project.scene is None:
        raise HTTPException(status_code=409, detail="No scene available")
    scene = delete_room(project.scene, room_id)
    return persist_scene(project, scene)


@app.post("/api/v1/projects/{project_id}/drawings")
def drawings(project_id: str, payload: DrawingRequest) -> Job:
    project = project_or_404(project_id)
    return submit(create_job("drawing_set", project_id), generate_drawing_set, project, payload)


@app.post("/api/v1/projects/{project_id}/render")
def render(project_id: str, payload: RenderRequest) -> Job:
    project = project_or_404(project_id)
    renderer = blender_render if payload.engine in {"auto", "blender"} else technical_render
    return submit(create_job("render", project_id), renderer, project, payload)


@app.post("/api/v1/projects/{project_id}/walkthrough")
def create_walkthrough(project_id: str, payload: WalkthroughRequest) -> Job:
    project = project_or_404(project_id)
    renderer = blender_render if payload.engine in {"auto", "blender"} else technical_render
    return submit(create_job("walkthrough", project_id), renderer, project, payload)


@app.post("/api/v1/projects/{project_id}/reconstruct/{category}/{slot}")
def reconstruct_asset(project_id: str, category: str, slot: str) -> Job:
    project = project_or_404(project_id)
    key = f"{category}:{slot}"
    asset = project.assets.get(key)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return submit(create_job("reconstruction", project_id), reconstruct_image_to_3d, project, asset)


@app.get("/api/v1/jobs/{job_id}")
def read_job(job_id: str) -> Job:
    try:
        return get_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@app.get("/api/v1/files")
def files(path: str) -> FileResponse:
    requested = Path(path).resolve()
    data_root = PROJECTS_DIR.parent.resolve()
    if data_root not in requested.parents and requested != data_root:
        raise HTTPException(status_code=403, detail="Path is outside the application data directory")
    if not requested.exists() or not requested.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(requested)
