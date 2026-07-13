from __future__ import annotations

import math
import uuid
from collections import defaultdict

from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import unary_union

from ..models import RoomCreateRequest, RoomShape, SceneManifest, WallSegment


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _normalise_polygon(
    points: list[tuple[float, float]],
    scene: SceneManifest,
) -> tuple[list[tuple[float, float]], float, tuple[float, float]]:
    cleaned = [
        (
            round(_clamp(float(x), 0.0, scene.width_m), 3),
            round(_clamp(float(z), 0.0, scene.depth_m), 3),
        )
        for x, z in points
    ]
    polygon = Polygon(cleaned)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty or polygon.geom_type != "Polygon" or polygon.area < 0.1:
        raise ValueError("Room geometry must form one valid polygon with an area of at least 0.1 m².")
    exterior = [(round(float(x), 3), round(float(z), 3)) for x, z in list(polygon.exterior.coords)[:-1]]
    return exterior, round(float(polygon.area), 2), (
        round(float(polygon.centroid.x), 3),
        round(float(polygon.centroid.y), 3),
    )


def _flatten_lines(geometry) -> list[LineString]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, LineString):
        return [geometry]
    if isinstance(geometry, MultiLineString):
        return list(geometry.geoms)
    result: list[LineString] = []
    for item in getattr(geometry, "geoms", []):
        result.extend(_flatten_lines(item))
    return result


def _merge_axis_intervals(
    groups: dict[float, list[tuple[float, float]]],
    horizontal: bool,
    tolerance: float = 0.03,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    merged_segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for axis, intervals in groups.items():
        intervals.sort()
        merged: list[list[float]] = []
        for start, end in intervals:
            if not merged or start > merged[-1][1] + tolerance:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        for start, end in merged:
            if end - start < 0.08:
                continue
            if horizontal:
                merged_segments.append(((start, axis), (end, axis)))
            else:
                merged_segments.append(((axis, start), (axis, end)))
    return merged_segments


def walls_from_rooms(scene: SceneManifest) -> list[WallSegment]:
    source_lines: list[LineString] = []
    for room in scene.rooms:
        if len(room.polygon) < 3:
            continue
        closed = room.polygon + [room.polygon[0]]
        for start, end in zip(closed, closed[1:]):
            if math.dist(start, end) >= 0.08:
                source_lines.append(LineString([start, end]))

    if not source_lines:
        return []

    network = unary_union(source_lines)
    horizontal: dict[float, list[tuple[float, float]]] = defaultdict(list)
    vertical: dict[float, list[tuple[float, float]]] = defaultdict(list)
    diagonal: list[tuple[tuple[float, float], tuple[float, float]]] = []

    for line in _flatten_lines(network):
        coordinates = list(line.coords)
        for start, end in zip(coordinates, coordinates[1:]):
            x1, z1 = map(float, start)
            x2, z2 = map(float, end)
            if math.dist((x1, z1), (x2, z2)) < 0.08:
                continue
            if abs(z2 - z1) <= 0.025:
                axis = round((z1 + z2) / 2, 2)
                horizontal[axis].append((min(x1, x2), max(x1, x2)))
            elif abs(x2 - x1) <= 0.025:
                axis = round((x1 + x2) / 2, 2)
                vertical[axis].append((min(z1, z2), max(z1, z2)))
            else:
                diagonal.append(((x1, z1), (x2, z2)))

    segments = _merge_axis_intervals(horizontal, True) + _merge_axis_intervals(vertical, False) + diagonal
    thickness = scene.walls[0].thickness if scene.walls else 0.16
    return [
        WallSegment(
            id=f"wall-{uuid.uuid4().hex[:8]}",
            start=(round(start[0], 3), round(start[1], 3)),
            end=(round(end[0], 3), round(end[1], 3)),
            height=scene.wall_height_m,
            thickness=thickness,
        )
        for start, end in segments
    ]


def rebuild_scene_from_rooms(scene: SceneManifest) -> SceneManifest:
    normalised_rooms: list[RoomShape] = []
    for room in scene.rooms:
        polygon, area, centroid = _normalise_polygon(room.polygon, scene)
        normalised_rooms.append(
            RoomShape(
                id=room.id,
                name=room.name,
                polygon=polygon,
                area_m2=area,
                centroid=centroid,
            )
        )
    scene.rooms = normalised_rooms
    scene.walls = walls_from_rooms(scene)
    scene.camera_path = [
        (room.centroid[0], 1.6, room.centroid[1]) for room in scene.rooms
    ]
    scene.layout_mode = "manual"
    scene.warnings = [
        warning for warning in scene.warnings
        if "wall count" not in warning.lower() and "probabilistic" not in warning.lower()
    ]
    if "Manual room layout is authoritative; walls are rebuilt from room boundaries." not in scene.warnings:
        scene.warnings.append("Manual room layout is authoritative; walls are rebuilt from room boundaries.")
    return scene


def add_room(scene: SceneManifest, request: RoomCreateRequest) -> SceneManifest:
    width = min(request.width, scene.width_m)
    depth = min(request.depth, scene.depth_m)
    x = _clamp(request.x, 0.0, max(0.0, scene.width_m - width))
    z = _clamp(request.z, 0.0, max(0.0, scene.depth_m - depth))
    polygon = [
        (x, z),
        (x + width, z),
        (x + width, z + depth),
        (x, z + depth),
    ]
    points, area, centroid = _normalise_polygon(polygon, scene)
    scene.rooms.append(
        RoomShape(
            id=f"room-{uuid.uuid4().hex[:8]}",
            name=request.name,
            polygon=points,
            area_m2=area,
            centroid=centroid,
        )
    )
    return rebuild_scene_from_rooms(scene)


def update_room_geometry(
    scene: SceneManifest,
    room_id: str,
    polygon: list[tuple[float, float]],
) -> SceneManifest:
    room = next((item for item in scene.rooms if item.id == room_id), None)
    if room is None:
        raise KeyError(room_id)
    points, area, centroid = _normalise_polygon(polygon, scene)
    room.polygon = points
    room.area_m2 = area
    room.centroid = centroid
    return rebuild_scene_from_rooms(scene)


def delete_room(scene: SceneManifest, room_id: str) -> SceneManifest:
    before = len(scene.rooms)
    scene.rooms = [room for room in scene.rooms if room.id != room_id]
    if len(scene.rooms) == before:
        raise KeyError(room_id)
    return rebuild_scene_from_rooms(scene)
