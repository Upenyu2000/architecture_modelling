from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image

from .models import AssetFile, BuildingModelFile, FloorplanFile, Project
from .storage import load_project, project_dir, restore_save_slot, save_project, save_upload
from .services.floorplan import rasterize_floorplan

router = APIRouter(prefix="/api/v1")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}
MODEL_SUFFIXES = {".glb", ".gltf", ".obj", ".fbx", ".stl", ".ply", ".blend"}


def _project(project_id: str) -> Project:
    try:
        return load_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


def _inside_project(project_id: str, relative_path: str) -> Path:
    root = project_dir(project_id).resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=403, detail="Requested file is outside the project directory")
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return candidate


@router.post("/projects/{project_id}/floorplan", response_model=Project)
async def upload_floorplan(project_id: str, file: UploadFile = File(...)) -> Project:
    project = _project(project_id)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise HTTPException(status_code=415, detail="Floor plans must be PNG, JPG, WEBP or PDF")

    source = await save_upload(project_id, file, "uploads/floorplans")
    working = project_dir(project_id) / "working"
    preview = working / "floorplan.png"
    for stale_name in ("building-mask.png", "interior-mask.png", "detection-preview.png"):
        (working / stale_name).unlink(missing_ok=True)
    try:
        rasterize_floorplan(source, preview)
        with Image.open(preview) as image:
            width_px, height_px = image.size
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"The floor plan could not be prepared: {exc}") from exc

    preview_url = f"/api/v1/projects/{project_id}/floorplan-preview"
    project.floorplan = FloorplanFile(
        filename=source.name,
        path=str(source),
        preview_url=preview_url,
        width_px=width_px,
        height_px=height_px,
    )
    if project.scene:
        project.scene.reference_image_url = preview_url
        project.scene.reference_image_path = str(preview)
    project.status = "floorplan_uploaded"
    return save_project(project)


@router.get("/projects/{project_id}/floorplan-preview")
def floorplan_preview(project_id: str) -> FileResponse:
    _project(project_id)
    preview = project_dir(project_id) / "working" / "floorplan.png"
    if not preview.exists():
        raise HTTPException(status_code=404, detail="Floor-plan preview is unavailable")
    return FileResponse(
        preview,
        media_type="image/png",
        headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
    )


@router.get("/projects/{project_id}/building-mask")
def building_mask(project_id: str) -> FileResponse:
    _project(project_id)
    target = project_dir(project_id) / "working" / "building-mask.png"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Building mask is unavailable until the floor plan is analysed")
    return FileResponse(
        target,
        media_type="image/png",
        headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
    )


@router.get("/projects/{project_id}/files/{relative_path:path}")
def project_file(project_id: str, relative_path: str) -> FileResponse:
    _project(project_id)
    target = _inside_project(project_id, relative_path)
    return FileResponse(target, headers={"Cache-Control": "private, max-age=60"})


@router.post("/projects/{project_id}/assets/{category}/{slot}", response_model=Project)
async def upload_surface_asset(
    project_id: str,
    category: str,
    slot: str,
    file: UploadFile = File(...),
    label: str = Form(""),
) -> Project:
    project = _project(project_id)
    if category not in {"flooring", "walls"}:
        raise HTTPException(status_code=400, detail="This route accepts flooring or wall material images only")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in IMAGE_SUFFIXES - {".pdf"}:
        raise HTTPException(status_code=415, detail="Surface materials must be PNG, JPG or WEBP")
    destination = await save_upload(project_id, file, f"assets/{category}", f"{slot}-")
    key = f"{category}/{slot}"
    project.assets[key] = AssetFile(
        filename=destination.name,
        path=str(destination),
        url=f"/api/v1/projects/{project_id}/files/assets/{category}/{destination.name}",
        category=category,
        slot=slot,
        label=label.strip() or slot.replace("_", " ").title(),
        status="reference_ready",
    )
    project.status = "surface_asset_uploaded"
    return save_project(project)


@router.post("/projects/{project_id}/building-model", response_model=Project)
async def upload_building_model(project_id: str, file: UploadFile = File(...)) -> Project:
    project = _project(project_id)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in MODEL_SUFFIXES:
        raise HTTPException(status_code=415, detail="Building models must be GLB, GLTF, OBJ, FBX, STL, PLY or BLEND")
    destination = await save_upload(project_id, file, "uploads/building_models")
    project.building_model = BuildingModelFile(
        filename=destination.name,
        path=str(destination),
        url=f"/api/v1/projects/{project_id}/files/uploads/building_models/{destination.name}",
        format=suffix.lstrip("."),
        size_bytes=destination.stat().st_size,
    )
    project.status = "building_model_uploaded"
    return save_project(project)


@router.post("/projects/{project_id}/save-slots/{slot_id}/load", response_model=Project)
@router.post("/projects/{project_id}/save-slots/{slot_id}/restore", response_model=Project)
def load_saved_build(project_id: str, slot_id: str) -> Project:
    _project(project_id)
    try:
        return restore_save_slot(project_id, slot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Save slot not found") from exc


@router.get("/projects/{project_id}/storage")
def project_storage(project_id: str) -> dict[str, str]:
    _project(project_id)
    root = project_dir(project_id).resolve()
    return {
        "project": str(root),
        "save_slots": str((root / "save_slots").resolve()),
        "uploads": str((root / "uploads").resolve()),
        "outputs": str((root / "outputs").resolve()),
    }
