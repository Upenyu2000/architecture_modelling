from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from shapely.geometry import Polygon

from ..config import load_settings
from ..models import Opening, RoomShape, SceneManifest, WallSegment


DEFAULT_LABELS = ["background", "wall", "room", "door", "window"]
_MODEL_CACHE: dict[str, tuple[float, cv2.dnn.Net]] = {}


@dataclass
class SemanticPrediction:
    masks: dict[str, np.ndarray]
    confidences: dict[str, float]
    model_path: str
    input_size: int


def _metadata(model_path: Path, settings: dict[str, Any]) -> tuple[list[str], int, float]:
    labels = DEFAULT_LABELS
    input_size = int(settings.get("segmentation_input_size") or 512)
    threshold = float(settings.get("segmentation_threshold") or 0.5)
    sidecar_candidates = [model_path.with_suffix(".json"), model_path.parent / "model-metadata.json"]
    for sidecar in sidecar_candidates:
        if not sidecar.exists():
            continue
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            if isinstance(payload.get("labels"), list) and payload["labels"]:
                labels = [str(item).strip().lower() for item in payload["labels"]]
            input_size = int(payload.get("input_size") or input_size)
            threshold = float(payload.get("threshold") or threshold)
            break
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return labels, max(128, min(input_size, 2048)), max(0.05, min(threshold, 0.95))


def _net(model_path: Path) -> cv2.dnn.Net:
    key = str(model_path.resolve())
    modified = model_path.stat().st_mtime
    cached = _MODEL_CACHE.get(key)
    if cached and cached[0] == modified:
        return cached[1]
    net = cv2.dnn.readNetFromONNX(key)
    try:
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    except cv2.error:
        pass
    _MODEL_CACHE[key] = (modified, net)
    return net


def _letterbox(image: np.ndarray, size: int) -> tuple[np.ndarray, float, int, int]:
    height, width = image.shape[:2]
    scale = min(size / max(width, 1), size / max(height, 1))
    resized_width = max(1, int(round(width * scale)))
    resized_height = max(1, int(round(height * scale)))
    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_AREA)
    canvas = np.full((size, size, 3), 255, dtype=np.uint8)
    offset_x = (size - resized_width) // 2
    offset_y = (size - resized_height) // 2
    canvas[offset_y:offset_y + resized_height, offset_x:offset_x + resized_width] = resized
    return canvas, scale, offset_x, offset_y


def _class_map(output: np.ndarray, labels: list[str], threshold: float) -> tuple[np.ndarray, np.ndarray]:
    tensor = np.asarray(output)
    while tensor.ndim > 3 and tensor.shape[0] == 1:
        tensor = tensor[0]
    if tensor.ndim == 2:
        tensor = tensor[None, ...]
    if tensor.ndim != 3:
        raise ValueError(f"Unsupported ONNX segmentation output shape: {tuple(np.asarray(output).shape)}")
    if tensor.shape[0] > 32 and tensor.shape[-1] <= 32:
        tensor = np.transpose(tensor, (2, 0, 1))
    if tensor.shape[0] == 1:
        logits = tensor[0].astype(np.float32)
        probability = 1.0 / (1.0 + np.exp(-np.clip(logits, -30, 30)))
        classes = (probability >= threshold).astype(np.uint8)
        confidence = np.maximum(probability, 1.0 - probability)
        return classes, confidence
    logits = tensor.astype(np.float32)
    logits -= logits.max(axis=0, keepdims=True)
    exp = np.exp(np.clip(logits, -30, 30))
    probabilities = exp / np.maximum(exp.sum(axis=0, keepdims=True), 1e-8)
    return probabilities.argmax(axis=0).astype(np.uint8), probabilities.max(axis=0)


