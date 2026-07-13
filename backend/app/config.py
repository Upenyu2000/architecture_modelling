from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

APP_NAME = "Dream Home Visualizer"
DATA_DIR = Path(os.getenv("DREAMHOME_DATA_DIR", Path.home() / ".dream-home-visualizer")).resolve()
PROJECTS_DIR = DATA_DIR / "projects"
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_SETTINGS: dict[str, Any] = {
    "blender_executable": "",
    "image_to_3d_command": "",
    "ai_endpoint": "",
    "ai_token": "",
    "allow_remote_processing": False,
}


def ensure_directories() -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict[str, Any]:
    ensure_directories()
    if not SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        return {**DEFAULT_SETTINGS, **json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))}
    except (json.JSONDecodeError, OSError):
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    ensure_directories()
    cleaned = {**DEFAULT_SETTINGS, **settings}
    SETTINGS_FILE.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
    return cleaned


def find_blender() -> str | None:
    configured = str(load_settings().get("blender_executable") or "").strip()
    if configured and Path(configured).exists():
        return configured
    from_path = shutil.which("blender")
    if from_path:
        return from_path
    candidates = [
        Path("C:/Program Files/Blender Foundation/Blender 4.4/blender.exe"),
        Path("C:/Program Files/Blender Foundation/Blender 4.3/blender.exe"),
        Path("C:/Program Files/Blender Foundation/Blender 4.2/blender.exe"),
        Path("C:/Program Files/Blender Foundation/Blender/blender.exe"),
    ]
    return next((str(path) for path in candidates if path.exists()), None)
