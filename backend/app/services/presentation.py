from __future__ import annotations

from copy import deepcopy
from math import hypot
from typing import Any

from ..models import SceneManifest


def _material(
    name: str,
    material_type: str,
    colour: str,
    roughness: float,
    metallic: float = 0.0,
    specular: float = 0.45,
    texture_scale: float = 1.0,
) -> dict[str, Any]:
    return {
        "name": name,
        "material_type": material_type,
        "hex_color": colour,
        "roughness": roughness,
        "metallic": metallic,
        "specular": specular,
        "texture_scale": texture_scale,
    }


def _preset(
    label: str,
    floor: tuple[str, str, str, float],
    walls: tuple[str, str, str, float],
    exterior: tuple[str, str, str, float],
    accent: tuple[str, str, str, float],
    furniture_material: str,
    furniture_colour: str,
    world_colour: str,
    daylight_strength: float,
    warm_light: str,
    exposure: float,
    lens: float,
    decor_density: float = 0.55,
) -> dict[str, Any]:
    return {
        "label": label,
        "floor": _material(*floor),
        "walls": _material(*walls),
        "exterior": _material(*exterior),
        "accent": _material(*accent),
        "metal": _material("Architectural metal", "metal", "#A5A7AA", 0.24, 0.82, 0.75, 1.0),
        "furniture_material": furniture_material,
        "furniture_colour": furniture_colour,
        "world_colour": world_colour,
        "daylight_strength": daylight_strength,
        "warm_light": warm_light,
        "exposure": exposure,
        "lens": lens,
        "decor_density": decor_density,
    }


STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "modern": _preset(
        "Modern",
        ("Natural oak", "wood", "#B58A5A", 0.42),
        ("Warm architectural white", "plaster", "#EEEAE2", 0.76),
        ("Pale concrete", "concrete", "#A8AAA6", 0.82),
        ("Charcoal graphite", "painted_metal", "#32383A", 0.38),
        "fabric", "#66756D", "#C8D6DF", 1.0, "#FFD8AA", 0.35, 27.0,
    ),
    "contemporary": _preset(
        "Contemporary",
        ("Smoked oak", "wood", "#8B6C50", 0.38),
        ("Layered greige", "plaster", "#DDD8D0", 0.72),
        ("Textured mineral render", "stone", "#8C918E", 0.78),
        ("Sculptural bronze", "metal", "#8A6C4B", 0.3),
        "fabric", "#5E6A73", "#BBC9D2", 0.95, "#FFD1A1", 0.42, 28.0,
    ),
    "farmhouse": _preset(
        "Farmhouse",
        ("Wide plank oak", "wood", "#A8794C", 0.5),
        ("Milk paint white", "plaster", "#F3EFE5", 0.84),
        ("Limewashed masonry", "brick", "#C8BCA8", 0.9),
        ("Sage cabinetry", "painted_metal", "#71806B", 0.55),
        "linen", "#B8AA92", "#D9E1DF", 0.92, "#FFD0A0", 0.28, 30.0,
    ),
    "mediterranean": _preset(
        "Mediterranean",
        ("Terracotta tile", "tile", "#B8663E", 0.67),
        ("Sun-washed lime plaster", "plaster", "#EADCC4", 0.9),
        ("Honey limestone", "stone", "#C2A77E", 0.88),
        ("Aegean blue", "paint", "#315D73", 0.56),
        "linen", "#B6825B", "#BFD6E3", 1.05, "#FFC788", 0.5, 30.0,
    ),
    "scandinavian": _preset(
        "Scandinavian",
        ("Whitewashed ash", "wood", "#D5C7AD", 0.52),
        ("Soft Nordic white", "plaster", "#F4F1E9", 0.86),
        ("Pale timber cladding", "wood", "#B7A98D", 0.72),
        ("Muted fjord blue", "paint", "#617B84", 0.62),
        "fabric", "#B8B2A5", "#D8E4E9", 1.12, "#FFE0B8", 0.48, 29.0,
    ),
    "industrial": _preset(
        "Industrial",
        ("Polished concrete", "concrete", "#777A78", 0.48),
        ("Raw plaster", "plaster", "#B7B4AD", 0.78),
        ("Weathered brick", "brick", "#774D3D", 0.88),
        ("Blackened steel", "metal", "#282C2E", 0.27),
        "leather", "#5A3C2C", "#8393A0", 0.8, "#F3B36B", 0.18, 26.0, 0.42,
    ),
    "traditional": _preset(
        "Traditional",
        ("Classic walnut", "wood", "#765035", 0.44),
        ("Ivory wall finish", "plaster", "#E8DDC8", 0.78),
        ("Warm dressed stone", "stone", "#9E8A72", 0.86),
        ("Deep heritage green", "paint", "#394E3E", 0.5),
        "velvet", "#6D5448", "#CAD4D7", 0.86, "#FFD09A", 0.3, 32.0,
    ),
    "craftsman": _preset(
        "Craftsman",
        ("Quarter-sawn oak", "wood", "#805A38", 0.46),
        ("Warm putty plaster", "plaster", "#D8C7AA", 0.84),
        ("River stone", "stone", "#81776A", 0.92),
        ("Forest green", "paint", "#344A38", 0.56),
        "leather", "#79543A", "#BEC9C8", 0.82, "#FFCA8A", 0.22, 31.0,
    ),
    "colonial": _preset(
        "Colonial",
        ("Mahogany boards", "wood", "#68412E", 0.4),
        ("Colonial cream", "plaster", "#EADFCB", 0.82),
        ("Painted masonry", "brick", "#C7C0B2", 0.86),
        ("Federal blue", "paint", "#435B72", 0.46),
        "fabric", "#7D6B57", "#C7D3DA", 0.88, "#FFD09A", 0.27, 33.0,
    ),
    "ranch": _preset(
        "Ranch",
        ("Honey oak", "wood", "#9B7046", 0.5),
        ("Desert neutral", "plaster", "#DFD1BA", 0.84),
        ("Stacked fieldstone", "stone", "#8B7D68", 0.9),
        ("Burnt sienna", "paint", "#9B5540", 0.58),
        "leather", "#78604E", "#BED0D8", 0.9, "#FFC98B", 0.25, 29.0,
    ),
    "cape_cod": _preset(
        "Cape Cod",
        ("Weathered light oak", "wood", "#C7B79B", 0.58),
        ("Crisp coastal white", "plaster", "#F2F1EA", 0.88),
        ("Silvered shingle", "wood", "#939994", 0.84),
        ("Atlantic navy", "paint", "#304C65", 0.52),
        "linen", "#B9C8CC", "#D8E7ED", 1.08, "#FFDEB0", 0.46, 31.0,
    ),
    "tudor": _preset(
        "Tudor",
        ("Dark oak boards", "wood", "#523725", 0.42),
        ("Hand-trowelled plaster", "plaster", "#D8C9AD", 0.9),
        ("Old English brick", "brick", "#68483B", 0.94),
        ("Oxblood red", "paint", "#673A35", 0.5),
        "velvet", "#665344", "#9FAAB0", 0.72, "#F6B96E", 0.08, 34.0, 0.48,
    ),
    "victorian": _preset(
        "Victorian",
        ("Polished walnut parquet", "wood", "#6B452E", 0.32),
        ("Decorative warm ivory", "plaster", "#DED0BA", 0.74),
        ("Patterned brick", "brick", "#765044", 0.88),
        ("Jewel teal", "paint", "#315D5B", 0.4),
        "velvet", "#6F4D66", "#BCC7D0", 0.78, "#FFC27C", 0.2, 35.0, 0.72,
    ),
    "spanish": _preset(
        "Spanish",
        ("Saltillo terracotta", "tile", "#A95738", 0.72),
        ("Limewashed white", "plaster", "#E9DEC7", 0.92),
        ("White stucco", "plaster", "#D8CDBB", 0.9),
        ("Wrought iron", "metal", "#2F302E", 0.34),
        "leather", "#8C5E42", "#C2D5DE", 1.0, "#FFC27A", 0.4, 30.0,
    ),
    "minimalist": _preset(
        "Minimalist",
        ("Seamless pale oak", "wood", "#C9B99B", 0.48),
        ("Gallery white", "plaster", "#F2F0EA", 0.88),
        ("Monolithic concrete", "concrete", "#A6A7A4", 0.78),
        ("Ink black", "paint", "#25282A", 0.42),
        "fabric", "#B0ACA3", "#D7E0E4", 1.03, "#FFE1B6", 0.45, 27.0, 0.15,
    ),
    "transitional": _preset(
        "Transitional",
        ("Medium oak", "wood", "#9B7755", 0.44),
        ("Soft greige", "plaster", "#E1DAD0", 0.8),
        ("Smooth limestone", "stone", "#AAA092", 0.84),
        ("Smoky blue", "paint", "#5F7180", 0.5),
        "fabric", "#8A8179", "#CBD7DC", 0.94, "#FFD3A0", 0.36, 30.0,
    ),
    "coastal": _preset(
        "Coastal",
        ("Bleached oak", "wood", "#D2C4AA", 0.56),
        ("Sea-salt white", "plaster", "#F0F2ED", 0.9),
        ("Sandstone render", "stone", "#C8BBA3", 0.9),
        ("Ocean blue", "paint", "#4E7890", 0.56),
        "linen", "#B8CACB", "#D8EAF1", 1.16, "#FFE0B2", 0.52, 28.0,
    ),
    "midcentury_modern": _preset(
        "Mid-century Modern",
        ("Warm walnut", "wood", "#704B32", 0.38),
        ("Soft parchment", "plaster", "#DDD1BC", 0.78),
        ("Roman brick", "brick", "#8B5D47", 0.88),
        ("Mustard accent", "paint", "#B58131", 0.48),
        "fabric", "#7A755F", "#C6D5DB", 0.92, "#FFC88E", 0.34, 27.0,
    ),
    "neo_classical": _preset(
        "Neo-classical",
        ("Pale stone parquet", "wood", "#B9A98F", 0.36),
        ("Chalk white", "plaster", "#EEE9DF", 0.76),
        ("Limestone ashlar", "stone", "#B6AD9F", 0.78),
        ("Antique brass", "metal", "#9A7A45", 0.25),
        "velvet", "#777080", "#CCD3D7", 0.96, "#FFD2A0", 0.38, 35.0, 0.68,
    ),
}


