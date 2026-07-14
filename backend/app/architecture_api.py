from __future__ import annotations

import math
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .models import AnalyzeRequest, MaterialUpdateRequest, Opening, Project, SceneManifest
from .storage import load_project, project_dir, save_project, save_upload, write_json
from .services.architecture import compile_architecture, update_materials
from .services.architecture_export import production_architecture_payload
from .services.furniture_detection import detect_furniture_symbols, merge_furniture_objects
from .services.opening_symbols import classify_opening_symbols
from .services.openings import restore_manual_openings
from .services.scene import apply_assets
from .services.segmentation import refine_scene_with_model
from .services.training_data import export_corrected_training_example, import_training_seed_pack
from .services.vector_refinement import add_diagonal_wall_candidates

router = APIRouter(prefix="/api/v1")


class TrainingExampleRequest(BaseModel):
    confirmed_rights: bool = False


def _project(project_id: str) -> Project:
    try:
        return load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


def _persist(project: Project, scene: SceneManifest, status: str) -> SceneManifest:
    scene = apply_assets(scene, project.assets)
    scene.project_metadata.detected_objects = len(scene.fixtures_and_furniture) + len(scene.assets)
    scene.project_metadata.detected_openings = len(scene.openings)
    scene.project_metadata.detected_rooms = len(scene.rooms)
    working = project_dir(project.id) / "working"
    scene_path = working / "scene.json"
    export_path = working / "architecture.json"
    scene.architecture_json_url = f"/api/v1/projects/{project.id}/architecture.json"
    write_json(scene_path, scene.model_dump(mode="json"))
    write_json(export_path, production_architecture_payload(scene))
    project.scene = scene
    project.status = status
    save_project(project)
    return scene


def _priority(opening: Opening) -> tuple[int, float]:
    return ({"manual": 4, "vision": 3, "model": 2, "heuristic": 1}.get(opening.source, 0), opening.confidence)


def _merge_openings(primary: list[Opening], secondary: list[Opening]) -> list[Opening]:
    merged: list[Opening] = []
    for opening in [*primary, *secondary]:
        duplicate = next((
            item for item in merged
            if math.dist(item.position, opening.position) <= max(0.3, min(item.width, opening.width) * 0.5)
            and (not item.wall_id or not opening.wall_id or item.wall_id == opening.wall_id)
        ), None)
        if duplicate is None:
            merged.append(opening)
        elif _priority(opening) > _priority(duplicate):
            merged[merged.index(duplicate)] = opening
    return merged[:160]


@router.post("/projects/{project_id}/compile-architecture", response_model=SceneManifest)
def compile_project_architecture(project_id: str, request: AnalyzeRequest) -> SceneManifest:
    project = _project(project_id)
    if not project.scene:
        raise HTTPException(status_code=409, detail="Analyze the floor plan or create a manual layout first")
    if not project.floorplan:
        raise HTTPException(status_code=409, detail="Upload a floor plan first")
    image_path = project_dir(project_id) / "working" / "floorplan.png"
    if not image_path.exists():
        raise HTTPException(status_code=409, detail="The floor-plan preview is unavailable")
    try:
        manual_openings = [item.model_copy(deep=True) for item in project.scene.openings if item.source == "manual"]
        user_furniture = [item.model_copy(deep=True) for item in project.scene.fixtures_and_furniture if item.source == "user"]
        vector_refined = add_diagonal_wall_candidates(project.scene, image_path)
        refined = refine_scene_with_model(vector_refined, image_path)
        learned_openings = [item.model_copy(deep=True) for item in refined.openings if item.source != "manual"]
        scene = compile_architecture(refined, image_path, request)
        scene = classify_opening_symbols(scene, image_path)
        scene.openings = _merge_openings(learned_openings, scene.openings)
        scene = restore_manual_openings(scene, manual_openings)
        detected_furniture = detect_furniture_symbols(scene, image_path) if request.auto_furnish else []
        scene.fixtures_and_furniture = merge_furniture_objects(
            user_furniture,
            detected_furniture,
            scene.fixtures_and_furniture if request.auto_furnish else [],
        )
        scene.project_metadata.detected_openings = len(scene.openings)
        scene.project_metadata.detected_objects = len(scene.fixtures_and_furniture)
        if detected_furniture:
            message = f"Detected {len(detected_furniture)} room-aware furniture footprint proposals. Verify or replace them in Interior Design."
            if message not in scene.warnings:
                scene.warnings.append(message)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Architectural compilation failed: {exc}")
    return _persist(project, scene, "architecture_compiled")


@router.post("/projects/{project_id}/training-example")
def create_training_example(project_id: str, request: TrainingExampleRequest) -> dict[str, object]:
    project = _project(project_id)
    if not request.confirmed_rights:
        raise HTTPException(status_code=400, detail="Confirm that you own or are authorised to use this plan for model training.")
    if not project.floorplan or not project.scene:
        raise HTTPException(status_code=409, detail="Upload a plan and confirm its room geometry first.")
    image_path = project_dir(project_id) / "working" / "floorplan.png"
    try:
        return export_corrected_training_example(project, image_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/projects/{project_id}/training-seed-pack")
async def import_seed_pack(
    project_id: str,
    file: UploadFile = File(...),
    confirmed_rights: bool = Form(False),
) -> dict[str, object]:
    _project(project_id)
    if Path(file.filename or "").suffix.lower() != ".zip":
        raise HTTPException(status_code=415, detail="Training seed pack must be a ZIP archive")
    archive_path = await save_upload(project_id, file, "training-imports", "seed-pack-")
    try:
        return import_training_seed_pack(archive_path, confirmed_rights=confirmed_rights)
    except (ValueError, zipfile.BadZipFile) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.put("/projects/{project_id}/materials", response_model=SceneManifest)
def set_project_materials(project_id: str, request: MaterialUpdateRequest) -> SceneManifest:
    project = _project(project_id)
    if not project.scene:
        raise HTTPException(status_code=409, detail="Create a scene before applying materials")
    scene = update_materials(
        project.scene,
        palette_name=request.palette_name,
        floor_type=request.floor_type,
        floor_color=request.floor_color,
        wall_color=request.wall_color,
        exterior_color=request.exterior_color,
        accent_color=request.accent_color,
        roughness=request.roughness,
        cutaway_height_m=request.cutaway_height_m,
    )
    return _persist(project, scene, "materials_updated")


@router.get("/projects/{project_id}/architecture.json")
def download_architecture_json(project_id: str):
    project = _project(project_id)
    if not project.scene:
        raise HTTPException(status_code=409, detail="Compile the architectural scene first")
    target = project_dir(project_id) / "working" / "architecture.json"
    write_json(target, production_architecture_payload(project.scene))
    return FileResponse(target, filename=f"{project.name.replace(' ', '-')}-architecture.json", media_type="application/json")
