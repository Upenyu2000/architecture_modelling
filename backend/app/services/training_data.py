from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from ..config import DATA_DIR, load_settings
from ..models import Project


CLASS_NAMES = ["background", "wall", "room", "door", "window"]
CLASS_IDS = {name: index for index, name in enumerate(CLASS_NAMES)}


def _workspace() -> Path:
    configured = str(load_settings().get("training_workspace") or "").strip()
    root = Path(configured).expanduser().resolve() if configured else DATA_DIR / "training-workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _split(identifier: str) -> str:
    value = int(hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if value < 80 else "val" if value < 90 else "test"


def export_corrected_training_example(project: Project, image_path: Path) -> dict[str, object]:
    if not project.scene or not project.scene.rooms:
        raise ValueError("The project needs at least one confirmed room polygon before it can become training data.")
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The floor-plan image could not be read.")
    scene = project.scene
    height, width = image.shape[:2]
    px_per_m_x = width / max(scene.width_m, 1e-6)
    px_per_m_z = height / max(scene.depth_m, 1e-6)
    mask = np.zeros((height, width), dtype=np.uint8)

    for room in scene.rooms:
        points = np.asarray([
            [round(x * px_per_m_x), round(z * px_per_m_z)] for x, z in room.polygon
        ], dtype=np.int32)
        if len(points) >= 3:
            cv2.fillPoly(mask, [points], CLASS_IDS["room"], lineType=cv2.LINE_8)

    for wall in scene.walls:
        thickness = max(2, round(wall.thickness * (px_per_m_x + px_per_m_z) / 2))
        start = (round(wall.start[0] * px_per_m_x), round(wall.start[1] * px_per_m_z))
        end = (round(wall.end[0] * px_per_m_x), round(wall.end[1] * px_per_m_z))
        cv2.line(mask, start, end, CLASS_IDS["wall"], thickness, cv2.LINE_8)

    for opening in scene.openings:
        class_id = CLASS_IDS["window"] if opening.opening_type == "window" else CLASS_IDS["door"]
        centre = (round(opening.position[0] * px_per_m_x), round(opening.position[1] * px_per_m_z))
        half = max(2, round(opening.width * (px_per_m_x + px_per_m_z) / 4))
        angle = np.deg2rad(opening.rotation_deg)
        dx = round(np.cos(angle) * half)
        dy = round(np.sin(angle) * half)
        cv2.line(
            mask,
            (centre[0] - dx, centre[1] - dy),
            (centre[0] + dx, centre[1] + dy),
            class_id,
            max(3, round(min(px_per_m_x, px_per_m_z) * 0.12)),
            cv2.LINE_8,
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    identifier = hashlib.sha256(f"{project.id}:{timestamp}:{len(scene.rooms)}:{len(scene.walls)}".encode("utf-8")).hexdigest()[:16]
    split = _split(identifier)
    workspace = _workspace()
    image_dir = workspace / "processed" / "images" / split
    mask_dir = workspace / "processed" / "masks" / split
    annotation_dir = workspace / "processed" / "annotations"
    image_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)
    annotation_dir.mkdir(parents=True, exist_ok=True)
    target_image = image_dir / f"{identifier}.png"
    target_mask = mask_dir / f"{identifier}.png"
    target_scene = annotation_dir / f"{identifier}.json"
    shutil.copy2(image_path, target_image)
    cv2.imwrite(str(target_mask), mask)
    target_scene.write_text(scene.model_dump_json(indent=2), encoding="utf-8")

    record = {
        "id": identifier,
        "source": "corrected_app_project",
        "source_id": project.id,
        "project_name": project.name,
        "split": split,
        "image": str(target_image.relative_to(workspace)).replace("\\", "/"),
        "mask": str(target_mask.relative_to(workspace)).replace("\\", "/"),
        "scene": str(target_scene.relative_to(workspace)).replace("\\", "/"),
        "width": width,
        "height": height,
        "classes": CLASS_NAMES,
        "annotation": "human_corrected_freeform_scene",
        "rights_confirmed_by_user": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest = workspace / "processed" / "manifest.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    (workspace / "processed" / "classes.json").write_text(json.dumps({"classes": CLASS_NAMES}, indent=2), encoding="utf-8")
    return {
        "id": identifier,
        "split": split,
        "workspace": str(workspace),
        "image": str(target_image),
        "mask": str(target_mask),
        "scene": str(target_scene),
    }
