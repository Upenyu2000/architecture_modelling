from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy


BASE_PATH = Path(__file__).with_name("generate_scene.py")
SPEC = importlib.util.spec_from_file_location("arch_ai_blender_base", BASE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load Blender scene helpers from {BASE_PATH}")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


WINDOW_TYPES = {
    "window", "fixed_window", "casement_window", "double_casement_window", "glider_window",
    "garden_window", "bay_window", "bow_window", "double_hung_window",
    "vertical_sliding_window", "horizontal_sliding_window",
}
SLIDING_TYPES = {
    "pocket_door", "double_pocket_door", "bypass_door", "sliding_door",
    "double_sliding_door", "sliding_glass_door",
}
DOUBLE_TYPES = {"double_door", "double_bifold_door", "double_pocket_door", "double_sliding_door", "bypass_door"}
FOLDING_TYPES = {"bifold_door", "double_bifold_door", "folding_door"}


def is_window(opening_type: str) -> bool:
    return opening_type in WINDOW_TYPES


def projected_openings(wall: dict, openings: list[dict]) -> list[dict]:
    x1, z1 = map(float, wall["start"])
    x2, z2 = map(float, wall["end"])
    dx, dz = x2 - x1, z2 - z1
    length = math.hypot(dx, dz)
    if length < 0.01:
        return []
    ux, uz = dx / length, dz / length
    results: list[dict] = []
    for opening in openings:
        wall_id = opening.get("wall_id")
        if wall_id and wall_id != wall.get("id"):
            continue
        ox, oz = map(float, opening.get("position", (0, 0)))
        centre = (ox - x1) * ux + (oz - z1) * uz
        closest_x = x1 + max(0.0, min(length, centre)) * ux
        closest_z = z1 + max(0.0, min(length, centre)) * uz
        tolerance = max(0.28, float(wall.get("thickness", 0.16)) * 2.5)
        if math.hypot(ox - closest_x, oz - closest_z) > tolerance:
            continue
        width = min(max(float(opening.get("width", 0.9)), 0.25), length)
        results.append({
            "opening": opening,
            "centre": max(0.0, min(length, centre)),
            "start": max(0.0, min(length, centre - width / 2)),
            "end": max(0.0, min(length, centre + width / 2)),
        })
    return sorted(results, key=lambda item: item["start"])


def add_wall_piece(wall: dict, start_offset: float, end_offset: float, bottom: float, height: float, mat):
    x1, z1 = map(float, wall["start"])
    x2, z2 = map(float, wall["end"])
    dx, dz = x2 - x1, z2 - z1
    full_length = math.hypot(dx, dz)
    length = end_offset - start_offset
    if full_length < 0.01 or length < 0.025 or height < 0.025:
        return None
    ux, uz = dx / full_length, dz / full_length
    middle = (start_offset + end_offset) / 2
    return base.add_box(
        f'{wall.get("id", "wall")}-{start_offset:.3f}-{end_offset:.3f}-{bottom:.3f}',
        (x1 + ux * middle, bottom + height / 2, z1 + uz * middle),
        (length, height, float(wall.get("thickness", 0.16))),
        mat,
        -math.atan2(dz, dx),
    )


def add_cut_wall(wall: dict, openings: list[dict], exterior_mat, interior_mat, visible_height: float):
    x1, z1 = map(float, wall["start"])
    x2, z2 = map(float, wall["end"])
    length = math.hypot(x2 - x1, z2 - z1)
    mat = exterior_mat if wall.get("wall_type") == "exterior" else interior_mat
    projected = projected_openings(wall, openings)
    if not projected:
        return add_wall_piece(wall, 0.0, length, 0.0, visible_height, mat)

    cursor = 0.0
    for item in projected:
        if item["start"] > cursor + 0.02:
            add_wall_piece(wall, cursor, item["start"], 0.0, visible_height, mat)
        cursor = max(cursor, item["end"])
    if cursor < length - 0.02:
        add_wall_piece(wall, cursor, length, 0.0, visible_height, mat)

    for item in projected:
        opening = item["opening"]
        opening_type = str(opening.get("opening_type", "door"))
        if opening_type == "open_passage":
            continue
        if is_window(opening_type):
            sill = min(float(opening.get("sill_height", 0.9)), visible_height)
            opening_top = min(sill + float(opening.get("height", 1.25)), visible_height)
            add_wall_piece(wall, item["start"], item["end"], 0.0, sill, mat)
            if visible_height > opening_top:
                add_wall_piece(wall, item["start"], item["end"], opening_top, visible_height - opening_top, mat)
        else:
            opening_top = min(float(opening.get("height", 2.1)), visible_height)
            if visible_height > opening_top:
                add_wall_piece(wall, item["start"], item["end"], opening_top, visible_height - opening_top, mat)
    return None


def pbr_texture_material(name: str, spec: dict, image_path: str | None, normal_path: str | None = None):
    if not image_path or not Path(image_path).exists():
        return base.material_from_spec(name, spec, spec.get("hex_color", "#808080"))
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    coordinate = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(image_path, check_existing=True)
    texture.extension = "REPEAT"
    texture.projection = "BOX"
    texture.projection_blend = 0.24
    scale = float(spec.get("texture_scale", 1.0))
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    links.new(coordinate.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], texture.inputs["Vector"])
    if bsdf:
        links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = float(spec.get("roughness", 0.6))
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = float(spec.get("metallic", 0.0))
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = float(spec.get("specular", 0.45))
    if normal_path and Path(normal_path).exists() and bsdf:
        normal_texture = nodes.new("ShaderNodeTexImage")
        normal_texture.image = bpy.data.images.load(normal_path, check_existing=True)
        normal_texture.image.colorspace_settings.name = "Non-Color"
        normal_texture.extension = "REPEAT"
        normal_texture.projection = "BOX"
        normal_texture.projection_blend = 0.24
        normal_node = nodes.new("ShaderNodeNormalMap")
        links.new(mapping.outputs["Vector"], normal_texture.inputs["Vector"])
        links.new(normal_texture.outputs["Color"], normal_node.inputs["Color"])
        links.new(normal_node.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def _door_angle(opening: dict) -> float:
    if not bool(opening.get("default_open", False)):
        return 0.0
    direction = -1.0 if opening.get("swing_direction") == "counterclockwise" else 1.0
    return direction * math.radians(float(opening.get("swing_angle_deg", 90.0)))


def _add_hinged_leaf(name: str, x: float, z: float, width: float, height: float, rotation: float, angle: float, hinge_right: bool, mat):
    hinge_x = x + math.cos(rotation) * (width / 2 if hinge_right else -width / 2)
    hinge_z = z + math.sin(rotation) * (width / 2 if hinge_right else -width / 2)
    leaf_rotation = rotation + angle
    centre_offset = -width / 2 if hinge_right else width / 2
    centre_x = hinge_x + math.cos(leaf_rotation) * centre_offset
    centre_z = hinge_z + math.sin(leaf_rotation) * centre_offset
    base.add_box(name, (centre_x, height / 2, centre_z), (width, height, 0.04), mat, leaf_rotation)


def add_opening_visual(opening: dict, accent_mat, glass_mat, wall_height: float):
    x, z = map(float, opening.get("position", (0, 0)))
    width = float(opening.get("width", 0.9))
    rotation = math.radians(float(opening.get("rotation_deg", 0.0)))
    opening_type = str(opening.get("opening_type", "door"))
    opening_id = str(opening.get("id", "opening"))

    if opening_type == "open_passage":
        return

    if is_window(opening_type):
        sill = float(opening.get("sill_height", 0.9))
        height = min(float(opening.get("height", 1.25)), max(0.1, wall_height - sill))
        depth = 0.12 if opening_type in {"bay_window", "bow_window", "garden_window"} else 0.025
        base.add_box(f"{opening_id}-glass", (x, sill + height / 2, z), (width * 0.96, height, depth), glass_mat, rotation)
        if opening_type in {"bay_window", "bow_window"}:
            side_width = width * 0.28
            offset = width * 0.41
            for index, sign in enumerate((-1, 1)):
                side_rotation = rotation - sign * math.radians(24)
                side_x = x + math.cos(rotation) * offset * sign + math.cos(rotation + math.pi / 2) * 0.12
                side_z = z + math.sin(rotation) * offset * sign + math.sin(rotation + math.pi / 2) * 0.12
                base.add_box(f"{opening_id}-bay-{index}", (side_x, sill + height / 2, side_z), (side_width, height, 0.025), glass_mat, side_rotation)
        return

    height = min(float(opening.get("height", 2.1)), wall_height)
    open_angle = _door_angle(opening)

    if opening_type == "revolving_door":
        base.add_cylinder(f"{opening_id}-drum", (x, height / 2, z), width / 2, height, glass_mat, vertices=48)
        for index, angle in enumerate((0.0, math.pi / 2)):
            base.add_box(f"{opening_id}-blade-{index}", (x, height / 2, z), (width, height, 0.04), accent_mat, angle + open_angle)
        return

    if opening_type == "overhead_door":
        raised = bool(opening.get("default_open", False))
        base.add_box(
            f"{opening_id}-overhead",
            (x, height if raised else height / 2, z - (height / 2 if raised else 0)),
            (width * 0.96, 0.06 if raised else height, height if raised else 0.05),
            accent_mat,
            rotation,
        )
        return

    if opening_type in SLIDING_TYPES:
        opened = bool(opening.get("default_open", False))
        double = opening_type in DOUBLE_TYPES
        glass = opening_type == "sliding_glass_door"
        material = glass_mat if glass else accent_mat
        shift = width * 0.46 if opened else 0.0
        if double:
            leaf_width = width / 2
            for index, sign in enumerate((-1, 1)):
                leaf_x = x + math.cos(rotation) * (sign * width * 0.25 + shift * sign)
                leaf_z = z + math.sin(rotation) * (sign * width * 0.25 + shift * sign)
                base.add_box(f"{opening_id}-slide-{index}", (leaf_x, height / 2, leaf_z), (leaf_width * 0.96, height, 0.04), material, rotation)
        else:
            leaf_x = x + math.cos(rotation) * shift
            leaf_z = z + math.sin(rotation) * shift
            base.add_box(f"{opening_id}-slide", (leaf_x, height / 2, leaf_z), (width * 0.96, height, 0.04), material, rotation)
        base.add_box(f"{opening_id}-rail", (x, height, z), (width + 0.08, 0.045, 0.06), accent_mat, rotation)
        return

    double = opening_type in {"double_door", "double_bifold_door"}
    folding = opening_type in FOLDING_TYPES
    if double:
        leaf_width = width / 2
        angle = open_angle if open_angle else (math.radians(38) if folding else 0.0)
        _add_hinged_leaf(f"{opening_id}-left", x - math.cos(rotation) * width / 4, z - math.sin(rotation) * width / 4, leaf_width, height, rotation, angle, False, accent_mat)
        _add_hinged_leaf(f"{opening_id}-right", x + math.cos(rotation) * width / 4, z + math.sin(rotation) * width / 4, leaf_width, height, rotation, -angle, True, accent_mat)
    else:
        hinge_right = opening.get("hinge_side") == "right"
        angle = open_angle if open_angle else (math.radians(38) if folding and opening.get("default_open") else 0.0)
        _add_hinged_leaf(f"{opening_id}-leaf", x, z, width * 0.94, height, rotation, angle, hinge_right, accent_mat)


def add_window_lights(openings: list[dict], ceiling_height: float):
    windows = [opening for opening in openings if is_window(str(opening.get("opening_type", "")))]
    for index, opening in enumerate(windows[:24]):
        x, z = map(float, opening.get("position", (0, 0)))
        width = max(0.6, float(opening.get("width", 1.2)))
        bpy.ops.object.light_add(type="AREA", location=(x, min(1.7, ceiling_height - 0.3), z))
        light = bpy.context.active_object
        light.name = f"WindowBounce-{index}"
        light.data.energy = 90 * width
        light.data.shape = "RECTANGLE"
        light.data.size = width
        light.data.color = (0.72, 0.84, 1.0)
        light.rotation_euler = (math.radians(90), 0, math.radians(float(opening.get("rotation_deg", 0.0))))


def main() -> None:
    args = base.parse_args()
    scene_data = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    base.clear_scene()

    materials = scene_data.get("materials", {})
    floor_spec = materials.get("floor_global", {})
    wall_spec = materials.get("walls_global", {})
    exterior_spec = materials.get("exterior_walls", {})
    accent_spec = materials.get("accent", {})
    metal_spec = materials.get("fixture_metal", {})

    floor_texture = scene_data.get("floor_texture_path") or floor_spec.get("texture_path")
    floor_normal = floor_spec.get("normal_path")
    wall_texture = scene_data.get("wall_texture_path") or wall_spec.get("texture_path")
    wall_normal = wall_spec.get("normal_path")
    floor_mat = pbr_texture_material("Floor", floor_spec, floor_texture, floor_normal)
    wall_mat = pbr_texture_material("Interior Walls", wall_spec, wall_texture, wall_normal)
    exterior_mat = pbr_texture_material("Exterior Walls", exterior_spec, exterior_spec.get("texture_path"), exterior_spec.get("normal_path"))
    accent_mat = base.material_from_spec("Accent", accent_spec, "#2E79C6")
    metal_mat = base.material_from_spec("Fixture Metal", metal_spec, "#A6ADB2")
    furniture_mat = base.material("Furniture Fabric", base.hex_rgba(accent_spec.get("hex_color", "#2E79C6")), 0.58, 0.0, 0.32)
    porcelain_mat = base.material("Porcelain", (0.91, 0.92, 0.90, 1), 0.28, 0.0, 0.55)
    glass_mat = base.material("Architectural Glass", (0.30, 0.55, 0.72, 0.22), 0.08, 0.0, 0.75)
    if hasattr(glass_mat, "surface_render_method"):
        glass_mat.surface_render_method = "DITHERED"
    ceiling_mat = base.material("Ceiling", (0.92, 0.92, 0.90, 1), 0.9, 0.0, 0.12)

    video_mode = args.mode == "video"
    ceiling_height = float(scene_data.get("ceiling_height_m", scene_data.get("wall_height_m", 2.8)))
    cutaway_height = float(scene_data.get("cutaway_height_m", min(1.65, ceiling_height)))
    wall_height = ceiling_height if video_mode else min(cutaway_height, ceiling_height)
    openings = list(scene_data.get("openings", []))

    for room in scene_data.get("rooms", []):
        base.add_room_surface(room, floor_mat, ceiling_mat if video_mode else None, ceiling_height)
    for wall in scene_data.get("walls", []):
        add_cut_wall(wall, openings, exterior_mat, wall_mat, wall_height)
    for opening in openings:
        add_opening_visual(opening, accent_mat, glass_mat, wall_height)
    for item in scene_data.get("fixtures_and_furniture", []):
        base.add_procedural_object(item, furniture_mat, accent_mat, metal_mat, porcelain_mat)
    for asset in scene_data.get("assets", []):
        mat = metal_mat if asset.get("slot") == "fridge" else furniture_mat
        if base.import_glb(asset) is None:
            source_mat = base.image_material(f'{asset["id"]}-reference', asset.get("source_path"), tuple(mat.diffuse_color), float(mat.roughness))
            base.add_box(asset["id"], asset["position"], asset["size"], source_mat, asset.get("rotation_y", 0.0))

    world = bpy.context.scene.world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.055, 0.07, 0.085, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.34

    centre_x = scene_data["width_m"] / 2
    centre_z = scene_data["depth_m"] / 2
    bpy.ops.object.light_add(type="AREA", location=(centre_x, ceiling_height + 4.5, centre_z))
    light = bpy.context.active_object
    light.data.energy = 1800
    light.data.shape = "DISK"
    light.data.size = max(scene_data["width_m"], scene_data["depth_m"]) * 1.15
    add_window_lights(openings, ceiling_height)

    if video_mode:
        camera_points = scene_data.get("camera_path") or [
            tuple(scene_data.get("first_person_start") or (2, 1.7, 2)),
            (scene_data["width_m"] - 2, 1.7, scene_data["depth_m"] - 2),
        ]
        camera = base.add_camera_path(camera_points, args.seconds)
        camera.data.lens = 24
    else:
        base.add_isometric_camera(scene_data)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_x, scene.render.resolution_y = {
        "preview": (1280, 720), "1080p": (1920, 1080), "4k": (3840, 2160),
    }[args.quality]
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.filepath = str(Path(args.output))
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.use_file_extension = True

    if video_mode:
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.fps = 30
        scene.frame_start = 1
        scene.frame_end = args.seconds * 30
        bpy.ops.render.render(animation=True)
    else:
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
