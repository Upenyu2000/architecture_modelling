from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from .models import ArchitecturalObject, AssetFile, Project, SceneManifest
from .storage import load_project, project_dir, save_project, save_upload, write_json
from .services.providers import reconstruct_image_to_3d
from .services.scene import apply_assets

router = APIRouter(prefix="/api/v1")

MATERIALS = Literal["fabric", "leather", "oak", "walnut", "stone", "porcelain", "chrome", "painted_metal"]
INTERIOR_CATEGORIES = {
    "kitchen", "living_room", "bathroom", "bedroom", "dining_room", "office", "outdoor", "characters",
}
MODEL_SUFFIXES = {".glb", ".gltf", ".obj", ".stl", ".ply"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class FurnitureCreateRequest(BaseModel):
    object_type: str = Field(default="sofa", min_length=1, max_length=80)
    room_id: str | None = None
    x: float
    z: float
    rotation_deg: float = Field(default=0.0, ge=-360.0, le=360.0)
    width: float = Field(default=2.2, gt=0.15, le=30.0)
    height: float = Field(default=0.9, gt=0.1, le=12.0)
    depth: float = Field(default=0.95, gt=0.15, le=30.0)
    style: str = Field(default="modern", min_length=1, max_length=40)
    material: MATERIALS = "fabric"
    color: str = Field(default="#486B5A", pattern=r"^#[0-9A-Fa-f]{6}$")
    reference_asset_key: str | None = Field(default=None, max_length=180)


class FurnitureUpdateRequest(BaseModel):
    object_type: str | None = Field(default=None, min_length=1, max_length=80)
    room_id: str | None = None
    x: float | None = None
    z: float | None = None
    rotation_deg: float | None = Field(default=None, ge=-360.0, le=360.0)
    width: float | None = Field(default=None, gt=0.15, le=30.0)
    height: float | None = Field(default=None, gt=0.1, le=12.0)
    depth: float | None = Field(default=None, gt=0.15, le=30.0)
    style: str | None = Field(default=None, min_length=1, max_length=40)
    material: MATERIALS | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    reference_asset_key: str | None = Field(default=None, max_length=180)


DEFAULT_SIZES: dict[str, tuple[float, float, float]] = {
    "sofa": (2.25, 0.92, 0.98),
    "sectional_sofa": (2.8, 0.95, 1.45),
    "armchair": (1.0, 0.92, 0.95),
    "chair": (0.62, 0.92, 0.62),
    "bed": (1.65, 0.72, 2.05),
    "nightstand": (0.52, 0.56, 0.46),
    "dresser": (1.35, 0.92, 0.5),
    "coffee_table": (1.15, 0.46, 0.68),
    "dining_table": (1.9, 0.78, 1.0),
    "dining_chair": (0.55, 0.92, 0.58),
    "sideboard": (1.6, 0.9, 0.46),
    "tv_unit": (1.8, 0.65, 0.45),
    "wardrobe": (1.8, 2.1, 0.6),
    "desk": (1.45, 0.76, 0.7),
    "office_chair": (0.68, 1.05, 0.68),
    "shelving": (1.2, 2.0, 0.36),
    "lamp": (0.42, 1.55, 0.42),
    "kitchen_island": (2.1, 0.94, 0.95),
    "countertop": (2.1, 0.94, 0.7),
    "cabinetry": (2.4, 0.92, 0.62),
    "fridge": (0.9, 2.0, 0.75),
    "stove": (0.75, 0.92, 0.68),
    "washing_machine": (0.68, 0.9, 0.68),
    "dryer": (0.68, 0.9, 0.68),
    "sink": (0.65, 0.9, 0.55),
    "toilet": (0.48, 0.78, 0.72),
    "bathtub": (1.75, 0.62, 0.82),
    "vanity": (1.1, 0.9, 0.55),
    "light_fixture": (0.5, 0.65, 0.5),
    "patio_sofa": (2.2, 0.82, 0.92),
    "outdoor_table": (1.45, 0.75, 0.85),
    "planter": (0.55, 0.72, 0.55),
}


def _project(project_id: str) -> Project:
    try:
        return load_project(project_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")


def _encode(object_type: str, style: str, material: str, color: str, reference_asset_key: str | None) -> str:
    return "|".join((object_type, style, material, color, reference_asset_key or ""))


def _decode(value: str, fallback_type: str) -> tuple[str, str, str, str, str | None]:
    parts = str(value or "").split("|")
    parts.extend([""] * (5 - len(parts)))
    object_type = parts[0] or fallback_type
    style = parts[1] or "modern"
    material = parts[2] or "fabric"
    color = parts[3] if len(parts[3]) == 7 and parts[3].startswith("#") else "#486B5A"
    return object_type, style, material, color, parts[4] or None


def _room_polygons(scene: SceneManifest) -> list[tuple[str, Polygon]]:
    result: list[tuple[str, Polygon]] = []
    for room in scene.rooms:
        if len(room.polygon) < 3:
            continue
        polygon = Polygon(room.polygon)
        if polygon.is_valid and not polygon.is_empty:
            result.append((room.id, polygon))
    return result


def _room_at(scene: SceneManifest, x: float, z: float, requested: str | None = None) -> str | None:
    point = Point(x, z)
    polygons = _room_polygons(scene)
    containing = next((room_id for room_id, polygon in polygons if polygon.contains(point) or polygon.touches(point)), None)
    if containing:
        return containing

    # Automatic layouts use the confirmed room union as the authoritative
    # interior. Do not silently attach an outside point to the nearest room.
    if scene.layout_mode == "automatic":
        return None

    if requested and any(room.id == requested for room in scene.rooms):
        return requested
    if not scene.rooms:
        return None
    return min(scene.rooms, key=lambda room: (room.centroid[0] - x) ** 2 + (room.centroid[1] - z) ** 2).id


def _validate_furniture_footprint(scene: SceneManifest, x: float, z: float, width: float, depth: float) -> str | None:
    room_id = _room_at(scene, x, z)
    if scene.layout_mode != "automatic":
        return room_id
    polygons = [polygon for _room_id, polygon in _room_polygons(scene)]
    if not polygons:
        raise HTTPException(status_code=422, detail="No confirmed interior rooms are available")
    interior = unary_union(polygons).buffer(max(0.08, min(width, depth) * 0.08), join_style=2)
    footprint = Polygon([
        (x - width / 2, z - depth / 2),
        (x + width / 2, z - depth / 2),
        (x + width / 2, z + depth / 2),
        (x - width / 2, z + depth / 2),
    ])
    covered_ratio = float(footprint.intersection(interior).area) / max(float(footprint.area), 1e-6)
    if room_id is None or covered_ratio < 0.72:
        raise HTTPException(
            status_code=422,
            detail="Furniture cannot be placed in exterior white space. Move its centre and footprint inside the detected house boundary.",
        )
    return room_id


def _persist(project: Project, scene: SceneManifest) -> SceneManifest:
    scene = apply_assets(scene, project.assets)
    scene.project_metadata.detected_objects = len(scene.fixtures_and_furniture) + len(scene.assets)
    project.scene = scene
    project.status = "interior_updated"
    write_json(project_dir(project.id) / "working" / "scene.json", scene.model_dump(mode="json"))
    write_json(project_dir(project.id) / "working" / "architecture.json", scene.model_dump(mode="json"))
    save_project(project)
    return scene


@router.get("/interior-library")
def interior_library() -> dict[str, object]:
    return {
        "objects": [{"type": object_type, "size": size} for object_type, size in DEFAULT_SIZES.items()],
        "styles": ["modern", "contemporary", "classic", "minimal", "industrial", "scandinavian", "luxury"],
        "materials": ["fabric", "leather", "oak", "walnut", "stone", "porcelain", "chrome", "painted_metal"],
    }


@router.post("/projects/{project_id}/interior-assets/{category}/{slot}", response_model=Project)
async def upload_interior_asset(
    project_id: str,
    category: str,
    slot: str,
    file: UploadFile = File(...),
    label: str = Form(""),
) -> Project:
    project = _project(project_id)
    if category not in INTERIOR_CATEGORIES:
        raise HTTPException(status_code=400, detail="Unknown interior asset category")
    suffix = Path(file.filename or "").suffix.lower()
    allowed = MODEL_SUFFIXES if category == "characters" else IMAGE_SUFFIXES | MODEL_SUFFIXES
    if suffix not in allowed:
        raise HTTPException(
            status_code=415,
            detail="Character/model assets must be GLB, GLTF, OBJ, STL or PLY; reference images may be PNG, JPG or WEBP",
        )
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
    if suffix in MODEL_SUFFIXES:
        asset.mesh_path = str(destination)
        asset.mesh_url = asset.url
        asset.status = "mesh_ready"
    else:
        mesh_output = project_dir(project_id) / "assets" / category / f"{slot}.glb"
        try:
            generated = reconstruct_image_to_3d(destination, mesh_output)
            if generated:
                asset.mesh_path = str(generated)
                asset.mesh_url = f"/api/v1/projects/{project_id}/files/assets/{category}/{generated.name}"
                asset.status = "mesh_ready"
            else:
                asset.status = "reference_ready"
        except Exception as exc:
            asset.status = f"reference_ready; reconstruction_failed: {str(exc)[:140]}"
    project.assets[key] = asset
    project.status = "interior_asset_uploaded"
    if project.scene:
        project.scene = apply_assets(project.scene, project.assets)
        write_json(project_dir(project.id) / "working" / "scene.json", project.scene.model_dump(mode="json"))
    return save_project(project)


@router.post("/projects/{project_id}/furniture", response_model=SceneManifest)
def create_furniture(project_id: str, request: FurnitureCreateRequest) -> SceneManifest:
    project = _project(project_id)
    if not project.scene:
        raise HTTPException(status_code=409, detail="Create or analyze a room layout before adding furniture")
    scene = project.scene
    x = max(0.0, min(scene.width_m, request.x))
    z = max(0.0, min(scene.depth_m, request.z))
    size = (request.width, request.height, request.depth)
    room_id = _validate_furniture_footprint(scene, x, z, request.width, request.depth)
    item = ArchitecturalObject(
        id=f"furniture-{uuid.uuid4().hex[:10]}",
        object_type=request.object_type,
        asset_id=_encode(request.object_type, request.style, request.material, request.color, request.reference_asset_key),
        category="fixture" if request.object_type in {"sink", "toilet", "bathtub", "vanity"} else "utility" if request.object_type in {"fridge", "stove", "washing_machine", "dryer"} else "furniture",
        room_id=request.room_id if request.room_id and request.room_id == room_id else room_id,
        coordinates=(round(x, 3), round(request.height / 2, 3), round(z, 3)),
        rotation_deg=request.rotation_deg,
        size=tuple(round(value, 3) for value in size),
        scale=(1.0, 1.0, 1.0),
        source="user",
        confidence=1.0,
    )
    scene.fixtures_and_furniture.append(item)
    return _persist(project, scene)


@router.patch("/projects/{project_id}/furniture/{object_id}", response_model=SceneManifest)
def update_furniture(project_id: str, object_id: str, request: FurnitureUpdateRequest) -> SceneManifest:
    project = _project(project_id)
    if not project.scene:
        raise HTTPException(status_code=409, detail="Create or analyze a room layout first")
    scene = project.scene
    item = next((candidate for candidate in scene.fixtures_and_furniture if candidate.id == object_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Furniture object not found")

    current_type, current_style, current_material, current_color, current_reference = _decode(item.asset_id, item.object_type)
    object_type = request.object_type or current_type
    style = request.style or current_style
    material = request.material or current_material
    color = request.color or current_color
    reference = request.reference_asset_key if request.reference_asset_key is not None else current_reference
    x = max(0.0, min(scene.width_m, request.x if request.x is not None else item.coordinates[0]))
    z = max(0.0, min(scene.depth_m, request.z if request.z is not None else item.coordinates[2]))
    width = request.width if request.width is not None else item.size[0]
    height = request.height if request.height is not None else item.size[1]
    depth = request.depth if request.depth is not None else item.size[2]
    room_id = _validate_furniture_footprint(scene, x, z, width, depth)

    item.object_type = object_type
    item.asset_id = _encode(object_type, style, material, color, reference)
    item.room_id = request.room_id if request.room_id and request.room_id == room_id else room_id
    item.coordinates = (round(x, 3), round(height / 2, 3), round(z, 3))
    item.rotation_deg = request.rotation_deg if request.rotation_deg is not None else item.rotation_deg
    item.size = (round(width, 3), round(height, 3), round(depth, 3))
    item.category = "fixture" if object_type in {"sink", "toilet", "bathtub", "vanity"} else "utility" if object_type in {"fridge", "stove", "washing_machine", "dryer"} else "furniture"
    item.source = "user"
    item.confidence = 1.0
    return _persist(project, scene)


@router.delete("/projects/{project_id}/furniture/{object_id}", response_model=SceneManifest)
def remove_furniture(project_id: str, object_id: str) -> SceneManifest:
    project = _project(project_id)
    if not project.scene:
        raise HTTPException(status_code=409, detail="Create or analyze a room layout first")
    before = len(project.scene.fixtures_and_furniture)
    project.scene.fixtures_and_furniture = [item for item in project.scene.fixtures_and_furniture if item.id != object_id]
    if len(project.scene.fixtures_and_furniture) == before:
        raise HTTPException(status_code=404, detail="Furniture object not found")
    return _persist(project, project.scene)
