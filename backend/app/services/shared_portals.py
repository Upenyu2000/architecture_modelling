from __future__ import annotations

import math
import uuid
from collections import defaultdict

from shapely.geometry import Point, Polygon

from ..models import RoomShape, SceneManifest, WallSegment


PARALLEL_ANGLE_DEGREES = 6.0
SHARED_WALL_DISTANCE_M = 0.22
MINIMUM_OVERLAP_M = 0.18


def _vector(wall: WallSegment) -> tuple[float, float, float]:
    dx = wall.end[0] - wall.start[0]
    dz = wall.end[1] - wall.start[1]
    length = math.hypot(dx, dz)
    if length <= 1e-8:
        return 0.0, 0.0, 0.0
    return dx / length, dz / length, length


def _point_line_distance(point: tuple[float, float], wall: WallSegment) -> float:
    ux, uz, length = _vector(wall)
    if length <= 1e-8:
        return math.dist(point, wall.start)
    px = point[0] - wall.start[0]
    pz = point[1] - wall.start[1]
    along = max(0.0, min(length, px * ux + pz * uz))
    closest = (wall.start[0] + ux * along, wall.start[1] + uz * along)
    return math.dist(point, closest)


def _interval_on_wall(reference: WallSegment, candidate: WallSegment) -> tuple[float, float]:
    ux, uz, _length = _vector(reference)
    values = [
        (point[0] - reference.start[0]) * ux + (point[1] - reference.start[1]) * uz
        for point in (candidate.start, candidate.end)
    ]
    return min(values), max(values)


def _overlap_interval(first: WallSegment, second: WallSegment) -> tuple[float, float] | None:
    _ux, _uz, first_length = _vector(first)
    if first_length <= 1e-8:
        return None
    other_start, other_end = _interval_on_wall(first, second)
    start = max(0.0, other_start)
    end = min(first_length, other_end)
    return (start, end) if end - start >= MINIMUM_OVERLAP_M else None


def walls_share_boundary(
    first: WallSegment,
    second: WallSegment,
    maximum_distance: float = SHARED_WALL_DISTANCE_M,
) -> bool:
    if first.id == second.id:
        return False
    if first.owner_room_id and first.owner_room_id == second.owner_room_id:
        return False
    ux1, uz1, length1 = _vector(first)
    ux2, uz2, length2 = _vector(second)
    if min(length1, length2) < MINIMUM_OVERLAP_M:
        return False

    cross = abs(ux1 * uz2 - uz1 * ux2)
    if cross > math.sin(math.radians(PARALLEL_ANGLE_DEGREES)):
        return False

    line_distance = min(
        _point_line_distance(second.start, first),
        _point_line_distance(second.end, first),
        _point_line_distance(first.start, second),
        _point_line_distance(first.end, second),
    )
    if line_distance > maximum_distance:
        return False
    return _overlap_interval(first, second) is not None


def _room_centroid(scene: SceneManifest, room_id: str | None) -> tuple[float, float] | None:
    if not room_id:
        return None
    room = next((item for item in scene.rooms if item.id == room_id), None)
    return room.centroid if room else None


def annotate_shared_walls(scene: SceneManifest, walls: list[WallSegment] | None = None) -> list[WallSegment]:
    """Keep every room-owned wall independent while recording touching-wall relationships."""
    resolved = walls if walls is not None else scene.walls
    by_id = {wall.id: wall for wall in resolved}
    parent = {wall.id: wall.id for wall in resolved}

    def find(wall_id: str) -> str:
        while parent[wall_id] != wall_id:
            parent[wall_id] = parent[parent[wall_id]]
            wall_id = parent[wall_id]
        return wall_id

    def union(first_id: str, second_id: str) -> None:
        first_root = find(first_id)
        second_root = find(second_id)
        if first_root != second_root:
            parent[second_root] = first_root

    for wall in resolved:
        wall.linked_wall_ids = []
        wall.shared_group_id = None
        wall.render_offset = (0.0, 0.0)
        wall.render_thickness = None
        wall.wall_type = "exterior"

    for index, first in enumerate(resolved):
        for second in resolved[index + 1:]:
            if not walls_share_boundary(first, second):
                continue
            first.linked_wall_ids.append(second.id)
            second.linked_wall_ids.append(first.id)
            union(first.id, second.id)

    groups: dict[str, list[WallSegment]] = defaultdict(list)
    for wall in resolved:
        groups[find(wall.id)].append(wall)

    for members in groups.values():
        if len(members) <= 1:
            continue
        group_id = f"shared-{uuid.uuid5(uuid.NAMESPACE_URL, '|'.join(sorted(item.id for item in members))).hex[:12]}"
        for index, wall in enumerate(members):
            wall.shared_group_id = group_id
            wall.wall_type = "interior"
            wall.linked_wall_ids = sorted(set(wall.linked_wall_ids))
            wall.render_thickness = round(wall.thickness / len(members), 4)

            ux, uz, _length = _vector(wall)
            normal = (-uz, ux)
            midpoint = ((wall.start[0] + wall.end[0]) / 2, (wall.start[1] + wall.end[1]) / 2)
            centroid = _room_centroid(scene, wall.owner_room_id)
            if centroid is not None:
                side = 1.0 if (centroid[0] - midpoint[0]) * normal[0] + (centroid[1] - midpoint[1]) * normal[1] >= 0 else -1.0
            else:
                side = -1.0 if index % 2 == 0 else 1.0
            offset_distance = max(0.0, (wall.thickness - wall.render_thickness) / 2)
            wall.render_offset = (
                round(normal[0] * side * offset_distance, 5),
                round(normal[1] * side * offset_distance, 5),
            )

    return resolved


def shared_wall_cluster(
    scene: SceneManifest,
    primary: WallSegment,
    position: tuple[float, float] | None = None,
    opening_width: float = 0.9,
) -> list[WallSegment]:
    """Return all independent walls that the same physical portal must punch through."""
    candidates: list[WallSegment] = [primary]
    explicit = set(primary.linked_wall_ids)
    for wall in scene.walls:
        if wall.id == primary.id:
            continue
        if wall.id not in explicit and not (
            primary.shared_group_id and wall.shared_group_id == primary.shared_group_id
        ) and not walls_share_boundary(primary, wall):
            continue
        if position is not None:
            distance = _point_line_distance(position, wall)
            allowed = max(SHARED_WALL_DISTANCE_M + 0.08, (primary.thickness + wall.thickness) / 2 + 0.08)
            if distance > allowed:
                continue
            ux, uz, length = _vector(wall)
            along = (position[0] - wall.start[0]) * ux + (position[1] - wall.start[1]) * uz
            half = opening_width / 2
            if along + half < -0.04 or along - half > length + 0.04:
                continue
        candidates.append(wall)
    return sorted({wall.id: wall for wall in candidates}.values(), key=lambda item: item.id)


def portal_room_ids(
    scene: SceneManifest,
    walls: list[WallSegment],
    position: tuple[float, float],
) -> list[str]:
    room_ids = {wall.owner_room_id for wall in walls if wall.owner_room_id}
    if len(room_ids) >= 2:
        return sorted(room_ids)

    point = Point(position)
    tolerance = max((wall.thickness for wall in walls), default=0.16) + SHARED_WALL_DISTANCE_M
    for room in scene.rooms:
        if len(room.polygon) < 3:
            continue
        polygon = Polygon(room.polygon)
        if polygon.is_valid and polygon.boundary.distance(point) <= tolerance:
            room_ids.add(room.id)
    return sorted(room_ids)[:2]
