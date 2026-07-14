from __future__ import annotations

import math
import uuid

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points

from ..models import RoomCreateRequest, RoomShape, SceneManifest, WallSegment
from .shared_portals import annotate_shared_walls


MIN_VERTEX_DISTANCE = 0.025
MAX_ROOM_VERTICES = 64
ROOM_SNAP_DISTANCE = 0.22


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _clean_vertices(points: list[tuple[float, float]], scene: SceneManifest) -> list[tuple[float, float]]:
    cleaned: list[tuple[float, float]] = []
    for x, z in points:
        point = (
            round(_clamp(float(x), 0.0, scene.width_m), 3),
            round(_clamp(float(z), 0.0, scene.depth_m), 3),
        )
        if cleaned and math.dist(cleaned[-1], point) < MIN_VERTEX_DISTANCE:
            continue
        cleaned.append(point)
    if len(cleaned) > 1 and math.dist(cleaned[0], cleaned[-1]) < MIN_VERTEX_DISTANCE:
        cleaned.pop()
    if len(cleaned) < 3:
        raise ValueError("A room needs at least three distinct points.")
    if len(cleaned) > MAX_ROOM_VERTICES:
        raise ValueError(f"A room can contain at most {MAX_ROOM_VERTICES} points.")
    return cleaned


def _normalise_polygon(
    points: list[tuple[float, float]],
    scene: SceneManifest,
) -> tuple[list[tuple[float, float]], float, tuple[float, float]]:
    cleaned = _clean_vertices(points, scene)
    polygon = Polygon(cleaned)
    if not polygon.is_valid:
        raise ValueError(
            "Room edges cannot cross or overlap. Move the numbered points until the polygon forms one simple closed boundary."
        )
    if polygon.is_empty or polygon.geom_type != "Polygon" or polygon.area < 0.1:
        raise ValueError("Room geometry must form one valid polygon with an area of at least 0.1 m².")
    exterior = [(round(float(x), 3), round(float(z), 3)) for x, z in list(polygon.exterior.coords)[:-1]]
    return exterior, round(float(polygon.area), 2), (
        round(float(polygon.centroid.x), 3),
        round(float(polygon.centroid.y), 3),
    )


def _room_edges(room: RoomShape) -> list[LineString]:
    if len(room.polygon) < 2:
        return []
    closed = room.polygon + [room.polygon[0]]
    return [LineString([start, end]) for start, end in zip(closed, closed[1:]) if math.dist(start, end) >= 0.08]


def snap_room_polygon(
    scene: SceneManifest,
    points: list[tuple[float, float]],
    room_id: str | None = None,
    tolerance: float = ROOM_SNAP_DISTANCE,
) -> list[tuple[float, float]]:
    """Snap vertices to nearby room boundaries while preserving separate room-owned walls."""
    other_rooms = [room for room in scene.rooms if room.id != room_id and len(room.polygon) >= 3]
    if not other_rooms:
        return points

    target_vertices = [vertex for room in other_rooms for vertex in room.polygon]
    target_edges = [edge for room in other_rooms for edge in _room_edges(room)]
    snapped: list[tuple[float, float]] = []

    for raw in points:
        point = (float(raw[0]), float(raw[1]))
        best_vertex = min(target_vertices, key=lambda vertex: math.dist(point, vertex), default=None)
        if best_vertex is not None and math.dist(point, best_vertex) <= tolerance:
            snapped.append((round(best_vertex[0], 3), round(best_vertex[1], 3)))
            continue

        source_point = Point(point)
        best_projection: tuple[float, tuple[float, float]] | None = None
        for edge in target_edges:
            distance = source_point.distance(edge)
            if distance > tolerance:
                continue
            projected = nearest_points(source_point, edge)[1]
            candidate = (distance, (float(projected.x), float(projected.y)))
            if best_projection is None or candidate[0] < best_projection[0]:
                best_projection = candidate
        if best_projection is not None:
            snapped.append((round(best_projection[1][0], 3), round(best_projection[1][1], 3)))
        else:
            snapped.append(point)

    return snapped


