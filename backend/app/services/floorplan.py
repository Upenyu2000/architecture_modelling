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


def _merge_lines(lines: list[tuple[int, int, int, int]], tolerance: int = 10, gap: int = 18) -> list[tuple[int, int, int, int]]:
    horizontal: list[list[int]] = []
    vertical: list[list[int]] = []
    for x1, y1, x2, y2 in lines:
        if abs(y2 - y1) <= max(2, abs(x2 - x1) * 0.12):
            y = round((y1 + y2) / 2)
            horizontal.append([min(x1, x2), y, max(x1, x2), y])
        elif abs(x2 - x1) <= max(2, abs(y2 - y1) * 0.12):
            x = round((x1 + x2) / 2)
            vertical.append([x, min(y1, y2), x, max(y1, y2)])

    def merge_axis(items: list[list[int]], horizontal_axis: bool) -> list[tuple[int, int, int, int]]:
        result: list[list[int]] = []
        items.sort(key=lambda item: (item[1] if horizontal_axis else item[0], item[0] if horizontal_axis else item[1]))
        for item in items:
            match: list[int] | None = None
            for previous in reversed(result[-12:]):
                same_axis = abs((item[1] if horizontal_axis else item[0]) - (previous[1] if horizontal_axis else previous[0])) <= tolerance
                if not same_axis:
                    continue
                if horizontal_axis:
                    overlaps = item[0] <= previous[2] + gap and item[2] >= previous[0] - gap
                else:
                    overlaps = item[1] <= previous[3] + gap and item[3] >= previous[1] - gap
                if overlaps:
                    match = previous
                    break
            if match is None:
                result.append(item)
                continue
            if horizontal_axis:
                match[0] = min(match[0], item[0])
                match[2] = max(match[2], item[2])
                match[1] = match[3] = round((match[1] + item[1]) / 2)
            else:
                match[1] = min(match[1], item[1])
                match[3] = max(match[3], item[3])
                match[0] = match[2] = round((match[0] + item[0]) / 2)
        return [tuple(item) for item in result]

    return merge_axis(horizontal, True) + merge_axis(vertical, False)


def _component_centerlines(mask: np.ndarray, orientation: str, minimum_length_px: int) -> list[tuple[tuple[int, int, int, int], int]]:
    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    components: list[tuple[tuple[int, int, int, int], int]] = []
    for index in range(1, count):
        x, y, width, height, area = [int(value) for value in stats[index]]
        if area <= 0:
            continue
        if orientation == "horizontal":
            if width < minimum_length_px or width < max(8, height * 2):
                continue
            centre = int(round(float(centroids[index][1])))
            components.append(((x, centre, x + width - 1, centre), max(1, height)))
        else:
            if height < minimum_length_px or height < max(8, width * 2):
                continue
            centre = int(round(float(centroids[index][0])))
            components.append(((centre, y, centre, y + height - 1), max(1, width)))
    return components


def _touches_other(line: tuple[int, int, int, int], other: tuple[int, int, int, int], tolerance: int) -> bool:
    x1, y1, x2, y2 = line
    a1, b1, a2, b2 = other
    line_horizontal = abs(y2 - y1) <= abs(x2 - x1)
    other_horizontal = abs(b2 - b1) <= abs(a2 - a1)
    if line_horizontal != other_horizontal:
        horizontal = line if line_horizontal else other
        vertical = other if line_horizontal else line
        hx1, hy, hx2, _ = horizontal
        vx, vy1, _, vy2 = vertical
        return hx1 - tolerance <= vx <= hx2 + tolerance and vy1 - tolerance <= hy <= vy2 + tolerance

    endpoints = ((x1, y1), (x2, y2))
    other_endpoints = ((a1, b1), (a2, b2))
    return any(math.hypot(px - qx, py - qy) <= tolerance for px, py in endpoints for qx, qy in other_endpoints)


