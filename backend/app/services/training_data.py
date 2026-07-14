from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import cv2
import numpy as np

from ..config import DATA_DIR, load_settings
from ..models import Project
from .plan_boundary import detect_plan_boundary


CLASS_NAMES = ["background", "wall", "room", "door", "window"]
CLASS_IDS = {name: index for index, name in enumerate(CLASS_NAMES)}
SEED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".json", ".jsonl",
    ".glb", ".gltf", ".obj", ".mtl", ".blend", ".stl", ".ply",
}


def _workspace() -> Path:
    configured = str(load_settings().get("training_workspace") or "").strip()
    root = Path(configured).expanduser().resolve() if configured else DATA_DIR / "training-workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _split(identifier: str) -> str:
    value = int(hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if value < 80 else "val" if value < 90 else "test"


def _append_manifest(workspace: Path, record: dict[str, object]) -> None:
    manifest = workspace / "processed" / "manifest.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    (workspace / "processed" / "classes.json").write_text(
        json.dumps({"classes": CLASS_NAMES}, indent=2), encoding="utf-8"
    )


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
        class_id = CLASS_IDS["window"] if "window" in opening.opening_type else CLASS_IDS["door"]
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
    _append_manifest(workspace, record)
    return {
        "id": identifier,
        "split": split,
        "workspace": str(workspace),
        "image": str(target_image),
        "mask": str(target_mask),
        "scene": str(target_scene),
    }


def _safe_member(name: str) -> Path:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe path in training seed pack: {name}")
    if Path(path.name).suffix.lower() not in SEED_EXTENSIONS:
        raise ValueError(f"Unsupported file in training seed pack: {name}")
    return Path(*path.parts)


def import_training_seed_pack(archive_path: Path, *, confirmed_rights: bool) -> dict[str, object]:
    """Import a rights-confirmed ZIP containing floor plans, masks, materials and 3D test assets."""
    if not confirmed_rights:
        raise ValueError("Confirm that every file in the seed pack may be used for local model training and testing.")
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()[:16]
    workspace = _workspace()
    pack_root = workspace / "seed-packs" / digest
    if pack_root.exists():
        shutil.rmtree(pack_root)
    pack_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            relative = _safe_member(member.filename)
            target = (pack_root / relative).resolve()
            if pack_root.resolve() not in target.parents:
                raise ValueError(f"Unsafe path in training seed pack: {member.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)

    manifest_path = pack_root / "manifest.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    imported_examples = 0
    imported_models = 0
    imported_materials = 0

    annotations = manifest_data.get("annotations", {}) if isinstance(manifest_data, dict) else {}
    for key, annotation in annotations.items():
        if not isinstance(annotation, dict) or not annotation.get("image"):
            continue
        image_source = pack_root / str(annotation["image"])
        image = cv2.imread(str(image_source), cv2.IMREAD_COLOR)
        if image is None:
            continue
        identifier = hashlib.sha256(f"{digest}:{key}".encode("utf-8")).hexdigest()[:16]
        split = "test"
        image_dir = workspace / "processed" / "images" / split
        mask_dir = workspace / "processed" / "masks" / split
        annotation_dir = workspace / "processed" / "annotations"
        image_dir.mkdir(parents=True, exist_ok=True)
        mask_dir.mkdir(parents=True, exist_ok=True)
        annotation_dir.mkdir(parents=True, exist_ok=True)
        image_target = image_dir / f"{identifier}.png"
        mask_target = mask_dir / f"{identifier}.png"
        scene_target = annotation_dir / f"{identifier}.json"
        cv2.imwrite(str(image_target), image)

        mask_source = pack_root / str(annotation.get("interior_mask", ""))
        supplied = cv2.imread(str(mask_source), cv2.IMREAD_GRAYSCALE) if mask_source.is_file() else None
        if supplied is None:
            supplied = detect_plan_boundary(image).interior_mask * 255
        class_mask = np.zeros_like(supplied, dtype=np.uint8)
        class_mask[supplied >= 128] = CLASS_IDS["room"]
        cv2.imwrite(str(mask_target), class_mask)
        scene_target.write_text(json.dumps(annotation, indent=2), encoding="utf-8")
        _append_manifest(workspace, {
            "id": identifier,
            "source": "user_seed_pack",
            "source_id": digest,
            "split": split,
            "image": str(image_target.relative_to(workspace)).replace("\\", "/"),
            "mask": str(mask_target.relative_to(workspace)).replace("\\", "/"),
            "scene": str(scene_target.relative_to(workspace)).replace("\\", "/"),
            "width": int(image.shape[1]),
            "height": int(image.shape[0]),
            "classes": CLASS_NAMES,
            "annotation": "seed_pack_boundary_and_interior_mask",
            "rights_confirmed_by_user": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        imported_examples += 1

    asset_root = workspace / "seed-assets" / digest
    asset_root.mkdir(parents=True, exist_ok=True)
    for source in pack_root.rglob("*"):
        if not source.is_file():
            continue
        suffix = source.suffix.lower()
        if suffix in {".glb", ".gltf", ".obj", ".mtl", ".blend", ".stl", ".ply"}:
            target = asset_root / "models" / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            imported_models += 1
        elif suffix in {".png", ".jpg", ".jpeg", ".webp"} and "material" in source.parts:
            target = asset_root / "materials" / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            imported_materials += 1

    return {
        "pack_id": digest,
        "workspace": str(workspace),
        "pack_root": str(pack_root),
        "training_examples": imported_examples,
        "model_assets": imported_models,
        "material_assets": imported_materials,
    }
