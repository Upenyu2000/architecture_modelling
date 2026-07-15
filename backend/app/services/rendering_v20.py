from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from ..config import find_blender


def _run_blender(
    blender: str,
    script: Path,
    scene_path: Path,
    output: Path,
    quality: str,
    view: str,
) -> None:
    command = [
        blender,
        "--background",
        "--python",
        str(script),
        "--",
        "--scene",
        str(scene_path),
        "--output",
        str(output),
        "--quality",
        quality,
        "--view",
        view,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=60 * 60 * 5)
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout)[-6000:]
        raise RuntimeError(f"Blender {view.replace('_', ' ')} presentation render failed: {tail}")
    if not output.exists():
        raise RuntimeError(f"Blender completed without producing {output}")


def render_presentation_views(
    scene_path: Path,
    top_down_output: Path,
    perspective_output: Path,
    quality: str,
    engine: str,
    progress: Callable[[int, str], None],
) -> tuple[Path, Path]:
    blender = find_blender()
    if not blender:
        message = (
            "Blender 4.x was not found. Install Blender or choose blender.exe in Settings "
            "to generate photorealistic top-down and eye-level presentation renders."
        )
        if engine == "blender":
            raise RuntimeError(message)
        raise RuntimeError(message)

    script = Path(__file__).resolve().parent.parent / "blender" / "generate_presentation.py"
    if not script.exists():
        raise RuntimeError(f"Presentation renderer not found at {script}")

    top_down_output.parent.mkdir(parents=True, exist_ok=True)
    progress(8, "Preparing style-consistent PBR materials and furniture")
    _run_blender(blender, script, scene_path, top_down_output, quality, "top_down")
    progress(52, "Top-down layout complete; composing eye-level interior")
    _run_blender(blender, script, scene_path, perspective_output, quality, "perspective")
    progress(94, "Both architectural presentation views are rendered")
    return top_down_output, perspective_output
