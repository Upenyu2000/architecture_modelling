from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from ..config import load_settings
from ..models import Project, SceneManifest, utc_now
from ..storage import load_project, project_dir, save_project, write_json

Progress = Callable[[int, str], None]

EXPORT_EXTENSIONS: dict[str, str] = {
    "fcstd": ".FCStd",
    "step": ".step",
    "iges": ".iges",
    "brep": ".brep",
    "ifc": ".ifc",
    "dxf": ".dxf",
    "svg": ".svg",
    "stl": ".stl",
    "obj": ".obj",
}
SUPPORTED_EXPORT_FORMATS = tuple(EXPORT_EXTENSIONS)
SUPPORTED_IMPORT_SUFFIXES = {
    ".fcstd", ".step", ".stp", ".iges", ".igs", ".brep", ".brp",
    ".ifc", ".dxf", ".svg", ".stl", ".obj", ".dae", ".off", ".3mf",
}
CORE_FORMATS = {"fcstd", "step", "iges", "brep", "stl", "obj"}
OPTIONAL_FORMAT_MODULES = {
    "ifc": "importIFC",
    "dxf": "importDXF",
    "svg": "importSVG",
}
HISTORY_LIMIT = 50


def _candidate_paths(*relative_paths: str) -> list[Path]:
    roots = [
        Path("C:/Program Files/FreeCAD 1.1/bin"),
        Path("C:/Program Files/FreeCAD 1.0/bin"),
        Path("C:/Program Files/FreeCAD 0.21/bin"),
        Path("C:/Program Files/FreeCAD/bin"),
        Path("C:/Program Files (x86)/FreeCAD/bin"),
    ]
    return [root / relative for root in roots for relative in relative_paths]


def _configured_path(key: str) -> str | None:
    configured = str(load_settings().get(key) or "").strip()
    return configured if configured and Path(configured).exists() else None


def find_freecad_cmd() -> str | None:
    configured = _configured_path("freecad_cmd_executable")
    if configured:
        return configured
    env_path = str(os.getenv("FREECAD_CMD", "")).strip()
    if env_path and Path(env_path).exists():
        return env_path
    for command in ("FreeCADCmd", "FreeCADCmd.exe", "freecadcmd", "freecadcmd.exe"):
        found = shutil.which(command)
        if found:
            return found
    return next((str(path) for path in _candidate_paths("FreeCADCmd.exe") if path.exists()), None)


def find_freecad_gui() -> str | None:
    configured = _configured_path("freecad_gui_executable")
    if configured:
        return configured
    env_path = str(os.getenv("FREECAD_GUI", "")).strip()
    if env_path and Path(env_path).exists():
        return env_path
    for command in ("FreeCAD", "FreeCAD.exe", "freecad", "freecad.exe"):
        found = shutil.which(command)
        if found:
            return found
    return next((str(path) for path in _candidate_paths("FreeCAD.exe") if path.exists()), None)


def _worker_script() -> Path:
    return Path(__file__).resolve().parent.parent / "freecad" / "bridge_worker.py"


