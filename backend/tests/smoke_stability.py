from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

from app.models import Opening, RoomShape, SceneManifest, WallSegment
from app.services.floor_mask import write_boundary_floor_masks, write_scene_floor_mask
from app.services.plan_boundary import detect_plan_boundary


def _room(room_id: str, name: str, polygon: list[tuple[float, float]]) -> RoomShape:
    xs = [point[0] for point in polygon]
    zs = [point[1] for point in polygon]
    return RoomShape(
        id=room_id,
        name=name,
        polygon=polygon,
        area_m2=(max(xs) - min(xs)) * (max(zs) - min(zs)),
        centroid=((min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2),
    )


def _scene() -> SceneManifest:
    first = _room("room-a", "Room A", [(1, 1), (4.92, 1), (4.92, 6), (1, 6)])
    second = _room("room-b", "Room B", [(5.08, 1), (9, 1), (9, 6), (5.08, 6)])
    shared_a = WallSegment(
        id="wall-a",
        start=(4.92, 1),
        end=(4.92, 6),
        height=2.8,
        owner_room_id="room-a",
        linked_wall_ids=["wall-b"],
    )
    shared_b = WallSegment(
        id="wall-b",
        start=(5.08, 1),
        end=(5.08, 6),
        height=2.8,
        owner_room_id="room-b",
        linked_wall_ids=["wall-a"],
    )
    door = Opening(
        id="door-shared",
        opening_type="door",
        position=(5.0, 3.5),
        width=1.0,
        height=2.1,
        rotation_deg=90,
        wall_id="wall-a",
        wall_ids=["wall-a", "wall-b"],
        room_ids=["room-a", "room-b"],
        portal_id="portal-shared",
        source="manual",
    )
    return SceneManifest(
        project_id="stability-test",
        width_m=10,
        depth_m=8,
        wall_height_m=2.8,
        walls=[shared_a, shared_b],
        rooms=[first, second],
        assets=[],
        camera_path=[(2, 1.7, 3), (7, 1.7, 3)],
        openings=[door],
        collision_segments=[(shared_a.start, shared_a.end), (shared_b.start, shared_b.end)],
        first_person_start=(2, 1.7, 3),
        layout_mode="manual",
    )


def run() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        mask_path = write_scene_floor_mask(_scene(), root / "scene-mask.png", width_px=1000)
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        assert mask is not None, "Scene floor mask was not written"
        assert int(mask[300, 250]) > 0, "First room is missing from the floor mask"
        assert int(mask[300, 700]) > 0, "Second room is missing from the floor mask"
        assert int(mask[350, 500]) > 0, "Shared doorway threshold was not bridged"
        assert int(mask[40, 40]) == 0, "Exterior white space became walkable floor"

        image = np.full((600, 800, 3), 255, dtype=np.uint8)
        cv2.rectangle(image, (100, 100), (700, 500), (0, 0, 0), 14)
        cv2.line(image, (400, 100), (400, 500), (0, 0, 0), 8)
        boundary = detect_plan_boundary(image)
        building_path, interior_path = write_boundary_floor_masks(boundary, root)
        assert building_path.exists() and interior_path.exists(), "Boundary floor masks were not persisted"
        assert int(boundary.building_mask[300, 250]) == 1, "Enclosed interior was not classified as building"
        assert int(boundary.building_mask[20, 20]) == 0, "Border-connected white space became building"
        assert boundary.confidence > 0.45, "Synthetic closed plan boundary confidence is unexpectedly low"

    print("Stability smoke test passed: continuous floor, doorway bridging and exterior white-space exclusion")


if __name__ == "__main__":
    run()
