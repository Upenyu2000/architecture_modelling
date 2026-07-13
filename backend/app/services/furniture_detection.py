from __future__ import annotations

import math
import uuid
from pathlib import Path

import cv2
import numpy as np

from ..models import ArchitecturalObject, RoomShape, SceneManifest


DEFAULT_STYLE = "modern"
DEFAULT_MATERIALS: dict[str, tuple[str, str]] = {
    "sofa": ("fabric", "#486B5A"),
    "sectional_sofa": ("fabric", "#486B5A"),
    "armchair": ("fabric", "#607D6D"),
    "bed": ("fabric", "#D9D4C9"),
    "coffee_table": ("walnut", "#704A32"),
    "dining_table": ("walnut", "#704A32"),
    "wardrobe": ("oak", "#A77B52"),
    "kitchen_island": ("stone", "#D4CEC3"),
    "fridge": ("painted_metal", "#B6BEC2"),
    "stove": ("painted_metal", "#70787C"),
    "toilet": ("porcelain", "#F2F2EE"),
    "sink": ("porcelain", "#F2F2EE"),
    "bathtub": ("porcelain", "#F2F2EE"),
}


def _asset_id(object_type: str) -> str:
    material, colour = DEFAULT_MATERIALS.get(object_type, ("fabric", "#486B5A"))
    return "|".join((object_type, DEFAULT_STYLE, material, colour, ""))


def _category(object_type: str) -> str:
    if object_type in {"sink", "toilet", "bathtub", "vanity"}:
        return "fixture"
    if object_type in {"fridge", "stove", "washing_machine", "dryer"}:
        return "utility"
    return "furniture"


def _room_pixel_polygon(room: RoomShape, scene: SceneManifest, width: int, height: int) -> np.ndarray:
    points = [
        [
            int(round(max(0.0, min(scene.width_m, x)) / max(scene.width_m, 1e-6) * (width - 1))),
            int(round(max(0.0, min(scene.depth_m, z)) / max(scene.depth_m, 1e-6) * (height - 1))),
        ]
        for x, z in room.polygon
    ]
    return np.asarray(points, dtype=np.int32)


def _classify(room: RoomShape, width_m: float, depth_m: float, area_m2: float, rank: int) -> str | None:
    long_side = max(width_m, depth_m)
    short_side = min(width_m, depth_m)
    ratio = long_side / max(short_side, 0.05)
    room_type = room.room_type.lower()

    if room_type in {"bedroom", "master_bedroom"}:
        if rank == 0 and area_m2 >= 1.1 and long_side >= 1.45:
            return "bed"
        if ratio >= 2.3 and long_side >= 1.0:
            return "wardrobe"
        return None
    if room_type == "living_room":
        if long_side >= 1.45 and ratio >= 1.55:
            return "sofa"
        if 0.45 <= short_side <= 1.15 and area_m2 >= 0.28:
            return "coffee_table" if rank <= 2 else "armchair"
        return None
    if room_type == "dining_room":
        return "dining_table" if area_m2 >= 0.45 else None
    if room_type == "kitchen":
        if area_m2 >= 0.75 and ratio >= 1.25:
            return "kitchen_island"
        if ratio >= 1.8 and short_side <= 0.9:
            return "countertop"
        return "stove" if rank == 0 and area_m2 >= 0.25 else None
    if room_type == "bathroom":
        if long_side >= 1.25 and ratio >= 1.7:
            return "bathtub"
        if area_m2 >= 0.24 and rank == 0:
            return "toilet"
        if area_m2 >= 0.12:
            return "sink"
        return None
    if room_type == "laundry":
        return "washing_machine" if rank == 0 else "dryer" if rank == 1 else None
    if room_type in {"office", "study"}:
        return "desk" if area_m2 >= 0.45 else "office_chair"
    return None


