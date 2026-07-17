from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from .config import PROJECTS_DIR, ensure_directories
from .models import Project, SaveSlotSummary, utc_now

SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")
SLOT_ID = re.compile(r"^[a-f0-9]{32}$")
ACTIVE_FOLDERS = ("uploads", "assets", "outputs", "working")
DEFAULT_MAX_UPLOAD_BYTES = 250 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024


class UploadStorageError(RuntimeError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def max_upload_bytes() -> int:
    configured = os.getenv("DREAMHOME_MAX_UPLOAD_BYTES", "").strip()
    if not configured:
        return DEFAULT_MAX_UPLOAD_BYTES
    try:
        return max(1024 * 1024, int(configured))
    except ValueError:
        return DEFAULT_MAX_UPLOAD_BYTES


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def project_file(project_id: str) -> Path:
    return project_dir(project_id) / "project.json"


def save_slots_dir(project_id: str) -> Path:
    path = project_dir(project_id) / "save_slots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_project(name: str) -> Project:
    ensure_directories()
    project = Project(id=str(uuid.uuid4()), name=name.strip() or "My Dream Home")
    directory = project_dir(project.id)
    for child in ACTIVE_FOLDERS:
        (directory / child).mkdir(parents=True, exist_ok=True)
    save_slots_dir(project.id)
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
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.upload")
    limit = max_upload_bytes()
    declared_size = getattr(upload, "size", None)
    if isinstance(declared_size, int) and declared_size > limit:
        await upload.close()
        raise UploadStorageError(f"Upload exceeds the {limit // (1024 * 1024)} MB size limit.", 413)

    written = 0
    try:
        with temporary.open("xb") as output:
            while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
                written += len(chunk)
                if written > limit:
                    raise UploadStorageError(f"Upload exceeds the {limit // (1024 * 1024)} MB size limit.", 413)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if written == 0:
            raise UploadStorageError("The uploaded file is empty.", 422)
        temporary.replace(destination)
        return destination
    except UploadStorageError:
        raise
    except OSError as exc:
        raise UploadStorageError(f"The upload could not be saved: {exc}", 500) from exc
    finally:
        temporary.unlink(missing_ok=True)
        await upload.close()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def reset_working(project_id: str) -> Path:
    path = project_dir(project_id) / "working"
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def _clear_active_folders(project_id: str) -> None:
    root = project_dir(project_id)
    for folder in ACTIVE_FOLDERS:
        path = root / folder
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def reset_project(project_id: str) -> Project:
    project = load_project(project_id)
    _clear_active_folders(project_id)
    project.floorplan = None
    project.building_model = None
    project.assets = {}
    project.scene = None
    project.drawing_set = None
    project.status = "created"
    return save_project(project)


def _slot_dir(project_id: str, slot_id: str) -> Path:
    if not SLOT_ID.fullmatch(slot_id):
        raise FileNotFoundError(slot_id)
    return save_slots_dir(project_id) / slot_id


def _read_slot_summary(project_id: str, slot_id: str) -> SaveSlotSummary:
    path = _slot_dir(project_id, slot_id) / "slot.json"
    if not path.exists():
        raise FileNotFoundError(slot_id)
    return SaveSlotSummary.model_validate_json(path.read_text(encoding="utf-8"))


def list_save_slots(project_id: str) -> list[SaveSlotSummary]:
    slots: list[SaveSlotSummary] = []
    for item in save_slots_dir(project_id).iterdir():
        if not item.is_dir() or not SLOT_ID.fullmatch(item.name):
            continue
        try:
            slots.append(_read_slot_summary(project_id, item.name))
        except (FileNotFoundError, ValueError):
            continue
    return sorted(slots, key=lambda slot: slot.updated_at, reverse=True)


def create_save_slot(project_id: str, name: str) -> SaveSlotSummary:
    project = load_project(project_id)
    slot_id = uuid.uuid4().hex
    slot_root = _slot_dir(project_id, slot_id)
    data_root = slot_root / "data"
    data_root.mkdir(parents=True, exist_ok=False)

    for folder in ACTIVE_FOLDERS:
        source = project_dir(project_id) / folder
        destination = data_root / folder
        if source.exists():
            shutil.copytree(source, destination)
        else:
            destination.mkdir(parents=True, exist_ok=True)

    (slot_root / "project.json").write_text(project.model_dump_json(indent=2), encoding="utf-8")
    timestamp = utc_now()
    summary = SaveSlotSummary(
        id=slot_id,
        name=name.strip() or "Saved Build",
        created_at=timestamp,
        updated_at=timestamp,
        status=project.status,
        floorplan_filename=project.floorplan.filename if project.floorplan else None,
        building_model_filename=project.building_model.filename if project.building_model else None,
        preview_url=project.floorplan.preview_url if project.floorplan else None,
        asset_count=len(project.assets),
        has_scene=project.scene is not None,
        has_drawings=project.drawing_set is not None,
    )
    (slot_root / "slot.json").write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    return summary


def restore_save_slot(project_id: str, slot_id: str) -> Project:
    summary = _read_slot_summary(project_id, slot_id)
    slot_root = _slot_dir(project_id, slot_id)
    snapshot_path = slot_root / "project.json"
    if not snapshot_path.exists():
        raise FileNotFoundError(slot_id)

    snapshot = Project.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
    _clear_active_folders(project_id)
    data_root = slot_root / "data"
    for folder in ACTIVE_FOLDERS:
        source = data_root / folder
        destination = project_dir(project_id) / folder
        if destination.exists():
            shutil.rmtree(destination)
        if source.exists():
            shutil.copytree(source, destination)
        else:
            destination.mkdir(parents=True, exist_ok=True)

    snapshot.id = project_id
    snapshot.name = summary.name
    if snapshot.scene:
        snapshot.scene.project_id = project_id
    if snapshot.drawing_set:
        snapshot.drawing_set.project_id = project_id
    return save_project(snapshot)


def delete_save_slot(project_id: str, slot_id: str) -> None:
    slot_root = _slot_dir(project_id, slot_id)
    if not slot_root.exists():
        raise FileNotFoundError(slot_id)
    shutil.rmtree(slot_root)