def available_styles() -> list[dict[str, str]]:
    return [{"value": key, "label": value["label"]} for key, value in STYLE_PRESETS.items()]


def _bbox(room: dict[str, Any]) -> tuple[float, float, float, float]:
    points = list(room.get("polygon") or [])
    xs = [float(point[0]) for point in points]
    zs = [float(point[1]) for point in points]
    if not xs or not zs:
        cx, cz = map(float, room.get("centroid") or (0.0, 0.0))
        return cx - 0.5, cx + 0.5, cz - 0.5, cz + 0.5
    return min(xs), max(xs), min(zs), max(zs)


def _point_in_polygon(point: tuple[float, float], polygon: list[list[float]] | list[tuple[float, float]]) -> bool:
    x, z = point
    inside = False
    previous = len(polygon) - 1
    for index, current in enumerate(polygon):
        xi, zi = map(float, current)
        xj, zj = map(float, polygon[previous])
        crosses = (zi > z) != (zj > z) and x < ((xj - xi) * (z - zi)) / ((zj - zi) or 1e-9) + xi
        if crosses:
            inside = not inside
        previous = index
    return inside


def _room_kind(room: dict[str, Any]) -> str:
    value = f'{room.get("name", "")} {room.get("room_type", "")}'.lower().replace("-", " ")
    if any(token in value for token in ("dining", "breakfast")):
        return "dining"
    if any(token in value for token in ("living", "lounge", "family", "great room", "sitting")):
        return "living"
    if any(token in value for token in ("bed", "master", "guest")):
        return "bedroom"
    if any(token in value for token in ("kitchen", "galley")):
        return "kitchen"
    if any(token in value for token in ("bath", "shower", "wc", "toilet", "ensuite")):
        return "bathroom"
    if any(token in value for token in ("office", "study", "library")):
        return "office"
    return "other"


def _material_for_object(object_type: str, preset: dict[str, Any]) -> tuple[str, str]:
    if object_type in {"dining_table", "coffee_table", "desk", "sideboard", "tv_unit", "wardrobe", "cabinetry", "nightstand", "dresser", "shelving"}:
        return "walnut" if preset["floor"]["hex_color"].lower() < "#900000" else "oak", preset["floor"]["hex_color"]
    if object_type in {"countertop", "kitchen_island"}:
        return "stone", preset["walls"]["hex_color"]
    if object_type in {"fridge", "stove", "washing_machine", "dryer"}:
        return "painted_metal", preset["metal"]["hex_color"]
    if object_type in {"toilet", "sink", "bathtub"}:
        return "porcelain", "#F0F0EB"
    if object_type in {"planter"}:
        return "stone", preset["accent"]["hex_color"]
    return preset["furniture_material"] if preset["furniture_material"] in {"fabric", "leather", "oak", "walnut", "stone", "porcelain", "chrome", "painted_metal"} else "fabric", preset["furniture_colour"]


