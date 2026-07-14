from __future__ import annotations

import math
import uuid

from ..models import Opening, OpeningCreateRequest, OpeningUpdateRequest, SceneManifest, WallSegment
from .shared_portals import annotate_shared_walls, portal_room_ids, shared_wall_cluster


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


def _project_ratio(wall: WallSegment, point: tuple[float, float]) -> tuple[float, float]:
    x1, z1 = wall.start
    x2, z2 = wall.end
    dx, dz = x2 - x1, z2 - z1
    length_squared = dx * dx + dz * dz
    if length_squared <= 1e-8:
        return 0.5, math.dist(point, wall.start)
    ratio = max(0.0, min(1.0, ((point[0] - x1) * dx + (point[1] - z1) * dz) / length_squared))
    closest = (x1 + dx * ratio, z1 + dz * ratio)
    return ratio, math.dist(point, closest)


def nearest_wall(
    scene: SceneManifest,
    point: tuple[float, float],
    maximum_distance: float = 0.85,
) -> tuple[WallSegment, float, float] | None:
    best: tuple[WallSegment, float, float] | None = None
    for wall in scene.walls:
        ratio, distance = _project_ratio(wall, point)
        if distance > maximum_distance:
            continue
        if best is None or distance < best[2]:
            best = (wall, ratio, distance)
    return best


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


def _clamped_position(scene: SceneManifest, point: tuple[float, float]) -> tuple[float, float]:
    return (
        round(max(0.0, min(scene.width_m, float(point[0]))), 4),
        round(max(0.0, min(scene.depth_m, float(point[1]))), 4),
    )


def _opening_wall_ids(opening: Opening) -> set[str]:
    values = set(opening.wall_ids)
    if opening.wall_id:
        values.add(opening.wall_id)
    return values


def _attach_portal(
    scene: SceneManifest,
    opening: Opening,
    primary: WallSegment,
) -> None:
    walls = shared_wall_cluster(scene, primary, opening.position, opening.width)
    opening.wall_id = primary.id
    opening.wall_ids = [wall.id for wall in walls]
    opening.room_ids = portal_room_ids(scene, walls, opening.position)
    opening.portal_id = opening.portal_id or f"portal-{uuid.uuid4().hex[:10]}"


def _equivalent_portal(
    scene: SceneManifest,
    candidate: Opening,
    ignore_id: str | None = None,
) -> Opening | None:
    candidate_ids = _opening_wall_ids(candidate)
    for item in scene.openings:
        if item.id == ignore_id or item.opening_type != candidate.opening_type:
            continue
        item_ids = _opening_wall_ids(item)
        same_boundary = bool(candidate_ids and item_ids and candidate_ids.intersection(item_ids))
        if not same_boundary and candidate.portal_id and item.portal_id == candidate.portal_id:
            same_boundary = True
        if not same_boundary:
            continue
        tolerance = max(0.16, min(candidate.width, item.width) * 0.28)
        if math.dist(candidate.position, item.position) <= tolerance:
            return item
    return None


def _overlaps(scene: SceneManifest, candidate: Opening, ignore_id: str | None = None) -> bool:
    candidate_ids = _opening_wall_ids(candidate)
    for item in scene.openings:
        if item.id == ignore_id:
            continue
        item_ids = _opening_wall_ids(item)
        if candidate_ids and item_ids and candidate_ids.intersection(item_ids):
            clearance = max(0.12, (candidate.width + item.width) / 2 - 0.04)
            if math.dist(candidate.position, item.position) < clearance:
                return True
        elif not candidate_ids and not item_ids:
            clearance = max(0.22, min(candidate.width, item.width) * 0.34)
            if math.dist(candidate.position, item.position) < clearance:
                return True
    return False


def _deduplicate_portals(scene: SceneManifest) -> None:
    canonical: list[Opening] = []
    for opening in scene.openings:
        existing = None
        for candidate in canonical:
            if candidate.opening_type != opening.opening_type:
                continue
            shared_ids = _opening_wall_ids(candidate).intersection(_opening_wall_ids(opening))
            same_portal = candidate.portal_id and opening.portal_id and candidate.portal_id == opening.portal_id
            tolerance = max(0.16, min(candidate.width, opening.width) * 0.28)
            if (shared_ids or same_portal) and math.dist(candidate.position, opening.position) <= tolerance:
                existing = candidate
                break
        if existing is None:
            canonical.append(opening)
            continue
        existing.wall_ids = sorted(_opening_wall_ids(existing).union(_opening_wall_ids(opening)))
        existing.room_ids = sorted(set(existing.room_ids).union(opening.room_ids))
        existing.portal_id = existing.portal_id or opening.portal_id or f"portal-{uuid.uuid4().hex[:10]}"
        if opening.source == "manual" and existing.source != "manual":
            preserved_id = existing.id
            replacement = opening.model_copy(deep=True)
            replacement.id = preserved_id
            replacement.wall_ids = existing.wall_ids
            replacement.room_ids = existing.room_ids
            replacement.portal_id = existing.portal_id
            canonical[canonical.index(existing)] = replacement
    scene.openings = canonical