def _filter_structural_lines(
    lines: list[tuple[int, int, int, int]],
    minimum_length_px: int,
    detail: str,
    connection_tolerance: int,
) -> list[tuple[int, int, int, int]]:
    if detail == "detailed":
        return lines
    long_multiplier = 2.1 if detail == "clean" else 1.6
    retained: list[tuple[int, int, int, int]] = []
    for index, line in enumerate(lines):
        x1, y1, x2, y2 = line
        length = math.hypot(x2 - x1, y2 - y1)
        connected = any(
            _touches_other(line, other, connection_tolerance)
            for other_index, other in enumerate(lines)
            if other_index != index
        )
        if length >= minimum_length_px * long_multiplier or connected:
            retained.append(line)
    return retained


def _detect_rooms(wall_mask: np.ndarray, metres_per_pixel: float) -> list[RoomShape]:
    height, width = wall_mask.shape
    free_space = cv2.bitwise_not(wall_mask)
    flood = free_space.copy()
    mask = np.zeros((height + 2, width + 2), np.uint8)
    cv2.floodFill(flood, mask, (0, 0), 0)
    contours, _ = cv2.findContours(flood, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    minimum_area = width * height * 0.009
    maximum_area = width * height * 0.72
    rooms: list[RoomShape] = []
    for contour in contours:
        area_px = cv2.contourArea(contour)
        if area_px < minimum_area or area_px > maximum_area:
            continue
        epsilon = 0.014 * cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, epsilon, True).reshape(-1, 2)
        if len(polygon) < 3:
            continue
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue
        cx = moments["m10"] / moments["m00"]
        cy = moments["m01"] / moments["m00"]
        metres_polygon = [
            (round(float(x) * metres_per_pixel, 3), round(float(y) * metres_per_pixel, 3))
            for x, y in polygon
        ]
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
    return rooms[:30]


def _save_detection_preview(
    source: np.ndarray,
    destination: Path,
    lines: list[tuple[int, int, int, int]],
    rooms: list[RoomShape],
    metres_per_pixel: float,
) -> None:
    overlay = source.copy()
    for x1, y1, x2, y2 in lines:
        cv2.line(overlay, (x1, y1), (x2, y2), (45, 190, 90), 3, cv2.LINE_AA)
    for room in rooms:
        points = np.array([
            [round(x / metres_per_pixel), round(y / metres_per_pixel)]
            for x, y in room.polygon
        ], dtype=np.int32)
        if len(points) >= 3:
            cv2.polylines(overlay, [points], True, (235, 145, 40), 2, cv2.LINE_AA)
            cx = round(room.centroid[0] / metres_per_pixel)
            cy = round(room.centroid[1] / metres_per_pixel)
            cv2.putText(overlay, room.name, (cx - 22, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (235, 145, 40), 1, cv2.LINE_AA)
    destination.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(destination), overlay)