def _styled_asset_id(item: dict[str, Any], style: str, preset: dict[str, Any]) -> str:
    object_type = str(item.get("object_type") or "furniture")
    existing = str(item.get("asset_id") or "").split("|")
    reference_key = existing[4] if len(existing) > 4 else ""
    material_type, colour = _material_for_object(object_type, preset)
    return "|".join((object_type, style, material_type, colour, reference_key))


def _new_object(
    room: dict[str, Any],
    object_type: str,
    index: int,
    position: tuple[float, float],
    size: tuple[float, float, float],
    rotation: float,
    style: str,
    preset: dict[str, Any],
    category: str = "furniture",
) -> dict[str, Any]:
    item = {
        "id": f'presentation-{room.get("id", "room")}-{object_type}-{index}',
        "object_type": object_type,
        "asset_id": "",
        "category": category,
        "room_id": room.get("id"),
        "coordinates": [round(position[0], 4), 0.0, round(position[1], 4)],
        "rotation_deg": rotation,
        "scale": [1.0, 1.0, 1.0],
        "size": [round(size[0], 4), round(size[1], 4), round(size[2], 4)],
        "source": "room_inference",
        "confidence": 0.82,
    }
    item["asset_id"] = _styled_asset_id(item, style, preset)
    return item


def _existing_types(fixtures: list[dict[str, Any]], room_id: str) -> set[str]:
    return {
        str(item.get("object_type") or "").lower()
        for item in fixtures
        if str(item.get("room_id") or "") == room_id
    }


def _safe_room_position(room: dict[str, Any], x_ratio: float, z_ratio: float) -> tuple[float, float]:
    min_x, max_x, min_z, max_z = _bbox(room)
    candidate = (min_x + (max_x - min_x) * x_ratio, min_z + (max_z - min_z) * z_ratio)
    polygon = list(room.get("polygon") or [])
    if polygon and _point_in_polygon(candidate, polygon):
        return candidate
    return tuple(map(float, room.get("centroid") or candidate))


def _auto_furnish(
    rooms: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    style: str,
    preset: dict[str, Any],
) -> int:
    added = 0
    for room in rooms:
        room_id = str(room.get("id") or "")
        kind = _room_kind(room)
        min_x, max_x, min_z, max_z = _bbox(room)
        width = max_x - min_x
        depth = max_z - min_z
        if width < 1.25 or depth < 1.25:
            continue
        types = _existing_types(fixtures, room_id)
        centre = tuple(map(float, room.get("centroid") or ((min_x + max_x) / 2, (min_z + max_z) / 2)))
        long_rotation = 0.0 if width >= depth else 90.0

        def add(object_type: str, position: tuple[float, float], size: tuple[float, float, float], rotation: float = 0.0, category: str = "furniture") -> None:
            nonlocal added
            fixtures.append(_new_object(room, object_type, added, position, size, rotation, style, preset, category))
            types.add(object_type)
            added += 1

        if kind == "bedroom" and "bed" not in types:
            add("bed", centre, (min(1.85, width - 0.7), 0.72, min(2.15, depth - 0.7)), long_rotation)
            if width > 3.0 and "nightstand" not in types:
                add("nightstand", _safe_room_position(room, 0.2, 0.2), (0.52, 0.62, 0.46), 0.0)
        elif kind == "living":
            if not types.intersection({"sofa", "couch", "sectional_sofa"}):
                add("sofa", _safe_room_position(room, 0.5, 0.72), (min(2.6, width - 0.7), 0.9, 0.95), 0.0)
            if "coffee_table" not in types and min(width, depth) > 2.4:
                add("coffee_table", _safe_room_position(room, 0.5, 0.45), (1.15, 0.48, 0.68), 0.0)
            if "tv_unit" not in types and width > 2.7:
                add("tv_unit", _safe_room_position(room, 0.5, 0.14), (min(1.8, width - 0.9), 0.58, 0.42), 0.0)
            if preset["decor_density"] > 0.25 and "planter" not in types:
                add("planter", _safe_room_position(room, 0.84, 0.18), (0.52, 1.25, 0.52), 0.0)
        elif kind == "kitchen":
            if "countertop" not in types and "cabinetry" not in types:
                add("countertop", _safe_room_position(room, 0.5, 0.16), (max(1.3, width - 0.8), 0.92, 0.62), 0.0)
            if "fridge" not in types:
                add("fridge", _safe_room_position(room, 0.16, 0.18), (0.78, 1.9, 0.72), 0.0, "utility")
            if "stove" not in types:
                add("stove", _safe_room_position(room, 0.72, 0.17), (0.72, 0.92, 0.68), 0.0, "utility")
            if width > 3.4 and depth > 3.2 and "kitchen_island" not in types:
                add("kitchen_island", centre, (min(2.0, width - 1.8), 0.96, min(0.9, depth - 1.8)), long_rotation)
        elif kind == "bathroom":
            if "toilet" not in types:
                add("toilet", _safe_room_position(room, 0.22, 0.24), (0.68, 0.82, 0.78), 0.0, "fixture")
            if "sink" not in types:
                add("sink", _safe_room_position(room, 0.72, 0.22), (0.68, 0.9, 0.55), 0.0, "fixture")
            if width > 2.1 and depth > 2.0 and "bathtub" not in types:
                add("bathtub", _safe_room_position(room, 0.5, 0.75), (min(1.75, width - 0.5), 0.62, 0.82), 0.0, "fixture")
        elif kind == "office":
            if "desk" not in types:
                add("desk", _safe_room_position(room, 0.5, 0.24), (min(1.5, width - 0.7), 0.78, 0.7), 0.0)
            if "office_chair" not in types:
                add("office_chair", _safe_room_position(room, 0.5, 0.48), (0.7, 1.0, 0.72), 180.0)
    return added