def _refresh(scene: SceneManifest) -> SceneManifest:
    annotate_shared_walls(scene)
    valid_wall_ids = {wall.id for wall in scene.walls}
    for opening in scene.openings:
        opening.wall_ids = [wall_id for wall_id in opening.wall_ids if wall_id in valid_wall_ids]
        if opening.wall_id and opening.wall_id not in valid_wall_ids:
            opening.wall_id = None
        if opening.wall_id:
            primary = _wall(scene, opening.wall_id)
            _attach_portal(scene, opening, primary)
        elif not opening.portal_id:
            opening.portal_id = f"portal-{uuid.uuid4().hex[:10]}"
    _deduplicate_portals(scene)
    scene.project_metadata.detected_openings = len(scene.openings)
    scene.collision_segments = [(wall.start, wall.end) for wall in scene.walls]
    return scene


def _normalised_properties(
    opening_type: str,
    swing_direction: str,
    hinge_side: str,
    interactive: bool,
    default_open: bool,
    sill_height: float,
) -> tuple[str, str, bool, bool, float]:
    window = is_window(opening_type)
    passage = opening_type == "open_passage"
    if window or passage:
        swing_direction = "none"
        hinge_side = "none"
        interactive = False
    if passage:
        default_open = True
    if not window:
        sill_height = 0.0
    return swing_direction, hinge_side, bool(interactive and is_door(opening_type)), bool(default_open), sill_height


def add_opening_at_position(
    scene: SceneManifest,
    *,
    opening_type: str,
    position: tuple[float, float],
    wall_id: str | None = None,
    placement_ratio: float | None = None,
    rotation_deg: float = 0.0,
    snap_to_wall: bool = True,
    width: float | None = None,
    height: float | None = None,
    swing_direction: str = "clockwise",
    hinge_side: str = "left",
    swing_angle_deg: float = 90.0,
    sill_height: float = 0.9,
    interactive: bool = True,
    default_open: bool = False,
) -> SceneManifest:
    annotate_shared_walls(scene)
    default_width, default_height = DEFAULTS[opening_type]
    resolved_width = float(width or default_width)
    resolved_height = float(height or default_height)
    target_wall: WallSegment | None = None
    ratio = placement_ratio

    if wall_id:
        target_wall = _wall(scene, wall_id)
        if ratio is None:
            ratio, _ = _project_ratio(target_wall, position)
    elif snap_to_wall and scene.walls:
        match = nearest_wall(scene, position, maximum_distance=max(0.5, min(1.2, resolved_width * 0.55)))
        if match:
            target_wall, ratio, _ = match

    if target_wall is not None:
        resolved_position, resolved_rotation, safe_ratio = _pose(target_wall, float(ratio if ratio is not None else 0.5), resolved_width)
        resolved_wall_id: str | None = target_wall.id
        resolved_ratio: float | None = safe_ratio
    else:
        resolved_position = _clamped_position(scene, position)
        resolved_rotation = round(float(rotation_deg), 3)
        resolved_wall_id = None
        resolved_ratio = None

    swing_direction, hinge_side, interactive, default_open, sill_height = _normalised_properties(
        opening_type, swing_direction, hinge_side, interactive, default_open, sill_height,
    )
    opening = Opening(
        id=f"opening-{uuid.uuid4().hex[:10]}",
        portal_id=f"portal-{uuid.uuid4().hex[:10]}",
        opening_type=opening_type,  # type: ignore[arg-type]
        position=resolved_position,
        width=round(resolved_width, 3),
        height=round(resolved_height, 3),
        rotation_deg=resolved_rotation,
        wall_id=resolved_wall_id,
        placement_ratio=resolved_ratio,
        swing_direction=swing_direction,  # type: ignore[arg-type]
        hinge_side=hinge_side,  # type: ignore[arg-type]
        swing_angle_deg=float(swing_angle_deg),
        sill_height=float(sill_height),
        interactive=interactive,
        default_open=default_open,
        source="manual",
        confidence=1.0,
    )
    if target_wall is not None:
        _attach_portal(scene, opening, target_wall)

    duplicate = _equivalent_portal(scene, opening)
    if duplicate is not None:
        duplicate.wall_ids = sorted(_opening_wall_ids(duplicate).union(_opening_wall_ids(opening)))
        duplicate.room_ids = sorted(set(duplicate.room_ids).union(opening.room_ids))
        duplicate.portal_id = duplicate.portal_id or opening.portal_id
        return _refresh(scene)
    if _overlaps(scene, opening):
        raise ValueError("This opening overlaps another opening at the selected location.")

    scene.openings.append(opening)
    if opening.wall_id is None:
        warning = "A manually placed opening is not attached to a wall yet. It will snap automatically when a nearby wall is created or detected."
        if warning not in scene.warnings:
            scene.warnings.append(warning)
    return _refresh(scene)


