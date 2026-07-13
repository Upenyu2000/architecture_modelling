from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

from ..models import Opening, SceneManifest
from .openings import DOOR_TYPES, WINDOW_TYPES


def _line_features(patch: np.ndarray, wall_rotation: float) -> dict[str, float]:
    blurred = cv2.GaussianBlur(patch, (3, 3), 0)
    edges = cv2.Canny(blurred, 45, 150)
    minimum = max(8, min(patch.shape[:2]) // 8)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=18, minLineLength=minimum, maxLineGap=6)
    diagonal = 0
    parallel = 0
    perpendicular = 0
    short_lines = 0
    angles: list[float] = []
    if lines is not None:
        wall_angle = wall_rotation % 180
        for raw in lines[:, 0]:
            x1, y1, x2, y2 = [float(value) for value in raw]
            length = math.hypot(x2 - x1, y2 - y1)
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180
            angles.append(angle)
            delta = min(abs(angle - wall_angle), 180 - abs(angle - wall_angle))
            if 18 <= delta <= 72:
                diagonal += 1
            elif delta < 12:
                parallel += 1
            elif delta > 78:
                perpendicular += 1
            if length < min(patch.shape[:2]) * 0.32:
                short_lines += 1

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(10, min(patch.shape[:2]) // 4),
        param1=90,
        param2=22,
        minRadius=max(5, min(patch.shape[:2]) // 10),
        maxRadius=max(8, min(patch.shape[:2]) // 2),
    )
    circle_count = 0 if circles is None else int(circles.shape[1])

    _, ink = cv2.threshold(blurred, 165, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(ink, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    curved = 0
    enclosed = 0
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        area = cv2.contourArea(contour)
        if perimeter < 15 or area < 10:
            continue
        circularity = 4 * math.pi * area / max(perimeter * perimeter, 1e-6)
        if circularity > 0.28:
            curved += 1
        if circularity > 0.55:
            enclosed += 1

    return {
        "diagonal": float(diagonal),
        "parallel": float(parallel),
        "perpendicular": float(perpendicular),
        "short": float(short_lines),
        "circles": float(circle_count),
        "curved": float(curved),
        "enclosed": float(enclosed),
        "ink_ratio": float(np.count_nonzero(ink) / max(ink.size, 1)),
    }


def _patch(image: np.ndarray, scene: SceneManifest, opening: Opening) -> np.ndarray | None:
    height, width = image.shape[:2]
    px_x = width / max(scene.width_m, 1e-6)
    px_z = height / max(scene.depth_m, 1e-6)
    centre_x = int(round(opening.position[0] * px_x))
    centre_y = int(round(opening.position[1] * px_z))
    radius_x = max(26, int(round(opening.width * px_x * 0.9)))
    radius_y = max(26, int(round(opening.width * px_z * 0.9)))
    x1, x2 = max(0, centre_x - radius_x), min(width, centre_x + radius_x)
    y1, y2 = max(0, centre_y - radius_y), min(height, centre_y + radius_y)
    if x2 - x1 < 16 or y2 - y1 < 16:
        return None
    return image[y1:y2, x1:x2]


def _classify_window(opening: Opening, features: dict[str, float]) -> str:
    diagonal = features["diagonal"]
    parallel = features["parallel"]
    perpendicular = features["perpendicular"]
    if diagonal >= 5 and opening.width >= 1.7:
        return "bay_window"
    if perpendicular >= 5 and parallel >= 3:
        return "garden_window"
    if diagonal >= 4:
        return "double_casement_window"
    if diagonal >= 2:
        return "casement_window"
    if parallel >= 5 and opening.width >= 1.25:
        return "glider_window"
    if perpendicular >= 4 and opening.width < 1.2:
        return "vertical_sliding_window"
    if parallel >= 4:
        return "horizontal_sliding_window"
    if opening.width < 1.05:
        return "double_hung_window"
    return "fixed_window"


def _classify_door(opening: Opening, features: dict[str, float]) -> str:
    diagonal = features["diagonal"]
    parallel = features["parallel"]
    circles = features["circles"]
    curved = features["curved"]
    if (circles >= 1 or features["enclosed"] >= 1) and diagonal >= 3 and opening.width >= 1.6:
        return "revolving_door"
    if diagonal >= 7:
        return "double_bifold_door" if opening.width >= 1.45 else "bifold_door"
    if diagonal >= 4 and curved <= 1:
        return "double_bifold_door" if opening.width >= 1.45 else "bifold_door"
    if parallel >= 6 and curved <= 1:
        if opening.width >= 2.0:
            return "double_sliding_door"
        if opening.width >= 1.35:
            return "sliding_door"
        return "pocket_door"
    if opening.opening_type in {"sliding_door", "double_sliding_door", "sliding_glass_door"}:
        return "double_sliding_door" if opening.width >= 2.0 else "sliding_door"
    if opening.width >= 1.5:
        return "double_door"
    return "door"


def classify_opening_symbols(scene: SceneManifest, image_path: Path) -> SceneManifest:
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return scene
    for opening in scene.openings:
        if opening.source == "manual" or opening.opening_type == "open_passage":
            continue
        patch = _patch(image, scene, opening)
        if patch is None:
            continue
        features = _line_features(patch, opening.rotation_deg)
        original = opening.opening_type
        if original in WINDOW_TYPES:
            opening.opening_type = _classify_window(opening, features)  # type: ignore[assignment]
            opening.interactive = False
            opening.swing_direction = "none"
            opening.hinge_side = "none"
            opening.sill_height = max(0.65, opening.sill_height)
        elif original in DOOR_TYPES:
            opening.opening_type = _classify_door(opening, features)  # type: ignore[assignment]
            opening.interactive = True
            opening.sill_height = 0.0
            if opening.swing_direction == "none" and opening.opening_type not in {
                "sliding_door", "double_sliding_door", "sliding_glass_door", "pocket_door",
                "double_pocket_door", "bypass_door", "overhead_door", "revolving_door",
            }:
                opening.swing_direction = "clockwise"
            if opening.hinge_side == "none" and opening.opening_type not in {
                "sliding_door", "double_sliding_door", "sliding_glass_door", "pocket_door",
                "double_pocket_door", "bypass_door", "overhead_door", "revolving_door",
            }:
                opening.hinge_side = "left"
        opening.source = "heuristic"
        opening.confidence = max(opening.confidence, 0.62 if opening.opening_type != original else 0.58)
    return scene