def _optimise_dining(
    rooms: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    openings: list[dict[str, Any]],
    style: str,
    preset: dict[str, Any],
    auto_furnish: bool,
) -> tuple[bool, int]:
    adjusted = False
    added = 0
    for room in rooms:
        if _room_kind(room) != "dining":
            continue
        room_id = str(room.get("id") or "")
        min_x, max_x, min_z, max_z = _bbox(room)
        width = max_x - min_x
        depth = max_z - min_z
        if width < 1.8 or depth < 1.8:
            continue
        table = next((item for item in fixtures if item.get("room_id") == room_id and item.get("object_type") == "dining_table"), None)
        if table is None and auto_furnish:
            table = _new_object(room, "dining_table", added, tuple(map(float, room.get("centroid") or ((min_x + max_x) / 2, (min_z + max_z) / 2))), (1.6, 0.78, 0.9), 0.0, style, preset)
            fixtures.append(table)
            added += 1

        if table is None:
            continue

        clearance = 0.9 if min(width, depth) >= 3.0 else max(0.62, min(width, depth) * 0.22)
        available_x = max(0.9, width - clearance * 2)
        available_z = max(0.72, depth - clearance * 2)
        if width >= depth:
            table_size = (min(2.35, available_x), 0.78, min(1.05, available_z))
        else:
            table_size = (min(1.05, available_x), 0.78, min(2.35, available_z))

        centre_x, centre_z = map(float, room.get("centroid") or ((min_x + max_x) / 2, (min_z + max_z) / 2))
        linked_openings = [opening for opening in openings if room_id in (opening.get("room_ids") or [])]
        if linked_openings:
            nearest = min(linked_openings, key=lambda opening: hypot(float(opening.get("position", [centre_x, centre_z])[0]) - centre_x, float(opening.get("position", [centre_x, centre_z])[1]) - centre_z))
            ox, oz = map(float, nearest.get("position") or (centre_x, centre_z))
            dx, dz = centre_x - ox, centre_z - oz
            distance = max(0.001, hypot(dx, dz))
            centre_x += dx / distance * min(0.35, width * 0.08)
            centre_z += dz / distance * min(0.35, depth * 0.08)

        centre_x = min(max(centre_x, min_x + clearance), max_x - clearance)
        centre_z = min(max(centre_z, min_z + clearance), max_z - clearance)
        table["coordinates"] = [round(centre_x, 4), 0.0, round(centre_z, 4)]
        table["size"] = [round(table_size[0], 4), table_size[1], round(table_size[2], 4)]
        table["rotation_deg"] = 0.0
        table["asset_id"] = _styled_asset_id(table, style, preset)

        fixtures[:] = [
            item for item in fixtures
            if not (item.get("room_id") == room_id and item.get("object_type") == "dining_chair")
        ]
        adjusted = True

        if preset["decor_density"] > 0.3 and not any(item.get("room_id") == room_id and item.get("object_type") == "sideboard" for item in fixtures):
            fixtures.append(_new_object(room, "sideboard", added, _safe_room_position(room, 0.5, 0.12), (min(1.7, width - 0.8), 0.82, 0.44), 0.0, style, preset))
            added += 1
    return adjusted, added