def run_semantic_model(image: np.ndarray) -> SemanticPrediction | None:
    settings = load_settings()
    configured = str(settings.get("segmentation_model_path") or "").strip()
    if not configured:
        return None
    model_path = Path(configured).expanduser().resolve()
    if not model_path.exists() or model_path.suffix.lower() != ".onnx":
        return None
    labels, input_size, threshold = _metadata(model_path, settings)
    prepared, scale, offset_x, offset_y = _letterbox(image, input_size)
    blob = cv2.dnn.blobFromImage(
        prepared,
        scalefactor=1.0 / 255.0,
        size=(input_size, input_size),
        mean=(0.0, 0.0, 0.0),
        swapRB=True,
        crop=False,
    )
    blob[:, 0] = (blob[:, 0] - 0.485) / 0.229
    blob[:, 1] = (blob[:, 1] - 0.456) / 0.224
    blob[:, 2] = (blob[:, 2] - 0.406) / 0.225
    net = _net(model_path)
    net.setInput(blob)
    output = net.forward()
    classes, confidence = _class_map(output, labels, threshold)
    resized_height = max(1, int(round(image.shape[0] * scale)))
    resized_width = max(1, int(round(image.shape[1] * scale)))
    classes = cv2.resize(classes, (input_size, input_size), interpolation=cv2.INTER_NEAREST)
    confidence = cv2.resize(confidence.astype(np.float32), (input_size, input_size), interpolation=cv2.INTER_LINEAR)
    classes = classes[offset_y:offset_y + resized_height, offset_x:offset_x + resized_width]
    confidence = confidence[offset_y:offset_y + resized_height, offset_x:offset_x + resized_width]
    classes = cv2.resize(classes, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
    confidence = cv2.resize(confidence, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_LINEAR)

    masks: dict[str, np.ndarray] = {}
    confidences: dict[str, float] = {}
    for index, label in enumerate(labels):
        mask = (classes == index).astype(np.uint8) * 255
        if int(mask.max()) == 0:
            continue
        masks[label] = mask
        selected = confidence[mask > 0]
        confidences[label] = round(float(selected.mean()) if selected.size else 0.0, 4)
    if len(labels) == 1 or (set(masks) <= {"background", "wall"} and "wall" not in masks and 1 in np.unique(classes)):
        masks["wall"] = (classes == 1).astype(np.uint8) * 255
    return SemanticPrediction(masks=masks, confidences=confidences, model_path=str(model_path), input_size=input_size)


def _mask(prediction: SemanticPrediction, *names: str) -> np.ndarray | None:
    for name in names:
        candidate = prediction.masks.get(name)
        if candidate is not None:
            return candidate
    return None


def _rooms_from_mask(mask: np.ndarray, scene: SceneManifest) -> list[RoomShape]:
    metres_per_pixel = scene.width_m / max(mask.shape[1], 1)
    cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(mask.shape[0] * mask.shape[1])
    rooms: list[RoomShape] = []
    for contour in contours:
        area_px = float(cv2.contourArea(contour))
        if area_px < image_area * 0.0025 or area_px > image_area * 0.8:
            continue
        epsilon = max(1.0, cv2.arcLength(contour, True) * 0.006)
        points_px = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
        if len(points_px) < 3 or len(points_px) > 64:
            continue
        points = [(round(float(x) * metres_per_pixel, 3), round(float(y) * metres_per_pixel, 3)) for x, y in points_px]
        polygon = Polygon(points)
        if not polygon.is_valid or polygon.area < 0.1:
            continue
        rooms.append(RoomShape(
            id=f"room-{uuid.uuid4().hex[:8]}",
            name="",
            polygon=points,
            area_m2=round(float(polygon.area), 2),
            centroid=(round(float(polygon.centroid.x), 3), round(float(polygon.centroid.y), 3)),
            width_m=round(float(polygon.bounds[2] - polygon.bounds[0]), 3),
            depth_m=round(float(polygon.bounds[3] - polygon.bounds[1]), 3),
            label_confidence=0.0,
        ))
    rooms.sort(key=lambda room: (-room.area_m2, room.centroid[1], room.centroid[0]))
    for index, room in enumerate(rooms, 1):
        room.name = f"Room {index}"
    return rooms[:60]


def _walls_from_mask(mask: np.ndarray, scene: SceneManifest) -> list[WallSegment]:
    metres_per_pixel = scene.width_m / max(mask.shape[1], 1)
    edges = cv2.Canny(mask, 60, 160)
    minimum = max(12, int(round(0.45 / max(metres_per_pixel, 1e-6))))
    raw = cv2.HoughLinesP(edges, 1, np.pi / 720, threshold=max(18, minimum // 2), minLineLength=minimum, maxLineGap=max(5, minimum // 5))
    if raw is None:
        return []
    candidates: list[tuple[float, tuple[int, int, int, int]]] = []
    for item in raw[:, 0, :]:
        x1, y1, x2, y2 = map(int, item)
        length = math.hypot(x2 - x1, y2 - y1)
        if length >= minimum:
            candidates.append((length, (x1, y1, x2, y2)))
    candidates.sort(reverse=True)
    retained: list[tuple[int, int, int, int]] = []
    for _length, line in candidates:
        x1, y1, x2, y2 = line
        angle = round(math.atan2(y2 - y1, x2 - x1) / math.radians(2))
        midpoint = ((x1 + x2) / 2, (y1 + y2) / 2)
        duplicate = False
        for a1, b1, a2, b2 in retained:
            other_angle = round(math.atan2(b2 - b1, a2 - a1) / math.radians(2))
            other_midpoint = ((a1 + a2) / 2, (b1 + b2) / 2)
            if abs(angle - other_angle) <= 1 and math.dist(midpoint, other_midpoint) < max(8, minimum * 0.35):
                duplicate = True
                break
        if not duplicate:
            retained.append(line)
        if len(retained) >= 180:
            break
    thickness = scene.walls[0].thickness if scene.walls else 0.16
    return [WallSegment(
        id=f"wall-{uuid.uuid4().hex[:8]}",
        start=(round(x1 * metres_per_pixel, 3), round(y1 * metres_per_pixel, 3)),
        end=(round(x2 * metres_per_pixel, 3), round(y2 * metres_per_pixel, 3)),
        height=scene.wall_height_m,
        thickness=thickness,
        wall_type="interior",
        confidence=0.7,
    ) for x1, y1, x2, y2 in retained]


def _openings_from_mask(mask: np.ndarray, scene: SceneManifest, opening_type: str) -> list[Opening]:
    metres_per_pixel = scene.width_m / max(mask.shape[1], 1)
    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    results: list[Opening] = []
    for index in range(1, count):
        x, y, width, height, area = [int(value) for value in stats[index]]
        if area < 8 or max(width, height) < 4:
            continue
        real_width = max(width, height) * metres_per_pixel
        if not 0.25 <= real_width <= 4.5:
            continue
        centre_x, centre_y = map(float, centroids[index])
        results.append(Opening(
            id=f"opening-{uuid.uuid4().hex[:8]}",
            opening_type="window" if opening_type == "window" else "door",
            position=(round(centre_x * metres_per_pixel, 3), round(centre_y * metres_per_pixel, 3)),
            width=round(real_width, 3),
            height=1.25 if opening_type == "window" else 2.1,
            rotation_deg=0.0 if width >= height else 90.0,
            swing_direction="none" if opening_type == "window" else "clockwise",
            confidence=0.82,
        ))
    return results[:80]


def refine_scene_with_model(scene: SceneManifest, image_path: Path) -> SceneManifest:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        return scene
    prediction = run_semantic_model(image)
    if prediction is None:
        return scene

    room_mask = _mask(prediction, "room", "rooms", "zone", "floor", "interior")
    wall_mask = _mask(prediction, "wall", "walls", "structure")
    door_mask = _mask(prediction, "door", "doors")
    window_mask = _mask(prediction, "window", "windows")

    if room_mask is not None and wall_mask is not None:
        room_mask = cv2.bitwise_and(room_mask, cv2.bitwise_not(cv2.dilate(wall_mask, np.ones((3, 3), np.uint8))))
    model_rooms = _rooms_from_mask(room_mask, scene) if room_mask is not None else []
    if model_rooms:
        total_area = sum(room.area_m2 for room in model_rooms)
        footprint_area = max(scene.width_m * scene.depth_m, 0.001)
        coverage = total_area / footprint_area
        if 0.05 <= coverage <= 0.92:
            scene.rooms = model_rooms
            from .layout import walls_from_rooms
            scene.walls = walls_from_rooms(scene)
    elif wall_mask is not None:
        model_walls = _walls_from_mask(wall_mask, scene)
        if model_walls:
            scene.walls = model_walls

    openings: list[Opening] = []
    if door_mask is not None:
        openings.extend(_openings_from_mask(door_mask, scene, "door"))
    if window_mask is not None:
        openings.extend(_openings_from_mask(window_mask, scene, "window"))
    if openings:
        scene.openings = openings

    scene.project_metadata.parser_version = "arch-ai-onnx-1.1"
    scene.project_metadata.detected_rooms = len(scene.rooms)
    scene.project_metadata.detected_openings = len(scene.openings)
    average_confidence = float(np.mean(list(prediction.confidences.values()))) if prediction.confidences else 0.0
    scene.project_metadata.structural_confidence = round(max(scene.project_metadata.structural_confidence, average_confidence), 3)
    scene.warnings = [warning for warning in scene.warnings if "local segmentation" not in warning.lower()]
    scene.warnings.append(
        f"Local segmentation model applied before vector cleanup ({Path(prediction.model_path).name}, {prediction.input_size}px input)."
    )

    preview = image.copy()
    colors = {"wall": (54, 206, 108), "room": (41, 142, 232), "door": (44, 90, 242), "window": (236, 181, 50)}
    for label, color in colors.items():
        mask = _mask(prediction, label, f"{label}s")
        if mask is None:
            continue
        overlay = np.zeros_like(preview)
        overlay[:] = color
        selected = mask > 0
        preview[selected] = cv2.addWeighted(preview, 0.45, overlay, 0.55, 0)[selected]
    target = image_path.parent / "model-segmentation-preview.png"
    cv2.imwrite(str(target), preview)
    scene.detection_preview_url = f"/api/v1/projects/{scene.project_id}/files/working/{target.name}"
    return scene