def _symbol_mask(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    minimum = max(9, int(min(width, height) * 0.012))
    block = max(21, minimum * 2 + 1)
    if block % 2 == 0:
        block += 1
    dark = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block,
        8,
    )
    horizontal = cv2.morphologyEx(
        dark,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (minimum * 3, 3)),
    )
    vertical = cv2.morphologyEx(
        dark,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, minimum * 3)),
    )
    walls = cv2.dilate(cv2.bitwise_or(horizontal, vertical), np.ones((5, 5), np.uint8), iterations=1)
    symbols = cv2.bitwise_and(dark, cv2.bitwise_not(walls))
    symbols = cv2.morphologyEx(symbols, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
    symbols = cv2.dilate(symbols, np.ones((3, 3), np.uint8), iterations=1)
    return symbols


def detect_furniture_symbols(scene: SceneManifest, image_path: Path) -> list[ArchitecturalObject]:
    """Extract conservative furniture footprints from a floor-plan raster.

    This detector intentionally returns only high-support room-aware proposals. The
    interior editor remains authoritative and can replace every proposal.
    """
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None or not scene.rooms:
        return []
    height, width = image.shape[:2]
    symbols = _symbol_mask(image)
    metres_per_x = scene.width_m / max(width, 1)
    metres_per_z = scene.depth_m / max(height, 1)
    results: list[ArchitecturalObject] = []

    for room in scene.rooms:
        if len(room.polygon) < 3:
            continue
        polygon = _room_pixel_polygon(room, scene, width, height)
        if polygon.shape[0] < 3:
            continue
        room_mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(room_mask, [polygon], 255)
        erosion = max(2, int(min(width, height) * 0.003))
        room_mask = cv2.erode(room_mask, np.ones((erosion * 2 + 1, erosion * 2 + 1), np.uint8), iterations=1)
        candidate = cv2.bitwise_and(symbols, room_mask)
        contours, _ = cv2.findContours(candidate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        room_area_px = max(float(cv2.contourArea(polygon)), 1.0)
        footprints: list[tuple[float, tuple[tuple[float, float], tuple[float, float], float]]] = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < max(22.0, room_area_px * 0.004) or area > room_area_px * 0.36:
                continue
            rect = cv2.minAreaRect(contour)
            (_, _), (pixel_w, pixel_h), _ = rect
            if min(pixel_w, pixel_h) < 5 or max(pixel_w, pixel_h) < 11:
                continue
            fill_ratio = area / max(pixel_w * pixel_h, 1.0)
            if fill_ratio < 0.08:
                continue
            footprints.append((area, rect))
        footprints.sort(key=lambda item: item[0], reverse=True)

        used_types: set[str] = set()
        for rank, (_area, rect) in enumerate(footprints[:8]):
            (cx, cy), (pixel_w, pixel_h), angle = rect
            width_m = max(0.2, pixel_w * metres_per_x)
            depth_m = max(0.2, pixel_h * metres_per_z)
            if width_m < depth_m:
                width_m, depth_m = depth_m, width_m
                angle += 90.0
            area_m2 = width_m * depth_m
            object_type = _classify(room, width_m, depth_m, area_m2, rank)
            if not object_type:
                continue
            if object_type in used_types and object_type not in {"sink", "armchair"}:
                continue
            used_types.add(object_type)
            x = cx / max(width - 1, 1) * scene.width_m
            z = cy / max(height - 1, 1) * scene.depth_m
            expected_height = {
                "bed": 0.72, "wardrobe": 2.1, "sofa": 0.92, "armchair": 0.92,
                "coffee_table": 0.46, "dining_table": 0.78, "kitchen_island": 0.94,
                "countertop": 0.94, "stove": 0.92, "toilet": 0.78, "sink": 0.9,
                "bathtub": 0.62, "washing_machine": 0.9, "dryer": 0.9, "desk": 0.76,
                "office_chair": 1.05,
            }.get(object_type, 0.9)
            confidence = min(0.82, 0.48 + min(area_m2, 3.0) * 0.08 + (0.08 if room.room_type != "room" else 0.0))
            results.append(ArchitecturalObject(
                id=f"symbol-{uuid.uuid4().hex[:10]}",
                object_type=object_type,
                asset_id=_asset_id(object_type),
                category=_category(object_type),  # type: ignore[arg-type]
                room_id=room.id,
                coordinates=(round(x, 3), round(expected_height / 2, 3), round(z, 3)),
                rotation_deg=round(float(angle) % 180.0, 2),
                scale=(1.0, 1.0, 1.0),
                size=(round(width_m, 3), expected_height, round(depth_m, 3)),
                source="symbol_heuristic",
                confidence=round(confidence, 3),
            ))
    return results[:120]


def merge_furniture_objects(
    user_objects: list[ArchitecturalObject],
    detected_objects: list[ArchitecturalObject],
    inferred_objects: list[ArchitecturalObject],
) -> list[ArchitecturalObject]:
    priority = {"user": 4, "vision": 3, "symbol_heuristic": 2, "room_inference": 1}
    merged: list[ArchitecturalObject] = []
    for candidate in [*user_objects, *detected_objects, *inferred_objects]:
        duplicate = next((
            item for item in merged
            if item.room_id == candidate.room_id
            and math.dist((item.coordinates[0], item.coordinates[2]), (candidate.coordinates[0], candidate.coordinates[2]))
            <= max(0.45, min(max(item.size[0], item.size[2]), max(candidate.size[0], candidate.size[2])) * 0.42)
        ), None)
        if duplicate is None:
            merged.append(candidate)
            continue
        candidate_rank = (priority.get(candidate.source, 0), candidate.confidence)
        existing_rank = (priority.get(duplicate.source, 0), duplicate.confidence)
        if candidate_rank > existing_rank:
            merged[merged.index(duplicate)] = candidate
    return merged[:180]
