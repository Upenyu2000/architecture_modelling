from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import APP_NAME, PROJECTS_DIR, ensure_directories, load_settings, save_settings
from .models import (
    AnalyzeRequest, AssetFile, BuildingModelFile, CreateProjectRequest, DrawingRequest,
    FloorplanFile, Job, Project, RenderRequest, RoomUpdateRequest, SaveSlotRequest,
    SaveSlotSummary, SceneManifest, WalkthroughRequest,
)
from .storage import (
    create_project, create_save_slot, delete_save_slot, list_save_slots, load_project,
    project_dir, reset_project, restore_save_slot, save_project, save_upload, write_json,
)
from .services.drawings import generate_drawing_set
from .services.floorplan import analyze_floorplan, rasterize_floorplan
from .services.jobs import create_job, get_job, submit
from .services.providers import reconstruct_image_to_3d
from .services.rendering import blender_render, technical_render
from .services.scene import apply_assets

app = FastAPI(title=f"{APP_NAME} Local API", version="1.1.0")
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


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": APP_NAME, "version": "1.1.0"}


@app.get("/api/v1/projects", response_model=list[Project])
def list_projects() -> list[Project]:
    projects: list[Project] = []
    for item in PROJECTS_DIR.iterdir():
        try:
            projects.append(load_project(item.name))
        except (FileNotFoundError, ValueError):
            continue
    return sorted(projects, key=lambda project: project.updated_at, reverse=True)


@app.post("/api/v1/projects", response_model=Project)
def new_project(request: CreateProjectRequest) -> Project:
    return create_project(request.name)


@app.get("/api/v1/projects/{project_id}", response_model=Project)
def get_project(project_id: str) -> Project:
    return project_or_404(project_id)


@app.post("/api/v1/projects/{project_id}/reset", response_model=Project)
def clear_project(project_id: str) -> Project:
    project_or_404(project_id)
    return reset_project(project_id)


@app.get("/api/v1/projects/{project_id}/save-slots", response_model=list[SaveSlotSummary])
def get_save_slots(project_id: str) -> list[SaveSlotSummary]:
    project_or_404(project_id)
    return list_save_slots(project_id)


@app.post("/api/v1/projects/{project_id}/save-slots", response_model=SaveSlotSummary)
def save_to_slot(project_id: str, request: SaveSlotRequest) -> SaveSlotSummary:
    project_or_404(project_id)
    return create_save_slot(project_id, request.name)


@app.post("/api/v1/projects/{project_id}/save-slots/{slot_id}/load", response_model=Project)
def load_from_slot(project_id: str, slot_id: str) -> Project:
    project_or_404(project_id)
    try:
        return restore_save_slot(project_id, slot_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Save slot not found")


@app.delete("/api/v1/projects/{project_id}/save-slots/{slot_id}")
def remove_save_slot(project_id: str, slot_id: str) -> dict[str, str]:
    project_or_404(project_id)
    try:
        delete_save_slot(project_id, slot_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Save slot not found")
    return {"deleted": slot_id}


@app.post("/api/v1/projects/{project_id}/floorplan", response_model=Project)
async def upload_floorplan(project_id: str, file: UploadFile = File(...)) -> Project:
    project = project_or_404(project_id)
    allowed = {".png", ".jpg", ".jpeg", ".pdf"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status_code=415, detail="Floor plan must be PNG, JPG, JPEG or PDF")
    source = await save_upload(project_id, file, "uploads", "floorplan-")
    preview = project_dir(project_id) / "working" / "floorplan.png"
    preview.parent.mkdir(parents=True, exist_ok=True)
    try:
        rasterize_floorplan(source, preview)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    from PIL import Image
    with Image.open(preview) as image:
        width, height = image.size
    project.floorplan = FloorplanFile(
        filename=source.name,
        path=str(source),
        preview_url=f"/api/v1/projects/{project_id}/files/working/floorplan.png",
        width_px=width,
        height_px=height,
    )
    project.scene = None
    project.status = "floorplan_uploaded"
    return save_project(project)


@app.post("/api/v1/projects/{project_id}/building-model", response_model=Project)
async def upload_building_model(project_id: str, file: UploadFile = File(...)) -> Project:
    project = project_or_404(project_id)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".glb", ".obj", ".stl", ".ply"}:
        raise HTTPException(status_code=415, detail="3D building model must be GLB, OBJ, STL or PLY")
    destination = await save_upload(project_id, file, "uploads", "building-")
    project.building_model = BuildingModelFile(
        filename=destination.name,
        path=str(destination),
        url=f"/api/v1/projects/{project_id}/files/uploads/{destination.name}",
        format=suffix.lstrip("."),
        size_bytes=destination.stat().st_size,
    )
    project.drawing_set = None
    project.status = "building_model_uploaded"
    return save_project(project)


@app.post("/api/v1/projects/{project_id}/drawings", response_model=Job)
def create_drawings(project_id: str, request: DrawingRequest) -> Job:
    project = project_or_404(project_id)
    if not project.building_model:
        raise HTTPException(status_code=409, detail="Upload a 3D building model first")

    job = create_job(project_id, "drawing_set")
    output_dir = project_dir(project_id) / "outputs" / f"drawings-{job.id[:8]}"
    archive = output_dir.with_suffix(".zip")
    url_prefix = f"/api/v1/projects/{project_id}/files/outputs/{output_dir.name}"
    archive_url = f"/api/v1/projects/{project_id}/files/outputs/{archive.name}"
    model_path = Path(project.building_model.path)
    source_filename = project.building_model.filename

    def task(progress):
        drawing_set, generated_archive = generate_drawing_set(
            project_id=project_id,
            model_path=model_path,
            source_filename=source_filename,
            output_dir=output_dir,
            url_prefix=url_prefix,
            request=request,
            progress=progress,
        )
        current = load_project(project_id)
        current.drawing_set = drawing_set
        current.status = "drawings_generated"
        save_project(current)
        return generated_archive, archive_url, {"drawing_set": drawing_set.model_dump(mode="json")}

    return submit(job, task)


@app.post("/api/v1/projects/{project_id}/assets/{category}/{slot}", response_model=Project)
async def upload_asset(project_id: str, category: str, slot: str, file: UploadFile = File(...), label: str = Form("")) -> Project:
    project = project_or_404(project_id)
    if category not in {"flooring", "walls", "kitchen", "living_room", "bathroom"}:
        raise HTTPException(status_code=400, detail="Unknown asset category")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=415, detail="Asset must be PNG, JPG, JPEG or WEBP")
    destination = await save_upload(project_id, file, f"assets/{category}", f"{slot}-")
    key = f"{category}/{slot}"
    asset = AssetFile(
        filename=destination.name,
        path=str(destination),
        url=f"/api/v1/projects/{project_id}/files/assets/{category}/{destination.name}",
        category=category,
        slot=slot,
        label=label.strip() or slot.replace("_", " ").title(),
    )
    if category not in {"flooring", "walls"}:
        mesh_output = project_dir(project_id) / "assets" / category / f"{slot}.glb"
        try:
            generated = reconstruct_image_to_3d(destination, mesh_output)
            if generated:
                asset.mesh_path = str(generated)
                asset.mesh_url = f"/api/v1/projects/{project_id}/files/assets/{category}/{generated.name}"
                asset.status = "mesh_ready"
        except Exception as exc:
            asset.status = f"reconstruction_failed: {str(exc)[:160]}"
    project.assets[key] = asset
    project.status = "assets_uploaded"
    return save_project(project)


