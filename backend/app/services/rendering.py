from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageEnhance

from ..config import find_blender
from ..models import SceneManifest

QUALITY = {
    "preview": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
}

WINDOW_TYPES = {
    "window", "fixed_window", "casement_window", "double_casement_window", "glider_window",
    "garden_window", "bay_window", "bow_window", "double_hung_window",
    "vertical_sliding_window", "horizontal_sliding_window",
}
DOUBLE_DOOR_TYPES = {"double_door", "double_bifold_door", "double_pocket_door", "double_sliding_door", "bypass_door"}
SLIDING_TYPES = {"pocket_door", "double_pocket_door", "bypass_door", "sliding_door", "double_sliding_door", "sliding_glass_door"}


def _rgb(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    raw = str(value or "").lstrip("#")
    if len(raw) != 6:
        return fallback
    try:
        return tuple(int(raw[index:index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return fallback


def _rotated_rectangle(
    draw: ImageDraw.ImageDraw,
    centre: tuple[float, float],
    size: tuple[float, float],
    angle_deg: float,
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int],
    width: int,
) -> None:
    cx, cy = centre
    half_x, half_y = size[0] / 2, size[1] / 2
    angle = math.radians(angle_deg)
    cosine, sine = math.cos(angle), math.sin(angle)
    points = []
    for x, y in ((-half_x, -half_y), (half_x, -half_y), (half_x, half_y), (-half_x, half_y)):
        points.append((cx + x * cosine - y * sine, cy + x * sine + y * cosine))
    draw.polygon(points, fill=fill)
    draw.line(points + [points[0]], fill=outline, width=width, joint="curve")


def _draw_opening_symbol(draw: ImageDraw.ImageDraw, opening, offset_x: int, offset_y: int, scale: float, accent_color, line_width: int) -> None:
    x = offset_x + opening.position[0] * scale
    z = offset_y + opening.position[1] * scale
    span = opening.width * scale
    angle = math.radians(opening.rotation_deg)
    ux, uz = math.cos(angle), math.sin(angle)
    nx, nz = -uz, ux
    dx, dz = ux * span / 2, uz * span / 2
    opening_type = str(opening.opening_type)

    if opening_type in WINDOW_TYPES:
        colour = (102, 190, 235, 255)
        draw.line((x - dx, z - dz, x + dx, z + dz), fill=colour, width=line_width)
        inset = max(2, line_width * 2)
        draw.line((x - dx + nx * inset, z - dz + nz * inset, x + dx + nx * inset, z + dz + nz * inset), fill=colour, width=max(1, line_width // 2))
        if opening_type in {"bay_window", "bow_window", "garden_window"}:
            bow = span * 0.18
            draw.line((x - dx, z - dz, x - dx * 0.55 + nx * bow, z - dz * 0.55 + nz * bow, x + dx * 0.55 + nx * bow, z + dz * 0.55 + nz * bow, x + dx, z + dz), fill=colour, width=max(1, line_width // 2), joint="curve")
        return

    if opening_type == "open_passage":
        draw.line((x - dx, z - dz, x + dx, z + dz), fill=(215, 168, 97, 255), width=max(2, line_width // 2))
        return

    colour = (*accent_color, 255)
    if opening_type == "revolving_door":
        radius = span / 2
        draw.ellipse((x - radius, z - radius, x + radius, z + radius), outline=colour, width=line_width)
        draw.line((x - radius * 0.7, z - radius * 0.7, x + radius * 0.7, z + radius * 0.7), fill=colour, width=max(1, line_width // 2))
        draw.line((x - radius * 0.7, z + radius * 0.7, x + radius * 0.7, z - radius * 0.7), fill=colour, width=max(1, line_width // 2))
        return

    if opening_type in SLIDING_TYPES:
        draw.line((x - dx, z - dz, x + dx, z + dz), fill=colour, width=line_width)
        shift = span * 0.18
        draw.line((x - dx + ux * shift + nx * line_width * 2, z - dz + uz * shift + nz * line_width * 2, x + dx + ux * shift + nx * line_width * 2, z + dz + uz * shift + nz * line_width * 2), fill=colour, width=max(1, line_width // 2))
        return

    if opening_type == "overhead_door":
        draw.line((x - dx, z - dz, x + dx, z + dz), fill=colour, width=line_width)
        draw.arc((x - span / 2, z - span / 2, x + span / 2, z + span / 2), 180, 360, fill=colour, width=max(1, line_width // 2))
        return

    double = opening_type in DOUBLE_DOOR_TYPES
    swing = -1 if opening.swing_direction == "counterclockwise" else 1
    radius = span / 2 if double else span
    if double:
        draw.line((x - dx, z - dz, x, z), fill=colour, width=line_width)
        draw.line((x, z, x + dx, z + dz), fill=colour, width=line_width)
        for sign in (-1, 1):
            hinge_x, hinge_z = x + ux * radius * sign, z + uz * radius * sign
            end_x = hinge_x - ux * radius * sign + nx * radius * 0.82 * swing
            end_z = hinge_z - uz * radius * sign + nz * radius * 0.82 * swing
            draw.line((hinge_x, hinge_z, end_x, end_z), fill=colour, width=max(1, line_width // 2))
    else:
        hinge_sign = 1 if opening.hinge_side == "right" else -1
        hinge_x, hinge_z = x + ux * span / 2 * hinge_sign, z + uz * span / 2 * hinge_sign
        end_x = hinge_x - ux * span * hinge_sign + nx * span * 0.78 * swing
        end_z = hinge_z - uz * span * hinge_sign + nz * span * 0.78 * swing
        draw.line((x - dx, z - dz, x + dx, z + dz), fill=colour, width=line_width)
        draw.line((hinge_x, hinge_z, end_x, end_z), fill=colour, width=max(1, line_width // 2))


def technical_render(scene: SceneManifest, output: Path, quality: str, progress: Callable[[int, str], None]) -> Path:
    width, height = QUALITY[quality]
    progress(10, "Preparing compiled architectural projection")
    image = Image.new("RGBA", (width, height), (8, 22, 15, 255))
    margin = int(min(width, height) * 0.07)
    scale = min((width - margin * 2) / max(scene.width_m, 1), (height - margin * 2) / max(scene.depth_m, 1))
    layout_width = max(1, round(scene.width_m * scale))
    layout_height = max(1, round(scene.depth_m * scale))
    offset_x = round((width - layout_width) / 2)
    offset_y = round((height - layout_height) / 2)

    if scene.reference_image_path and Path(scene.reference_image_path).exists():
        try:
            reference = Image.open(scene.reference_image_path).convert("RGBA")
            reference = reference.resize((layout_width, layout_height), Image.Resampling.LANCZOS)
            reference = ImageEnhance.Brightness(reference).enhance(0.68)
            image.alpha_composite(reference, (offset_x, offset_y))
        except OSError:
            pass

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    floor_color = _rgb(scene.materials.floor_global.hex_color, (139, 118, 95))
    wall_color = _rgb(scene.materials.walls_global.hex_color, (230, 235, 230))
    exterior_color = _rgb(scene.materials.exterior_walls.hex_color, (155, 155, 150))
    accent_color = _rgb(scene.materials.accent.hex_color, (46, 121, 198))
    metal_color = _rgb(scene.materials.fixture_metal.hex_color, (166, 173, 178))

    progress(28, "Drawing calibrated rooms and labels")
    for room in scene.rooms:
        polygon = [(offset_x + x * scale, offset_y + z * scale) for x, z in room.polygon]
        if len(polygon) < 3:
            continue
        draw.polygon(polygon, fill=(*floor_color, 185), outline=(102, 155, 119, 255), width=max(1, width // 1100))
        cx, cz = room.centroid
        label = room.name
        if room.extracted_dimension:
            label += f"\n{room.extracted_dimension}"
        elif room.width_m and room.depth_m:
            label += f"\n{room.width_m:.1f} × {room.depth_m:.1f} m"
        draw.multiline_text(
            (offset_x + cx * scale, offset_y + cz * scale),
            label,
            fill=(238, 247, 241, 255),
            anchor="mm",
            align="center",
            spacing=3,
            stroke_width=max(1, width // 1500),
            stroke_fill=(5, 15, 9, 235),
        )

    progress(48, "Drawing classified walls and openings")
    for wall in scene.walls:
        thickness = max(3, int(wall.thickness * scale))
        colour = exterior_color if wall.wall_type == "exterior" else wall_color
        draw.line(
            (
                offset_x + wall.start[0] * scale,
                offset_y + wall.start[1] * scale,
                offset_x + wall.end[0] * scale,
                offset_y + wall.end[1] * scale,
            ),
            fill=(*colour, 255),
            width=thickness,
        )

    symbol_width = max(3, width // 700)
    for opening in scene.openings:
        _draw_opening_symbol(draw, opening, offset_x, offset_y, scale, accent_color, symbol_width)

    progress(66, "Placing fixtures, furniture and user assets")
    for item in scene.fixtures_and_furniture:
        x, _, z = item.coordinates
        sx, _, sz = item.size
        colour = metal_color if item.category in {"utility", "structure"} else accent_color
        if item.category == "fixture":
            colour = (230, 234, 231)
        _rotated_rectangle(
            draw,
            (offset_x + x * scale, offset_y + z * scale),
            (sx * scale, sz * scale),
            item.rotation_deg,
            (*colour, 220),
            (225, 244, 232, 255),
            max(1, width // 1000),
        )

    for asset in scene.assets:
        x, _, z = asset.position
        sx, _, sz = asset.size
        _rotated_rectangle(
            draw,
            (offset_x + x * scale, offset_y + z * scale),
            (sx * scale, sz * scale),
            math.degrees(asset.rotation_y),
            (*accent_color, 225),
            (137, 220, 164, 255),
            max(1, width // 1000),
        )

    image = Image.alpha_composite(image, overlay)
    footer = ImageDraw.Draw(image, "RGBA")
    confidence = round(scene.project_metadata.structural_confidence * 100)
    footer_height = max(38, margin // 2)
    footer.rectangle((0, height - footer_height, width, height), fill=(5, 16, 11, 225))
    footer.text(
        (margin, height - footer_height / 2),
        f"Arch-AI Convert · {scene.materials.palette_name} · {len(scene.rooms)} rooms · {len(scene.openings)} openings · {confidence}% confidence",
        fill=(170, 205, 184, 255),
        anchor="lm",
    )

    progress(90, f"Writing {quality} architectural image")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output, "PNG", optimize=True)
    progress(100, "Render complete")
    return output


def blender_render(scene_path: Path, output: Path, quality: str, mode: str, seconds: int, progress: Callable[[int, str], None]) -> Path:
    blender = find_blender()
    if not blender:
        raise RuntimeError("Blender was not found. Install Blender 4.x or choose its blender.exe in Settings.")
    script = Path(__file__).resolve().parent.parent / "blender" / "generate_scene_v2.py"
    progress(8, "Starting opening-aware PBR Blender scene")
    command = [
        blender, "--background", "--python", str(script), "--",
        "--scene", str(scene_path), "--output", str(output), "--quality", quality,
        "--mode", mode, "--seconds", str(seconds),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=60 * 60 * 4)
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout)[-4000:]
        raise RuntimeError(f"Blender render failed: {tail}")
    progress(100, "Blender render complete")
    return output
