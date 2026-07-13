from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path
from fastapi import UploadFile

from .config import PROJECTS_DIR, ensure_directories
from .models import Project, utc_now

SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def project_file(project_id: str) -> Path:
    return project_dir(project_id) / "project.json"


def create_project(name: str) -> Project:
    ensure_directories()
    project = Project(id=str(uuid.uuid4()), name=name.strip() or "My Dream Home")
    directory = project_dir(project.id)
    for child in ("uploads", "assets", "outputs", "working"):
        (directory / child).mkdir(parents=True, exist_ok=True)
    save_project(project)
    return project


def load_project(project_id: str) -> Project:
    path = project_file(project_id)
    if not path.exists():
        raise FileNotFoundError(project_id)
    return Project.model_validate_json(path.read_text(encoding="utf-8"))


def save_project(project: Project) -> Project:
    project.updated_at = utc_now()
    path = project_file(project.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    return project


def safe_filename(filename: str) -> str:
    cleaned = SAFE_NAME.sub("_", Path(filename).name).strip("._")
    return cleaned or f"upload-{uuid.uuid4().hex[:8]}"


async def save_upload(project_id: str, upload: UploadFile, folder: str, prefix: str = "") -> Path:
    destination_dir = project_dir(project_id) / folder
    destination_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}{safe_filename(upload.filename or 'upload.bin')}"
    destination = destination_dir / filename
    with destination.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            output.write(chunk)
    await upload.close()
    return destination


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def reset_working(project_id: str) -> Path:
    path = project_dir(project_id) / "working"
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path
