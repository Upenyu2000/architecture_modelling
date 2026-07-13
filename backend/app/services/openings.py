from __future__ import annotations

import math
import uuid

from ..models import Opening, OpeningCreateRequest, OpeningUpdateRequest, SceneManifest, WallSegment


WINDOW_TYPES = {
    "window", "fixed_window", "casement_window", "double_casement_window", "glider_window",
    "garden_window", "bay_window", "bow_window", "double_hung_window",
    "vertical_sliding_window", "horizontal_sliding_window",
}
DOOR_TYPES = {
    "door", "double_door", "pocket_door", "double_pocket_door", "bypass_door",
    "sliding_door", "double_sliding_door", "sliding_glass_door", "bifold_door",
    "double_bifold_door", "folding_door", "overhead_door", "revolving_door",
}

DEFAULTS: dict[str, tuple[float, float]] = {
    "door": (0.9, 2.1),
    "double_door": (1.8, 2.1),
    "pocket_door": (0.9, 2.1),
    "double_pocket_door": (1.8, 2.1),
    "bypass_door": (1.5, 2.1),
    "sliding_door": (1.5, 2.2),
    "double_sliding_door": (2.4, 2.2),
    "sliding_glass_door": (2.2, 2.2),
    "bifold_door": (0.9, 2.1),
    "double_bifold_door": (1.8, 2.1),
    "folding_door": (1.5, 2.1),
    "overhead_door": (2.4, 2.3),
    "revolving_door": (2.1, 2.3),
    "open_passage": (1.2, 2.2),
    "window": (1.2, 1.2),
    "fixed_window": (1.2, 1.2),
    "casement_window": (0.9, 1.2),
    "double_casement_window": (1.6, 1.2),
    "glider_window": (1.4, 1.2),
    "garden_window": (1.6, 1.2),
    "bay_window": (2.0, 1.35),
    "bow_window": (2.4, 1.35),
    "double_hung_window": (1.0, 1.3),
    "vertical_sliding_window": (0.9, 1.3),
    "horizontal_sliding_window": (1.5, 1.1),
}


def is_window(opening_type: str) -> bool:
    return opening_type in WINDOW_TYPES


def is_door(opening_type: str) -> bool:
    return opening_type in DOOR_TYPES


def _wall(scene: SceneManifest, wall_id: str) -> WallSegment:
    wall = next((item for item in scene.walls if item.id == wall_id), None)
    if not wall:
        raise KeyError("Wall not found")
    return wall


def _pose(wall: WallSegment, placement_ratio: float, width: float) -> tuple[tuple[float, float], float, float]:
    x1, z1 = wall.start
    x2, z2 = wall.end
    dx, dz = x2 - x1, z2 - z1
    length = math.hypot(dx, dz)
    if length < 0.35:
        raise ValueError("The selected wall is too short for an opening.")
    if width > length - 0.12:
        raise ValueError(f"Opening width must be smaller than the selected {length:.2f} m wall.")
    half_ratio = width / (2 * length)
    safe_ratio = min(max(placement_ratio, half_ratio + 0.015), 1 - half_ratio - 0.015)
    position = (round(x1 + dx * safe_ratio, 4), round(z1 + dz * safe_ratio, 4))
    rotation = round(math.degrees(math.atan2(dz, dx)), 3)
    return position, rotation, round(safe_ratio, 5)


def _overlaps(scene: SceneManifest, candidate: Opening, ignore_id: str | None = None) -> bool:
    if not candidate.wall_id or candidate.placement_ratio is None:
        return False
    wall = _wall(scene, candidate.wall_id)
    length = max(math.dist(wall.start, wall.end), 1e-6)
    start = candidate.placement_ratio - candidate.width / (2 * length)
    end = candidate.placement_ratio + candidate.width / (2 * length)
    for item in scene.openings:
        if item.id == ignore_id or item.wall_id != candidate.wall_id or item.placement_ratio is None:
            continue
        other_start = item.placement_ratio - item.width / (2 * length)
        other_end = item.placement_ratio + item.width / (2 * length)
        if min(end, other_end) - max(start, other_start) > 0.04 / length:
            return True
    return False


def _refresh(scene: SceneManifest) -> SceneManifest:
    scene.project_metadata.detected_openings = len(scene.openings)
    scene.collision_segments = [(wall.start, wall.end) for wall in scene.walls]
    return scene


def add_opening(scene: SceneManifest, request: OpeningCreateRequest) -> SceneManifest:
    wall = _wall(scene, request.wall_id)
    default_width, default_height = DEFAULTS[request.opening_type]
    width = request.width or default_width
    height = request.height or default_height
    position, rotation, ratio = _pose(wall, request.placement_ratio, width)
    window = is_window(request.opening_type)
    passage = request.opening_type == "open_passage"
    opening = Opening(
        id=f"opening-{uuid.uuid4().hex[:10]}",
        opening_type=request.opening_type,
        position=position,
        width=round(width, 3),
        height=round(height, 3),
        rotation_deg=rotation,
        wall_id=wall.id,
        placement_ratio=ratio,
        swing_direction="none" if window or passage else request.swing_direction,
        hinge_side="none" if window or passage else request.hinge_side,
        swing_angle_deg=request.swing_angle_deg,
        sill_height=request.sill_height if window else 0.0,
        interactive=bool(request.interactive and is_door(request.opening_type)),
        default_open=bool(request.default_open or passage),
        source="manual",
        confidence=1.0,
    )
    if _overlaps(scene, opening):
        raise ValueError("This opening overlaps another opening on the selected wall.")
    scene.openings.append(opening)
    return _refresh(scene)


def update_opening(scene: SceneManifest, opening_id: str, request: OpeningUpdateRequest) -> SceneManifest:
    opening = next((item for item in scene.openings if item.id == opening_id), None)
    if not opening:
        raise KeyError("Opening not found")
    data = request.model_dump(exclude_none=True)
    opening_type = str(data.get("opening_type", opening.opening_type))
    wall_id = str(data.get("wall_id", opening.wall_id or ""))
    if not wall_id:
        raise ValueError("Choose a wall for this opening.")
    width = float(data.get("width", opening.width))
    ratio = float(data.get("placement_ratio", opening.placement_ratio if opening.placement_ratio is not None else 0.5))
    wall = _wall(scene, wall_id)
    position, rotation, safe_ratio = _pose(wall, ratio, width)

    opening.opening_type = opening_type  # type: ignore[assignment]
    opening.wall_id = wall_id
    opening.position = position
    opening.rotation_deg = rotation
    opening.placement_ratio = safe_ratio
    opening.width = round(width, 3)
    for key in ("height", "swing_direction", "hinge_side", "swing_angle_deg", "sill_height", "interactive", "default_open"):
        if key in data:
            setattr(opening, key, data[key])
    if is_window(opening_type):
        opening.swing_direction = "none"
        opening.hinge_side = "none"
        opening.interactive = False
    elif opening_type == "open_passage":
        opening.swing_direction = "none"
        opening.hinge_side = "none"
        opening.interactive = False
        opening.default_open = True
        opening.sill_height = 0.0
    else:
        opening.sill_height = 0.0
    opening.source = "manual"
    opening.confidence = 1.0
    if _overlaps(scene, opening, ignore_id=opening.id):
        raise ValueError("This opening overlaps another opening on the selected wall.")
    return _refresh(scene)


def delete_opening(scene: SceneManifest, opening_id: str) -> SceneManifest:
    original = len(scene.openings)
    scene.openings = [item for item in scene.openings if item.id != opening_id]
    if len(scene.openings) == original:
        raise KeyError("Opening not found")
    return _refresh(scene)
