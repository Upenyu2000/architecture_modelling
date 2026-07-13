from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
import requests
from PIL import Image, ImageDraw


CLASSES = ["background", "wall", "room", "door", "window"]
CLASS_IDS = {name: index for index, name in enumerate(CLASSES)}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
EPSAP_ROOM_COLOURS = {
    (230, 230, 230), (200, 230, 230), (230, 200, 230), (230, 230, 200),
    (230, 200, 200), (200, 200, 230), (170, 170, 230), (230, 170, 170),
    (140, 140, 230), (110, 110, 230), (230, 170, 230),
}


@dataclass
class PreparedSample:
    source: str
    source_id: str
    image: Image.Image
    mask: Image.Image
    metadata: dict


def split_for(key: str) -> str:
    value = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 100
    if value < 80:
        return "train"
    if value < 90:
        return "val"
    return "test"


def image_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)


def resize_pair(image: Image.Image, mask: Image.Image, maximum: int) -> tuple[Image.Image, Image.Image]:
    width, height = image.size
    scale = min(1.0, maximum / max(width, height))
    if scale >= 1:
        return image.convert("RGB"), mask.convert("L")
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.convert("RGB").resize(size, Image.Resampling.LANCZOS), mask.convert("L").resize(size, Image.Resampling.NEAREST)


def weak_floorplan_mask(image: Image.Image) -> Image.Image:
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    dark = (gray < 105).astype(np.uint8) * 255
    minimum = min(gray.shape)
    long_side = max(9, int(minimum * 0.025))
    horizontal = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((3, long_side), np.uint8))
    vertical = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((long_side, 3), np.uint8))
    wall = cv2.bitwise_or(horizontal, vertical)
    wall = cv2.morphologyEx(wall, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)
    # Retain large dark connected regions so diagonal and irregular envelope pieces survive.
    count, labels, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=8)
    minimum_area = max(24, int(gray.size * 0.00003))
    for index in range(1, count):
        x, y, width, height, area = [int(value) for value in stats[index]]
        if area >= minimum_area and max(width, height) >= long_side:
            wall[labels == index] = 255

    closed_wall = cv2.dilate(wall, np.ones((5, 5), np.uint8), iterations=1)
    free = cv2.bitwise_not(closed_wall)
    outside = free.copy()
    flood_mask = np.zeros((free.shape[0] + 2, free.shape[1] + 2), np.uint8)
    cv2.floodFill(outside, flood_mask, (0, 0), 0)
    room = outside > 0
    output = np.zeros_like(gray, dtype=np.uint8)
    output[room] = CLASS_IDS["room"]
    output[wall > 0] = CLASS_IDS["wall"]
    return Image.fromarray(output, mode="L")


def colour_floorplan_mask(image: Image.Image) -> Image.Image:
    rgb = np.asarray(image.convert("RGB"))
    output = np.zeros(rgb.shape[:2], dtype=np.uint8)
    near_black = np.max(rgb, axis=2) < 55
    output[near_black] = CLASS_IDS["wall"]
    for colour in EPSAP_ROOM_COLOURS:
        distance = np.linalg.norm(rgb.astype(np.int16) - np.asarray(colour, dtype=np.int16), axis=2)
        output[distance < 14] = CLASS_IDS["room"]
    return Image.fromarray(output, mode="L")


def local_samples(root: Path) -> Iterable[PreparedSample]:
    for path in image_files(root):
        image = Image.open(path).convert("RGB")
        yield PreparedSample(
            source="local_user_seed",
            source_id=str(path.relative_to(root)).replace("\\", "/"),
            image=image,
            mask=weak_floorplan_mask(image),
            metadata={"annotation": "weak_cv", "review_required": True},
        )


def _download(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=180) as response:
        response.raise_for_status()
        with destination.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)
    return destination


def figshare_samples(workspace: Path) -> Iterable[PreparedSample]:
    article = requests.get("https://api.figshare.com/v2/articles/28282802", timeout=60)
    article.raise_for_status()
    files = article.json().get("files", [])
    archives: list[Path] = []
    raw = workspace / "raw" / "figshare_epsap_2500"
    for item in files:
        name = str(item.get("name") or f"file-{item.get('id')}")
        url = str(item.get("download_url") or "")
        if not url:
            continue
        target = raw / name
        if not target.exists():
            _download(url, target)
        if zipfile.is_zipfile(target):
            archives.append(target)
    if len(archives) < 2:
        raise RuntimeError("The Figshare release did not expose both expected ZIP archives.")

    extraction_roots: list[Path] = []
    for archive in archives:
        destination = raw / archive.stem
        if not destination.exists():
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(destination)
        extraction_roots.append(destination)

    collections = [image_files(root) for root in extraction_roots]
    colour_index = next((index for index, fileset in enumerate(collections) if fileset and _looks_coloured(Image.open(fileset[0]))), 1)
    bw_index = 1 - colour_index if len(collections) == 2 else next(index for index in range(len(collections)) if index != colour_index)
    colour_files = collections[colour_index]
    bw_files = collections[bw_index]
    colour_by_name = {path.stem.lower(): path for path in colour_files}

    for index, plan_path in enumerate(bw_files):
        colour_path = colour_by_name.get(plan_path.stem.lower())
        if colour_path is None and index < len(colour_files):
            colour_path = colour_files[index]
        plan = Image.open(plan_path).convert("RGB")
        mask = colour_floorplan_mask(Image.open(colour_path).convert("RGB")) if colour_path else weak_floorplan_mask(plan)
        yield PreparedSample(
            source="figshare_epsap_2500",
            source_id=plan_path.stem,
            image=plan,
            mask=mask,
            metadata={"annotation": "paired_colour_ground_truth" if colour_path else "weak_cv", "license": "CC BY 4.0"},
        )


