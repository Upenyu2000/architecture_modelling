from __future__ import annotations

import math
import re
import shutil
import uuid
from pathlib import Path
from typing import Any

import cv2
import httpx

from ..config import load_settings
from ..models import (
    AnalyzeRequest, ArchitecturalObject, MaterialSpec, Opening, ProjectMetadata,
    RoomShape, SceneManifest, SceneMaterials, WallSegment,
)

ROOM_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("master_bedroom", ("master bedroom", "primary bedroom", "master bed")),
    ("bedroom", ("bedroom", "bed room", "room 1", "room 2", "room 3", "room 4", "room 5")),
    ("bathroom", ("bathroom", "bath", "wc", "toilet", "shower")),
    ("kitchen", ("kitchen", "breakfast")),
    ("living_room", ("living room", "family room", "lounge")),
    ("dining_room", ("dining room", "dining")),
    ("garage", ("garage",)),
    ("laundry", ("laundry", "utility")),
    ("foyer", ("foyer", "entry", "hall", "corridor", "landing")),
    ("stairs", ("stairs", "stair", "staircase")),
    ("closet", ("closet", "wardrobe", "w.i.c", "wic")),
    ("porch", ("porch", "terrace", "balcony")),
    ("lift", ("lift", "elevator")),
]

DIMENSION_PATTERN = re.compile(
    r"(?P<a>\d{1,3})\s*(?:'|ft)?\s*[- ]?\s*(?P<ai>\d{0,2})\s*(?:\"|in)?\s*[xX×]\s*"
    r"(?P<b>\d{1,3})\s*(?:'|ft)?\s*[- ]?\s*(?P<bi>\d{0,2})\s*(?:\"|in)?"
)

PALETTES: dict[str, SceneMaterials] = {
    "Light Oak / Modern Tech": SceneMaterials(),
    "Warm Walnut / Blue Accents": SceneMaterials(
        palette_name="Warm Walnut / Blue Accents",
        floor_global=MaterialSpec(name="Warm Walnut", material_type="hardwood", hex_color="#74513B", roughness=0.42, specular=0.34),
        walls_global=MaterialSpec(name="Soft Ivory", material_type="paint", hex_color="#EEE8DD", roughness=0.82, specular=0.2),
        exterior_walls=MaterialSpec(name="Warm Grey Brick", material_type="brick", hex_color="#81756D", roughness=0.91, specular=0.12),
        accent=MaterialSpec(name="Navy Blue", material_type="accent", hex_color="#1F4772", roughness=0.52, specular=0.38),
        fixture_metal=MaterialSpec(name="Brushed Steel", material_type="metal", hex_color="#A6ADB2", roughness=0.28, metallic=0.82, specular=0.75),
    ),
    "Minimal White / Black Metal": SceneMaterials(
        palette_name="Minimal White / Black Metal",
        floor_global=MaterialSpec(name="Pale Ash", material_type="hardwood", hex_color="#C7B9A4", roughness=0.48, specular=0.3),
        walls_global=MaterialSpec(name="Gallery White", material_type="paint", hex_color="#F3F3F0", roughness=0.86, specular=0.16),
        exterior_walls=MaterialSpec(name="Graphite Render", material_type="render", hex_color="#555A5D", roughness=0.78, specular=0.22),
        accent=MaterialSpec(name="Matte Black", material_type="metal", hex_color="#171A1C", roughness=0.4, metallic=0.45, specular=0.55),
        fixture_metal=MaterialSpec(name="Black Chrome", material_type="metal", hex_color="#303438", roughness=0.24, metallic=0.88, specular=0.8),
    ),
    "Natural Stone / Sage": SceneMaterials(
        palette_name="Natural Stone / Sage",
        floor_global=MaterialSpec(name="Travertine", material_type="stone", hex_color="#BEB09B", roughness=0.62, specular=0.26),
        walls_global=MaterialSpec(name="Warm Chalk", material_type="paint", hex_color="#E7E1D5", roughness=0.86, specular=0.18),
        exterior_walls=MaterialSpec(name="Limestone", material_type="stone", hex_color="#A9A08E", roughness=0.9, specular=0.15),
        accent=MaterialSpec(name="Sage Green", material_type="accent", hex_color="#6F8068", roughness=0.58, specular=0.28),
        fixture_metal=MaterialSpec(name="Brushed Brass", material_type="metal", hex_color="#B18A52", roughness=0.3, metallic=0.78, specular=0.7),
    ),
}


