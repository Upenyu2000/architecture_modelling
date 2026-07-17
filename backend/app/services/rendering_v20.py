from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Callable

from ..config import find_blender


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
RENDER_TIMEOUT_SECONDS = 60 * 60 * 5


def _validate_png(path: Path, view: str) -> None:
    if not path.exists() or not path.is_file():
        raise RuntimeError(f"Blender completed without producing the {view.replace('_', ' ')} image")
    if path.stat().st_size < 64:
        raise RuntimeError(f"Blender produced an empty or truncated {view.replace('_', ' ')} image")
    with path.open("rb") as rendered:
        if rendered.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
            raise RuntimeError(f"Blender produced an invalid PNG for the {view.replace('_', ' ')} view")


def _run_blender(
    blender: str,
    script: Path,
    scene_path: Path,
    output: Path,
    quality: str,
    view: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_name(f".{output.stem}-{uuid.uuid4().hex}.tmp.png")
    output.unlink(missing_ok=True)
    temporary_output.unlink(missing_ok=True)

    command = [
        blender,
        "--background",
        "--factory-startup",
        "--disable-autoexec",
        "--python",
        str(script),
        "--",
        "--scene",
        str(scene_path),
        "--output",
        str(temporary_output),
        "--quality",
        quality,
        "--view",
        view,
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=RENDER_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Blender timed out while rendering the {view.replace('_', ' ')} view after "
            f"{RENDER_TIMEOUT_SECONDS // 3600} hours"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"Blender could not be started: {exc}") from exc

    try:
        if completed.returncode != 0:
            combined = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
            tail = combined[-6000:] or "Blender exited without diagnostic output."
            raise RuntimeError(f"Blender {view.replace('_', ' ')} presentation render failed: {tail}")
        _validate_png(temporary_output, view)
        temporary_output.replace(output)
        _validate_png(output, view)
    finally:
        temporary_output.unlink(missing_ok=True)


def render_presentation_views(
    scene_path: Path,
    top_down_output: Path,
    perspective_output: Path,
    quality: str,
    engine: str,
    progress: Callable[[int, str], None],
) -> tuple[Path, Path]:
    if engine not in {"auto", "blender"}:
        raise RuntimeError(f"Unsupported presentation renderer: {engine}")
    if quality not in {"preview", "1080p", "4k"}:
        raise RuntimeError(f"Unsupported presentation quality: {quality}")
    if not scene_path.exists():
        raise RuntimeError("The prepared presentation scene is missing")

    blender = find_blender()
    if not blender:
        raise RuntimeError(
            "Blender 4.x was not found. Install Blender or choose blender.exe in Settings "
            "to generate photorealistic top-down and eye-level presentation renders."
        )

    script = Path(__file__).resolve().parent.parent / "blender" / "generate_presentation.py"
    if not script.exists():
        raise RuntimeError(f"Presentation renderer not found at {script}")

    top_down_output.parent.mkdir(parents=True, exist_ok=True)
    top_down_output.unlink(missing_ok=True)
    perspective_output.unlink(missing_ok=True)

    try:
        progress(8, "Preparing style-consistent PBR materials and furniture")
        _run_blender(blender, script, scene_path, top_down_output, quality, "top_down")
        progress(52, "Top-down layout complete; composing eye-level interior")
        _run_blender(blender, script, scene_path, perspective_output, quality, "perspective")
        progress(94, "Both architectural presentation views are rendered")
        return top_down_output, perspective_output
    except Exception:
        top_down_output.unlink(missing_ok=True)
        perspective_output.unlink(missing_ok=True)
        raise
