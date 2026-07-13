from __future__ import annotations

import math
from typing import Any

from ..models import Opening, SceneManifest, WallSegment


def _vertex(point: tuple[float, float]) -> dict[str, float]:
    return {"x": round(float(point[0]), 4), "y": round(float(point[1]), 4)}


def _wall_for_opening(scene: SceneManifest, opening: Opening) -> tuple[WallSegment | None, float | None]:
    if opening.wall_id:
        matched = next((wall for wall in scene.walls if wall.id == opening.wall_id), None)
        if matched:
            return matched, _placement_ratio(matched, opening.position)
    best: tuple[float, WallSegment] | None = None
    px, pz = opening.position
    for wall in scene.walls:
        x1, z1 = wall.start
        x2, z2 = wall.end
        dx, dz = x2 - x1, z2 - z1
        length_squared = dx * dx + dz * dz
        if length_squared <= 1e-8:
            continue
        t = max(0.0, min(1.0, ((px - x1) * dx + (pz - z1) * dz) / length_squared))
        closest = (x1 + dx * t, z1 + dz * t)
        distance = math.dist((px, pz), closest)
        tolerance = max(0.32, wall.thickness * 2.5)
        if distance <= tolerance and (best is None or distance < best[0]):
            best = (distance, wall)
    if best is None:
        return None, None
    return best[1], _placement_ratio(best[1], opening.position)


def _placement_ratio(wall: WallSegment, position: tuple[float, float]) -> float:
    x1, z1 = wall.start
    x2, z2 = wall.end
    dx, dz = x2 - x1, z2 - z1
    length_squared = dx * dx + dz * dz
    if length_squared <= 1e-8:
        return 0.0
    ratio = ((position[0] - x1) * dx + (position[1] - z1) * dz) / length_squared
    return round(max(0.0, min(1.0, ratio)), 5)


def _material(spec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "type": spec.material_type,
        "hex_color": spec.hex_color,
        "albedo_url": spec.texture_url,
        "normal_url": spec.normal_url,
        "displacement_url": spec.displacement_url,
        "pbr_roughness": spec.roughness,
        "pbr_metalness": spec.metallic,
        "pbr_specular": spec.specular,
        "uv_scale": [spec.texture_scale, spec.texture_scale],
        "mapping": "box_triplanar",
    }


def production_architecture_payload(scene: SceneManifest) -> dict[str, Any]:
    total_area = round(sum(room.area_m2 for room in scene.rooms), 3)
    opening_records: list[dict[str, Any]] = []
    for opening in scene.openings:
        wall, placement = _wall_for_opening(scene, opening)
        opening_records.append({
            "opening_id": opening.id,
            "type": opening.opening_type,
            "parent_wall": wall.id if wall else opening.wall_id,
            "placement_ratio": placement,
            "position": _vertex(opening.position),
            "width": opening.width,
            "height": opening.height,
            "rotation_deg": opening.rotation_deg,
            "swing": opening.swing_direction,
            "confidence": opening.confidence,
        })

    return {
        "schema": "arch-ai-freeform-1.0",
        "project_metadata": {
            "project_id": scene.project_id,
            "scale_ratio": scene.project_metadata.scale_ratio,
            "scale_ratio_px_to_meter": round(scene.width_m / max(1.0, scene.width_m), 6),
            "width_m": scene.width_m,
            "depth_m": scene.depth_m,
            "wall_height_m": scene.wall_height_m,
            "ceiling_height_m": scene.ceiling_height_m,
            "total_area_m2": total_area,
            "detected_rooms": len(scene.rooms),
            "detected_openings": len(scene.openings),
            "detected_objects": len(scene.fixtures_and_furniture) + len(scene.assets),
            "parser_version": scene.project_metadata.parser_version,
            "structural_confidence": scene.project_metadata.structural_confidence,
            "source_plan_type": scene.project_metadata.source_plan_type,
            "coordinate_system": "X left-to-right, Y top-to-bottom in plan space, Z vertical in 3D exports",
        },
        "rooms": [
            {
                "room_id": room.id,
                "name": room.name,
                "room_type": room.room_type,
                "vertices": [_vertex(point) for point in room.polygon],
                "centroid": _vertex(room.centroid),
                "area_m2": room.area_m2,
                "width_m": room.width_m,
                "depth_m": room.depth_m,
                "extracted_dimension": room.extracted_dimension,
                "label_confidence": room.label_confidence,
                "flooring_material": _material(scene.materials.floor_global),
            }
            for room in scene.rooms
        ],
        "walls": [
            {
                "wall_id": wall.id,
                "type": wall.wall_type,
                "is_exterior": wall.wall_type == "exterior",
                "thickness": wall.thickness,
                "height": wall.height,
                "path": [_vertex(wall.start), _vertex(wall.end)],
                "confidence": wall.confidence,
                "material": _material(scene.materials.exterior_walls if wall.wall_type == "exterior" else scene.materials.walls_global),
            }
            for wall in scene.walls
        ],
        "openings": opening_records,
        "fixtures": [
            {
                "fixture_id": item.id,
                "class": item.object_type,
                "model_key": item.asset_id,
                "category": item.category,
                "room_id": item.room_id,
                "position": {"x": item.coordinates[0], "y": item.coordinates[2], "z": item.coordinates[1]},
                "rotation_y": item.rotation_deg,
                "scale": list(item.scale),
                "size": list(item.size),
                "source": item.source,
                "confidence": item.confidence,
            }
            for item in scene.fixtures_and_furniture
        ],
        "user_assets": [asset.model_dump(mode="json") for asset in scene.assets],
        "materials": {
            "palette_name": scene.materials.palette_name,
            "floor_global": _material(scene.materials.floor_global),
            "walls_global": _material(scene.materials.walls_global),
            "exterior_walls": _material(scene.materials.exterior_walls),
            "accent": _material(scene.materials.accent),
            "fixture_metal": _material(scene.materials.fixture_metal),
        },
        "viewport_compilation": {
            "aerial_cutaway": {
                "enabled": True,
                "wall_cut_height_m": scene.cutaway_height_m,
                "camera_target": {"x": scene.width_m / 2, "y": scene.depth_m / 2, "z": 0.65},
            },
            "first_person": {
                "enabled": True,
                "eye_height_m": 1.7,
                "start": list(scene.first_person_start) if scene.first_person_start else None,
                "camera_path": [list(point) for point in scene.camera_path],
                "collision_segments": [[_vertex(start), _vertex(end)] for start, end in scene.collision_segments],
                "door_aware_collision": True,
            },
        },
        "warnings": scene.warnings,
    }