def _looks_coloured(image: Image.Image) -> bool:
    rgb = np.asarray(image.convert("RGB").resize((128, 128)))
    return float(np.mean(np.max(rgb, axis=2) - np.min(rgb, axis=2) > 12)) > 0.02


def pseudo12k_samples(accept_unverified: bool, limit: int | None) -> Iterable[PreparedSample]:
    if not accept_unverified:
        raise RuntimeError("pseudo-floor-plan-12k has no declared licence. Re-run with --accept-unverified-license only after recording permission.")
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError("Install the optional 'datasets' package from training/requirements.txt") from exc
    dataset = load_dataset("zimhe/pseudo-floor-plan-12k", split="train", streaming=limit is not None)
    for index, row in enumerate(dataset):
        if limit is not None and index >= limit:
            break
        plan = row["plans"].convert("RGB")
        wall_image = np.asarray(row["walls"].convert("L"))
        colour_image = row["colors"].convert("RGB")
        wall = wall_image < 190 if float(wall_image.mean()) > 127 else wall_image > 65
        mask = np.asarray(colour_floorplan_mask(colour_image)).copy()
        mask[wall] = CLASS_IDS["wall"]
        yield PreparedSample(
            source="pseudo_floor_plan_12k",
            source_id=str(row.get("indices") or index),
            image=plan,
            mask=Image.fromarray(mask.astype(np.uint8), mode="L"),
            metadata={"annotation": "provided_wall_and_colour_layers", "license": "unverified"},
        )


def coco_samples(coco_json: Path, images_root: Path, source_name: str) -> Iterable[PreparedSample]:
    payload = json.loads(coco_json.read_text(encoding="utf-8"))
    categories = {int(item["id"]): str(item["name"]).lower() for item in payload.get("categories", [])}
    images = {int(item["id"]): item for item in payload.get("images", [])}
    annotations: dict[int, list[dict]] = {}
    for item in payload.get("annotations", []):
        annotations.setdefault(int(item["image_id"]), []).append(item)
    for image_id, item in images.items():
        path = images_root / item["file_name"]
        if not path.exists():
            continue
        image = Image.open(path).convert("RGB")
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        for annotation in annotations.get(image_id, []):
            category = categories.get(int(annotation.get("category_id", -1)), "")
            target = "door" if "door" in category else "window" if "window" in category else "wall" if "wall" in category else "room" if any(token in category for token in ("room", "zone", "area")) else None
            if target is None:
                continue
            class_id = CLASS_IDS[target]
            segmentation = annotation.get("segmentation")
            if isinstance(segmentation, list) and segmentation:
                for polygon in segmentation:
                    if isinstance(polygon, list) and len(polygon) >= 6:
                        draw.polygon([(polygon[index], polygon[index + 1]) for index in range(0, len(polygon) - 1, 2)], fill=class_id)
            else:
                x, y, width, height = annotation.get("bbox", [0, 0, 0, 0])
                draw.rectangle((x, y, x + width, y + height), fill=class_id)
        yield PreparedSample(
            source=source_name,
            source_id=str(item.get("file_name") or image_id),
            image=image,
            mask=mask,
            metadata={"annotation": "coco", "categories": sorted(set(categories.values()))},
        )


