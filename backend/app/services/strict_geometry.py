from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..models import AnalyzeRequest, RoomCreateRequest, SceneManifest
from .floorplan import analyze_floorplan as legacy_analyze_floorplan
from .layout import add_room as legacy_add_room
from .layout import update_room_geometry as legacy_update_room_geometry
from .plan_boundary import detect_plan_boundary, filter_rooms_by_image_boundary


EXTERIOR_WARNING = (
    "Exterior white space touching any image edge is classified as empty space and is excluded from rooms."
)


def _wall_mask(scene: SceneManifest, width_px: int, height_px: int) -> np.ndarray:
    mask = np.zeros((height_px, width_px), dtype=np.uint8)
    scale_x = width_px / max(scene.width_m, 1e-6)
    scale_z = height_px / max(scene.depth_m, 1e-6)
    pixel_scale = (scale_x + scale_z) / 2

    for wall in scene.walls:
        start = (
            int(round(wall.start[0] * scale_x)),
            int(round(wall.start[1] * scale_z)),
        )
        end = (
            int(round(wall.end[0] * scale_x)),
            int(round(wall.end[1] * scale_z)),
        )
        thickness = max(2, int(round(max(wall.thickness, 0.08) * pixel_scale)))
        cv2.line(mask, start, end, 255, thickness, cv2.LINE_8)

    if scene.walls:
        bridge = max(3, int(round(0.16 * pixel_scale)))
        bridge = bridge + 1 if bridge % 2 == 0 else bridge
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            np.ones((bridge, bridge), dtype=np.uint8),
            iterations=1,
        )
    return mask


def _label_at(labels: np.ndarray, x: int, y: int) -> int:
    height, width = labels.shape
    x = max(0, min(width - 1, x))
    y = max(0, min(height - 1, y))
    direct = int(labels[y, x])
    if direct:
        return direct

    radius = max(2, min(width, height) // 200)
    x1, x2 = max(0, x - radius), min(width, x + radius + 1)
    y1, y2 = max(0, y - radius), min(height, y + radius + 1)
    values = [int(value) for value in labels[y1:y2, x1:x2].reshape(-1) if int(value) > 0]
    return Counter(values).most_common(1)[0][0] if values else 0


def filter_exterior_rooms(
    scene: SceneManifest,
    *,
    width_px: int = 1600,
    height_px: int | None = None,
) -> SceneManifest:
    """Remove any proposed room whose free-space component touches an image border.

    A single flood-fill seed is not sufficient because the top-left pixel can be
    occupied by a crop edge or drawing mark. Connected-component classification
    against all four borders makes exterior white space deterministic.
    """
    if not scene.rooms or not scene.walls:
        return scene

    resolved_height = height_px or max(320, int(round(width_px * scene.depth_m / max(scene.width_m, 1e-6))))
    wall_mask = _wall_mask(scene, width_px, resolved_height)
    free_space = (wall_mask == 0).astype(np.uint8)
    _count, labels, _stats, _centroids = cv2.connectedComponentsWithStats(free_space, connectivity=8)

    border_labels = {
        int(value)
        for value in np.concatenate((labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]))
        if int(value) > 0
    }
    scale_x = width_px / max(scene.width_m, 1e-6)
    scale_z = resolved_height / max(scene.depth_m, 1e-6)

    retained = []
    rejected = 0
    for room in scene.rooms:
        label = _label_at(
            labels,
            int(round(room.centroid[0] * scale_x)),
            int(round(room.centroid[1] * scale_z)),
        )
        if label == 0 or label in border_labels:
            rejected += 1
            continue
        retained.append(room)

    scene.rooms = retained
    scene.project_metadata.detected_rooms = len(retained)
    if rejected:
        scene.warnings.append(f"Rejected {rejected} exterior white-space room proposal(s).")
    if EXTERIOR_WARNING not in scene.warnings:
        scene.warnings.append(EXTERIOR_WARNING)
    return scene


def analyze_floorplan_strict(project_id: str, image_path: Path, request: AnalyzeRequest) -> SceneManifest:
    scene = legacy_analyze_floorplan(project_id, image_path, request)
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is not None:
        boundary = detect_plan_boundary(image)
        scene = filter_rooms_by_image_boundary(scene, boundary)
        height, width = image.shape[:2]
        scene = filter_exterior_rooms(scene, width_px=width, height_px=height)
    else:
        scene = filter_exterior_rooms(scene)
    scene.project_metadata.parser_version = "arch-ai-1.5.4"
    return scene


def _interior_envelope(scene: SceneManifest):
    polygons = []
    for room in scene.rooms:
        if len(room.polygon) < 3:
            continue
        polygon = Polygon(room.polygon)
        if polygon.is_valid and not polygon.is_empty and polygon.area >= 0.1:
            polygons.append(polygon)
    if not polygons:
        return None
    wall_clearance = max([wall.thickness for wall in scene.walls] or [0.16]) * 1.8
    return unary_union(polygons).buffer(max(0.18, wall_clearance), join_style=2)


def _validate_against_existing_envelope(scene: SceneManifest, polygon_points: list[tuple[float, float]]) -> None:
    if scene.layout_mode != "automatic" or not scene.rooms:
        return
    envelope = _interior_envelope(scene)
    candidate = Polygon(polygon_points)
    if envelope is None or not candidate.is_valid or candidate.is_empty:
        return
    outside_area = float(candidate.difference(envelope).area)
    tolerance = max(0.06, float(candidate.area) * 0.035)
    if outside_area > tolerance:
        raise ValueError(
            "This room extends into exterior white space. Keep room geometry inside the detected house boundary, "
            "or start a blank manual layout to define a different building footprint."
        )


def add_room_guarded(scene: SceneManifest, request: RoomCreateRequest) -> SceneManifest:
    original = scene.model_copy(deep=True)
    candidate = legacy_add_room(scene.model_copy(deep=True), request)
    original_ids = {room.id for room in original.rooms}
    added = next((room for room in candidate.rooms if room.id not in original_ids), None)
    if added is not None:
        _validate_against_existing_envelope(original, added.polygon)
    return candidate


def update_room_geometry_guarded(
    scene: SceneManifest,
    room_id: str,
    polygon: list[tuple[float, float]],
) -> SceneManifest:
    original = scene.model_copy(deep=True)
    _validate_against_existing_envelope(original, polygon)
    return legacy_update_room_geometry(scene.model_copy(deep=True), room_id, polygon)