def update_opening_at_position(
    scene: SceneManifest,
    opening_id: str,
    *,
    opening_type: str | None = None,
    position: tuple[float, float] | None = None,
    wall_id: str | None = None,
    placement_ratio: float | None = None,
    rotation_deg: float | None = None,
    snap_to_wall: bool = True,
    width: float | None = None,
    height: float | None = None,
    swing_direction: str | None = None,
    hinge_side: str | None = None,
    swing_angle_deg: float | None = None,
    sill_height: float | None = None,
    interactive: bool | None = None,
    default_open: bool | None = None,
) -> SceneManifest:
    annotate_shared_walls(scene)
    opening = next((item for item in scene.openings if item.id == opening_id), None)
    if not opening:
        raise KeyError("Opening not found")

    resolved_type = opening_type or opening.opening_type
    resolved_width = float(width if width is not None else opening.width)
    requested_position = position or opening.position
    target_wall: WallSegment | None = None
    ratio = placement_ratio

    if wall_id:
        target_wall = _wall(scene, wall_id)
        if ratio is None:
            ratio, _ = _project_ratio(target_wall, requested_position)
    elif snap_to_wall and scene.walls:
        match = nearest_wall(scene, requested_position, maximum_distance=max(0.5, min(1.2, resolved_width * 0.55)))
        if match:
            target_wall, ratio, _ = match

    if target_wall is not None:
        resolved_position, resolved_rotation, safe_ratio = _pose(target_wall, float(ratio if ratio is not None else 0.5), resolved_width)
        opening.wall_id = target_wall.id
        opening.placement_ratio = safe_ratio
        opening.position = resolved_position
        opening.rotation_deg = resolved_rotation
    else:
        opening.wall_id = None
        opening.wall_ids = []
        opening.room_ids = []
        opening.placement_ratio = None
        opening.position = _clamped_position(scene, requested_position)
        opening.rotation_deg = round(float(rotation_deg if rotation_deg is not None else opening.rotation_deg), 3)

    opening.opening_type = resolved_type  # type: ignore[assignment]
    opening.width = round(resolved_width, 3)
    if height is not None:
        opening.height = round(float(height), 3)
    resolved_swing = swing_direction if swing_direction is not None else opening.swing_direction
    resolved_hinge = hinge_side if hinge_side is not None else opening.hinge_side
    resolved_interactive = interactive if interactive is not None else opening.interactive
    resolved_default_open = default_open if default_open is not None else opening.default_open
    resolved_sill = sill_height if sill_height is not None else opening.sill_height
    resolved_swing, resolved_hinge, resolved_interactive, resolved_default_open, resolved_sill = _normalised_properties(
        resolved_type, resolved_swing, resolved_hinge, resolved_interactive, resolved_default_open, resolved_sill,
    )
    opening.swing_direction = resolved_swing  # type: ignore[assignment]
    opening.hinge_side = resolved_hinge  # type: ignore[assignment]
    opening.interactive = resolved_interactive
    opening.default_open = resolved_default_open
    opening.sill_height = resolved_sill
    if swing_angle_deg is not None:
        opening.swing_angle_deg = float(swing_angle_deg)
    opening.source = "manual"
    opening.confidence = 1.0
    opening.portal_id = opening.portal_id or f"portal-{uuid.uuid4().hex[:10]}"
    if target_wall is not None:
        _attach_portal(scene, opening, target_wall)

    duplicate = _equivalent_portal(scene, opening, ignore_id=opening.id)
    if duplicate is not None:
        raise ValueError("Another door or window already owns this shared portal.")
    if _overlaps(scene, opening, ignore_id=opening.id):
        raise ValueError("This opening overlaps another opening at the selected location.")
    return _refresh(scene)