def palette_by_name(name: str) -> SceneMaterials:
    palette = PALETTES.get(name) or PALETTES["Light Oak / Modern Tech"]
    return palette.model_copy(deep=True)


def _room_bounds(room: RoomShape) -> tuple[float, float, float, float]:
    xs = [point[0] for point in room.polygon]
    zs = [point[1] for point in room.polygon]
    return min(xs), min(zs), max(xs), max(zs)


def _classify_room(name: str) -> str:
    normalised = re.sub(r"\s+", " ", name.strip().lower())
    for room_type, keywords in ROOM_KEYWORDS:
        if any(keyword in normalised for keyword in keywords):
            return room_type
    return "room"


def _annotate_rooms(scene: SceneManifest) -> None:
    for room in scene.rooms:
        min_x, min_z, max_x, max_z = _room_bounds(room)
        room.width_m = round(max_x - min_x, 3)
        room.depth_m = round(max_z - min_z, 3)
        room.room_type = _classify_room(room.name)


def _classify_walls(scene: SceneManifest) -> None:
    boundary_tolerance = max(0.35, max((wall.thickness for wall in scene.walls), default=0.16) * 2.6)
    for wall in scene.walls:
        x1, z1 = wall.start
        x2, z2 = wall.end
        near_left = max(x1, x2) <= boundary_tolerance
        near_right = min(x1, x2) >= scene.width_m - boundary_tolerance
        near_top = max(z1, z2) <= boundary_tolerance
        near_bottom = min(z1, z2) >= scene.depth_m - boundary_tolerance
        wall.wall_type = "exterior" if near_left or near_right or near_top or near_bottom else "interior"
        wall.confidence = 0.88 if wall.wall_type == "exterior" else 0.76


def _group_axis_walls(walls: list[WallSegment], horizontal: bool, tolerance: float = 0.22) -> list[list[WallSegment]]:
    selected = []
    for wall in walls:
        dx = abs(wall.end[0] - wall.start[0])
        dz = abs(wall.end[1] - wall.start[1])
        if (horizontal and dx >= dz) or (not horizontal and dz > dx):
            selected.append(wall)
    groups: list[list[WallSegment]] = []
    for wall in sorted(selected, key=lambda item: ((item.start[1] + item.end[1]) / 2 if horizontal else (item.start[0] + item.end[0]) / 2)):
        coordinate = (wall.start[1] + wall.end[1]) / 2 if horizontal else (wall.start[0] + wall.end[0]) / 2
        target = next((group for group in groups if abs(
            (((group[0].start[1] + group[0].end[1]) / 2) if horizontal else ((group[0].start[0] + group[0].end[0]) / 2)) - coordinate
        ) <= tolerance), None)
        if target is None:
            groups.append([wall])
        else:
            target.append(wall)
    return groups


def _detect_openings(scene: SceneManifest) -> list[Opening]:
    openings: list[Opening] = []
    seen: set[tuple[int, int, str]] = set()
    for horizontal in (True, False):
        for group in _group_axis_walls(scene.walls, horizontal):
            if horizontal:
                ordered = sorted(group, key=lambda wall: min(wall.start[0], wall.end[0]))
            else:
                ordered = sorted(group, key=lambda wall: min(wall.start[1], wall.end[1]))
            for previous, current in zip(ordered, ordered[1:]):
                if horizontal:
                    previous_end = max(previous.start[0], previous.end[0])
                    current_start = min(current.start[0], current.end[0])
                    gap = current_start - previous_end
                    coordinate = ((previous.start[1] + previous.end[1] + current.start[1] + current.end[1]) / 4)
                    position = ((previous_end + current_start) / 2, coordinate)
                    rotation = 0.0
                else:
                    previous_end = max(previous.start[1], previous.end[1])
                    current_start = min(current.start[1], current.end[1])
                    gap = current_start - previous_end
                    coordinate = ((previous.start[0] + previous.end[0] + current.start[0] + current.end[0]) / 4)
                    position = (coordinate, (previous_end + current_start) / 2)
                    rotation = 90.0
                if not 0.62 <= gap <= 3.2:
                    continue
                exterior = previous.wall_type == "exterior" and current.wall_type == "exterior"
                if gap <= 1.25:
                    opening_type = "door"
                    height = 2.1
                    swing = "clockwise" if len(openings) % 2 == 0 else "counterclockwise"
                elif exterior and gap <= 2.45:
                    opening_type = "window"
                    height = 1.25
                    swing = "none"
                elif gap > 2.25:
                    opening_type = "sliding_door"
                    height = 2.2
                    swing = "none"
                else:
                    opening_type = "open_passage"
                    height = 2.2
                    swing = "none"
                key = (round(position[0] * 10), round(position[1] * 10), opening_type)
                if key in seen:
                    continue
                seen.add(key)
                openings.append(Opening(
                    id=f"opening-{uuid.uuid4().hex[:8]}",
                    opening_type=opening_type,
                    position=(round(position[0], 3), round(position[1], 3)),
                    width=round(gap, 3),
                    height=height,
                    rotation_deg=rotation,
                    swing_direction=swing,
                    confidence=0.66 if opening_type == "door" else 0.58,
                ))
    return openings[:80]