def analyze_floorplan(project_id: str, image_path: Path, request: AnalyzeRequest) -> SceneManifest:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The floor plan could not be decoded.")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, dark_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)

    height, width = gray.shape
    minimum_dimension = min(width, height)
    metres_per_pixel = request.plan_width_m / width
    depth_m = height * metres_per_pixel

    detail_config = {
        "clean": (0.040, 0.075),
        "balanced": (0.028, 0.055),
        "detailed": (0.018, 0.038),
    }
    kernel_factor, length_factor = detail_config[request.wall_detection]
    directional_length = max(11, int(minimum_dimension * kernel_factor))
    minimum_length_px = max(
        int(request.minimum_wall_length_m / metres_per_pixel),
        int(minimum_dimension * length_factor),
        18,
    )

    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (directional_length, 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, directional_length))
    horizontal_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, horizontal_kernel)
    vertical_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, vertical_kernel)

    bridge = max(3, directional_length // 5)
    horizontal_mask = cv2.morphologyEx(
        horizontal_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (bridge, 3)),
    )
    vertical_mask = cv2.morphologyEx(
        vertical_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (3, bridge)),
    )

    horizontal_components = _component_centerlines(horizontal_mask, "horizontal", minimum_length_px)
    vertical_components = _component_centerlines(vertical_mask, "vertical", minimum_length_px)
    components = horizontal_components + vertical_components
    component_thicknesses = [thickness for _line, thickness in components]
    estimated_thickness_px = int(np.percentile(component_thicknesses, 65)) if component_thicknesses else 5
    thickness_ratio = {"clean": 0.35, "balanced": 0.22, "detailed": 0.0}[request.wall_detection]
    minimum_component_thickness = max(2, int(round(estimated_thickness_px * thickness_ratio)))
    raw_lines = [line for line, thickness in components if thickness >= minimum_component_thickness]
    merge_tolerance = max(4, min(18, estimated_thickness_px // 2 + 2))
    merged = _merge_lines(raw_lines, tolerance=merge_tolerance, gap=max(8, int(minimum_dimension * 0.014)))
    merged = _filter_structural_lines(
        merged,
        minimum_length_px,
        request.wall_detection,
        connection_tolerance=max(8, estimated_thickness_px * 2),
    )

    walls: list[WallSegment] = []
    for x1, y1, x2, y2 in merged:
        length_m = math.hypot(x2 - x1, y2 - y1) * metres_per_pixel
        if length_m < request.minimum_wall_length_m:
            continue
        walls.append(WallSegment(
            id=f"wall-{uuid.uuid4().hex[:8]}",
            start=(round(x1 * metres_per_pixel, 3), round(y1 * metres_per_pixel, 3)),
            end=(round(x2 * metres_per_pixel, 3), round(y2 * metres_per_pixel, 3)),
            height=request.wall_height_m,
            thickness=request.wall_thickness_m,
        ))

    # Rebuild a clean room mask from the accepted centre lines. This prevents text,
    # furniture symbols and the two edges of a thick wall from becoming extra walls.
    wall_width_px = max(3, int(round(request.wall_thickness_m / metres_per_pixel)))
    door_gap_px = max(5, min(int(round(1.15 / metres_per_pixel)), int(minimum_dimension * 0.12)))
    room_lines = _merge_lines(
        merged,
        tolerance=max(4, wall_width_px),
        gap=door_gap_px,
    )
    horizontal_room_mask = np.zeros_like(gray)
    vertical_room_mask = np.zeros_like(gray)
    for x1, y1, x2, y2 in room_lines:
        if abs(y2 - y1) <= abs(x2 - x1):
            cv2.line(horizontal_room_mask, (x1, y1), (x2, y2), 255, wall_width_px)
        else:
            cv2.line(vertical_room_mask, (x1, y1), (x2, y2), 255, wall_width_px)

    horizontal_room_mask = cv2.morphologyEx(
        horizontal_room_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (door_gap_px, max(3, wall_width_px))),
    )
    vertical_room_mask = cv2.morphologyEx(
        vertical_room_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, wall_width_px), door_gap_px)),
    )
    room_mask = cv2.bitwise_or(horizontal_room_mask, vertical_room_mask)
    junction_kernel = max(3, min(17, wall_width_px + 3))
    room_mask = cv2.morphologyEx(
        room_mask, cv2.MORPH_CLOSE, np.ones((junction_kernel, junction_kernel), np.uint8), iterations=1
    )
    rooms = _detect_rooms(room_mask, metres_per_pixel)

    preview_path = image_path.parent / "structure-preview.png"
    _save_detection_preview(image, preview_path, merged, rooms, metres_per_pixel)

    warnings: list[str] = []
    if not walls:
        warnings.append("No reliable structural walls were detected. Try Balanced or Detailed mode, or upload a higher-contrast plan.")
    if not rooms:
        warnings.append("No closed room regions were detected. Check the structure overlay and plan scale.")
    if len(walls) > 180:
        warnings.append("A high wall count remains. Switch to Clean mode or increase the minimum wall length.")
    warnings.append("Green lines in the structure overlay are the exact wall centre lines used for the 3D model.")

    return SceneManifest(
        project_id=project_id,
        width_m=round(request.plan_width_m, 3),
        depth_m=round(depth_m, 3),
        wall_height_m=request.wall_height_m,
        walls=walls[:240],
        rooms=rooms,
        assets=[],
        camera_path=[],
        detection_preview_url=f"/api/v1/projects/{project_id}/files/working/structure-preview.png",
        wall_detection_mode=request.wall_detection,
        warnings=warnings,
    )
