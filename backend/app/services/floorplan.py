from __future__ import annotations

import math
import uuid
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import pypdfium2 as pdfium

from ..models import AnalyzeRequest, RoomShape, SceneManifest, WallSegment


def rasterize_floorplan(source: Path, destination: Path) -> Path:
    suffix = source.suffix.lower()
    if suffix == ".pdf":
        pdf = pdfium.PdfDocument(str(source))
        if len(pdf) == 0:
            raise ValueError("The uploaded PDF has no pages.")
        bitmap = pdf[0].render(scale=2.0)
        image = bitmap.to_pil().convert("RGB")
        image.save(destination, "PNG")
        return destination
    image = Image.open(source).convert("RGB")
    image.thumbnail((5000, 5000))
    image.save(destination, "PNG")
    return destination


def _merge_lines(lines: list[tuple[int, int, int, int]], tolerance: int = 12) -> list[tuple[int, int, int, int]]:
    horizontal: list[list[int]] = []
    vertical: list[list[int]] = []
    for x1, y1, x2, y2 in lines:
        if abs(y2 - y1) <= abs(x2 - x1) * 0.2:
            y = round((y1 + y2) / 2)
            horizontal.append([min(x1, x2), y, max(x1, x2), y])
        elif abs(x2 - x1) <= abs(y2 - y1) * 0.2:
            x = round((x1 + x2) / 2)
            vertical.append([x, min(y1, y2), x, max(y1, y2)])

    def merge_axis(items: list[list[int]], horizontal_axis: bool) -> list[tuple[int, int, int, int]]:
        result: list[list[int]] = []
        items.sort(key=lambda item: (item[1] if horizontal_axis else item[0], item[0] if horizontal_axis else item[1]))
        for item in items:
            if not result:
                result.append(item)
                continue
            previous = result[-1]
            same_axis = abs((item[1] if horizontal_axis else item[0]) - (previous[1] if horizontal_axis else previous[0])) <= tolerance
            if horizontal_axis:
                overlaps = item[0] <= previous[2] + tolerance * 2
                if same_axis and overlaps:
                    previous[0] = min(previous[0], item[0]); previous[2] = max(previous[2], item[2]); previous[1] = previous[3] = round((previous[1] + item[1]) / 2)
                else: result.append(item)
            else:
                overlaps = item[1] <= previous[3] + tolerance * 2
                if same_axis and overlaps:
                    previous[1] = min(previous[1], item[1]); previous[3] = max(previous[3], item[3]); previous[0] = previous[2] = round((previous[0] + item[0]) / 2)
                else: result.append(item)
        return [tuple(item) for item in result]

    return merge_axis(horizontal, True) + merge_axis(vertical, False)


def _detect_rooms(wall_mask: np.ndarray, metres_per_pixel: float) -> list[RoomShape]:
    height, width = wall_mask.shape
    closed = cv2.morphologyEx(wall_mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2)
    free_space = cv2.bitwise_not(closed)
    flood = free_space.copy()
    mask = np.zeros((height + 2, width + 2), np.uint8)
    cv2.floodFill(flood, mask, (0, 0), 0)
    contours, _ = cv2.findContours(flood, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    minimum_area = width * height * 0.006
    rooms: list[RoomShape] = []
    for contour in contours:
        area_px = cv2.contourArea(contour)
        if area_px < minimum_area:
            continue
        epsilon = 0.012 * cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
        if len(polygon) < 3:
            continue
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue
        cx = moments["m10"] / moments["m00"]
        cy = moments["m01"] / moments["m00"]
        metres_polygon = [(round(float(x) * metres_per_pixel, 3), round(float(y) * metres_per_pixel, 3)) for x, y in polygon]
        rooms.append(RoomShape(
            id=f"room-{uuid.uuid4().hex[:8]}",
            name="",
            polygon=metres_polygon,
            area_m2=round(area_px * metres_per_pixel * metres_per_pixel, 2),
            centroid=(round(cx * metres_per_pixel, 3), round(cy * metres_per_pixel, 3)),
        ))
    rooms.sort(key=lambda room: (-room.area_m2, room.centroid[1], room.centroid[0]))
    for index, room in enumerate(rooms, 1):
        room.name = f"Room {index}"
    return rooms[:40]


def analyze_floorplan(project_id: str, image_path: Path, request: AnalyzeRequest) -> SceneManifest:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The floor plan could not be decoded.")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, wall_mask = cv2.threshold(gray, 190, 255, cv2.THRESH_BINARY_INV)
    wall_mask = cv2.morphologyEx(wall_mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)

    height, width = gray.shape
    metres_per_pixel = request.plan_width_m / width
    depth_m = height * metres_per_pixel
    edges = cv2.Canny(gray, 45, 150, apertureSize=3)
    raw = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=max(35, int(min(width, height) * 0.04)),
        minLineLength=max(35, int(min(width, height) * 0.07)),
        maxLineGap=max(8, int(min(width, height) * 0.015)),
    )
    raw_lines = [tuple(map(int, line[0])) for line in raw] if raw is not None else []
    merged = _merge_lines(raw_lines, tolerance=max(8, int(min(width, height) * 0.008)))
    walls: list[WallSegment] = []
    for x1, y1, x2, y2 in merged:
        length_m = math.hypot(x2 - x1, y2 - y1) * metres_per_pixel
        if length_m < 0.7:
            continue
        walls.append(WallSegment(
            id=f"wall-{uuid.uuid4().hex[:8]}",
            start=(round(x1 * metres_per_pixel, 3), round(y1 * metres_per_pixel, 3)),
            end=(round(x2 * metres_per_pixel, 3), round(y2 * metres_per_pixel, 3)),
            height=request.wall_height_m,
            thickness=request.wall_thickness_m,
        ))
    rooms = _detect_rooms(wall_mask, metres_per_pixel)
    warnings: list[str] = []
    if not walls:
        warnings.append("No reliable wall lines were detected. Use a high-contrast blueprint or enable the optional YOLO model.")
    if not rooms:
        warnings.append("No closed room regions were detected. The scene contains walls only.")
    warnings.append("Review the scale and room names before a final architectural render; automatic blueprint extraction is probabilistic.")
    return SceneManifest(
        project_id=project_id,
        width_m=round(request.plan_width_m, 3),
        depth_m=round(depth_m, 3),
        wall_height_m=request.wall_height_m,
        walls=walls[:600],
        rooms=rooms,
        assets=[],
        camera_path=[],
        warnings=warnings,
    )
