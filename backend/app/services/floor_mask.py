from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..models import SceneManifest
from .plan_boundary import PlanBoundaryResult

WINDOW_TYPES = {
    "window", "fixed_window", "casement_window", "double_casement_window", "glider_window",
    "garden_window", "bay_window", "bow_window", "double_hung_window",
    "vertical_sliding_window", "horizontal_sliding_window",
}


def write_boundary_floor_masks(boundary: PlanBoundaryResult, working_dir: Path) -> tuple[Path, Path]:
    working_dir.mkdir(parents=True, exist_ok=True)
    building_path = working_dir / "building-mask.png"
    interior_path = working_dir / "interior-mask.png"
    cv2.imwrite(str(building_path), boundary.building_mask.astype(np.uint8) * 255)
    cv2.imwrite(str(interior_path), boundary.interior_mask.astype(np.uint8) * 255)
    return building_path, interior_path


def write_scene_floor_mask(
    scene: SceneManifest,
    destination: Path,
    *,
    width_px: int = 1600,
) -> Path:
    """Rasterise a continuous walkable floor from room polygons and portals.

    This fallback is used for manual layouts and legacy saved scenes that do not
    have an image-derived building envelope. Small room-edge gaps are closed, but
    the mask is never expanded to the full scene rectangle, so exterior white
    space remains empty.
    """
    width_px = max(320, int(width_px))
    height_px = max(320, int(round(width_px * scene.depth_m / max(scene.width_m, 1e-6))))
    mask = np.zeros((height_px, width_px), dtype=np.uint8)
    scale_x = width_px / max(scene.width_m, 1e-6)
    scale_z = height_px / max(scene.depth_m, 1e-6)

    for room in scene.rooms:
        if len(room.polygon) < 3:
            continue
        points = np.array([
            [int(round(x * scale_x)), int(round(z * scale_z))]
            for x, z in room.polygon
        ], dtype=np.int32)
        cv2.fillPoly(mask, [points], 255, lineType=cv2.LINE_8)

    # Door and passage thresholds belong to the walkable floor even when two
    # independently owned room polygons stop at opposite wall faces.
    for opening in scene.openings:
        if opening.opening_type in WINDOW_TYPES:
            continue
        x = int(round(opening.position[0] * scale_x))
        z = int(round(opening.position[1] * scale_z))
        half_width = max(2, int(round(opening.width * (scale_x + scale_z) * 0.25)))
        wall_depth = max(3, int(round(max((wall.thickness for wall in scene.walls), default=0.16) * (scale_x + scale_z) * 0.7)))
        angle = np.deg2rad(opening.rotation_deg)
        dx = int(round(np.cos(angle) * half_width))
        dz = int(round(np.sin(angle) * half_width))
        cv2.line(mask, (x - dx, z - dz), (x + dx, z + dz), 255, wall_depth, cv2.LINE_8)

    if scene.rooms:
        pixel_scale = (scale_x + scale_z) / 2
        close_metres = max(0.08, min(0.22, max((wall.thickness for wall in scene.walls), default=0.16) * 1.1))
        kernel_size = max(3, int(round(close_metres * pixel_scale)))
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    destination.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(destination), mask)
    return destination
