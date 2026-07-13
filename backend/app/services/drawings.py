from __future__ import annotations

import html
import math
import zipfile
from pathlib import Path
from typing import Callable, Iterable

import cv2
import numpy as np
import trimesh

from ..models import DrawingFile, DrawingRequest, DrawingSet

Progress = Callable[[int, str], None]
Line2D = tuple[tuple[float, float], tuple[float, float]]

UNIT_SCALE = {
    "metres": 1.0,
    "millimetres": 0.001,
    "centimetres": 0.01,
    "feet": 0.3048,
}


def _load_mesh(path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(str(path), force="scene", process=False)
    if isinstance(loaded, trimesh.Trimesh):
        mesh = loaded
    elif isinstance(loaded, trimesh.Scene):
        if not loaded.geometry:
            raise ValueError("The uploaded 3D file contains no mesh geometry.")
        if hasattr(loaded, "to_mesh"):
            mesh = loaded.to_mesh()
        else:
            dumped = loaded.dump(concatenate=True)
            mesh = dumped if isinstance(dumped, trimesh.Trimesh) else trimesh.util.concatenate(tuple(dumped))
    else:
        raise ValueError("The uploaded file could not be interpreted as a 3D building mesh.")
    if len(mesh.vertices) < 3 or len(mesh.faces) < 1:
        raise ValueError("The 3D model does not contain usable triangular faces.")
    return mesh.copy()


def _unit_scale(mesh: trimesh.Trimesh, requested: str) -> tuple[float, str, list[str]]:
    warnings: list[str] = []
    if requested in UNIT_SCALE:
        return UNIT_SCALE[requested], requested, warnings

    units = str(getattr(mesh, "units", "") or "").lower()
    aliases = {
        "m": "metres", "meter": "metres", "meters": "metres", "metre": "metres", "metres": "metres",
        "mm": "millimetres", "millimeter": "millimetres", "millimeters": "millimetres",
        "cm": "centimetres", "centimeter": "centimetres", "centimeters": "centimetres",
        "ft": "feet", "foot": "feet", "feet": "feet",
    }
    if units in aliases:
        resolved = aliases[units]
        return UNIT_SCALE[resolved], resolved, warnings

    maximum_extent = float(np.max(mesh.extents))
    if maximum_extent > 500:
        warnings.append("Model units were not declared; millimetres were inferred from its size.")
        return UNIT_SCALE["millimetres"], "millimetres (inferred)", warnings
    if maximum_extent > 80:
        warnings.append("Model units were not declared; centimetres were inferred from its size.")
        return UNIT_SCALE["centimetres"], "centimetres (inferred)", warnings
    warnings.append("Model units were not declared; metres were assumed. Change the units selector if dimensions look wrong.")
    return 1.0, "metres (assumed)", warnings


def _deduplicate_lines(lines: Iterable[Line2D], precision: int = 4) -> list[Line2D]:
    unique: dict[tuple[tuple[float, float], tuple[float, float]], Line2D] = {}
    for start, end in lines:
        if math.dist(start, end) < 0.002:
            continue
        a = (round(start[0], precision), round(start[1], precision))
        b = (round(end[0], precision), round(end[1], precision))
        key = (a, b) if a <= b else (b, a)
        unique[key] = (a, b)
    return list(unique.values())


def _section_lines(mesh: trimesh.Trimesh, up_axis: str, slice_height_m: float) -> tuple[list[Line2D], tuple[int, int], float]:
    up_index = 1 if up_axis == "y" else 2
    drawing_axes = (0, 2) if up_axis == "y" else (0, 1)
    base_height = float(mesh.bounds[0, up_index])
    plane_height = base_height + slice_height_m
    origin = np.zeros(3, dtype=float)
    origin[up_index] = plane_height
    normal = np.zeros(3, dtype=float)
    normal[up_index] = 1.0
    section = mesh.section(plane_origin=origin, plane_normal=normal)
    lines: list[Line2D] = []
    if section is not None:
        for polyline in section.discrete:
            points = np.asarray(polyline, dtype=float)
            if len(points) < 2:
                continue
            projected = points[:, drawing_axes]
            for first, second in zip(projected[:-1], projected[1:]):
                lines.append(((float(first[0]), float(first[1])), (float(second[0]), float(second[1]))))
    return _deduplicate_lines(lines), drawing_axes, plane_height


def _projected_hull(mesh: trimesh.Trimesh, axes: tuple[int, int]) -> np.ndarray:
    points = np.asarray(mesh.vertices[:, axes], dtype=np.float64)
    if len(points) < 3:
        raise ValueError("The model does not contain enough points for a drawing.")
    scaled = np.round(points * 10000).astype(np.int32)
    hull = cv2.convexHull(scaled).reshape(-1, 2).astype(np.float64) / 10000.0
    return hull


def _hull_lines(hull: np.ndarray) -> list[Line2D]:
    lines: list[Line2D] = []
    for index in range(len(hull)):
        first = hull[index]
        second = hull[(index + 1) % len(hull)]
        lines.append(((float(first[0]), float(first[1])), (float(second[0]), float(second[1]))))
    return lines


def _bounds_for_lines(lines: list[Line2D]) -> tuple[float, float, float, float]:
    coordinates = [point for line in lines for point in line]
    xs = [point[0] for point in coordinates]
    ys = [point[1] for point in coordinates]
    if not xs or not ys:
        raise ValueError("No drawable geometry was found at the selected slice height.")
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if max_x - min_x < 0.001 or max_y - min_y < 0.001:
        raise ValueError("The selected drawing view is effectively flat or empty.")
    return min_x, min_y, max_x, max_y


def _pixel_transform(bounds: tuple[float, float, float, float], width: int, height: int, margin: int):
    min_x, min_y, max_x, max_y = bounds
    scale = min((width - margin * 2) / (max_x - min_x), (height - margin * 2) / (max_y - min_y))

    def convert(point: tuple[float, float]) -> tuple[int, int]:
        x = margin + (point[0] - min_x) * scale
        y = height - margin - (point[1] - min_y) * scale
        return int(round(x)), int(round(y))

    return convert


def _render_png(
    lines: list[Line2D],
    output: Path,
    title: str,
    include_dimensions: bool,
    width: int = 1800,
    height: int = 1300,
) -> tuple[float, float]:
    bounds = _bounds_for_lines(lines)
    min_x, min_y, max_x, max_y = bounds
    drawing_width = max_x - min_x
    drawing_height = max_y - min_y
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    convert = _pixel_transform(bounds, width, height, 130)
    for start, end in lines:
        cv2.line(canvas, convert(start), convert(end), (20, 20, 20), 3, cv2.LINE_AA)

    cv2.putText(canvas, title, (70, 62), cv2.FONT_HERSHEY_SIMPLEX, 1.15, (15, 15, 15), 2, cv2.LINE_AA)
    cv2.putText(canvas, "Generated from the uploaded 3D building model", (72, 98), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (90, 90, 90), 1, cv2.LINE_AA)

    if include_dimensions:
        left_bottom = convert((min_x, min_y))
        right_bottom = convert((max_x, min_y))
        left_top = convert((min_x, max_y))
        offset = 55
        cv2.line(canvas, (left_bottom[0], left_bottom[1] + offset), (right_bottom[0], right_bottom[1] + offset), (70, 70, 70), 2)
        cv2.line(canvas, (left_bottom[0], left_bottom[1] + offset - 9), (left_bottom[0], left_bottom[1] + offset + 9), (70, 70, 70), 2)
        cv2.line(canvas, (right_bottom[0], right_bottom[1] + offset - 9), (right_bottom[0], right_bottom[1] + offset + 9), (70, 70, 70), 2)
        cv2.putText(canvas, f"{drawing_width:.2f} m", ((left_bottom[0] + right_bottom[0]) // 2 - 55, left_bottom[1] + offset - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (40, 40, 40), 2, cv2.LINE_AA)

        cv2.line(canvas, (left_bottom[0] - offset, left_bottom[1]), (left_top[0] - offset, left_top[1]), (70, 70, 70), 2)
        cv2.line(canvas, (left_bottom[0] - offset - 9, left_bottom[1]), (left_bottom[0] - offset + 9, left_bottom[1]), (70, 70, 70), 2)
        cv2.line(canvas, (left_top[0] - offset - 9, left_top[1]), (left_top[0] - offset + 9, left_top[1]), (70, 70, 70), 2)
        cv2.putText(canvas, f"{drawing_height:.2f} m", (left_bottom[0] - offset - 94, (left_bottom[1] + left_top[1]) // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (40, 40, 40), 2, cv2.LINE_AA)

    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), canvas)
    return drawing_width, drawing_height


def _write_svg(lines: list[Line2D], output: Path, title: str, include_dimensions: bool) -> None:
    bounds = _bounds_for_lines(lines)
    width, height, margin = 1800, 1300, 130
    convert = _pixel_transform(bounds, width, height, margin)
    min_x, min_y, max_x, max_y = bounds
    elements = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="70" y="62" font-family="Segoe UI, sans-serif" font-size="34" font-weight="700">{html.escape(title)}</text>',
        '<g fill="none" stroke="#171717" stroke-width="3" stroke-linecap="round">',
    ]
    for start, end in lines:
        x1, y1 = convert(start)
        x2, y2 = convert(end)
        elements.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>')
    elements.append('</g>')
    if include_dimensions:
        elements.append(f'<text x="{width // 2 - 65}" y="{height - 35}" font-family="Segoe UI, sans-serif" font-size="24">{max_x - min_x:.2f} m</text>')
        elements.append(f'<text x="20" y="{height // 2}" font-family="Segoe UI, sans-serif" font-size="24">{max_y - min_y:.2f} m</text>')
    elements.append('</svg>')
    output.write_text("\n".join(elements), encoding="utf-8")


def _write_dxf(lines: list[Line2D], output: Path) -> None:
    content = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "6", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for (x1, y1), (x2, y2) in lines:
        content.extend([
            "0", "LINE", "8", "WALLS",
            "10", f"{x1:.5f}", "20", f"{y1:.5f}", "30", "0.0",
            "11", f"{x2:.5f}", "21", f"{y2:.5f}", "31", "0.0",
        ])
    content.extend(["0", "ENDSEC", "0", "EOF"])
    output.write_text("\n".join(content), encoding="ascii")


def _add_file(files: list[DrawingFile], kind: str, path: Path, url_prefix: str) -> None:
    files.append(DrawingFile(
        kind=kind,
        format=path.suffix.lower().lstrip("."),
        filename=path.name,
        path=str(path),
        url=f"{url_prefix}/{path.name}",
    ))


def generate_drawing_set(
    project_id: str,
    model_path: Path,
    source_filename: str,
    output_dir: Path,
    url_prefix: str,
    request: DrawingRequest,
    progress: Progress,
) -> tuple[DrawingSet, Path]:
    progress(5, "Loading the 3D building model")
    mesh = _load_mesh(model_path)
    scale, resolved_units, warnings = _unit_scale(mesh, request.model_units)
    mesh.apply_scale(scale)

    progress(22, "Cutting the floor-plan section")
    plan_lines, plan_axes, _plane_height = _section_lines(mesh, request.up_axis, request.slice_height_m)
    if not plan_lines:
        warnings.append("The selected slice height did not intersect closed geometry; a projected footprint was used instead.")
        plan_lines = _hull_lines(_projected_hull(mesh, plan_axes))

    output_dir.mkdir(parents=True, exist_ok=True)
    files: list[DrawingFile] = []

    progress(42, "Drawing the floor plan")
    plan_png = output_dir / "floor-plan.png"
    plan_svg = output_dir / "floor-plan.svg"
    plan_dxf = output_dir / "floor-plan.dxf"
    _render_png(plan_lines, plan_png, "Floor Plan", request.include_dimensions)
    _write_svg(plan_lines, plan_svg, "Floor Plan", request.include_dimensions)
    _write_dxf(plan_lines, plan_dxf)
    _add_file(files, "floor_plan", plan_png, url_prefix)
    _add_file(files, "floor_plan", plan_svg, url_prefix)
    _add_file(files, "floor_plan", plan_dxf, url_prefix)

    up_index = 1 if request.up_axis == "y" else 2
    horizontal_axes = [axis for axis in (0, 1, 2) if axis != up_index]
    elevation_views = [
        ("front_elevation", (horizontal_axes[0], up_index), "Front Elevation"),
        ("side_elevation", (horizontal_axes[1], up_index), "Side Elevation"),
    ]

    progress(63, "Generating architectural elevations")
    for kind, axes, title in elevation_views:
        lines = _hull_lines(_projected_hull(mesh, axes))
        png = output_dir / f"{kind.replace('_', '-')}.png"
        svg = output_dir / f"{kind.replace('_', '-')}.svg"
        _render_png(lines, png, title, request.include_dimensions)
        _write_svg(lines, svg, title, request.include_dimensions)
        _add_file(files, kind, png, url_prefix)
        _add_file(files, kind, svg, url_prefix)

    extents = tuple(round(float(value), 3) for value in mesh.extents)
    drawing_set = DrawingSet(
        project_id=project_id,
        source_filename=source_filename,
        slice_height_m=request.slice_height_m,
        up_axis=request.up_axis,
        model_units=resolved_units,
        bounds_m=extents,
        files=files,
        warnings=warnings,
    )

    progress(86, "Packaging the drawing set")
    manifest = output_dir / "drawing-set.json"
    manifest.write_text(drawing_set.model_dump_json(indent=2), encoding="utf-8")
    _add_file(files, "manifest", manifest, url_prefix)
    drawing_set.files = files
    manifest.write_text(drawing_set.model_dump_json(indent=2), encoding="utf-8")

    archive = output_dir.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for drawing in files:
            bundle.write(drawing.path, arcname=drawing.filename)
    progress(96, "Drawing set ready")
    return drawing_set, archive