def reattach_manual_openings(scene: SceneManifest, maximum_distance: float = 1.0) -> SceneManifest:
    annotate_shared_walls(scene)
    for opening in scene.openings:
        if opening.source != "manual":
            continue
        current_wall = next((wall for wall in scene.walls if wall.id == opening.wall_id), None) if opening.wall_id else None
        if current_wall is not None:
            ratio, _ = _project_ratio(current_wall, opening.position)
            try:
                opening.position, opening.rotation_deg, opening.placement_ratio = _pose(current_wall, ratio, opening.width)
                _attach_portal(scene, opening, current_wall)
            except ValueError:
                opening.wall_id = None
                opening.wall_ids = []
                opening.room_ids = []
                opening.placement_ratio = None
            continue
        match = nearest_wall(scene, opening.position, maximum_distance=max(maximum_distance, opening.width * 0.5))
        if not match:
            opening.wall_id = None
            opening.wall_ids = []
            opening.room_ids = []
            opening.placement_ratio = None
            continue
        wall, ratio, _distance = match
        try:
            opening.position, opening.rotation_deg, opening.placement_ratio = _pose(wall, ratio, opening.width)
            opening.wall_id = wall.id
            _attach_portal(scene, opening, wall)
        except ValueError:
            opening.wall_id = None
            opening.wall_ids = []
            opening.room_ids = []
            opening.placement_ratio = None
    return _refresh(scene)


def restore_manual_openings(scene: SceneManifest, preserved: list[Opening]) -> SceneManifest:
    detected = [item for item in scene.openings if item.source != "manual"]
    manual = [item.model_copy(deep=True) for item in preserved]
    scene.openings = detected
    for opening in manual:
        duplicate = next((
            item for item in scene.openings
            if item.opening_type == opening.opening_type
            and math.dist(item.position, opening.position) < max(0.25, min(item.width, opening.width) * 0.4)
        ), None)
        if duplicate is not None:
            scene.openings.remove(duplicate)
        scene.openings.append(opening)
    return reattach_manual_openings(scene)


def add_opening(scene: SceneManifest, request: OpeningCreateRequest) -> SceneManifest:
    wall = _wall(scene, request.wall_id)
    ratio = request.placement_ratio
    position = (
        wall.start[0] + (wall.end[0] - wall.start[0]) * ratio,
        wall.start[1] + (wall.end[1] - wall.start[1]) * ratio,
    )
    return add_opening_at_position(
        scene,
        opening_type=request.opening_type,
        position=position,
        wall_id=request.wall_id,
        placement_ratio=ratio,
        width=request.width,
        height=request.height,
        swing_direction=request.swing_direction,
        hinge_side=request.hinge_side,
        swing_angle_deg=request.swing_angle_deg,
        sill_height=request.sill_height,
        interactive=request.interactive,
        default_open=request.default_open,
    )


def update_opening(scene: SceneManifest, opening_id: str, request: OpeningUpdateRequest) -> SceneManifest:
    opening = next((item for item in scene.openings if item.id == opening_id), None)
    if not opening:
        raise KeyError("Opening not found")
    data = request.model_dump(exclude_none=True)
    wall_id = data.get("wall_id", opening.wall_id)
    if not wall_id:
        raise ValueError("Choose a wall for this opening.")
    return update_opening_at_position(
        scene,
        opening_id,
        opening_type=data.get("opening_type"),
        position=opening.position,
        wall_id=str(wall_id),
        placement_ratio=data.get("placement_ratio", opening.placement_ratio),
        width=data.get("width"),
        height=data.get("height"),
        swing_direction=data.get("swing_direction"),
        hinge_side=data.get("hinge_side"),
        swing_angle_deg=data.get("swing_angle_deg"),
        sill_height=data.get("sill_height"),
        interactive=data.get("interactive"),
        default_open=data.get("default_open"),
    )


def delete_opening(scene: SceneManifest, opening_id: str) -> SceneManifest:
    original = len(scene.openings)
    scene.openings = [item for item in scene.openings if item.id != opening_id]
    if len(scene.openings) == original:
        raise KeyError("Opening not found")
    return _refresh(scene)
