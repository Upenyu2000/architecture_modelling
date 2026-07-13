from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from ..config import find_blender
from .rendering import technical_render


def blender_render(
    scene_path: Path,
    output: Path,
    quality: str,
    mode: str,
    seconds: int,
    progress: Callable[[int, str], None],
) -> Path:
    blender = find_blender()
    if not blender:
        raise RuntimeError("Blender was not found. Install Blender 4.x or choose its blender.exe in Settings.")
    script = Path(__file__).resolve().parent.parent / "blender" / "generate_scene_v3.py"
    progress(8, "Starting portal-aware PBR interior scene")
    command = [
        blender, "--background", "--python", str(script), "--",
        "--scene", str(scene_path), "--output", str(output), "--quality", quality,
        "--mode", mode, "--seconds", str(seconds),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=60 * 60 * 4)
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout)[-4000:]
        raise RuntimeError(f"Blender interior render failed: {tail}")
    progress(100, "Detailed Blender interior render complete")
    return output
