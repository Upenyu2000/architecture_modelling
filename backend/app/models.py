from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


OpeningType = Literal[
    "door",
    "double_door",
    "pocket_door",
    "double_pocket_door",
    "bypass_door",
    "sliding_door",
    "double_sliding_door",
    "sliding_glass_door",
    "bifold_door",
    "double_bifold_door",
    "folding_door",
    "overhead_door",
    "revolving_door",
    "open_passage",
    "window",
    "fixed_window",
    "casement_window",
    "double_casement_window",
    "glider_window",
    "garden_window",
    "bay_window",
    "bow_window",
    "double_hung_window",
    "vertical_sliding_window",
    "horizontal_sliding_window",
]


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
    wall_type: Literal["exterior", "interior", "partition"] = "interior"
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)


class RoomShape(BaseModel):
    id: str
    name: str
    polygon: list[tuple[float, float]]
    area_m2: float
    centroid: tuple[float, float]
    room_type: str = "room"
    width_m: float | None = None
    depth_m: float | None = None
    extracted_dimension: str | None = None
    label_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class Opening(BaseModel):
    id: str
    opening_type: OpeningType
    position: tuple[float, float]
    width: float = Field(gt=0.15, le=20.0)
    height: float = Field(default=2.1, gt=0.15, le=12.0)
    rotation_deg: float = 0.0
    wall_id: str | None = None
    placement_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    swing_direction: Literal["clockwise", "counterclockwise", "none"] = "none"
    hinge_side: Literal["left", "right", "centre", "none"] = "none"
    swing_angle_deg: float = Field(default=90.0, ge=0.0, le=360.0)
    sill_height: float = Field(default=0.9, ge=0.0, le=8.0)
    interactive: bool = True
    default_open: bool = False
    source: Literal["heuristic", "model", "vision", "manual"] = "heuristic"
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)


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
    source: str = "user_upload"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ArchitecturalObject(BaseModel):
    id: str
    object_type: str
    asset_id: str
    category: Literal["furniture", "fixture", "utility", "structure"]
    room_id: str | None = None
    coordinates: tuple[float, float, float]
    rotation_deg: float = 0.0
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    size: tuple[float, float, float] = (1.0, 1.0, 1.0)
    source: Literal["vision", "symbol_heuristic", "room_inference", "user"] = "room_inference"
    confidence: float = Field(default=0.45, ge=0.0, le=1.0)


class MaterialSpec(BaseModel):
    name: str
    material_type: str
    hex_color: str
    roughness: float = Field(default=0.6, ge=0.0, le=1.0)
    metallic: float = Field(default=0.0, ge=0.0, le=1.0)
    specular: float = Field(default=0.5, ge=0.0, le=1.0)
    texture_url: str | None = None
    normal_url: str | None = None
    displacement_url: str | None = None
    texture_scale: float = Field(default=1.0, gt=0.0, le=100.0)


class SceneMaterials(BaseModel):
    palette_name: str = "Light Oak / Modern Tech"
    floor_global: MaterialSpec = Field(default_factory=lambda: MaterialSpec(
        name="Light Oak", material_type="hardwood", hex_color="#B99268", roughness=0.46, metallic=0.0, specular=0.32,
    ))
    walls_global: MaterialSpec = Field(default_factory=lambda: MaterialSpec(
        name="Warm White", material_type="paint", hex_color="#E8E5DE", roughness=0.82, metallic=0.0, specular=0.2,
    ))
    exterior_walls: MaterialSpec = Field(default_factory=lambda: MaterialSpec(
        name="Soft Grey Masonry", material_type="masonry", hex_color="#9C9C96", roughness=0.88, metallic=0.0, specular=0.15,
    ))
    accent: MaterialSpec = Field(default_factory=lambda: MaterialSpec(
        name="Technology Blue", material_type="accent", hex_color="#2E79C6", roughness=0.5, metallic=0.05, specular=0.45,
    ))
    fixture_metal: MaterialSpec = Field(default_factory=lambda: MaterialSpec(
        name="Brushed Steel", material_type="metal", hex_color="#A6ADB2", roughness=0.28, metallic=0.82, specular=0.75,
    ))