def _object(
    room: RoomShape,
    object_type: str,
    category: str,
    relative_x: float,
    relative_z: float,
    size: tuple[float, float, float],
    rotation_deg: float = 0.0,
    confidence: float = 0.46,
) -> ArchitecturalObject:
    min_x, min_z, max_x, max_z = _room_bounds(room)
    x = min_x + (max_x - min_x) * relative_x
    z = min_z + (max_z - min_z) * relative_z
    return ArchitecturalObject(
        id=f"object-{uuid.uuid4().hex[:8]}",
        object_type=object_type,
        asset_id=f"{object_type}_procedural_01",
        category=category,  # type: ignore[arg-type]
        room_id=room.id,
        coordinates=(round(x, 3), round(size[1] / 2, 3), round(z, 3)),
        rotation_deg=rotation_deg,
        size=size,
        source="room_inference",
        confidence=confidence,
    )


def _infer_objects(scene: SceneManifest) -> list[ArchitecturalObject]:
    objects: list[ArchitecturalObject] = []
    for room in scene.rooms:
        room_type = room.room_type
        min_x, min_z, max_x, max_z = _room_bounds(room)
        width = max_x - min_x
        depth = max_z - min_z
        if min(width, depth) < 1.0:
            continue
        if room_type in {"bedroom", "master_bedroom"}:
            bed_width = min(1.8 if room_type == "master_bedroom" else 1.45, width * 0.52)
            bed_depth = min(2.05, depth * 0.58)
            objects.append(_object(room, "bed", "furniture", 0.3, 0.38, (bed_width, 0.55, bed_depth), 0))
            if width > 3.1:
                objects.append(_object(room, "wardrobe", "furniture", 0.86, 0.5, (0.55, 2.0, min(1.8, depth * 0.55)), 90))
        elif room_type == "bathroom":
            objects.append(_object(room, "toilet", "fixture", 0.28, 0.7, (0.45, 0.72, 0.72), 0))
            objects.append(_object(room, "sink", "fixture", 0.72, 0.72, (0.58, 0.82, 0.46), 0))
            if room.area_m2 >= 4.2:
                objects.append(_object(room, "bathtub", "fixture", 0.5, 0.23, (min(1.75, width * 0.72), 0.55, min(0.78, depth * 0.28)), 0))
        elif room_type == "kitchen":
            objects.append(_object(room, "fridge", "utility", 0.1, 0.18, (0.82, 1.9, 0.78), 0))
            objects.append(_object(room, "stove", "utility", 0.88, 0.2, (0.76, 0.92, 0.68), 0))
            objects.append(_object(room, "sink", "fixture", 0.5, 0.12, (0.72, 0.9, 0.56), 0))
            if room.area_m2 >= 10:
                objects.append(_object(room, "kitchen_island", "furniture", 0.5, 0.57, (min(2.2, width * 0.48), 0.92, min(1.0, depth * 0.25)), 0))
        elif room_type == "living_room":
            objects.append(_object(room, "sofa", "furniture", 0.25, 0.5, (min(2.5, width * 0.48), 0.85, 0.92), 0))
            objects.append(_object(room, "coffee_table", "furniture", 0.55, 0.5, (min(1.2, width * 0.25), 0.42, 0.68), 0))
            objects.append(_object(room, "tv_unit", "furniture", 0.87, 0.5, (0.35, 1.2, min(1.8, depth * 0.42)), 90))
        elif room_type == "dining_room":
            objects.append(_object(room, "dining_table", "furniture", 0.5, 0.5, (min(2.0, width * 0.5), 0.76, min(1.05, depth * 0.36)), 0))
        elif room_type == "laundry":
            objects.append(_object(room, "washing_machine", "utility", 0.28, 0.3, (0.65, 0.9, 0.65), 0))
            objects.append(_object(room, "dryer", "utility", 0.72, 0.3, (0.65, 0.9, 0.65), 0))
        elif room_type == "stairs":
            objects.append(_object(room, "staircase", "structure", 0.5, 0.5, (max(0.9, width * 0.72), 1.4, max(1.8, depth * 0.82)), 0, 0.62))
        elif room_type == "lift":
            objects.append(_object(room, "lift", "structure", 0.5, 0.5, (max(1.1, width * 0.82), 2.2, max(1.1, depth * 0.82)), 0, 0.7))
    return objects[:160]


