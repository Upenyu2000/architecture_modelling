from __future__ import annotations

from app.models import ArchitecturalObject, Opening, ProjectMetadata, RoomShape, SceneManifest, WallSegment
from app.services.presentation import STYLE_PRESETS, prepare_presentation_scene


def main() -> None:
    room = RoomShape(
        id="dining-room",
        name="Dining Room",
        room_type="dining",
        polygon=[(0.0, 0.0), (5.0, 0.0), (5.0, 4.0), (0.0, 4.0)],
        area_m2=20.0,
        centroid=(2.5, 2.0),
        width_m=5.0,
        depth_m=4.0,
    )
    walls = [
        WallSegment(id="w1", start=(0.0, 0.0), end=(5.0, 0.0), height=2.8, wall_type="exterior"),
        WallSegment(id="w2", start=(5.0, 0.0), end=(5.0, 4.0), height=2.8, wall_type="exterior"),
        WallSegment(id="w3", start=(5.0, 4.0), end=(0.0, 4.0), height=2.8, wall_type="exterior"),
        WallSegment(id="w4", start=(0.0, 4.0), end=(0.0, 0.0), height=2.8, wall_type="exterior"),
    ]
    table = ArchitecturalObject(
        id="table",
        object_type="dining_table",
        asset_id="dining_table|modern|oak|#765432|",
        category="furniture",
        room_id=room.id,
        coordinates=(0.8, 0.0, 0.7),
        size=(3.7, 0.78, 1.8),
    )
    chair = ArchitecturalObject(
        id="chair",
        object_type="dining_chair",
        asset_id="dining_chair|modern|fabric|#777777|",
        category="furniture",
        room_id=room.id,
        coordinates=(0.5, 0.0, 0.5),
        size=(0.7, 1.0, 0.7),
    )
    door = Opening(
        id="door",
        opening_type="door",
        position=(2.5, 0.0),
        width=0.9,
        wall_id="w1",
        wall_ids=["w1"],
        room_ids=[room.id],
    )
    scene = SceneManifest(
        project_id="presentation-smoke",
        width_m=5.0,
        depth_m=4.0,
        wall_height_m=2.8,
        ceiling_height_m=2.8,
        walls=walls,
        rooms=[room],
        assets=[],
        camera_path=[],
        openings=[door],
        fixtures_and_furniture=[table, chair],
        project_metadata=ProjectMetadata(
            detected_rooms=1,
            detected_openings=1,
            detected_objects=2,
            ocr_status="completed",
            extracted_labels=["DINING ROOM", "5.0 x 4.0"],
        ),
    )

    payload, metadata = prepare_presentation_scene(scene, "scandinavian", auto_furnish=True, optimise_dining=True)

    assert len(STYLE_PRESETS) == 19, "Every requested architectural style must be available."
    assert payload["materials"]["palette_name"] == "Scandinavian"
    assert payload["project_metadata"]["extracted_labels"] == []
    assert payload["render_profile"]["text_policy"] == "geometry_only_no_source_text"
    assert metadata["text_removed"] is True
    assert metadata["dining_adjusted"] is True
    assert metadata["perspective_room_id"] == room.id

    rendered_table = next(item for item in payload["fixtures_and_furniture"] if item["object_type"] == "dining_table")
    assert 1.4 <= rendered_table["coordinates"][0] <= 3.6
    assert 1.2 <= rendered_table["coordinates"][2] <= 2.8
    assert rendered_table["size"][0] <= 3.2
    assert rendered_table["size"][2] <= 2.2
    assert "|scandinavian|" in rendered_table["asset_id"]
    assert not any(item["object_type"] == "dining_chair" for item in payload["fixtures_and_furniture"]), "Dining chairs are generated around the optimised table and must not be duplicated."

    print("Presentation smoke test passed: 19 styles, text-free geometry, practical dining flow and an interior camera.")


if __name__ == "__main__":
    main()
