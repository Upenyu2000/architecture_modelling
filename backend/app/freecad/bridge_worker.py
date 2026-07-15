from __future__ import annotations

import argparse
import importlib
import json
import math
import re
import sys
import traceback
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True)
    parser.add_argument("--result", required=True)
    args, _unknown = parser.parse_known_args(sys.argv[1:])
    return args


def safe_name(value: str, fallback: str = "Object") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_")
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = f"Object_{cleaned}"
    return cleaned[:80]


def optional_module(name: str):
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def probe() -> dict[str, Any]:
    import FreeCAD as App

    module_names = ["Part", "Mesh", "Import", "Draft", "Arch", "importIFC", "importDXF", "importSVG", "Spreadsheet"]
    modules = {name: optional_module(name) is not None for name in module_names}
    version_parts = App.Version()
    return {
        "ok": True,
        "version": ".".join(str(part) for part in version_parts[:3]),
        "modules": modules,
    }


def add_property(obj, property_type: str, name: str, value: Any, group: str = "Dream Home") -> None:
    try:
        obj.addProperty(property_type, name, group)
    except Exception:
        pass
    try:
        setattr(obj, name, value)
    except Exception:
        try:
            setattr(obj, name, str(value))
        except Exception:
            pass


def add_shape_feature(doc, group, name: str, label: str, shape, properties: dict[str, tuple[str, Any]]):
    obj = doc.addObject("Part::Feature", safe_name(name))
    obj.Label = label
    obj.Shape = shape
    group.addObject(obj)
    for prop_name, (prop_type, value) in properties.items():
        add_property(obj, prop_type, prop_name, value)
    return obj


def room_shape(Part, App, room: dict[str, Any], slab_mm: float = 80.0):
    polygon = list(room.get("polygon") or [])
    if len(polygon) < 3:
        return None
    points = [App.Vector(float(x) * 1000.0, float(z) * 1000.0, 0.0) for x, z in polygon]
    if points[0].distanceToPoint(points[-1]) > 0.001:
        points.append(points[0])
    wire = Part.makePolygon(points)
    face = Part.Face(wire)
    return face.extrude(App.Vector(0.0, 0.0, slab_mm))


def opening_links_to_wall(opening: dict[str, Any], wall_id: str) -> bool:
    linked = list(opening.get("wall_ids") or [])
    primary = opening.get("wall_id")
    if primary:
        linked.append(primary)
    return wall_id in set(str(item) for item in linked if item)


def physical_wall_key(wall: dict[str, Any]) -> str:
    shared_group = str(wall.get("shared_group_id") or "").strip()
    if shared_group:
        return f"shared:{shared_group}"
    linked = sorted({str(wall.get("id") or ""), *(str(value) for value in wall.get("linked_wall_ids") or [] if value)})
    return "linked:" + "|".join(linked) if len(linked) > 1 else f"wall:{wall.get('id', '')}"