def _camera_path(scene: SceneManifest) -> tuple[list[tuple[float, float, float]], tuple[float, float, float]]:
    if not scene.rooms:
        start = (max(0.6, scene.width_m * 0.1), 1.7, max(0.6, scene.depth_m * 0.1))
        return [start], start
    start_room = next((room for room in scene.rooms if room.room_type in {"foyer", "living_room"}), None)
    if start_room is None:
        start_room = max(scene.rooms, key=lambda room: room.area_m2)
    remaining = [room for room in scene.rooms if room.id != start_room.id]
    ordered = [start_room]
    while remaining:
        last = ordered[-1].centroid
        nearest = min(remaining, key=lambda room: math.dist(last, room.centroid))
        ordered.append(nearest)
        remaining.remove(nearest)
    points = [(round(room.centroid[0], 3), 1.7, round(room.centroid[1], 3)) for room in ordered]
    return points, points[0]


def _ocr_labels(image_path: Path, scene: SceneManifest) -> tuple[list[dict[str, Any]], str]:
    settings = load_settings()
    configured = str(settings.get("tesseract_executable") or "").strip()
    executable = configured if configured and Path(configured).exists() else shutil.which("tesseract")
    if not executable:
        return [], "tesseract_not_installed"
    try:
        import pytesseract  # type: ignore
        pytesseract.pytesseract.tesseract_cmd = executable
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            return [], "image_unavailable"
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config="--psm 11")
        labels: list[dict[str, Any]] = []
        for index, raw in enumerate(data.get("text", [])):
            text = str(raw or "").strip()
            confidence = float(data.get("conf", [0])[index] or 0)
            if len(text) < 2 or confidence < 25:
                continue
            x = float(data["left"][index] + data["width"][index] / 2) / image.shape[1] * scene.width_m
            z = float(data["top"][index] + data["height"][index] / 2) / image.shape[0] * scene.depth_m
            labels.append({"text": text, "x": x, "z": z, "confidence": confidence / 100.0})
        return labels, "completed"
    except Exception as exc:
        return [], f"ocr_failed:{str(exc)[:80]}"


def _apply_ocr(scene: SceneManifest, labels: list[dict[str, Any]]) -> list[str]:
    extracted: list[str] = []
    if not labels or not scene.rooms:
        return extracted
    lines: list[dict[str, Any]] = []
    for label in labels:
        target = next((line for line in lines if abs(line["z"] - label["z"]) < 0.35 and abs(line["x"] - label["x"]) < 3.2), None)
        if target is None:
            lines.append({"text": label["text"], "x": label["x"], "z": label["z"], "confidence": label["confidence"]})
        else:
            target["text"] += " " + label["text"]
            target["x"] = (target["x"] + label["x"]) / 2
            target["confidence"] = max(target["confidence"], label["confidence"])
    for line in lines:
        text = re.sub(r"\s+", " ", line["text"]).strip()
        lower = text.lower()
        room_type = _classify_room(lower)
        dimension = DIMENSION_PATTERN.search(text)
        if room_type == "room" and not dimension:
            continue
        room = min(scene.rooms, key=lambda item: math.dist(item.centroid, (line["x"], line["z"])))
        if room_type != "room":
            cleaned = re.sub(DIMENSION_PATTERN, "", text).strip(" -–—")
            if cleaned:
                room.name = cleaned.title()
                room.room_type = room_type
                room.label_confidence = round(float(line["confidence"]), 3)
                extracted.append(room.name)
        if dimension:
            room.extracted_dimension = dimension.group(0)
            extracted.append(dimension.group(0))
    _annotate_rooms(scene)
    return extracted[:100]


