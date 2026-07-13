from __future__ import annotations

import math
import uuid
from pathlib import Path

import cv2
import numpy as np

from ..models import SceneManifest, WallSegment


def _point_segment_distance(point: tuple[float, float], wall: WallSegment) -> float:
    px, pz = point
    x1, z1 = wall.start
    x2, z2 = wall.end
    dx, dz = x2 - x1, z2 - z1
    length_squared = dx * dx + dz * dz
    if length_squared <= 1e-8:
        return math.dist(point, wall.start)
    t = max(0.0, min(1.0, ((px - x1) * dx + (pz - z1) * dz) / length_squared))
    return math.dist(point, (x1 + dx * t, z1 + dz * t))


def _near_network(point: tuple[float, float], scene: SceneManifest, tolerance: float) -> bool:
    x, z = point
    if x <= tolerance or z <= tolerance or x >= scene.width_m - tolerance or z >= scene.depth_m - tolerance:
        return True
    return any(_point_segment_distance(point, wall) <= tolerance for wall in scene.walls)


def _dark_support(mask: np.ndarray, line: tuple[int, int, int, int], radius: int) -> float:
    x1, y1, x2, y2 = line
    samples = max(20, min(80, round(math.hypot(x2 - x1, y2 - y1) / 8)))
    supported = 0
    for index in range(samples):
        t = index / max(samples - 1, 1)
        x = round(x1 + (x2 - x1) * t)
        y = round(y1 + (y2 - y1) * t)
        left, right = max(0, x - radius), min(mask.shape[1], x + radius + 1)
        top, bottom = max(0, y - radius), min(mask.shape[0], y + radius + 1)
        patch = mask[top:bottom, left:right]
        if patch.size and float(np.mean(patch > 0)) >= 0.24:
            supported += 1
    return supported / max(samples, 1)


def _same_diagonal(candidate: WallSegment, existing: WallSegment, tolerance: float) -> bool:
    cdx = candidate.end[0] - candidate.start[0]
    cdz = candidate.end[1] - candidate.start[1]
    edx = existing.end[0] - existing.start[0]
    edz = existing.end[1] - existing.start[1]
    ca = math.atan2(cdz, cdx)
    ea = math.atan2(edz, edx)
    angle_delta = abs(math.atan2(math.sin(ca - ea), math.cos(ca - ea)))
    angle_delta = min(angle_delta, abs(math.pi - angle_delta))
    if angle_delta > math.radians(5):
        return False
    candidate_mid = ((candidate.start[0] + candidate.end[0]) / 2, (candidate.start[1] + candidate.end[1]) / 2)
    return _point_segment_distance(candidate_mid, existing) <= tolerance


def add_diagonal_wall_candidates(scene: SceneManifest, image_path: Path) -> SceneManifest:
    if scene.plan_type == "rendered":
        return scene
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return scene
    height, width = image.shape
    metres_per_pixel = scene.width_m / max(width, 1)
    blurred = cv2.GaussianBlur(image, (3, 3), 0)
    _, dark = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    edges = cv2.Canny(blurred, 45, 145)
    minimum_px = max(round(0.65 / max(metres_per_pixel, 1e-6)), round(min(width, height) * 0.025), 18)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 720,
        threshold=max(18, minimum_px // 2),
        minLineLength=minimum_px,
        maxLineGap=max(5, round(min(width, height) * 0.008)),
    )
    if lines is None:
        return scene

    radius = max(2, round(scene.walls[0].thickness / max(metres_per_pixel, 1e-6) / 2) if scene.walls else 4)
    tolerance = max(0.24, scene.walls[0].thickness * 2.2 if scene.walls else 0.35)
    candidates: list[WallSegment] = []
    for raw in lines[:, 0, :]:
        x1, y1, x2, y2 = map(int, raw)
        dx, dz = x2 - x1, y2 - y1
        length_px = math.hypot(dx, dz)
        if length_px < minimum_px:
            continue
        angle = abs(math.degrees(math.atan2(dz, dx))) % 180
        off_axis = min(angle, abs(90 - angle), abs(180 - angle))
        if off_axis < 9:
            continue
        if _dark_support(dark, (x1, y1, x2, y2), radius) < 0.72:
            continue
        start = (round(x1 * metres_per_pixel, 3), round(y1 * metres_per_pixel, 3))
        end = (round(x2 * metres_per_pixel, 3), round(y2 * metres_per_pixel, 3))
        length_m = length_px * metres_per_pixel
        connected_start = _near_network(start, scene, tolerance)
        connected_end = _near_network(end, scene, tolerance)
        if not ((connected_start and connected_end) or length_m >= 2.4):
            continue
        candidate = WallSegment(
            id=f"wall-diagonal-{uuid.uuid4().hex[:8]}",
            start=start,
            end=end,
            height=scene.wall_height_m,
            thickness=scene.walls[0].thickness if scene.walls else 0.16,
            wall_type="interior",
            confidence=0.64 if connected_start and connected_end else 0.56,
        )
        if any(_same_diagonal(candidate, wall, tolerance) for wall in [*scene.walls, *candidates]):
            continue
        candidates.append(candidate)
        if len(candidates) >= 45:
            break

    if candidates:
        scene.walls.extend(candidates)
        scene.collision_segments = [(wall.start, wall.end) for wall in scene.walls]
        scene.warnings.append(f"Added {len(candidates)} connected diagonal wall candidates; verify them in Detection or Edit rooms.")
    return scene