@app.post("/api/v1/projects/{project_id}/analyze", response_model=SceneManifest)
def analyze(project_id: str, request: AnalyzeRequest) -> SceneManifest:
    project = project_or_404(project_id)
    if not project.floorplan:
        raise HTTPException(status_code=409, detail="Upload a floor plan first")
    preview_path = project_dir(project_id) / "working" / "floorplan.png"
    try:
        scene = analyze_floorplan(project_id, preview_path, request)
        scene = apply_assets(scene, project.assets)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    project.scene = scene
    project.status = "analyzed"
    write_json(project_dir(project_id) / "working" / "scene.json", scene.model_dump(mode="json"))
    save_project(project)
    return scene


@app.patch("/api/v1/projects/{project_id}/rooms/{room_id}", response_model=SceneManifest)
def update_room(project_id: str, room_id: str, request: RoomUpdateRequest) -> SceneManifest:
    project = project_or_404(project_id)
    if not project.scene:
        raise HTTPException(status_code=409, detail="Analyze the floor plan first")
    room = next((item for item in project.scene.rooms if item.id == room_id), None)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    room.name = request.name
    project.scene = apply_assets(project.scene, project.assets)
    write_json(project_dir(project_id) / "working" / "scene.json", project.scene.model_dump(mode="json"))
    save_project(project)
    return project.scene


@app.post("/api/v1/projects/{project_id}/render", response_model=Job)
def render(project_id: str, request: RenderRequest) -> Job:
    project = project_or_404(project_id)
    if not project.scene:
        raise HTTPException(status_code=409, detail="Analyze the floor plan first")
    job = create_job(project_id, f"render_{request.quality}")
    output = project_dir(project_id) / "outputs" / f"render-{job.id[:8]}.png"
    scene_path = project_dir(project_id) / "working" / "scene.json"
    write_json(scene_path, project.scene.model_dump(mode="json"))

    def task(progress):
        if request.engine == "technical":
            technical_render(project.scene, output, request.quality, progress)
        elif request.engine == "blender":
            blender_render(scene_path, output, request.quality, "still", 15, progress)
        else:
            try:
                blender_render(scene_path, output, request.quality, "still", 15, progress)
            except Exception:
                technical_render(project.scene, output, request.quality, progress)
        return output, f"/api/v1/projects/{project_id}/files/outputs/{output.name}"
    return submit(job, task)


@app.post("/api/v1/projects/{project_id}/walkthrough", response_model=Job)
def walkthrough(project_id: str, request: WalkthroughRequest) -> Job:
    project = project_or_404(project_id)
    if not project.scene:
        raise HTTPException(status_code=409, detail="Analyze the floor plan first")
    job = create_job(project_id, "video_walkthrough")
    output = project_dir(project_id) / "outputs" / f"walkthrough-{job.id[:8]}.mp4"
    scene_path = project_dir(project_id) / "working" / "scene.json"
    write_json(scene_path, project.scene.model_dump(mode="json"))

    def task(progress):
        progress(5, "Preparing deterministic camera path")
        blender_render(scene_path, output, request.quality, "video", request.seconds, progress)
        return output, f"/api/v1/projects/{project_id}/files/outputs/{output.name}"
    return submit(job, task)


@app.get("/api/v1/jobs/{job_id}", response_model=Job)
def job_status(job_id: str) -> Job:
    try:
        return get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")


@app.get("/api/v1/settings")
def get_settings() -> dict[str, Any]:
    return load_settings()


@app.put("/api/v1/settings")
def update_settings(settings: dict[str, Any]) -> dict[str, Any]:
    return save_settings(settings)


@app.get("/api/v1/projects/{project_id}/files/{relative_path:path}")
def project_file(project_id: str, relative_path: str):
    root = project_dir(project_id).resolve()
    target = (root / relative_path).resolve()
    if root not in target.parents or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target)
