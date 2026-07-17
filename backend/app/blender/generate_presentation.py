from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import bpy


V3_PATH = Path(__file__).with_name("generate_scene_v3.py")
SPEC = importlib.util.spec_from_file_location("arch_ai_blender_v3_presentation", V3_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load detailed Blender renderer from {V3_PATH}")
v3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v3)
v2 = v3.v2
base = v2.base


TOP_RESOLUTIONS = {
    "preview": (1280, 960),
    "1080p": (1920, 1440),
    "4k": (4096, 3072),
}
PERSPECTIVE_RESOLUTIONS = {
    "preview": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
}


def parse_args() -> argparse.Namespace:
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--quality", choices=["preview", "1080p", "4k"], default="1080p")
    parser.add_argument("--view", choices=["top_down", "perspective"], required=True)
    return parser.parse_args(arguments)


def _rgb(value: str) -> tuple[float, float, float, float]:
    return base.hex_rgba(value or "#808080")


def _mix(colour: tuple[float, float, float, float], factor: float) -> tuple[float, float, float, float]:
    if factor >= 0:
        return tuple(min(1.0, channel + (1.0 - channel) * factor) for channel in colour[:3]) + (colour[3],)
    return tuple(max(0.0, channel * (1.0 + factor)) for channel in colour[:3]) + (colour[3],)


def _principled(name: str, spec: dict[str, Any]):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = _rgb(str(spec.get("hex_color", "#808080")))
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = float(spec.get("roughness", 0.65))
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = float(spec.get("metallic", 0.0))
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = float(spec.get("specular", 0.45))
    return material, bsdf


def _mapped_coordinates(nodes, links, scale: float):
    coordinate = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    links.new(coordinate.outputs["Generated"], mapping.inputs["Vector"])
    return mapping.outputs["Vector"]


