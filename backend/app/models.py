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
    warnings: list[str] = Field(default_factory=list)


class Project(BaseModel):
    id: str
    name: str
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    floorplan: FloorplanFile | None = None
    assets: dict[str, AssetFile] = Field(default_factory=dict)
    status: str = "created"
    scene: SceneManifest | None = None


class CreateProjectRequest(BaseModel):
    name: str = "My Dream Home"


class AnalyzeRequest(BaseModel):
    plan_width_m: float = Field(default=14.0, gt=1, le=500)
    wall_height_m: float = Field(default=2.8, ge=2.0, le=8.0)
    wall_thickness_m: float = Field(default=0.16, ge=0.05, le=1.0)


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
