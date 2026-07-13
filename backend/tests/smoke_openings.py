from __future__ import annotations

from app.models import (
    OpeningCreateRequest,
    OpeningUpdateRequest,
    ProjectMetadata,
    SceneManifest,
    WallSegment,
)
from app.services.openings import add_opening, delete_opening, update_opening


def sample_scene() -> SceneManifest:
    return SceneManifest(
        project_id="smoke-openings",
        width_m=12.0,
        depth_m=8.0,
        wall_height_m=2.8,
        walls=[
            WallSegment(
                id="wall-main",
                start=(0.0, 0.0),
                end=(10.0, 0.0),
                height=2.8,
                thickness=0.18,
                wall_type="exterior",
            )
        ],
        rooms=[],
        assets=[],
        camera_path=[],
        project_metadata=ProjectMetadata(),
    )


def main() -> None:
    scene = sample_scene()
    scene = add_opening(scene, OpeningCreateRequest(
        opening_type="door",
        wall_id="wall-main",
        placement_ratio=0.2,
        width=0.9,
        height=2.1,
        swing_direction="clockwise",
        hinge_side="left",
        interactive=True,
    ))
    door = scene.openings[0]
    assert door.wall_id == "wall-main"
    assert door.position == (2.0, 0.0)
    assert door.rotation_deg == 0.0
    assert door.interactive is True
    assert door.source == "manual"

    scene = add_opening(scene, OpeningCreateRequest(
        opening_type="bay_window",
        wall_id="wall-main",
        placement_ratio=0.72,
        width=2.0,
        height=1.35,
        sill_height=0.85,
    ))
    window = scene.openings[1]
    assert window.opening_type == "bay_window"
    assert window.interactive is False
    assert window.sill_height == 0.85
    assert scene.project_metadata.detected_openings == 2

    try:
        add_opening(scene, OpeningCreateRequest(
            opening_type="double_door",
            wall_id="wall-main",
            placement_ratio=0.2,
            width=1.8,
        ))
    except ValueError:
        pass
    else:
        raise AssertionError("Overlapping openings must be rejected")

    scene = update_opening(scene, door.id, OpeningUpdateRequest(
        opening_type="double_door",
        placement_ratio=0.35,
        width=1.8,
        hinge_side="centre",
        swing_angle_deg=100.0,
        default_open=True,
    ))
    updated = next(item for item in scene.openings if item.id == door.id)
    assert updated.opening_type == "double_door"
    assert updated.position == (3.5, 0.0)
    assert updated.default_open is True
    assert updated.swing_angle_deg == 100.0

    scene = delete_opening(scene, window.id)
    assert len(scene.openings) == 1
    assert scene.project_metadata.detected_openings == 1
    assert scene.collision_segments == [((0.0, 0.0), (10.0, 0.0))]

    print("Interactive opening smoke test passed: add, classify, update, overlap and delete")


if __name__ == "__main__":
    main()
