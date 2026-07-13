from __future__ import annotations

from app.interior_api import DEFAULT_SIZES, _decode, _encode, _room_at
from app.models import ArchitecturalObject, ProjectMetadata, RoomShape, SceneManifest
from app.services.furniture_detection import merge_furniture_objects


def scene_with_rooms() -> SceneManifest:
    return SceneManifest(
        project_id="smoke-interiors",
        width_m=10.0,
        depth_m=7.0,
        wall_height_m=2.8,
        walls=[],
        rooms=[
            RoomShape(
                id="living",
                name="Living Room",
                room_type="living_room",
                polygon=[(0.0, 0.0), (5.0, 0.0), (5.0, 7.0), (0.0, 7.0)],
                area_m2=35.0,
                centroid=(2.5, 3.5),
            ),
            RoomShape(
                id="bedroom",
                name="Bedroom",
                room_type="bedroom",
                polygon=[(5.0, 0.0), (10.0, 0.0), (10.0, 7.0), (5.0, 7.0)],
                area_m2=35.0,
                centroid=(7.5, 3.5),
            ),
        ],
        assets=[],
        camera_path=[],
        project_metadata=ProjectMetadata(),
    )


def object_at(identifier: str, source: str, x: float, z: float, confidence: float) -> ArchitecturalObject:
    return ArchitecturalObject(
        id=identifier,
        object_type="sofa",
        asset_id=_encode("sofa", "modern", "fabric", "#486B5A", None),
        category="furniture",
        room_id="living",
        coordinates=(x, 0.46, z),
        rotation_deg=0,
        scale=(1.0, 1.0, 1.0),
        size=DEFAULT_SIZES["sofa"],
        source=source,  # type: ignore[arg-type]
        confidence=confidence,
    )


def main() -> None:
    scene = scene_with_rooms()
    assert _room_at(scene, 2.0, 3.0) == "living"
    assert _room_at(scene, 8.0, 3.0) == "bedroom"

    encoded = _encode("sofa", "scandinavian", "leather", "#335577", "living_room/couch")
    decoded = _decode(encoded, "sofa")
    assert decoded == ("sofa", "scandinavian", "leather", "#335577", "living_room/couch")
    assert "sectional_sofa" in DEFAULT_SIZES and "office_chair" in DEFAULT_SIZES

    user = object_at("user-sofa", "user", 2.0, 3.0, 1.0)
    detected = object_at("detected-sofa", "symbol_heuristic", 2.1, 3.0, 0.8)
    inferred = object_at("inferred-sofa", "room_inference", 2.05, 3.05, 0.45)
    merged = merge_furniture_objects([user], [detected], [inferred])
    assert len(merged) == 1
    assert merged[0].id == "user-sofa", "User replacements must survive detection and recompilation"
    assert merged[0].asset_id.endswith("#486B5A|")

    print("Interior design smoke test passed: PBR styles, room assignment and user replacement priority")


if __name__ == "__main__":
    main()