class ProjectMetadata(BaseModel):
    scale_ratio: str = "unverified"
    detected_rooms: int = 0
    detected_openings: int = 0
    detected_objects: int = 0
    parser_version: str = "arch-ai-1.0"
    source_plan_type: str = "unknown"
    structural_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    ocr_status: str = "not_configured"
    extracted_labels: list[str] = Field(default_factory=list)


class SceneManifest(BaseModel):
    project_id: str
    width_m: float
    depth_m: float
    wall_height_m: float
    walls: list[WallSegment]
    rooms: list[RoomShape]
    assets: list[SceneAsset]
    camera_path: list[tuple[float, float, float]]
    openings: list[Opening] = Field(default_factory=list)
    fixtures_and_furniture: list[ArchitecturalObject] = Field(default_factory=list)
    materials: SceneMaterials = Field(default_factory=SceneMaterials)
    project_metadata: ProjectMetadata = Field(default_factory=ProjectMetadata)
    first_person_start: tuple[float, float, float] | None = None
    collision_segments: list[tuple[tuple[float, float], tuple[float, float]]] = Field(default_factory=list)
    ceiling_height_m: float = 2.8
    cutaway_height_m: float = 1.65
    floor_texture_url: str | None = None
    floor_texture_path: str | None = None
    wall_texture_url: str | None = None
    wall_texture_path: str | None = None
    reference_image_url: str | None = None
    reference_image_path: str | None = None
    detection_preview_url: str | None = None
    architecture_json_url: str | None = None
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
    detect_openings: bool = True
    auto_furnish: bool = True
    use_vision_ai: bool = False


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


class OpeningCreateRequest(BaseModel):
    opening_type: OpeningType = "door"
    wall_id: str
    placement_ratio: float = Field(default=0.5, ge=0.0, le=1.0)
    width: float | None = Field(default=None, gt=0.15, le=20.0)
    height: float | None = Field(default=None, gt=0.15, le=12.0)
    swing_direction: Literal["clockwise", "counterclockwise", "none"] = "clockwise"
    hinge_side: Literal["left", "right", "centre", "none"] = "left"
    swing_angle_deg: float = Field(default=90.0, ge=0.0, le=360.0)
    sill_height: float = Field(default=0.9, ge=0.0, le=8.0)
    interactive: bool = True
    default_open: bool = False


class OpeningUpdateRequest(BaseModel):
    opening_type: OpeningType | None = None
    wall_id: str | None = None
    placement_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    width: float | None = Field(default=None, gt=0.15, le=20.0)
    height: float | None = Field(default=None, gt=0.15, le=12.0)
    swing_direction: Literal["clockwise", "counterclockwise", "none"] | None = None
    hinge_side: Literal["left", "right", "centre", "none"] | None = None
    swing_angle_deg: float | None = Field(default=None, ge=0.0, le=360.0)
    sill_height: float | None = Field(default=None, ge=0.0, le=8.0)
    interactive: bool | None = None
    default_open: bool | None = None


class DrawingRequest(BaseModel):
    slice_height_m: float = Field(default=1.2, ge=0.05, le=100.0)
    up_axis: Literal["y", "z"] = "y"
    model_units: Literal["auto", "metres", "millimetres", "centimetres", "feet"] = "auto"
    include_dimensions: bool = True


class RoomUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class MaterialUpdateRequest(BaseModel):
    palette_name: str = Field(default="Light Oak / Modern Tech", min_length=1, max_length=100)
    floor_type: str = Field(default="hardwood", min_length=1, max_length=60)
    floor_color: str = Field(default="#B99268", pattern=r"^#[0-9A-Fa-f]{6}$")
    wall_color: str = Field(default="#E8E5DE", pattern=r"^#[0-9A-Fa-f]{6}$")
    exterior_color: str = Field(default="#9C9C96", pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str = Field(default="#2E79C6", pattern=r"^#[0-9A-Fa-f]{6}$")
    roughness: float = Field(default=0.55, ge=0.0, le=1.0)
    cutaway_height_m: float = Field(default=1.65, ge=0.6, le=3.5)


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