def _choose_perspective_room(rooms: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rooms:
        return None

    def score(room: dict[str, Any]) -> float:
        kind = _room_kind(room)
        preference = {"living": 5.0, "dining": 4.2, "kitchen": 3.6, "bedroom": 2.0, "office": 1.7}.get(kind, 1.0)
        return preference * 1000 + float(room.get("area_m2") or 0.0)

    return max(rooms, key=score)


def _perspective_camera(room: dict[str, Any] | None, scene: dict[str, Any], lens: float) -> dict[str, Any]:
    if room is None:
        centre_x = float(scene.get("width_m", 10.0)) / 2
        centre_z = float(scene.get("depth_m", 8.0)) / 2
        return {
            "position": [centre_x, 1.62, max(0.5, centre_z - 1.4)],
            "target": [centre_x, 1.15, centre_z + 1.2],
            "lens": lens,
            "room_id": None,
            "room_name": "Central interior",
        }

    min_x, max_x, min_z, max_z = _bbox(room)
    width = max_x - min_x
    depth = max_z - min_z
    margin_x = min(max(0.55, width * 0.18), width * 0.38)
    margin_z = min(max(0.55, depth * 0.18), depth * 0.38)
    position = (min_x + margin_x, min_z + margin_z)
    target = (max_x - margin_x * 0.72, max_z - margin_z * 0.72)
    polygon = list(room.get("polygon") or [])
    centroid = tuple(map(float, room.get("centroid") or ((min_x + max_x) / 2, (min_z + max_z) / 2)))
    if polygon and not _point_in_polygon(position, polygon):
        position = ((position[0] + centroid[0]) / 2, (position[1] + centroid[1]) / 2)
    if polygon and not _point_in_polygon(target, polygon):
        target = centroid
    return {
        "position": [round(position[0], 4), 1.62, round(position[1], 4)],
        "target": [round(target[0], 4), 1.15, round(target[1], 4)],
        "lens": lens,
        "room_id": room.get("id"),
        "room_name": room.get("name") or "Interior room",
    }


def prepare_presentation_scene(
    scene: SceneManifest,
    style: str,
    auto_furnish: bool = True,
    optimise_dining: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if style not in STYLE_PRESETS:
        raise ValueError(f"Unknown design style: {style}")

    preset = deepcopy(STYLE_PRESETS[style])
    payload = scene.model_dump(mode="json")
    rooms = list(payload.get("rooms") or [])
    fixtures = list(payload.get("fixtures_and_furniture") or [])
    openings = list(payload.get("openings") or [])

    payload["materials"] = {
        "palette_name": preset["label"],
        "floor_global": preset["floor"],
        "walls_global": preset["walls"],
        "exterior_walls": preset["exterior"],
        "accent": preset["accent"],
        "fixture_metal": preset["metal"],
    }

    for item in fixtures:
        item["asset_id"] = _styled_asset_id(item, style, preset)

    furnishing_added = _auto_furnish(rooms, fixtures, style, preset) if auto_furnish else 0
    dining_adjusted = False
    if optimise_dining:
        dining_adjusted, dining_added = _optimise_dining(rooms, fixtures, openings, style, preset, auto_furnish)
        furnishing_added += dining_added

    camera_room = _choose_perspective_room(rooms)
    camera = _perspective_camera(camera_room, payload, float(preset["lens"]))
    metadata = dict(payload.get("project_metadata") or {})
    metadata["extracted_labels"] = []
    metadata["ocr_status"] = "source_text_excluded_from_render"
    metadata["render_style"] = style
    payload["project_metadata"] = metadata
    payload["fixtures_and_furniture"] = fixtures
    payload["render_profile"] = {
        "style": style,
        "style_label": preset["label"],
        "world_colour": preset["world_colour"],
        "daylight_strength": preset["daylight_strength"],
        "warm_light": preset["warm_light"],
        "exposure": preset["exposure"],
        "decor_density": preset["decor_density"],
        "text_policy": "geometry_only_no_source_text",
    }
    payload["presentation_camera"] = camera

    return payload, {
        "style": style,
        "style_label": preset["label"],
        "perspective_room": camera["room_name"],
        "perspective_room_id": camera["room_id"],
        "text_removed": True,
        "dining_adjusted": dining_adjusted,
        "furnishing_added": furnishing_added,
    }
