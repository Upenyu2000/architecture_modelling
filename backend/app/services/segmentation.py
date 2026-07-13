from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ..config import load_settings


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
        mean=(0.485, 0.456, 0.406),
        swapRB=True,
        crop=False,
    )
    # Match common ImageNet normalization while remaining compatible with simple 0..1 exports.
    blob[:, 0] /= 0.229
    blob[:, 1] /= 0.224
    blob[:, 2] /= 0.225
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
    # Single-channel exports are interpreted as wall/background.
    if len(labels) == 1 or (set(masks) <= {"background", "wall"} and "wall" not in masks and 1 in np.unique(classes)):
        masks["wall"] = (classes == 1).astype(np.uint8) * 255
    return SemanticPrediction(
        masks=masks,
        confidences=confidences,
        model_path=str(model_path),
        input_size=input_size,
    )
