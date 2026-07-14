from __future__ import annotations

from app.models import OpeningCreateRequest, ProjectMetadata, RoomCreateRequest, SceneManifest
from app.services.layout import add_room
from app.services.openings import add_opening


def scene_with_adjacent_rooms() -> SceneManifest:
    scene = SceneManifest(
        project_id="shared-portal-smoke",
        width_m=12.0,
        depth_m=8.0,
        wall_height_m=2.8,
        walls=[],
        rooms=[],
        assets=[],
        camera_path=[],
        project_metadata=ProjectMetadata(),
        layout_mode="manual",
    )
    scene = add_room(scene, RoomCreateRequest(name="Room 1", x=0.0, z=0.0, width=4.0, depth=4.0))
    scene = add_room(scene, RoomCreateRequest(name="Room 2", x=4.0, z=0.0, width=4.0, depth=4.0))
    return scene


def main() -> None:
    scene = scene_with_adjacent_rooms()

    # Four room edges per room remain as independent wall records.
    assert len(scene.walls) == 8, f"Expected 8 independent room walls, got {len(scene.walls)}"
    shared = [wall for wall in scene.walls if wall.linked_wall_ids]
    assert len(shared) == 2, f"Expected one linked wall pair, got {len(shared)} walls"
    first, second = shared
    assert second.id in first.linked_wall_ids
    assert first.id in second.linked_wall_ids
    assert first.owner_room_id != second.owner_room_id
    assert first.shared_group_id == second.shared_group_id

    scene = add_opening(scene, OpeningCreateRequest(
        opening_type="door",
        wall_id=first.id,
        placement_ratio=0.5,
        width=0.9,
        height=2.1,
        interactive=True,
    ))
    assert len(scene.openings) == 1
    portal = scene.openings[0]
    assert portal.wall_id is None, "Shared portals use wall_ids so both walls receive the cut"
    assert set(portal.wall_ids) == {first.id, second.id}
    assert set(portal.room_ids) == {first.owner_room_id, second.owner_room_id}
    assert portal.portal_id

    # Simulate a second raycast hitting the opposite room wall at the same location.
    scene = add_opening(scene, OpeningCreateRequest(
        opening_type="door",
        wall_id=second.id,
        placement_ratio=0.5,
        width=0.9,
        height=2.1,
        interactive=True,
    ))
    assert len(scene.openings) == 1, "Opposite-wall placement must reuse the canonical portal"
    assert scene.openings[0].id == portal.id
    assert set(scene.openings[0].wall_ids) == {first.id, second.id}

    print("Shared portal smoke test passed: independent walls, one door, both wall cuts")


if __name__ == "__main__":
    main()
