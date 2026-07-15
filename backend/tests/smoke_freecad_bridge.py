from __future__ import annotations

import os
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory(prefix="freecad-smoke-") as temporary:
    os.environ["DREAMHOME_DATA_DIR"] = temporary

    from app.models import ArchitecturalObject, Opening, Project, RoomShape, SceneManifest, WallSegment
    from app.storage import save_project
    from app.services.freecad_bridge import (
        EXPORT_EXTENSIONS,
        SUPPORTED_IMPORT_SUFFIXES,
        freecad_status,
        history_summary,
        model_tree,
        quantity_schedule,
        record_history,
        redo_history,
        scene_parameters,
        undo_history,
    )

    room = RoomShape(
        id="living",
        name="Living Room",
        room_type="living",
        polygon=[(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0)],
        area_m2=24.0,
        centroid=(3.0, 2.0),
        width_m=6.0,
        depth_m=4.0,
    )
    walls = [
        WallSegment(id="w1", start=(0.0, 0.0), end=(6.0, 0.0), height=2.8, thickness=0.2, wall_type="exterior"),
        WallSegment(id="w2", start=(6.0, 0.0), end=(6.0, 4.0), height=2.8, thickness=0.2, wall_type="exterior"),
        WallSegment(id="w3", start=(6.0, 4.0), end=(0.0, 4.0), height=2.8, thickness=0.2, wall_type="exterior"),
        WallSegment(id="w4", start=(0.0, 4.0), end=(0.0, 0.0), height=2.8, thickness=0.2, wall_type="exterior"),
    ]
    door = Opening(
        id="door",
        opening_type="door",
        position=(3.0, 0.0),
        width=0.9,
        height=2.1,
        wall_id="w1",
        wall_ids=["w1"],
        room_ids=[room.id],
    )
    sofa = ArchitecturalObject(
        id="sofa",
        object_type="sofa",
        asset_id="sofa|modern|fabric|#777777|",
        category="furniture",
        room_id=room.id,
        coordinates=(3.0, 0.0, 2.0),
        size=(2.4, 0.9, 1.0),
    )
    scene = SceneManifest(
        project_id="freecad-smoke",
        width_m=6.0,
        depth_m=4.0,
        wall_height_m=2.8,
        ceiling_height_m=2.8,
        walls=walls,
        rooms=[room],
        openings=[door],
        fixtures_and_furniture=[sofa],
        assets=[],
        camera_path=[],
    )
    project = Project(id="freecad-smoke", name="FreeCAD Smoke", scene=scene)
    save_project(project)

    quantities = quantity_schedule(scene)
    assert quantities["summary"]["floor_area_m2"] == 24.0
    assert quantities["summary"]["exterior_wall_length_m"] == 20.0
    assert quantities["summary"]["doors"] == 1
    assert quantities["furniture"]["sofa"] == 1

    tree = model_tree(scene)
    assert tree["type"] == "App::Part"
    assert [node["id"] for node in tree["children"]] == ["rooms", "walls", "openings", "interior"]
    assert tree["children"][1]["children"][0]["type"] == "Part::Feature"

    parameters = scene_parameters(scene)
    assert parameters["default_wall_thickness_m"] == 0.2
    assert parameters["wall_height_m"] == 2.8

    record_history(project, "Initial model")
    project.scene.wall_height_m = 3.1
    for wall in project.scene.walls:
        wall.height = 3.1
    save_project(project)
    record_history(project, "Raised walls")
    summary = history_summary(project.id)
    assert summary["can_undo"] is True
    restored = undo_history(project.id)
    assert restored.scene and restored.scene.wall_height_m == 2.8
    restored = redo_history(project.id)
    assert restored.scene and restored.scene.wall_height_m == 3.1

    assert {"fcstd", "step", "iges", "brep", "stl", "obj"}.issubset(EXPORT_EXTENSIONS)
    assert {".fcstd", ".step", ".ifc", ".dxf", ".svg"}.issubset(SUPPORTED_IMPORT_SUFFIXES)
    status = freecad_status()
    assert "installed" in status and "export_formats" in status

    worker = Path(__file__).parents[1] / "app" / "freecad" / "bridge_worker.py"
    assert worker.exists(), "The packaged FreeCAD bridge worker must be present."
    source = worker.read_text(encoding="utf-8")
    assert "Part.makeBox" in source and "Part.Face" in source
    assert "Quantity Schedule / Bill of Materials" in source
    assert "importIFC" in source and "importDXF" in source and "importSVG" in source

    print("FreeCAD bridge smoke test passed: parametric properties, BRep model tree, quantity schedule, history and file exchange.")
