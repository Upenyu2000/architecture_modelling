from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw

from ..config import find_blender
from ..models import SceneManifest

QUALITY = {
    "preview": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
}


def technical_render(scene: SceneManifest, output: Path, quality: str, progress: Callable[[int, str], None]) -> Path:
    width, height = QUALITY[quality]
    progress(15, "Preparing aligned top-down projection")
    image = Image.new("RGBA", (width, height), (8, 22, 15, 255))
    margin = int(min(width, height) * 0.08)
    scale = min((width - margin * 2) / max(scene.width_m, 1), (height - margin * 2) / max(scene.depth_m, 1))
    layout_width = max(1, round(scene.width_m * scale))
    layout_height = max(1, round(scene.depth_m * scale))
    offset_x = round((width - layout_width) / 2)
    offset_y = round((height - layout_height) / 2)

    if scene.reference_image_path and Path(scene.reference_image_path).exists():
        progress(25, "Aligning the source plan beneath the geometry")
        with Image.open(scene.reference_image_path) as source:
            reference = source.convert("RGBA").resize((layout_width, layout_height), Image.Resampling.LANCZOS)
        image.alpha_composite(reference, (offset_x, offset_y))

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    progress(38, "Drawing editable room surfaces")
    for room in scene.rooms:
        polygon = [(offset_x + x * scale, offset_y + z * scale) for x, z in room.polygon]
        if len(polygon) >= 3:
            fill = (42, 91, 59, 74) if scene.reference_image_path else (42, 65, 50, 255)
            draw.polygon(polygon, fill=fill, outline=(102, 225, 145, 255), width=max(2, width // 900))
            cx, cz = room.centroid
            draw.text(
                (offset_x + cx * scale, offset_y + cz * scale),
                room.name,
                fill=(244, 255, 248, 255),
                stroke_width=max(1, width // 1400),
                stroke_fill=(5, 15, 9, 230),
                anchor="mm",
            )

    progress(58, "Drawing deduplicated structural walls")
    wall_width = max(3, int(max(0.08, scene.walls[0].thickness if scene.walls else 0.16) * scale))
    for wall in scene.walls:
        draw.line(
            (
                offset_x + wall.start[0] * scale,
                offset_y + wall.start[1] * scale,
                offset_x + wall.end[0] * scale,
                offset_y + wall.end[1] * scale,
            ),
            fill=(238, 241, 238, 255),
            width=wall_width,
        )

    progress(72, "Placing user-provided assets")
    for asset in scene.assets:
        x, _, z = asset.position
        sx, _, sz = asset.size
        box = [
            offset_x + (x - sx / 2) * scale,
            offset_y + (z - sz / 2) * scale,
            offset_x + (x + sx / 2) * scale,
            offset_y + (z + sz / 2) * scale,
        ]
        draw.rounded_rectangle(
            box,
            radius=max(3, width // 600),
            fill=(57, 125, 82, 205),
            outline=(137, 220, 164, 255),
            width=max(1, width // 1000),
        )

    image = Image.alpha_composite(image, overlay)
    footer = ImageDraw.Draw(image)
    footer.text(
        (margin, height - margin // 2),
        "Dream Home Visualizer · aligned top-down render",
        fill=(170, 205, 184, 255),
        anchor="ls",
    )
    progress(90, f"Writing {quality} image")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output, "PNG", optimize=True)
    progress(100, "Render complete")
    return output


def blender_render(scene_path: Path, output: Path, quality: str, mode: str, seconds: int, progress: Callable[[int, str], None]) -> Path:
    blender = find_blender()
    if not blender:
        raise RuntimeError("Blender was not found. Install Blender 4.x or choose its blender.exe in Settings.")
    script = Path(__file__).resolve().parent.parent / "blender" / "generate_scene.py"
    progress(8, "Starting Blender in background mode")
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
