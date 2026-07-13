from __future__ import annotations

import math
import uuid

from ..models import AssetFile, RoomShape, SceneAsset, SceneManifest

ASSET_SIZES: dict[str, tuple[float, float, float]] = {
    "fridge": (0.9, 2.0, 0.75),
    "cabinetry": (2.4, 0.9, 0.6),
    "countertop": (2.1, 0.9, 0.7),
    "stove": (0.7, 0.9, 0.65),
    "couch": (2.2, 0.9, 0.95),
    "tv_unit": (1.8, 0.65, 0.45),
    "coffee_table": (1.1, 0.45, 0.65),
    "light_fixture": (0.45, 0.45, 0.45),
    "sink": (0.65, 0.9, 0.55),
    "bathtub": (1.7, 0.65, 0.8),
    "tiles": (0.4, 0.04, 0.4),
    "vanity": (1.1, 0.9, 0.55),
}

ROOM_KEYWORDS = {
    "kitchen": ("kitchen",),
    "living_room": ("living", "lounge", "family"),
    "bathroom": ("bath", "wc", "toilet", "shower"),
}


def _room_for_asset(scene: SceneManifest, category: str, index: int) -> RoomShape | None:
    candidates = ROOM_KEYWORDS.get(category, ())
    for room in scene.rooms:
        if any(word in room.name.lower() for word in candidates):
            return room
    return scene.rooms[index % len(scene.rooms)] if scene.rooms else None


def _placed_position(room: RoomShape | None, slot: str, index: int) -> tuple[float, float, float]:
    size = ASSET_SIZES.get(slot, (1.0, 1.0, 1.0))
    if not room:
        return (1.0 + index * 1.3, size[1] / 2, 1.0)
    angle = (index * 2.3999632297) % (math.pi * 2)
    radius = min(1.3, max(0.25, math.sqrt(max(room.area_m2, 1)) * 0.15))
    x = room.centroid[0] + math.cos(angle) * radius
    z = room.centroid[1] + math.sin(angle) * radius
    return (round(x, 3), round(size[1] / 2, 3), round(z, 3))


def apply_assets(scene: SceneManifest, assets: dict[str, AssetFile]) -> SceneManifest:
    scene_assets: list[SceneAsset] = []
    floor_texture = None
    floor_texture_path = None
    wall_texture = None
    wall_texture_path = None
    object_index = 0
    for asset in assets.values():
        if asset.category == "flooring" and floor_texture is None:
            floor_texture = asset.url
            floor_texture_path = asset.path
            continue
        if asset.category == "walls" and wall_texture is None:
            wall_texture = asset.url
            wall_texture_path = asset.path
            continue
        room = _room_for_asset(scene, asset.category, object_index)
        size = ASSET_SIZES.get(asset.slot, (1.0, 1.0, 1.0))
        scene_assets.append(SceneAsset(
            id=f"asset-{uuid.uuid4().hex[:8]}",
            category=asset.category,
            slot=asset.slot,
            label=asset.label,
            room_id=room.id if room else None,
            position=_placed_position(room, asset.slot, object_index),
            rotation_y=(object_index % 4) * math.pi / 2,
            size=size,
            source_url=asset.url,
            source_path=asset.path,
            mesh_url=asset.mesh_url,
            mesh_path=asset.mesh_path,
            source="user_upload",
            confidence=1.0,
        ))
        object_index += 1
    scene.assets = scene_assets
    scene.floor_texture_url = floor_texture
    scene.floor_texture_path = floor_texture_path
    scene.wall_texture_url = wall_texture
    scene.wall_texture_path = wall_texture_path
    if not scene.camera_path:
        scene.camera_path = generate_camera_path(scene.rooms, scene.width_m, scene.depth_m)
    return scene


def generate_camera_path(rooms: list[RoomShape], width_m: float, depth_m: float) -> list[tuple[float, float, float]]:
    if not rooms:
        return [(width_m * 0.15, 1.7, depth_m * 0.15), (width_m * 0.85, 1.7, depth_m * 0.85)]
    remaining = rooms.copy()
    current = min(remaining, key=lambda room: room.centroid[0] + room.centroid[1])
    ordered = [current]
    remaining.remove(current)
    while remaining:
        current = min(remaining, key=lambda room: math.dist(current.centroid, room.centroid))
        ordered.append(current)
        remaining.remove(current)
    points: list[tuple[float, float, float]] = []
    for room in ordered:
        points.append((round(room.centroid[0], 3), 1.7, round(room.centroid[1], 3)))
    if len(points) == 1:
        x, y, z = points[0]
        points.append((min(width_m - 0.5, x + 1.0), y, min(depth_m - 0.5, z + 1.0)))
    return points