def _run_worker(payload: dict[str, Any], timeout: int = 60 * 30) -> dict[str, Any]:
    executable = find_freecad_cmd()
    if not executable:
        raise RuntimeError("FreeCADCmd was not found. Install FreeCAD 1.x or select FreeCADCmd.exe in Settings.")
    worker = _worker_script()
    if not worker.exists():
        raise RuntimeError(f"FreeCAD bridge worker is missing: {worker}")

    with tempfile.TemporaryDirectory(prefix="dreamhome-freecad-") as temporary:
        payload_path = Path(temporary) / "payload.json"
        result_path = Path(temporary) / "result.json"
        payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        command = [
            executable,
            str(worker),
            "--payload",
            str(payload_path),
            "--result",
            str(result_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "FreeCAD returned no diagnostics")[-6000:]
            raise RuntimeError(f"FreeCAD operation failed: {tail}")
        if not result_path.exists():
            tail = (completed.stderr or completed.stdout or "")[-3000:]
            raise RuntimeError(f"FreeCAD did not produce a result file. {tail}")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if not result.get("ok", False):
            raise RuntimeError(str(result.get("error") or "FreeCAD operation failed"))
        return result


def freecad_status() -> dict[str, Any]:
    command = find_freecad_cmd()
    gui = find_freecad_gui()
    base: dict[str, Any] = {
        "installed": bool(command),
        "command_path": command,
        "gui_path": gui,
        "gui_available": bool(gui),
        "version": None,
        "modules": {},
        "export_formats": sorted(CORE_FORMATS),
        "import_suffixes": sorted(SUPPORTED_IMPORT_SUFFIXES),
        "error": None,
    }
    if not command:
        return base
    try:
        probe = _run_worker({"action": "probe"}, timeout=45)
        modules = dict(probe.get("modules") or {})
        formats = set(CORE_FORMATS)
        for format_name, module_name in OPTIONAL_FORMAT_MODULES.items():
            if modules.get(module_name):
                formats.add(format_name)
        base.update({
            "version": probe.get("version"),
            "modules": modules,
            "export_formats": sorted(formats),
        })
    except Exception as exc:
        base["error"] = str(exc)
    return base


def _wall_length(wall: Any) -> float:
    x1, z1 = wall.start
    x2, z2 = wall.end
    return math.hypot(x2 - x1, z2 - z1)


def quantity_schedule(scene: SceneManifest) -> dict[str, Any]:
    room_area = sum(float(room.area_m2) for room in scene.rooms)
    exterior_length = sum(_wall_length(wall) for wall in scene.walls if wall.wall_type == "exterior")
    internal_length = sum(_wall_length(wall) for wall in scene.walls if wall.wall_type != "exterior")
    gross_wall_area = sum(_wall_length(wall) * float(wall.height) for wall in scene.walls)
    wall_volume = sum(_wall_length(wall) * float(wall.height) * float(wall.thickness) for wall in scene.walls)
    opening_area = sum(float(opening.width) * float(opening.height) for opening in scene.openings)
    window_types = {"window", "fixed_window", "casement_window", "double_casement_window", "glider_window", "garden_window", "bay_window", "bow_window", "double_hung_window", "vertical_sliding_window", "horizontal_sliding_window"}
    windows = sum(1 for opening in scene.openings if opening.opening_type in window_types)
    passages = sum(1 for opening in scene.openings if opening.opening_type == "open_passage")
    doors = max(0, len(scene.openings) - windows - passages)
    furniture = Counter(item.object_type for item in scene.fixtures_and_furniture)
    room_types = Counter(room.room_type for room in scene.rooms)
    return {
        "units": "metric",
        "summary": {
            "rooms": len(scene.rooms),
            "floor_area_m2": round(room_area, 3),
            "floor_slab_volume_m3": round(room_area * 0.08, 3),
            "exterior_wall_length_m": round(exterior_length, 3),
            "internal_wall_length_m": round(internal_length, 3),
            "gross_wall_area_m2": round(gross_wall_area, 3),
            "opening_area_m2": round(opening_area, 3),
            "net_wall_area_m2": round(max(0.0, gross_wall_area - opening_area), 3),
            "wall_volume_m3": round(wall_volume, 3),
            "doors": doors,
            "windows": windows,
            "open_passages": passages,
            "furniture_and_fixtures": len(scene.fixtures_and_furniture),
        },
        "room_types": dict(sorted(room_types.items())),
        "furniture": dict(sorted(furniture.items())),
        "rooms": [
            {
                "id": room.id,
                "name": room.name,
                "room_type": room.room_type,
                "area_m2": round(float(room.area_m2), 3),
                "width_m": room.width_m,
                "depth_m": room.depth_m,
            }
            for room in scene.rooms
        ],
    }


def model_tree(scene: SceneManifest) -> dict[str, Any]:
    return {
        "id": scene.project_id,
        "label": "Parametric Building",
        "type": "App::Part",
        "properties": {
            "width_m": scene.width_m,
            "depth_m": scene.depth_m,
            "wall_height_m": scene.wall_height_m,
            "ceiling_height_m": scene.ceiling_height_m,
            "cutaway_height_m": scene.cutaway_height_m,
            "layout_mode": scene.layout_mode,
        },
        "children": [
            {
                "id": "rooms",
                "label": f"Rooms ({len(scene.rooms)})",
                "type": "App::DocumentObjectGroup",
                "children": [
                    {
                        "id": room.id,
                        "label": room.name,
                        "type": "Part::Feature",
                        "properties": {
                            "room_type": room.room_type,
                            "area_m2": round(float(room.area_m2), 3),
                            "centroid": list(room.centroid),
                            "vertices": len(room.polygon),
                        },
                    }
                    for room in scene.rooms
                ],
            },
            {
                "id": "walls",
                "label": f"Walls ({len(scene.walls)})",
                "type": "App::DocumentObjectGroup",
                "children": [
                    {
                        "id": wall.id,
                        "label": wall.id,
                        "type": "Part::Feature",
                        "properties": {
                            "wall_type": wall.wall_type,
                            "length_m": round(_wall_length(wall), 3),
                            "height_m": wall.height,
                            "thickness_m": wall.thickness,
                            "shared_group_id": wall.shared_group_id,
                        },
                    }
                    for wall in scene.walls
                ],
            },
            {
                "id": "openings",
                "label": f"Doors & Windows ({len(scene.openings)})",
                "type": "App::DocumentObjectGroup",
                "children": [
                    {
                        "id": opening.id,
                        "label": opening.opening_type.replace("_", " ").title(),
                        "type": "Part::Feature",
                        "properties": {
                            "width_m": opening.width,
                            "height_m": opening.height,
                            "sill_height_m": opening.sill_height,
                            "wall_ids": opening.wall_ids or ([opening.wall_id] if opening.wall_id else []),
                            "room_ids": opening.room_ids,
                        },
                    }
                    for opening in scene.openings
                ],
            },
            {
                "id": "interior",
                "label": f"Furniture & Fixtures ({len(scene.fixtures_and_furniture)})",
                "type": "App::DocumentObjectGroup",
                "children": [
                    {
                        "id": item.id,
                        "label": item.object_type.replace("_", " ").title(),
                        "type": "Part::Feature",
                        "properties": {
                            "category": item.category,
                            "room_id": item.room_id,
                            "size_m": list(item.size),
                            "rotation_deg": item.rotation_deg,
                        },
                    }
                    for item in scene.fixtures_and_furniture
                ],
            },
        ],
    }


def scene_parameters(scene: SceneManifest) -> dict[str, Any]:
    thicknesses = [float(wall.thickness) for wall in scene.walls]
    default_thickness = sum(thicknesses) / len(thicknesses) if thicknesses else 0.16
    return {
        "wall_height_m": round(float(scene.wall_height_m), 3),
        "default_wall_thickness_m": round(default_thickness, 3),
        "ceiling_height_m": round(float(scene.ceiling_height_m), 3),
        "cutaway_height_m": round(float(scene.cutaway_height_m), 3),
        "unit_system": "metric",
    }


def _history_root(project_id: str) -> Path:
    root = project_dir(project_id) / "working" / "cad-history"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _history_index(project_id: str) -> Path:
    return _history_root(project_id) / "index.json"


def _load_history(project_id: str) -> dict[str, Any]:
    path = _history_index(project_id)
    if not path.exists():
        return {"cursor": -1, "entries": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload.get("entries"), list):
            raise ValueError
        return payload
    except (json.JSONDecodeError, OSError, ValueError):
        return {"cursor": -1, "entries": []}


def _scene_digest(scene: SceneManifest) -> str:
    raw = scene.model_dump_json(exclude_none=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def record_history(project: Project, label: str) -> dict[str, Any]:
    if not project.scene:
        return _load_history(project.id)
    history = _load_history(project.id)
    entries = list(history.get("entries") or [])
    cursor = int(history.get("cursor", -1))
    digest = _scene_digest(project.scene)
    if 0 <= cursor < len(entries) and entries[cursor].get("digest") == digest:
        return history
    entries = entries[: cursor + 1]
    snapshot_id = uuid.uuid4().hex
    snapshot_path = _history_root(project.id) / f"{snapshot_id}.json"
    write_json(snapshot_path, project.scene.model_dump(mode="json"))
    entries.append({
        "id": snapshot_id,
        "label": label,
        "created_at": utc_now(),
        "digest": digest,
        "path": str(snapshot_path),
    })
    while len(entries) > HISTORY_LIMIT:
        removed = entries.pop(0)
        try:
            Path(str(removed.get("path"))).unlink(missing_ok=True)
        except OSError:
            pass
    history = {"cursor": len(entries) - 1, "entries": entries}
    write_json(_history_index(project.id), history)
    return history


def history_summary(project_id: str) -> dict[str, Any]:
    history = _load_history(project_id)
    cursor = int(history.get("cursor", -1))
    entries = list(history.get("entries") or [])
    return {
        "cursor": cursor,
        "entries": [{key: value for key, value in entry.items() if key != "path"} for entry in entries],
        "can_undo": cursor > 0,
        "can_redo": 0 <= cursor < len(entries) - 1,
    }


def _restore_history(project_id: str, direction: int) -> Project:
    history = _load_history(project_id)
    entries = list(history.get("entries") or [])
    cursor = int(history.get("cursor", -1))
    target = cursor + direction
    if target < 0 or target >= len(entries):
        return load_project(project_id)
    snapshot_path = Path(str(entries[target].get("path")))
    if not snapshot_path.exists():
        raise RuntimeError("CAD history snapshot is missing")
    project = load_project(project_id)
    project.scene = SceneManifest.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
    project.status = "cad_history_restored"
    write_json(project_dir(project_id) / "working" / "scene.json", project.scene.model_dump(mode="json"))
    save_project(project)
    history["cursor"] = target
    write_json(_history_index(project_id), history)
    return project


def undo_history(project_id: str) -> Project:
    return _restore_history(project_id, -1)


def redo_history(project_id: str) -> Project:
    return _restore_history(project_id, 1)


def export_scene(
    project: Project,
    output: Path,
    format_name: str,
    include_furniture: bool,
    unit_system: str,
    progress: Progress,
) -> dict[str, Any]:
    if not project.scene:
        raise RuntimeError("The project has no architectural scene")
    format_name = format_name.lower()
    if format_name not in EXPORT_EXTENSIONS:
        raise RuntimeError(f"Unsupported FreeCAD export format: {format_name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    progress(8, "Starting the FreeCAD Open CASCADE geometry kernel")
    payload = {
        "action": "export_scene",
        "project_name": project.name,
        "scene": project.scene.model_dump(mode="json"),
        "output": str(output),
        "format": format_name,
        "include_furniture": include_furniture,
        "unit_system": unit_system,
        "quantities": quantity_schedule(project.scene),
    }
    result = _run_worker(payload, timeout=60 * 60)
    progress(92, f"FreeCAD {format_name.upper()} model generated")
    return result


def import_model(source: Path, output_dir: Path, progress: Progress) -> dict[str, Any]:
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_IMPORT_SUFFIXES:
        raise RuntimeError(f"Unsupported FreeCAD import format: {suffix or 'unknown'}")
    output_dir.mkdir(parents=True, exist_ok=True)
    progress(8, f"Opening {suffix.lstrip('.').upper()} with FreeCAD")
    result = _run_worker({
        "action": "import_model",
        "source": str(source),
        "output_dir": str(output_dir),
    }, timeout=60 * 60)
    progress(92, "FreeCAD import converted to an editable FCStd document and app-compatible OBJ")
    return result


def launch_freecad(document: Path) -> None:
    executable = find_freecad_gui()
    if not executable:
        raise RuntimeError("FreeCAD GUI was not found. Select FreeCAD.exe in Settings.")
    subprocess.Popen([executable, str(document)], close_fds=True)
