from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FloorplanFile(BaseModel):
    filename: str
    path: str
    preview_url: str
    width_px: int | None = None
    height_px: int | None = None


class BuildingModelFile(BaseModel):
    filename: str
    path: str
    url: str
    format: str
    size_bytes: int


class AssetFile(BaseModel):
    filename: str
    path: str
    url: str
    category: str
    slot: str
    label: str
    status: str = "uploaded"
    mesh_path: str | None = None
    mesh_url: str | None = None


class WallSegment(BaseModel):
    id: str
    start: tuple[float, float]
    end: tuple[float, float]
    height: float
    thickness: float = 0.16


class RoomShape(BaseModel):
    id: str
    name: str
    polygon: list[tuple[float, float]]
    area_m2: float
    centroid: tuple[float, float]


class SceneAsset(BaseModel):
    id: str
    category: str
    slot: str
    label: str
    room_id: str | None = None
    position: tuple[float, float, float]
    rotation_y: float = 0.0
    size: tuple[float, float, float]
    source_url: str | None = None
    source_path: str | None = None
    mesh_url: str | None = None
    mesh_path: str | None = None


class SceneManifest(BaseModel):
    project_id: str
    width_m: float
    depth_m: float
    wall_height_m: float
    walls: list[WallSegment]
    rooms: list[RoomShape]
    assets: list[SceneAsset]
    camera_path: list[tuple[float, float, float]]
    floor_texture_url: str | None = None
    floor_texture_path: str | None = None
    wall_texture_url: str | None = None
    wall_texture_path: str | None = None
    reference_image_url: str | None = None
    reference_image_path: str | None = None
    detection_preview_url: str | None = None
    wall_detection_mode: str = "clean"
    plan_type: Literal["auto", "blueprint", "rendered"] = "auto"
    layout_mode: Literal["automatic", "manual"] = "automatic"
    warnings: list[str] = Field(default_factory=list)


class DrawingFile(BaseModel):
    kind: str
    format: str
    filename: str
    path: str
    url: str


class DrawingSet(BaseModel):
    project_id: str
    source_filename: str
    created_at: str = Field(default_factory=utc_now)
    slice_height_m: float
    up_axis: Literal["y", "z"]
    model_units: str
    bounds_m: tuple[float, float, float]
    files: list[DrawingFile] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Project(BaseModel):
    id: str
    name: str
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    floorplan: FloorplanFile | None = None
    building_model: BuildingModelFile | None = None
    assets: dict[str, AssetFile] = Field(default_factory=dict)
    status: str = "created"
    scene: SceneManifest | None = None
    drawing_set: DrawingSet | None = None


class CreateProjectRequest(BaseModel):
    name: str = "My Dream Home"


class SaveSlotRequest(BaseModel):
    name: str = Field(default="Saved Build", min_length=1, max_length=80)


class SaveSlotSummary(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    status: str
    floorplan_filename: str | None = None
    building_model_filename: str | None = None
    preview_url: str | None = None
    asset_count: int = 0
    has_scene: bool = False
    has_drawings: bool = False


class AnalyzeRequest(BaseModel):
    plan_width_m: float = Field(default=14.0, gt=1, le=500)
    wall_height_m: float = Field(default=2.8, ge=2.0, le=8.0)
    wall_thickness_m: float = Field(default=0.16, ge=0.05, le=1.0)
    wall_detection: Literal["clean", "balanced", "detailed"] = "clean"
    minimum_wall_length_m: float = Field(default=0.9, ge=0.3, le=10.0)
    plan_type: Literal["auto", "blueprint", "rendered"] = "auto"


class ManualLayoutRequest(BaseModel):
    plan_width_m: float = Field(default=14.0, gt=1, le=500)
    wall_height_m: float = Field(default=2.8, ge=2.0, le=8.0)
    wall_thickness_m: float = Field(default=0.16, ge=0.05, le=1.0)
    clear_existing: bool = True


class RoomCreateRequest(BaseModel):
    name: str = Field(default="New Room", min_length=1, max_length=80)
    x: float = 1.0
    z: float = 1.0
    width: float = Field(default=3.0, ge=0.4, le=200.0)
    depth: float = Field(default=3.0, ge=0.4, le=200.0)


class RoomGeometryRequest(BaseModel):
    polygon: list[tuple[float, float]] = Field(min_length=3, max_length=64)


class DrawingRequest(BaseModel):
    slice_height_m: float = Field(default=1.2, ge=0.05, le=100.0)
    up_axis: Literal["y", "z"] = "y"
    model_units: Literal["auto", "metres", "millimetres", "centimetres", "feet"] = "auto"
    include_dimensions: bool = True


class RoomUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class RenderRequest(BaseModel):
    quality: Literal["preview", "1080p", "4k"] = "preview"
    engine: Literal["auto", "technical", "blender"] = "auto"


class WalkthroughRequest(BaseModel):
    seconds: int = Field(default=15, ge=5, le=30)
    quality: Literal["1080p", "4k"] = "1080p"
    engine: Literal["auto", "blender"] = "auto"


class Job(BaseModel):
    id: str
    project_id: str
    kind: str
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    progress: int = 0
    message: str = "Queued"
    output_url: str | None = None
    output_path: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
