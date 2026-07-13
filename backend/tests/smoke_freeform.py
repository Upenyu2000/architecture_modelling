from __future__ import annotations

from app.models import ProjectMetadata, RoomShape, SceneManifest
from app.services.layout import rebuild_scene_from_rooms, update_room_geometry


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

    print(f"Free-form smoke test passed: {len(scene.rooms)} rooms, {len(scene.walls)} wall segments")


if __name__ == "__main__":
    main()
