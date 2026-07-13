from __future__ import annotations

import math
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .models import AnalyzeRequest, MaterialUpdateRequest, Opening, Project, SceneManifest
from .storage import load_project, project_dir, save_project, write_json
from .services.architecture import compile_architecture, update_materials
from .services.scene import apply_assets
from .services.segmentation import refine_scene_with_model
from .services.training_data import export_corrected_training_example

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
    target = project_dir(project.id) / "working" / "architecture.json"
    scene.architecture_json_url = f"/api/v1/projects/{project.id}/architecture.json"
    write_json(target, scene.model_dump(mode="json"))
    write_json(project_dir(project.id) / "working" / "scene.json", scene.model_dump(mode="json"))
    project.scene = scene
    project.status = status
    save_project(project)
    return scene


def _merge_openings(primary: list[Opening], secondary: list[Opening]) -> list[Opening]:
    merged: list[Opening] = []
    for opening in [*primary, *secondary]:
        duplicate = next((
            item for item in merged
            if item.opening_type == opening.opening_type
            and math.dist(item.position, opening.position) <= max(0.3, min(item.width, opening.width) * 0.45)
        ), None)
        if duplicate is None:
            merged.append(opening)
        elif opening.confidence > duplicate.confidence:
            merged[merged.index(duplicate)] = opening
    return merged[:120]


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
        refined = refine_scene_with_model(project.scene, image_path)
        learned_openings = list(refined.openings)
        scene = compile_architecture(refined, image_path, request)
        if learned_openings:
            scene.openings = _merge_openings(learned_openings, scene.openings)
            scene.project_metadata.detected_openings = len(scene.openings)
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
    write_json(target, project.scene.model_dump(mode="json"))
    return FileResponse(target, filename=f"{project.name.replace(' ', '-')}-architecture.json", media_type="application/json")
