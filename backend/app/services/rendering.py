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
    progress(15, "Preparing deterministic scene projection")
    image = Image.new("RGB", (width, height), (8, 22, 15))
    draw = ImageDraw.Draw(image)
    margin = int(min(width, height) * 0.08)
    scale = min((width - margin * 2) / max(scene.width_m, 1), (height - margin * 2) / max(scene.depth_m, 1))
    offset_x = (width - scene.width_m * scale) / 2
    offset_y = (height - scene.depth_m * scale) / 2
    progress(35, "Drawing room surfaces")
    for room in scene.rooms:
        polygon = [(offset_x + x * scale, offset_y + z * scale) for x, z in room.polygon]
        if len(polygon) >= 3:
            draw.polygon(polygon, fill=(42, 65, 50), outline=(102, 155, 119), width=max(1, width // 900))
            cx, cz = room.centroid
            draw.text((offset_x + cx * scale, offset_y + cz * scale), room.name, fill=(223, 241, 228), anchor="mm")
    progress(55, "Drawing structural walls")
    wall_width = max(3, int(scene.wall_height_m * scale * 0.06))
    for wall in scene.walls:
        draw.line(
            (offset_x + wall.start[0] * scale, offset_y + wall.start[1] * scale, offset_x + wall.end[0] * scale, offset_y + wall.end[1] * scale),
            fill=(230, 235, 230), width=wall_width,
        )
    progress(72, "Placing user-provided assets")
    for asset in scene.assets:
        x, _, z = asset.position
        sx, _, sz = asset.size
        box = [offset_x + (x - sx / 2) * scale, offset_y + (z - sz / 2) * scale, offset_x + (x + sx / 2) * scale, offset_y + (z + sz / 2) * scale]
        draw.rounded_rectangle(box, radius=max(3, width // 600), fill=(57, 125, 82), outline=(137, 220, 164), width=max(1, width // 1000))
    draw.text((margin, height - margin // 2), "Dream Home Visualizer · deterministic technical render", fill=(125, 165, 141), anchor="ls")
    progress(90, f"Writing {quality} image")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "PNG", optimize=True)
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