def vector_json_samples(path: Path, source_name: str, canvas: int = 1024) -> Iterable[PreparedSample]:
    files = [path] if path.is_file() else sorted(path.rglob("*.json"))
    for file in files:
        payload = json.loads(file.read_text(encoding="utf-8"))
        records = payload if isinstance(payload, list) else [payload]
        for record_index, record in enumerate(records):
            rooms = record.get("rooms") or record.get("spaces") or []
            polygons: list[list[tuple[float, float]]] = []
            for room in rooms:
                raw = room.get("vertices") or room.get("polygon") or room.get("points") or []
                points = [(float(point.get("x")), float(point.get("y"))) if isinstance(point, dict) else (float(point[0]), float(point[1])) for point in raw]
                if len(points) >= 3:
                    polygons.append(points)
            if not polygons:
                continue
            xs = [point[0] for polygon in polygons for point in polygon]
            ys = [point[1] for polygon in polygons for point in polygon]
            min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
            scale = (canvas * 0.88) / max(max_x - min_x, max_y - min_y, 1e-6)
            offset_x = (canvas - (max_x - min_x) * scale) / 2
            offset_y = (canvas - (max_y - min_y) * scale) / 2
            mask = Image.new("L", (canvas, canvas), 0)
            mask_draw = ImageDraw.Draw(mask)
            for polygon in polygons:
                converted = [((x - min_x) * scale + offset_x, (y - min_y) * scale + offset_y) for x, y in polygon]
                mask_draw.polygon(converted, fill=CLASS_IDS["room"], outline=CLASS_IDS["wall"], width=max(3, canvas // 180))
            image = Image.new("RGB", (canvas, canvas), "white")
            draw = ImageDraw.Draw(image)
            for polygon in polygons:
                converted = [((x - min_x) * scale + offset_x, (y - min_y) * scale + offset_y) for x, y in polygon]
                draw.polygon(converted, fill="white", outline="black", width=max(5, canvas // 110))
            yield PreparedSample(
                source=source_name,
                source_id=f"{file.stem}-{record_index}",
                image=image,
                mask=mask,
                metadata={"annotation": "vector_ground_truth", "original_file": str(file)},
            )


def write_samples(samples: Iterable[PreparedSample], workspace: Path, maximum: int) -> dict[str, int]:
    output = workspace / "processed"
    manifest_path = output / "manifest.jsonl"
    output.mkdir(parents=True, exist_ok=True)
    counts = {"train": 0, "val": 0, "test": 0}
    with manifest_path.open("a", encoding="utf-8") as manifest:
        for sample in samples:
            key = f"{sample.source}:{sample.source_id}"
            split = split_for(key)
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
            image, mask = resize_pair(sample.image, sample.mask, maximum)
            image_dir = output / "images" / split
            mask_dir = output / "masks" / split
            image_dir.mkdir(parents=True, exist_ok=True)
            mask_dir.mkdir(parents=True, exist_ok=True)
            image_path = image_dir / f"{digest}.png"
            mask_path = mask_dir / f"{digest}.png"
            image.save(image_path, "PNG", optimize=True)
            mask.save(mask_path, "PNG", optimize=True)
            record = {
                "id": digest,
                "source": sample.source,
                "source_id": sample.source_id,
                "split": split,
                "image": str(image_path.relative_to(workspace)).replace("\\", "/"),
                "mask": str(mask_path.relative_to(workspace)).replace("\\", "/"),
                "width": image.width,
                "height": image.height,
                "classes": CLASSES,
                **sample.metadata,
            }
            manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
            counts[split] += 1
    (output / "classes.json").write_text(json.dumps({"classes": CLASSES}, indent=2), encoding="utf-8")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare licence-tracked floor-plan segmentation data.")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--source", choices=["local", "figshare", "pseudo12k", "coco", "vector-json"], required=True)
    parser.add_argument("--input", type=Path, help="Local image folder, COCO JSON, or vector JSON folder")
    parser.add_argument("--images-root", type=Path, help="Image root for COCO annotations")
    parser.add_argument("--source-name", default="custom_import")
    parser.add_argument("--max-size", type=int, default=1280)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--accept-unverified-license", action="store_true")
    parser.add_argument("--clear", action="store_true", help="Clear the existing processed dataset before import")
    args = parser.parse_args()
    workspace = args.workspace.expanduser().resolve()
    if args.clear:
        shutil.rmtree(workspace / "processed", ignore_errors=True)
    workspace.mkdir(parents=True, exist_ok=True)

    if args.source == "local":
        if not args.input:
            parser.error("--input is required for local images")
        samples = local_samples(args.input.expanduser().resolve())
    elif args.source == "figshare":
        samples = figshare_samples(workspace)
    elif args.source == "pseudo12k":
        samples = pseudo12k_samples(args.accept_unverified_license, args.limit)
    elif args.source == "coco":
        if not args.input or not args.images_root:
            parser.error("--input COCO_JSON and --images-root are required")
        samples = coco_samples(args.input.resolve(), args.images_root.resolve(), args.source_name)
    else:
        if not args.input:
            parser.error("--input is required for vector-json")
        samples = vector_json_samples(args.input.resolve(), args.source_name)

    counts = write_samples(samples, workspace, max(256, args.max_size))
    print(json.dumps({"workspace": str(workspace), "added": counts, "classes": CLASSES}, indent=2))


if __name__ == "__main__":
    main()