def procedural_material(name: str, spec: dict[str, Any], image_path: str | None = None, normal_path: str | None = None):
    if image_path and Path(image_path).exists():
        return v2.pbr_texture_material(name, spec, image_path, normal_path)

    material, bsdf = _principled(name, spec)
    if not bsdf:
        return material
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    material_type = str(spec.get("material_type", "paint")).lower()
    base_colour = _rgb(str(spec.get("hex_color", "#808080")))
    texture_scale = max(0.2, float(spec.get("texture_scale", 1.0)))
    vector = _mapped_coordinates(nodes, links, texture_scale)

    if material_type == "brick":
        brick = nodes.new("ShaderNodeTexBrick")
        brick.inputs["Color1"].default_value = _mix(base_colour, 0.06)
        brick.inputs["Color2"].default_value = _mix(base_colour, -0.16)
        brick.inputs["Mortar"].default_value = _mix(base_colour, 0.38)
        brick.inputs["Scale"].default_value = 5.0 * texture_scale
        brick.inputs["Mortar Size"].default_value = 0.028
        links.new(vector, brick.inputs["Vector"])
        links.new(brick.outputs["Color"], bsdf.inputs["Base Color"])
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.2
        bump.inputs["Distance"].default_value = 0.08
        links.new(brick.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        return material

    if material_type == "tile":
        voronoi = nodes.new("ShaderNodeTexVoronoi")
        voronoi.feature = "DISTANCE_TO_EDGE"
        voronoi.distance = "EUCLIDEAN"
        voronoi.inputs["Scale"].default_value = 7.5 * texture_scale
        links.new(vector, voronoi.inputs["Vector"])
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.035
        ramp.color_ramp.elements[0].color = _mix(base_colour, -0.24)
        ramp.color_ramp.elements[1].position = 0.085
        ramp.color_ramp.elements[1].color = _mix(base_colour, 0.08)
        links.new(voronoi.outputs["Distance"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.16
        bump.inputs["Distance"].default_value = 0.045
        links.new(voronoi.outputs["Distance"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        return material

    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = (4.0 if material_type == "wood" else 6.5) * texture_scale
    noise.inputs["Detail"].default_value = 5.0
    noise.inputs["Roughness"].default_value = 0.68
    if "Distortion" in noise.inputs:
        noise.inputs["Distortion"].default_value = 1.8 if material_type == "wood" else 0.35
    links.new(vector, noise.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    dark_factor = -0.26 if material_type == "wood" else -0.12
    light_factor = 0.16 if material_type in {"wood", "stone"} else 0.08
    ramp.color_ramp.elements[0].color = _mix(base_colour, dark_factor)
    ramp.color_ramp.elements[1].color = _mix(base_colour, light_factor)
    if material_type == "wood":
        ramp.color_ramp.elements[0].position = 0.28
        ramp.color_ramp.elements[1].position = 0.72
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = {
        "wood": 0.22,
        "stone": 0.28,
        "concrete": 0.2,
        "plaster": 0.11,
        "fabric": 0.16,
    }.get(material_type, 0.08)
    bump.inputs["Distance"].default_value = 0.055
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return material


def projected_openings_shared(wall: dict[str, Any], openings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    x1, z1 = map(float, wall["start"])
    x2, z2 = map(float, wall["end"])
    dx, dz = x2 - x1, z2 - z1
    length = math.hypot(dx, dz)
    if length < 0.01:
        return []
    ux, uz = dx / length, dz / length
    results: list[dict[str, Any]] = []
    for opening in openings:
        linked_ids = {str(value) for value in opening.get("wall_ids", []) if value}
        if opening.get("wall_id"):
            linked_ids.add(str(opening["wall_id"]))
        if linked_ids and str(wall.get("id")) not in linked_ids:
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


def add_top_camera(scene_data: dict[str, Any], aspect: float):
    width = float(scene_data["width_m"])
    depth = float(scene_data["depth_m"])
    centre_x = width / 2
    centre_z = depth / 2
    largest = max(width, depth, 4.0)
    bpy.ops.object.camera_add(location=(centre_x, largest * 2.35, centre_z), rotation=(-math.pi / 2, 0, 0))
    camera = bpy.context.active_object
    camera.name = "PresentationTopDownCamera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = max(depth * 1.14, width / max(aspect, 0.1) * 1.14, 3.0)
    bpy.context.scene.camera = camera
    return camera


def add_perspective_camera(scene_data: dict[str, Any]):
    configuration = dict(scene_data.get("presentation_camera") or {})
    position = tuple(configuration.get("position") or scene_data.get("first_person_start") or (2.0, 1.62, 2.0))
    target = tuple(configuration.get("target") or (float(scene_data["width_m"]) / 2, 1.15, float(scene_data["depth_m"]) / 2))
    bpy.ops.object.camera_add(location=position)
    camera = bpy.context.active_object
    camera.name = "PresentationEyeLevelCamera"
    camera.data.type = "PERSP"
    camera.data.lens = float(configuration.get("lens", 28.0))
    camera.data.sensor_width = 36.0
    base.point_camera(camera, target)
    bpy.context.scene.camera = camera
    return camera


def add_ground(scene_data: dict[str, Any], material):
    width = float(scene_data["width_m"])
    depth = float(scene_data["depth_m"])
    margin = max(1.5, min(5.0, max(width, depth) * 0.14))
    return base.add_box(
        "PresentationGround",
        (width / 2, -0.09, depth / 2),
        (width + margin * 2, 0.16, depth + margin * 2),
        material,
    )


def add_room_lighting(scene_data: dict[str, Any], profile: dict[str, Any], perspective: bool):
    width = float(scene_data["width_m"])
    depth = float(scene_data["depth_m"])
    ceiling_height = float(scene_data.get("ceiling_height_m", scene_data.get("wall_height_m", 2.8)))
    largest = max(width, depth, 4.0)
    daylight_strength = float(profile.get("daylight_strength", 1.0))

    bpy.ops.object.light_add(type="SUN", location=(width / 2, ceiling_height + 5.0, depth / 2), rotation=(math.radians(28), math.radians(-18), math.radians(-32)))
    sun = bpy.context.active_object
    sun.name = "PresentationSun"
    sun.data.energy = 2.1 * daylight_strength
    sun.data.angle = math.radians(10)
    sun.data.color = (0.96, 0.98, 1.0)

    if not perspective:
        bpy.ops.object.light_add(type="AREA", location=(width / 2, ceiling_height + largest * 0.85, depth / 2), rotation=(-math.pi / 2, 0, 0))
        area = bpy.context.active_object
        area.name = "TopDownSoftbox"
        area.data.energy = 1150 * daylight_strength
        area.data.shape = "RECTANGLE"
        area.data.size = largest * 1.55
        area.data.size_y = largest * 1.35
        area.data.color = (0.93, 0.97, 1.0)
        return

    warm_colour = _rgb(str(profile.get("warm_light", "#FFD5A3")))[:3]
    for index, room in enumerate(scene_data.get("rooms", [])[:32]):
        cx, cz = map(float, room.get("centroid") or (width / 2, depth / 2))
        area_m2 = max(2.0, float(room.get("area_m2") or 8.0))
        bpy.ops.object.light_add(type="AREA", location=(cx, ceiling_height - 0.22, cz), rotation=(-math.pi / 2, 0, 0))
        light = bpy.context.active_object
        light.name = f"InteriorSoftbox-{index}"
        light.data.energy = min(420.0, 65.0 + area_m2 * 11.0)
        light.data.shape = "DISK"
        light.data.size = min(2.2, max(0.8, math.sqrt(area_m2) * 0.38))
        light.data.color = warm_colour
    v2.add_window_lights(list(scene_data.get("openings", [])), ceiling_height)


def build_scene(scene_data: dict[str, Any], view: str):
    base.clear_scene()
    v2.projected_openings = projected_openings_shared

    materials = dict(scene_data.get("materials") or {})
    floor_spec = dict(materials.get("floor_global") or {})
    wall_spec = dict(materials.get("walls_global") or {})
    exterior_spec = dict(materials.get("exterior_walls") or {})
    accent_spec = dict(materials.get("accent") or {})
    metal_spec = dict(materials.get("fixture_metal") or {})
    profile = dict(scene_data.get("render_profile") or {})

    floor_mat = procedural_material(
        "Presentation Floor",
        floor_spec,
        scene_data.get("floor_texture_path"),
        floor_spec.get("normal_path"),
    )
    wall_mat = procedural_material(
        "Presentation Interior Walls",
        wall_spec,
        scene_data.get("wall_texture_path"),
        wall_spec.get("normal_path"),
    )
    exterior_mat = procedural_material("Presentation Exterior", exterior_spec, exterior_spec.get("texture_path"), exterior_spec.get("normal_path"))
    accent_mat = procedural_material("Presentation Accent", accent_spec)
    metal_mat = procedural_material("Presentation Metal", metal_spec)
    furniture_mat = procedural_material("Presentation Furniture", {
        "material_type": "fabric",
        "hex_color": profile.get("furniture_colour", accent_spec.get("hex_color", "#6F766F")),
        "roughness": 0.58,
        "metallic": 0.0,
        "specular": 0.32,
        "texture_scale": 4.0,
    })
    porcelain_mat = procedural_material("Presentation Porcelain", {
        "material_type": "porcelain",
        "hex_color": "#ECECE7",
        "roughness": 0.24,
        "metallic": 0.0,
        "specular": 0.58,
        "texture_scale": 1.0,
    })
    glass_mat = base.material("Presentation Glass", (0.30, 0.57, 0.72, 0.26), 0.08, 0.0, 0.76)
    if hasattr(glass_mat, "surface_render_method"):
        glass_mat.surface_render_method = "DITHERED"
    ceiling_mat = procedural_material("Presentation Ceiling", {
        "material_type": "plaster",
        "hex_color": wall_spec.get("hex_color", "#F0EEE8"),
        "roughness": 0.92,
        "metallic": 0.0,
        "specular": 0.12,
        "texture_scale": 2.0,
    })
    ground_mat = procedural_material("Presentation Ground", {
        "material_type": "stone",
        "hex_color": exterior_spec.get("hex_color", "#8D928D"),
        "roughness": 0.94,
        "metallic": 0.0,
        "specular": 0.1,
        "texture_scale": 2.6,
    })

    perspective = view == "perspective"
    ceiling_height = float(scene_data.get("ceiling_height_m", scene_data.get("wall_height_m", 2.8)))
    wall_height = ceiling_height if perspective else min(1.22, ceiling_height * 0.5)
    openings = list(scene_data.get("openings", []))

    add_ground(scene_data, ground_mat)
    for room in scene_data.get("rooms", []):
        base.add_room_surface(room, floor_mat, ceiling_mat if perspective else None, ceiling_height)
    for wall in scene_data.get("walls", []):
        v2.add_cut_wall(wall, openings, exterior_mat, wall_mat, wall_height)
    for opening in openings:
        v2.add_opening_visual(opening, accent_mat, glass_mat, wall_height)
    for item in scene_data.get("fixtures_and_furniture", []):
        base.add_procedural_object(item, furniture_mat, accent_mat, metal_mat, porcelain_mat)
    for asset in scene_data.get("assets", []):
        material = metal_mat if asset.get("slot") == "fridge" else furniture_mat
        if base.import_glb(asset) is None:
            source_mat = base.image_material(f'{asset.get("id", "asset")}-reference', asset.get("source_path"), tuple(material.diffuse_color), float(material.roughness))
            base.add_box(asset.get("id", "asset"), asset.get("position", (0, 0.5, 0)), asset.get("size", (1, 1, 1)), source_mat, asset.get("rotation_y", 0.0))

    world = bpy.context.scene.world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = _rgb(str(profile.get("world_colour", "#C8D7DF")))
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.42 if perspective else 0.55
    add_room_lighting(scene_data, profile, perspective)


def configure_render(args: argparse.Namespace, scene_data: dict[str, Any]):
    scene = bpy.context.scene
    resolutions = TOP_RESOLUTIONS if args.view == "top_down" else PERSPECTIVE_RESOLUTIONS
    width, height = resolutions[args.quality]
    if args.view == "top_down":
        add_top_camera(scene_data, width / height)
    else:
        add_perspective_camera(scene_data)

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.use_file_extension = True
    scene.render.filepath = str(Path(args.output))

    profile = dict(scene_data.get("render_profile") or {})
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    scene.view_settings.exposure = float(profile.get("exposure", 0.3))
    scene.view_settings.gamma = 1.0


def main() -> None:
    args = parse_args()
    scene_data = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    build_scene(scene_data, args.view)
    configure_render(args, scene_data)
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
