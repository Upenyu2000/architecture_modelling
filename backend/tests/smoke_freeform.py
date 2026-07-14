from __future__ import annotations

from app.models import ProjectMetadata, RoomShape, SceneManifest
from app.services.layout import rebuild_scene_from_rooms, update_room_geometry
from app.services.openings import add_opening_at_position


def scene_with_rooms() -> SceneManifest:
    return SceneManifest(
        project_id="smoke-freeform",
        width_m=12.0,
        depth_m=10.0,
        wall_height_m=2.8,
        walls=[],
        rooms=[
            RoomShape(
                id="rhombus",
                name="Rhombus Room",
                polygon=[(2.0, 1.0), (5.0, 3.0), (2.0, 5.0), (0.5, 3.0)],
                area_m2=0.0,
                centroid=(0.0, 0.0),
            ),
            RoomShape(
                id="l-room",
                name="L Room",
                polygon=[(5.0, 1.0), (10.0, 1.0), (10.0, 3.0), (8.0, 3.0), (8.0, 7.0), (5.0, 7.0)],
                area_m2=0.0,
                centroid=(0.0, 0.0),
            ),
        ],
        assets=[],
        camera_path=[],
        project_metadata=ProjectMetadata(),
    )


def adjacent_room_scene() -> SceneManifest:
    return SceneManifest(
        project_id="smoke-room-snap",
        width_m=12.0,
        depth_m=8.0,
        wall_height_m=2.8,
        walls=[],
        rooms=[
            RoomShape(
                id="room-1",
                name="Room 1",
                polygon=[(1.0, 1.0), (5.0, 1.0), (5.0, 5.0), (1.0, 5.0)],
                area_m2=16.0,
                centroid=(3.0, 3.0),
            ),
            RoomShape(
                id="room-2",
                name="Room 2",
                polygon=[(5.14, 1.0), (9.0, 1.0), (9.0, 5.0), (5.14, 5.0)],
                area_m2=15.44,
                centroid=(7.07, 3.0),
            ),
        ],
        assets=[],
        camera_path=[],
        project_metadata=ProjectMetadata(),
    )


def main() -> None:
    scene = rebuild_scene_from_rooms(scene_with_rooms())
    assert len(scene.rooms) == 2
    assert len(scene.rooms[0].polygon) == 4
    assert len(scene.rooms[1].polygon) == 6
    assert scene.rooms[0].area_m2 > 0
    assert scene.rooms[1].area_m2 > 0
    assert any(
        abs(wall.end[0] - wall.start[0]) > 0.025
        and abs(wall.end[1] - wall.start[1]) > 0.025
        for wall in scene.walls
    ), "Rhombus room must produce diagonal walls"
    assert scene.collision_segments == [(wall.start, wall.end) for wall in scene.walls]

    moved = update_room_geometry(
        scene,
        "rhombus",
        [(2.0, 0.8), (5.4, 3.0), (2.0, 5.2), (0.4, 3.0), (1.2, 2.2)],
    )
    assert len(next(room for room in moved.rooms if room.id == "rhombus").polygon) == 5

    try:
        update_room_geometry(moved, "rhombus", [(1.0, 1.0), (5.0, 5.0), (1.0, 5.0), (5.0, 1.0)])
    except ValueError:
        pass
    else:
        raise AssertionError("Self-crossing room polygons must be rejected")

    adjacent = adjacent_room_scene()
    adjacent = update_room_geometry(
        adjacent,
        "room-2",
        [(5.14, 1.0), (9.0, 1.0), (9.0, 5.0), (5.14, 5.0)],
    )
    room_2 = next(room for room in adjacent.rooms if room.id == "room-2")
    assert room_2.polygon[0][0] == 5.0 and room_2.polygon[-1][0] == 5.0, "Nearby room edge must snap to Room 1"
    shared = [
        wall for wall in adjacent.walls
        if abs(wall.start[0] - 5.0) < 0.02 and abs(wall.end[0] - 5.0) < 0.02
        and min(wall.start[1], wall.end[1]) <= 1.01 and max(wall.start[1], wall.end[1]) >= 4.99
    ]
    assert len(shared) == 2, "Each adjacent room must retain its independent shared-boundary wall"
    assert shared[1].id in shared[0].linked_wall_ids
    assert shared[0].id in shared[1].linked_wall_ids

    adjacent = add_opening_at_position(
        adjacent,
        opening_type="door",
        position=(5.08, 3.0),
        snap_to_wall=True,
        width=0.9,
    )
    door = adjacent.openings[0]
    assert door.wall_id is None
    assert set(door.wall_ids) == {shared[0].id, shared[1].id}
    assert abs(door.position[0] - 5.0) < 0.01
    assert door.interactive is True

    adjacent = update_room_geometry(
        adjacent,
        "room-2",
        [(5.08, 1.0), (9.0, 1.0), (9.0, 5.0), (5.08, 5.0)],
    )
    assert len(adjacent.openings) == 1
    assert len(adjacent.openings[0].wall_ids) == 2, "Manual shared portal must reattach to both rebuilt walls"

    print(f"Free-form smoke test passed: {len(scene.rooms)} rooms, independent shared walls and one portal")


if __name__ == "__main__":
    main()
