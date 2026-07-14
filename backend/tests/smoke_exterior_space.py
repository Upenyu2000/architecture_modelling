from __future__ import annotations

from app.models import ProjectMetadata, RoomCreateRequest, RoomShape, SceneManifest, WallSegment
from app.services.strict_geometry import add_room_guarded, filter_exterior_rooms, update_room_geometry_guarded


def sample_scene() -> SceneManifest:
    return SceneManifest(
        project_id="smoke-exterior-space",
        width_m=10.0,
        depth_m=8.0,
        wall_height_m=2.8,
        walls=[
            WallSegment(id="top", start=(2.0, 1.0), end=(8.0, 1.0), height=2.8, thickness=0.18),
            WallSegment(id="right", start=(8.0, 1.0), end=(8.0, 7.0), height=2.8, thickness=0.18),
            WallSegment(id="bottom", start=(8.0, 7.0), end=(2.0, 7.0), height=2.8, thickness=0.18),
            WallSegment(id="left", start=(2.0, 7.0), end=(2.0, 1.0), height=2.8, thickness=0.18),
        ],
        rooms=[
            RoomShape(
                id="inside",
                name="Inside",
                polygon=[(2.2, 1.2), (7.8, 1.2), (7.8, 6.8), (2.2, 6.8)],
                area_m2=31.36,
                centroid=(5.0, 4.0),
            ),
            RoomShape(
                id="outside",
                name="False exterior room",
                polygon=[(0.2, 0.2), (1.5, 0.2), (1.5, 0.9), (0.2, 0.9)],
                area_m2=0.91,
                centroid=(0.85, 0.55),
            ),
        ],
        assets=[],
        camera_path=[],
        layout_mode="automatic",
        project_metadata=ProjectMetadata(detected_rooms=2),
    )


def main() -> None:
    filtered = filter_exterior_rooms(sample_scene(), width_px=1000, height_px=800)
    assert [room.id for room in filtered.rooms] == ["inside"]
    assert filtered.project_metadata.detected_rooms == 1
    assert any("exterior white space" in warning.lower() for warning in filtered.warnings)

    try:
        update_room_geometry_guarded(
            filtered,
            "inside",
            [(0.2, 0.2), (3.0, 0.2), (3.0, 2.5), (0.2, 2.5)],
        )
    except ValueError as exc:
        assert "exterior white space" in str(exc).lower()
    else:
        raise AssertionError("Automatic room edits must not move into exterior white space")

    try:
        add_room_guarded(filtered, RoomCreateRequest(name="Outside", x=0.1, z=0.1, width=1.0, depth=1.0))
    except ValueError as exc:
        assert "exterior white space" in str(exc).lower()
    else:
        raise AssertionError("Automatic room creation must not register exterior white space")

    print("Exterior-space smoke test passed: border-connected white space is empty and guarded")


if __name__ == "__main__":
    main()
