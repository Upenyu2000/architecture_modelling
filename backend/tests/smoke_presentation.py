from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from app.models import ArchitecturalObject, Opening, ProjectMetadata, RoomShape, SceneManifest, WallSegment
from app.presentation_api import _remove_failed_outputs, _request_dedupe_key, _scene_fingerprint, PresentationRenderRequest
from app.services.jobs import JOBS, LOCK, create_unique_job, update_job
from app.services.presentation import STYLE_PRESETS, prepare_presentation_scene
from app.services.rendering_v20 import PNG_SIGNATURE, _validate_png


def _expect_runtime_error(callback, message: str) -> None:
    try:
        callback()
    except RuntimeError:
        return
    raise AssertionError(message)


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

    assert len(STYLE_PRESETS) == 19, "Every requested architectural style must be available."
    for style_name, preset in STYLE_PRESETS.items():
        styled_payload, styled_metadata = prepare_presentation_scene(
            scene,
            style_name,
            auto_furnish=True,
            optimise_dining=True,
        )
        assert styled_payload["materials"]["palette_name"] == preset["label"]
        assert styled_payload["project_metadata"]["extracted_labels"] == []
        assert styled_payload["render_profile"]["text_policy"] == "geometry_only_no_source_text"
        assert styled_metadata["text_removed"] is True
        assert styled_metadata["perspective_room_id"] == room.id

    payload, metadata = prepare_presentation_scene(scene, "scandinavian", auto_furnish=True, optimise_dining=True)
    assert metadata["dining_adjusted"] is True

    rendered_table = next(item for item in payload["fixtures_and_furniture"] if item["object_type"] == "dining_table")
    assert 1.4 <= rendered_table["coordinates"][0] <= 3.6
    assert 1.2 <= rendered_table["coordinates"][2] <= 2.8
    assert rendered_table["size"][0] <= 3.2
    assert rendered_table["size"][2] <= 2.2
    assert "|scandinavian|" in rendered_table["asset_id"]
    assert not any(item["object_type"] == "dining_chair" for item in payload["fixtures_and_furniture"]), "Dining chairs are generated around the optimised table and must not be duplicated."

    fingerprint = _scene_fingerprint(scene)
    changed_scene = scene.model_copy(deep=True)
    changed_scene.rooms[0].name = "Changed Dining Room"
    assert _scene_fingerprint(changed_scene) != fingerprint, "A changed plan must invalidate its persisted render."

    request = PresentationRenderRequest(style="modern", quality="1080p", engine="auto")
    dedupe_key = _request_dedupe_key(fingerprint, request)
    assert dedupe_key == _request_dedupe_key(fingerprint, request)
    assert dedupe_key != _request_dedupe_key(fingerprint, PresentationRenderRequest(style="coastal"))

    with LOCK:
        JOBS.clear()
    first, first_created = create_unique_job("presentation-smoke", "architectural_presentation", dedupe_key)
    duplicate, duplicate_created = create_unique_job("presentation-smoke", "architectural_presentation", dedupe_key)
    assert first_created is True
    assert duplicate_created is False
    assert duplicate.id == first.id
    changed, changed_created = create_unique_job("presentation-smoke", "architectural_presentation", "changed-revision")
    assert changed_created is True
    assert changed.id != first.id
    update_job(first.id, 100, "Complete", status="completed")
    replacement, replacement_created = create_unique_job("presentation-smoke", "architectural_presentation", dedupe_key)
    assert replacement_created is True
    assert replacement.id != first.id
    with LOCK:
        JOBS.clear()

    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        valid_png = root / "valid.png"
        valid_png.write_bytes(PNG_SIGNATURE + b"0" * 128)
        _validate_png(valid_png, "top_down")

        invalid_png = root / "invalid.png"
        invalid_png.write_bytes(b"not-a-png" * 20)
        _expect_runtime_error(
            lambda: _validate_png(invalid_png, "perspective"),
            "Invalid Blender output must be rejected.",
        )

        output_dir = root / "presentation-partial"
        output_dir.mkdir()
        (output_dir / "partial.png").write_bytes(b"partial")
        archive = root / "presentation-partial.zip"
        temporary_archive = root / ".presentation-partial.zip.tmp"
        archive.write_bytes(b"partial")
        temporary_archive.write_bytes(b"partial")
        _remove_failed_outputs(output_dir, archive, temporary_archive)
        assert not output_dir.exists()
        assert not archive.exists()
        assert not temporary_archive.exists()

    print("Presentation smoke test passed: 19 styles, scene revision invalidation, duplicate-job suppression, text-free geometry, practical dining flow, PNG validation and failed-output cleanup.")


if __name__ == "__main__":
    main()