def walls_from_rooms(scene: SceneManifest) -> list[WallSegment]:
    """Create one independent wall record for every room edge, then link coincident pairs.

    Shared walls remain separate room objects. Their render thickness and offsets divide the
    physical partition between the two room-owned meshes, preventing Z-fighting without
    permanently combining the meshes.
    """
    thickness = scene.walls[0].thickness if scene.walls else 0.16
    walls: list[WallSegment] = []
    for room in scene.rooms:
        if len(room.polygon) < 3:
            continue
        closed = room.polygon + [room.polygon[0]]
        for edge_index, (start, end) in enumerate(zip(closed, closed[1:])):
            if math.dist(start, end) < 0.08:
                continue
            walls.append(
                WallSegment(
                    id=f"wall-{room.id}-{edge_index}",
                    start=(round(start[0], 3), round(start[1], 3)),
                    end=(round(end[0], 3), round(end[1], 3)),
                    height=scene.wall_height_m,
                    thickness=thickness,
                    wall_type="exterior",
                    confidence=1.0,
                    owner_room_id=room.id,
                )
            )
    return annotate_shared_walls(scene, walls)


def rebuild_scene_from_rooms(scene: SceneManifest) -> SceneManifest:
    preserved_manual = [item.model_copy(deep=True) for item in scene.openings if item.source == "manual"]
    normalised_rooms: list[RoomShape] = []
    for room in scene.rooms:
        polygon, area, centroid = _normalise_polygon(room.polygon, scene)
        xs = [point[0] for point in polygon]
        zs = [point[1] for point in polygon]
        normalised_rooms.append(
            RoomShape(
                id=room.id,
                name=room.name,
                polygon=polygon,
                area_m2=area,
                centroid=centroid,
                room_type=room.room_type,
                width_m=round(max(xs) - min(xs), 3),
                depth_m=round(max(zs) - min(zs), 3),
                extracted_dimension=room.extracted_dimension,
                label_confidence=room.label_confidence,
            )
        )
    scene.rooms = normalised_rooms
    scene.walls = walls_from_rooms(scene)
    scene.camera_path = [(room.centroid[0], 1.6, room.centroid[1]) for room in scene.rooms]
    scene.openings = []
    if preserved_manual:
        from .openings import restore_manual_openings
        scene = restore_manual_openings(scene, preserved_manual)
    scene.fixtures_and_furniture = []
    scene.collision_segments = [(wall.start, wall.end) for wall in scene.walls]
    scene.first_person_start = scene.camera_path[0] if scene.camera_path else None
    scene.layout_mode = "manual"
    scene.project_metadata.detected_rooms = len(scene.rooms)
    scene.project_metadata.detected_openings = len(scene.openings)
    scene.project_metadata.detected_objects = 0
    scene.project_metadata.structural_confidence = 1.0 if scene.rooms else 0.0
    scene.warnings = [
        warning for warning in scene.warnings
        if "wall count" not in warning.lower()
        and "probabilistic" not in warning.lower()
        and "compile production" not in warning.lower()
        and "manually placed opening" not in warning.lower()
        and "nearby room vertices" not in warning.lower()
        and "shared wall" not in warning.lower()
    ]
    messages = [
        "Nearby room vertices snap within 0.22 m while each room keeps its own wall objects.",
        "Touching parallel walls are linked as one shared boundary without permanently merging their meshes.",
        "A door on a shared boundary creates one portal entity that punches every linked room wall.",
        "Compile the production scene after editing to recalculate objects and the walkthrough path.",
    ]
    if any(opening.wall_id is None for opening in scene.openings):
        messages.append("Some manually placed doors or windows are still unattached; move a room wall closer or reposition the opening to snap it.")
    for message in messages:
        if message not in scene.warnings:
            scene.warnings.append(message)
    return scene


def add_room(scene: SceneManifest, request: RoomCreateRequest) -> SceneManifest:
    width = min(request.width, scene.width_m)
    depth = min(request.depth, scene.depth_m)
    x = _clamp(request.x, 0.0, max(0.0, scene.width_m - width))
    z = _clamp(request.z, 0.0, max(0.0, scene.depth_m - depth))
    polygon = [(x, z), (x + width, z), (x + width, z + depth), (x, z + depth)]
    polygon = snap_room_polygon(scene, polygon)
    points, area, centroid = _normalise_polygon(polygon, scene)
    scene.rooms.append(
        RoomShape(
            id=f"room-{uuid.uuid4().hex[:8]}",
            name=request.name,
            polygon=points,
            area_m2=area,
            centroid=centroid,
            width_m=round(width, 3),
            depth_m=round(depth, 3),
            label_confidence=1.0,
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
    snapped = snap_room_polygon(scene, polygon, room_id=room_id)
    points, area, centroid = _normalise_polygon(snapped, scene)
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