def physical_walls(walls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for wall in walls:
        key = physical_wall_key(wall)
        x1, z1 = (float(value) for value in wall.get("start", (0.0, 0.0)))
        x2, z2 = (float(value) for value in wall.get("end", (0.0, 0.0)))
        length = math.hypot(x2 - x1, z2 - z1)
        current = selected.get(key)
        if current is None:
            selected[key] = wall
            continue
        cx1, cz1 = (float(value) for value in current.get("start", (0.0, 0.0)))
        cx2, cz2 = (float(value) for value in current.get("end", (0.0, 0.0)))
        if length > math.hypot(cx2 - cx1, cz2 - cz1):
            selected[key] = wall
    return list(selected.values())


def wall_shape(Part, App, wall: dict[str, Any], openings: list[dict[str, Any]]):
    x1, z1 = (float(value) for value in wall.get("start", (0.0, 0.0)))
    x2, z2 = (float(value) for value in wall.get("end", (0.0, 0.0)))
    dx, dz = x2 - x1, z2 - z1
    length_m = math.hypot(dx, dz)
    if length_m < 0.001:
        return None
    thickness_m = max(0.02, float(wall.get("thickness", 0.16)))
    height_m = max(0.1, float(wall.get("height", 2.8)))
    length_mm = length_m * 1000.0
    thickness_mm = thickness_m * 1000.0
    height_mm = height_m * 1000.0
    angle_deg = math.degrees(math.atan2(dz, dx))

    shape = Part.makeBox(length_mm, thickness_mm, height_mm, App.Vector(0.0, -thickness_mm / 2.0, 0.0))
    rotation = App.Rotation(App.Vector(0.0, 0.0, 1.0), angle_deg)
    placement = App.Placement(App.Vector(x1 * 1000.0, z1 * 1000.0, 0.0), rotation)
    shape.Placement = placement

    ux, uz = dx / length_m, dz / length_m
    wall_id = str(wall.get("id") or "")
    for opening in openings:
        if not opening_links_to_wall(opening, wall_id):
            continue
        ox, oz = (float(value) for value in opening.get("position", (x1, z1)))
        centre_m = max(0.0, min(length_m, (ox - x1) * ux + (oz - z1) * uz))
        width_m = min(length_m, max(0.15, float(opening.get("width", 0.9))))
        opening_type = str(opening.get("opening_type", "door"))
        is_window = "window" in opening_type
        sill_m = max(0.0, float(opening.get("sill_height", 0.9))) if is_window else 0.0
        opening_height_m = min(height_m - sill_m, max(0.15, float(opening.get("height", 2.1))))
        if opening_height_m <= 0.01:
            continue
        cutter = Part.makeBox(
            width_m * 1000.0,
            thickness_mm * 3.0,
            opening_height_m * 1000.0,
            App.Vector((centre_m - width_m / 2.0) * 1000.0, -thickness_mm * 1.5, sill_m * 1000.0),
        )
        cutter.Placement = placement
        try:
            shape = shape.cut(cutter)
        except Exception:
            pass
    return shape


def furniture_shape(Part, App, item: dict[str, Any]):
    coordinates = item.get("coordinates") or item.get("position") or (0.0, 0.0, 0.0)
    x, _y, z = (float(value) for value in coordinates)
    sx, sy, sz = (max(0.02, float(value)) for value in (item.get("size") or (1.0, 1.0, 1.0)))
    shape = Part.makeBox(sx * 1000.0, sz * 1000.0, sy * 1000.0, App.Vector(-sx * 500.0, -sz * 500.0, 0.0))
    rotation = App.Rotation(App.Vector(0.0, 0.0, 1.0), float(item.get("rotation_deg", 0.0)))
    shape.Placement = App.Placement(App.Vector(x * 1000.0, z * 1000.0, 0.0), rotation)
    return shape


def create_quantity_sheet(doc, quantities: dict[str, Any]):
    try:
        sheet = doc.addObject("Spreadsheet::Sheet", "QuantitySchedule")
    except Exception:
        return None
    sheet.Label = "Quantity Schedule / Bill of Materials"
    rows = [("Metric", "Value")]
    summary = dict(quantities.get("summary") or {})
    for key, value in summary.items():
        rows.append((key.replace("_", " ").title(), value))
    row = 1
    for label, value in rows:
        sheet.set(f"A{row}", str(label))
        sheet.set(f"B{row}", str(value))
        row += 1
    try:
        sheet.setStyle("A1:B1", "bold", "add")
        sheet.setColumnWidth("A", 34)
        sheet.setColumnWidth("B", 18)
    except Exception:
        pass
    return sheet


def build_document(payload: dict[str, Any]):
    import FreeCAD as App
    import Part

    scene = dict(payload.get("scene") or {})
    project_name = str(payload.get("project_name") or "Dream Home")
    doc = App.newDocument(safe_name(project_name, "DreamHome"))
    root = doc.addObject("App::Part", "Building")
    root.Label = project_name
    rooms_group = doc.addObject("App::DocumentObjectGroup", "Rooms")
    walls_group = doc.addObject("App::DocumentObjectGroup", "Walls")
    openings_group = doc.addObject("App::DocumentObjectGroup", "Openings")
    interiors_group = doc.addObject("App::DocumentObjectGroup", "FurnitureAndFixtures")
    root.addObject(rooms_group)
    root.addObject(walls_group)
    root.addObject(openings_group)
    root.addObject(interiors_group)

    add_property(root, "App::PropertyLength", "BuildingWidth", f"{float(scene.get('width_m', 0.0))} m")
    add_property(root, "App::PropertyLength", "BuildingDepth", f"{float(scene.get('depth_m', 0.0))} m")
    add_property(root, "App::PropertyLength", "WallHeight", f"{float(scene.get('wall_height_m', 2.8))} m")
    add_property(root, "App::PropertyString", "SourceProjectId", str(scene.get("project_id") or ""))
    add_property(root, "App::PropertyString", "UnitSystem", str(payload.get("unit_system") or "metric"))

    objects = []
    for room in scene.get("rooms", []):
        shape = room_shape(Part, App, room)
        if shape is None:
            continue
        obj = add_shape_feature(
            doc,
            rooms_group,
            f"Room_{room.get('id', '')}",
            str(room.get("name") or "Room"),
            shape,
            {
                "ExternalId": ("App::PropertyString", str(room.get("id") or "")),
                "RoomType": ("App::PropertyString", str(room.get("room_type") or "room")),
                "Area": ("App::PropertyArea", f"{float(room.get('area_m2', 0.0))} m^2"),
                "Polygon": ("App::PropertyString", json.dumps(room.get("polygon") or [])),
            },
        )
        objects.append(obj)

    openings = list(scene.get("openings") or [])
    for wall in physical_walls(list(scene.get("walls") or [])):
        shape = wall_shape(Part, App, wall, openings)
        if shape is None:
            continue
        x1, z1 = wall.get("start", (0.0, 0.0))
        x2, z2 = wall.get("end", (0.0, 0.0))
        obj = add_shape_feature(
            doc,
            walls_group,
            f"Wall_{wall.get('id', '')}",
            str(wall.get("id") or "Wall"),
            shape,
            {
                "ExternalId": ("App::PropertyString", str(wall.get("id") or "")),
                "WallType": ("App::PropertyString", str(wall.get("wall_type") or "interior")),
                "Length": ("App::PropertyLength", f"{math.hypot(float(x2) - float(x1), float(z2) - float(z1))} m"),
                "Height": ("App::PropertyLength", f"{float(wall.get('height', 2.8))} m"),
                "Thickness": ("App::PropertyLength", f"{float(wall.get('thickness', 0.16))} m"),
                "SharedGroup": ("App::PropertyString", str(wall.get("shared_group_id") or "")),
            },
        )
        objects.append(obj)

    for opening in openings:
        obj = doc.addObject("App::FeaturePython", safe_name(f"Opening_{opening.get('id', '')}"))
        obj.Label = str(opening.get("opening_type") or "Opening").replace("_", " ").title()
        openings_group.addObject(obj)
        add_property(obj, "App::PropertyString", "ExternalId", str(opening.get("id") or ""))
        add_property(obj, "App::PropertyString", "OpeningType", str(opening.get("opening_type") or "door"))
        add_property(obj, "App::PropertyLength", "Width", f"{float(opening.get('width', 0.9))} m")
        add_property(obj, "App::PropertyLength", "Height", f"{float(opening.get('height', 2.1))} m")
        add_property(obj, "App::PropertyLength", "SillHeight", f"{float(opening.get('sill_height', 0.0))} m")
        add_property(obj, "App::PropertyStringList", "WallIds", [str(value) for value in opening.get("wall_ids") or []])
        add_property(obj, "App::PropertyStringList", "RoomIds", [str(value) for value in opening.get("room_ids") or []])

    if bool(payload.get("include_furniture", True)):
        for item in scene.get("fixtures_and_furniture", []):
            shape = furniture_shape(Part, App, item)
            obj = add_shape_feature(
                doc,
                interiors_group,
                f"Interior_{item.get('id', '')}",
                str(item.get("object_type") or "Furniture").replace("_", " ").title(),
                shape,
                {
                    "ExternalId": ("App::PropertyString", str(item.get("id") or "")),
                    "ObjectType": ("App::PropertyString", str(item.get("object_type") or "furniture")),
                    "Category": ("App::PropertyString", str(item.get("category") or "furniture")),
                    "RoomId": ("App::PropertyString", str(item.get("room_id") or "")),
                },
            )
            objects.append(obj)

    create_quantity_sheet(doc, dict(payload.get("quantities") or {}))
    doc.recompute()
    return App, doc, objects


def export_objects(doc, objects, output: Path, format_name: str) -> list[str]:
    warnings: list[str] = []
    output.parent.mkdir(parents=True, exist_ok=True)
    if format_name == "fcstd":
        doc.saveAs(str(output))
        return warnings

    if format_name in {"step", "iges"}:
        import Import
        Import.export(objects, str(output))
    elif format_name == "brep":
        import Part
        Part.export(objects, str(output))
    elif format_name in {"stl", "obj"}:
        import Mesh
        Mesh.export(objects, str(output))
    elif format_name == "ifc":
        module = optional_module("importIFC")
        if module is None:
            raise RuntimeError("This FreeCAD installation does not include IFC export support")
        module.export(objects, str(output))
    elif format_name == "dxf":
        module = optional_module("importDXF")
        if module is None:
            raise RuntimeError("This FreeCAD installation does not include DXF export support")
        module.export(objects, str(output))
    elif format_name == "svg":
        module = optional_module("importSVG")
        if module is None:
            raise RuntimeError("This FreeCAD installation does not include SVG export support")
        module.export(objects, str(output))
    else:
        raise RuntimeError(f"Unsupported export format: {format_name}")
    return warnings


def export_scene(payload: dict[str, Any]) -> dict[str, Any]:
    output = Path(str(payload["output"]))
    format_name = str(payload.get("format") or "fcstd").lower()
    App, doc, objects = build_document(payload)
    companion = output if format_name == "fcstd" else output.with_suffix(".FCStd")
    doc.saveAs(str(companion))
    warnings = export_objects(doc, objects, output, format_name)
    object_count = len(objects)
    document_name = doc.Name
    App.closeDocument(doc.Name)
    return {
        "ok": True,
        "output": str(output),
        "fcstd": str(companion),
        "format": format_name,
        "object_count": object_count,
        "document": document_name,
        "warnings": warnings,
    }


def bounds_for_objects(objects) -> dict[str, list[float]] | None:
    minimum = [float("inf"), float("inf"), float("inf")]
    maximum = [float("-inf"), float("-inf"), float("-inf")]
    found = False
    for obj in objects:
        box = None
        try:
            if hasattr(obj, "Shape") and not obj.Shape.isNull():
                box = obj.Shape.BoundBox
            elif hasattr(obj, "Mesh") and obj.Mesh.CountFacets:
                box = obj.Mesh.BoundBox
        except Exception:
            box = None
        if box is None:
            continue
        found = True
        minimum = [min(minimum[0], box.XMin), min(minimum[1], box.YMin), min(minimum[2], box.ZMin)]
        maximum = [max(maximum[0], box.XMax), max(maximum[1], box.YMax), max(maximum[2], box.ZMax)]
    if not found:
        return None
    return {"min_mm": minimum, "max_mm": maximum}


def import_into_document(source: Path):
    import FreeCAD as App

    suffix = source.suffix.lower()
    if suffix == ".fcstd":
        return App.openDocument(str(source))

    doc = App.newDocument("ImportedCAD")
    if suffix in {".step", ".stp", ".iges", ".igs"}:
        import Import
        Import.insert(str(source), doc.Name)
    elif suffix in {".brep", ".brp"}:
        import Part
        Part.insert(str(source), doc.Name)
    elif suffix in {".stl", ".obj", ".dae", ".off", ".3mf"}:
        import Mesh
        Mesh.insert(str(source), doc.Name)
    elif suffix == ".ifc":
        module = optional_module("importIFC")
        if module is None:
            raise RuntimeError("This FreeCAD installation does not include IFC import support")
        module.insert(str(source), doc.Name)
    elif suffix == ".dxf":
        module = optional_module("importDXF")
        if module is None:
            raise RuntimeError("This FreeCAD installation does not include DXF import support")
        module.insert(str(source), doc.Name)
    elif suffix == ".svg":
        module = optional_module("importSVG")
        if module is None:
            raise RuntimeError("This FreeCAD installation does not include SVG import support")
        module.insert(str(source), doc.Name, "import")
    else:
        raise RuntimeError(f"Unsupported import format: {suffix}")
    doc.recompute()
    return doc


def import_model(payload: dict[str, Any]) -> dict[str, Any]:
    import FreeCAD as App
    import Mesh

    source = Path(str(payload["source"]))
    output_dir = Path(str(payload["output_dir"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = import_into_document(source)
    doc.recompute()
    fcstd = output_dir / "imported-model.FCStd"
    obj = output_dir / "converted-model.obj"
    doc.saveAs(str(fcstd))
    objects = [
        item for item in doc.Objects
        if (hasattr(item, "Shape") and not item.Shape.isNull())
        or (hasattr(item, "Mesh") and getattr(item.Mesh, "CountFacets", 0) > 0)
    ]
    if not objects:
        raise RuntimeError("FreeCAD imported the file but found no exportable solids, surfaces or meshes")
    Mesh.export(objects, str(obj))
    bounds = bounds_for_objects(objects)
    object_count = len(objects)
    document_name = doc.Name
    App.closeDocument(doc.Name)
    return {
        "ok": True,
        "source": str(source),
        "fcstd": str(fcstd),
        "obj": str(obj),
        "object_count": object_count,
        "document": document_name,
        "bounds": bounds,
        "warnings": [],
    }


def main() -> None:
    args = parse_args()
    result_path = Path(args.result)
    try:
        payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
        action = str(payload.get("action") or "")
        if action == "probe":
            result = probe()
        elif action == "export_scene":
            result = export_scene(payload)
        elif action == "import_model":
            result = import_model(payload)
        else:
            raise RuntimeError(f"Unknown FreeCAD bridge action: {action}")
    except Exception as exc:
        result = {
            "ok": False,
            "error": str(exc),
            "traceback": traceback.format_exc()[-8000:],
        }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
