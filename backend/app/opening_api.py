from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .models import OpeningType, Project, SceneManifest
from .storage import load_project, project_dir, save_project, write_json
from .services.openings import add_opening_at_position, delete_opening, update_opening_at_position
from .services.scene import apply_assets


router = APIRouter(prefix="/api/v1")


class DirectOpeningRequest(BaseModel):
    opening_type: OpeningType = "door"
    position: tuple[float, float] | None = None
    wall_id: str | None = None
    placement_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    rotation_deg: float = Field(default=0.0, ge=-360.0, le=360.0)
    snap_to_wall: bool = True
    width: float | None = Field(default=None, gt=0.15, le=20.0)
    height: float | None = Field(default=None, gt=0.15, le=12.0)
    swing_direction: Literal["clockwise", "counterclockwise", "none"] = "clockwise"
    hinge_side: Literal["left", "right", "centre", "none"] = "left"
    swing_angle_deg: float = Field(default=90.0, ge=0.0, le=360.0)
    sill_height: float = Field(default=0.9, ge=0.0, le=8.0)
    interactive: bool = True
    default_open: bool = False
    plan_width_m: float = Field(default=14.0, gt=1.0, le=500.0)
    wall_height_m: float = Field(default=2.8, ge=2.0, le=8.0)


class DirectOpeningUpdateRequest(BaseModel):
    opening_type: OpeningType | None = None
    position: tuple[float, float] | None = None
    wall_id: str | None = None
    placement_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    rotation_deg: float | None = Field(default=None, ge=-360.0, le=360.0)
    snap_to_wall: bool = True
    width: float | None = Field(default=None, gt=0.15, le=20.0)
    height: float | None = Field(default=None, gt=0.15, le=12.0)
    swing_direction: Literal["clockwise", "counterclockwise", "none"] | None = None
    hinge_side: Literal["left", "right", "centre", "none"] | None = None
    swing_angle_deg: float | None = Field(default=None, ge=0.0, le=360.0)
    sill_height: float | None = Field(default=None, ge=0.0, le=8.0)
    interactive: bool | None = None
    default_open: bool | None = None


def _project(project_id: str) -> Project:
    try:
        return load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


def _ensure_scene(project: Project, request: DirectOpeningRequest) -> SceneManifest:
    if project.scene:
        return project.scene
    if not project.floorplan or not project.floorplan.width_px or not project.floorplan.height_px:
        raise HTTPException(status_code=409, detail="Upload a floor plan before placing doors and windows")
    depth_m = request.plan_width_m * project.floorplan.height_px / project.floorplan.width_px
    return SceneManifest(
        project_id=project.id,
        width_m=round(request.plan_width_m, 3),
        depth_m=round(depth_m, 3),
        wall_height_m=request.wall_height_m,
        walls=[],
        rooms=[],
        assets=[],
        camera_path=[],
        reference_image_url=project.floorplan.preview_url,
        reference_image_path=str(project_dir(project.id) / "working" / "floorplan.png"),
        detection_preview_url=project.floorplan.preview_url,
        wall_detection_mode="manual",
        plan_type="blueprint",
        layout_mode="manual",
        warnings=[
            "Doors and windows can be placed directly on the source plan before rooms are traced.",
            "Unattached openings automatically snap to nearby walls after rooms are created or walls are detected.",
        ],
    )


def _requested_position(scene: SceneManifest, request: DirectOpeningRequest) -> tuple[float, float]:
    if request.position is not None:
        return request.position
    if request.wall_id:
        wall = next((item for item in scene.walls if item.id == request.wall_id), None)
        if wall is not None:
            ratio = request.placement_ratio if request.placement_ratio is not None else 0.5
            return (
                wall.start[0] + (wall.end[0] - wall.start[0]) * ratio,
                wall.start[1] + (wall.end[1] - wall.start[1]) * ratio,
            )
    return (scene.width_m / 2, scene.depth_m / 2)


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
@router.post("/projects/{project_id}/openings/direct", response_model=SceneManifest)
def create_opening(project_id: str, request: DirectOpeningRequest) -> SceneManifest:
    project = _project(project_id)
    scene = _ensure_scene(project, request)
    try:
        scene = add_opening_at_position(
            scene,
            opening_type=request.opening_type,
            position=_requested_position(scene, request),
            wall_id=request.wall_id or None,
            placement_ratio=request.placement_ratio,
            rotation_deg=request.rotation_deg,
            snap_to_wall=request.snap_to_wall,
            width=request.width,
            height=request.height,
            swing_direction=request.swing_direction,
            hinge_side=request.hinge_side,
            swing_angle_deg=request.swing_angle_deg,
            sill_height=request.sill_height,
            interactive=request.interactive,
            default_open=request.default_open,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _persist(project, scene)


@router.patch("/projects/{project_id}/openings/{opening_id}", response_model=SceneManifest)
@router.patch("/projects/{project_id}/openings/{opening_id}/direct", response_model=SceneManifest)
def change_opening(project_id: str, opening_id: str, request: DirectOpeningUpdateRequest) -> SceneManifest:
    project = _project(project_id)
    if not project.scene:
        raise HTTPException(status_code=409, detail="Place an opening or create a layout first")
    try:
        scene = update_opening_at_position(
            project.scene,
            opening_id,
            opening_type=request.opening_type,
            position=request.position,
            wall_id=request.wall_id or None,
            placement_ratio=request.placement_ratio,
            rotation_deg=request.rotation_deg,
            snap_to_wall=request.snap_to_wall,
            width=request.width,
            height=request.height,
            swing_direction=request.swing_direction,
            hinge_side=request.hinge_side,
            swing_angle_deg=request.swing_angle_deg,
            sill_height=request.sill_height,
            interactive=request.interactive,
            default_open=request.default_open,
        )
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
