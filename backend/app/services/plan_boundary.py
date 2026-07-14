from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ..models import SceneManifest


BOUNDARY_WARNING = (
    "Image-derived boundary classification is active: border-connected white space is empty and cannot become a room."
)


@dataclass(slots=True)
class PlanBoundaryResult:
    wall_mask: np.ndarray
    exterior_mask: np.ndarray
    interior_mask: np.ndarray
    building_mask: np.ndarray
    polygon_px: list[tuple[int, int]]
    confidence: float


def _odd(value: int) -> int:
    value = max(3, int(value))
    return value if value % 2 else value + 1


def _remove_small_components(mask: np.ndarray, minimum_area: int) -> np.ndarray:
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    retained = np.zeros_like(mask, dtype=np.uint8)
    for label in range(1, count):
        if int(stats[label, cv2.CC_STAT_AREA]) >= minimum_area:
            retained[labels == label] = 1
    return retained


def detect_plan_boundary(image: np.ndarray) -> PlanBoundaryResult:
    """Classify the architectural envelope directly from a raster floor plan.

    Dark structural pixels are bridged before connected-component analysis. Every
    free-space component touching any image edge is exterior. Remaining enclosed
    components are interior candidates. This works independently of room boxes and
    therefore supports free-form, concave and non-orthogonal building outlines.
    """
    if image is None or image.size == 0:
        raise ValueError("A non-empty floor-plan image is required")

    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    _threshold, dark = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    span = max(1, min(width, height))
    close_size = _odd(round(span * 0.012))
    bridge = cv2.getStructuringElement(cv2.MORPH_RECT, (close_size, close_size))
    structural = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, bridge, iterations=2)
    structural = cv2.dilate(
        structural,
        cv2.getStructuringElement(cv2.MORPH_RECT, (_odd(close_size // 3), _odd(close_size // 3))),
        iterations=1,
    )

    free_space = (structural == 0).astype(np.uint8)
    _count, labels, _stats, _centroids = cv2.connectedComponentsWithStats(free_space, connectivity=8)
    border_labels = {
        int(value)
        for value in np.concatenate((labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]))
        if int(value) > 0
    }
    exterior = np.isin(labels, list(border_labels)).astype(np.uint8)
    interior = ((free_space == 1) & (exterior == 0)).astype(np.uint8)
    interior = _remove_small_components(interior, max(24, int(width * height * 0.00035)))

    expanded_interior = cv2.dilate(
        interior * 255,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (_odd(close_size * 2), _odd(close_size * 2))),
        iterations=1,
    )
    building = (expanded_interior > 0).astype(np.uint8)
    contours, _hierarchy = cv2.findContours(building * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polygon: list[tuple[int, int]] = []
    final_building = np.zeros_like(building)
    if contours:
        contour = max(contours, key=cv2.contourArea)
        cv2.drawContours(final_building, [contour], -1, 1, thickness=cv2.FILLED)
        perimeter = max(cv2.arcLength(contour, True), 1.0)
        approximation = cv2.approxPolyDP(contour, 0.006 * perimeter, True)
        polygon = [(int(point[0][0]), int(point[0][1])) for point in approximation]
    else:
        final_building = interior.copy()

    interior = ((interior == 1) & (final_building == 1)).astype(np.uint8)
    exterior = ((final_building == 0) & (free_space == 1)).astype(np.uint8)
    interior_area = int(interior.sum())
    building_area = max(int(final_building.sum()), 1)
    page_ratio = building_area / max(width * height, 1)
    enclosed_ratio = interior_area / building_area
    confidence = float(np.clip(0.35 + 0.45 * enclosed_ratio + 0.2 * min(page_ratio / 0.25, 1.0), 0.0, 1.0))

    return PlanBoundaryResult(
        wall_mask=(structural > 0).astype(np.uint8),
        exterior_mask=exterior,
        interior_mask=interior,
        building_mask=final_building,
        polygon_px=polygon,
        confidence=round(confidence, 4),
    )


def _mask_vote(mask: np.ndarray, x: int, y: int) -> bool:
    height, width = mask.shape
    x = max(0, min(width - 1, x))
    y = max(0, min(height - 1, y))
    radius = max(2, min(width, height) // 180)
    x1, x2 = max(0, x - radius), min(width, x + radius + 1)
    y1, y2 = max(0, y - radius), min(height, y + radius + 1)
    region = mask[y1:y2, x1:x2]
    return bool(region.size and float(region.mean()) >= 0.18)


def filter_rooms_by_image_boundary(scene: SceneManifest, boundary: PlanBoundaryResult) -> SceneManifest:
    if not scene.rooms:
        return scene
    height, width = boundary.interior_mask.shape
    scale_x = width / max(scene.width_m, 1e-6)
    scale_z = height / max(scene.depth_m, 1e-6)
    retained = []
    rejected = 0
    for room in scene.rooms:
        x = int(round(room.centroid[0] * scale_x))
        y = int(round(room.centroid[1] * scale_z))
        if _mask_vote(boundary.interior_mask, x, y):
            retained.append(room)
        else:
            rejected += 1
    scene.rooms = retained
    scene.project_metadata.detected_rooms = len(retained)
    if rejected:
        scene.warnings.append(f"Rejected {rejected} room proposal(s) outside the image-derived building envelope.")
    confidence_message = f"Image boundary confidence: {round(boundary.confidence * 100)}%."
    if confidence_message not in scene.warnings:
        scene.warnings.append(confidence_message)
    if BOUNDARY_WARNING not in scene.warnings:
        scene.warnings.append(BOUNDARY_WARNING)
    return scene