def _merge_remote_vision(scene: SceneManifest, image_path: Path) -> tuple[SceneManifest, str]:
    settings = load_settings()
    endpoint = str(settings.get("vision_endpoint") or settings.get("ai_endpoint") or "").strip()
    token = str(settings.get("vision_token") or settings.get("ai_token") or "").strip()
    if not endpoint or not bool(settings.get("allow_remote_processing")):
        return scene, "remote_vision_not_configured"
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "architectural_vision_system.txt"
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "Return a strict architectural JSON scene."
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with image_path.open("rb") as stream:
        response = httpx.post(
            endpoint,
            headers=headers,
            files={"file": (image_path.name, stream, "image/png")},
            data={"system_prompt": prompt, "scene": scene.model_dump_json()},
            timeout=60 * 12,
        )
    response.raise_for_status()
    payload = response.json()
    candidate = payload.get("scene") if isinstance(payload, dict) and "scene" in payload else payload
    if not isinstance(candidate, dict):
        raise ValueError("Vision endpoint did not return an architectural JSON object")
    protected = scene.model_dump(mode="json")
    for key in ("rooms", "walls", "openings", "fixtures_and_furniture", "project_metadata"):
        if key in candidate:
            protected[key] = candidate[key]
    protected["project_id"] = scene.project_id
    protected["width_m"] = scene.width_m
    protected["depth_m"] = scene.depth_m
    protected["reference_image_url"] = scene.reference_image_url
    protected["reference_image_path"] = scene.reference_image_path
    return SceneManifest.model_validate(protected), "remote_vision_completed"


def compile_architecture(
    scene: SceneManifest,
    image_path: Path,
    request: AnalyzeRequest,
) -> SceneManifest:
    _annotate_rooms(scene)
    _classify_walls(scene)
    labels, ocr_status = _ocr_labels(image_path, scene)
    extracted = _apply_ocr(scene, labels)
    if request.detect_openings:
        scene.openings = _detect_openings(scene)
    if request.auto_furnish:
        scene.fixtures_and_furniture = _infer_objects(scene)
    path, start = _camera_path(scene)
    scene.camera_path = path
    scene.first_person_start = start
    scene.collision_segments = [(wall.start, wall.end) for wall in scene.walls]
    scene.ceiling_height_m = scene.wall_height_m
    scene.cutaway_height_m = min(max(1.2, scene.wall_height_m * 0.62), scene.wall_height_m)
    scene.materials = scene.materials or palette_by_name("Light Oak / Modern Tech")
    lengths = [math.dist(wall.start, wall.end) for wall in scene.walls]
    confidence = min(0.98, 0.42 + min(len(scene.rooms), 12) * 0.025 + min(len(scene.walls), 80) * 0.003)
    if not lengths:
        confidence = 0.12
    scene.project_metadata = ProjectMetadata(
        scale_ratio=f"1 px = {scene.width_m / max(1, cv2.imread(str(image_path)).shape[1]):.6f} m" if cv2.imread(str(image_path)) is not None else "user calibrated",
        detected_rooms=len(scene.rooms),
        detected_openings=len(scene.openings),
        detected_objects=len(scene.fixtures_and_furniture),
        parser_version="arch-ai-1.0",
        source_plan_type=scene.plan_type,
        structural_confidence=round(confidence, 3),
        ocr_status=ocr_status,
        extracted_labels=extracted,
    )
    if request.use_vision_ai:
        try:
            scene, vision_status = _merge_remote_vision(scene, image_path)
            scene.project_metadata.ocr_status = f"{scene.project_metadata.ocr_status};{vision_status}"
            _annotate_rooms(scene)
            _classify_walls(scene)
            path, start = _camera_path(scene)
            scene.camera_path = path
            scene.first_person_start = start
            scene.collision_segments = [(wall.start, wall.end) for wall in scene.walls]
        except Exception as exc:
            scene.warnings.append(f"Configured vision parser failed; deterministic geometry retained: {str(exc)[:180]}")
    return scene


def update_materials(
    scene: SceneManifest,
    palette_name: str,
    floor_type: str,
    floor_color: str,
    wall_color: str,
    exterior_color: str,
    accent_color: str,
    roughness: float,
    cutaway_height_m: float,
) -> SceneManifest:
    palette = palette_by_name(palette_name)
    palette.palette_name = palette_name
    palette.floor_global.material_type = floor_type
    palette.floor_global.hex_color = floor_color
    palette.floor_global.roughness = roughness
    palette.walls_global.hex_color = wall_color
    palette.walls_global.roughness = min(1.0, roughness + 0.24)
    palette.exterior_walls.hex_color = exterior_color
    palette.accent.hex_color = accent_color
    scene.materials = palette
    scene.cutaway_height_m = min(cutaway_height_m, scene.wall_height_m)
    return scene
