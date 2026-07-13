from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .models import OpeningCreateRequest, OpeningUpdateRequest, Project, SceneManifest
from .storage import load_project, project_dir, save_project, write_json
from .services.openings import add_opening, delete_opening, update_opening
from .services.scene import apply_assets


router = APIRouter(prefix="/api/v1")


def _project(project_id: str) -> Project:
    try:
        return load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


def _persist(project: Project, scene: SceneManifest) -> SceneManifest:
    scene = apply_assets(scene, project.assets)
    scene.project_metadata.detected_openings = len(scene.openings)
    project.scene = scene
    project.status = "openings_updated"
    write_json(project_dir(project.id) / "working" / "scene.json", scene.model_dump(mode="json"))
    write_json(project_dir(project.id) / "working" / "architecture.json", scene.model_dump(mode="json"))
    save_project(project)
    return scene


@router.post("/projects/{project_id}/openings", response_model=SceneManifest)
def create_opening(project_id: str, request: OpeningCreateRequest) -> SceneManifest:
    project = _project(project_id)
    if not project.scene:
        raise HTTPException(status_code=409, detail="Analyze the plan or create a manual layout first")
    if not project.scene.walls:
        raise HTTPException(status_code=409, detail="Create or detect walls before adding doors and windows")
    try:
        scene = add_opening(project.scene, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _persist(project, scene)


@router.patch("/projects/{project_id}/openings/{opening_id}", response_model=SceneManifest)
def change_opening(project_id: str, opening_id: str, request: OpeningUpdateRequest) -> SceneManifest:
    project = _project(project_id)
    if not project.scene:
        raise HTTPException(status_code=409, detail="Analyze the plan or create a manual layout first")
    try:
        scene = update_opening(project.scene, opening_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _persist(project, scene)


@router.delete("/projects/{project_id}/openings/{opening_id}", response_model=SceneManifest)
def remove_opening(project_id: str, opening_id: str) -> SceneManifest:
    project = _project(project_id)
    if not project.scene:
        raise HTTPException(status_code=409, detail="Analyze the plan or create a manual layout first")
    try:
        scene = delete_opening(project.scene, opening_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _persist(project, scene)
