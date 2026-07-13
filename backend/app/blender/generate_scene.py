from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--quality", choices=["preview", "1080p", "4k"], default="1080p")
    parser.add_argument("--mode", choices=["still", "video"], default="still")
    parser.add_argument("--seconds", type=int, default=15)
    return parser.parse_args(args)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def hex_rgba(value: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    raw = str(value or "#808080").lstrip("#")
    if len(raw) != 6:
        raw = "808080"
    return tuple(int(raw[index:index + 2], 16) / 255.0 for index in (0, 2, 4)) + (alpha,)


def material(name: str, color, roughness: float = 0.7, metallic: float = 0.0, specular: float = 0.45):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = color
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = specular
    return mat


def material_from_spec(name: str, spec: dict, fallback: str):
    return material(
        name,
        hex_rgba(spec.get("hex_color", fallback)),
        float(spec.get("roughness", 0.65)),
        float(spec.get("metallic", 0.0)),
        float(spec.get("specular", 0.45)),
    )


def image_material(name: str, image_path: str | None, fallback, roughness: float = 0.65):
    if not image_path or not Path(image_path).exists():
        return material(name, fallback, roughness)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if bsdf and "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = roughness
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(image_path, check_existing=True)
    texture.extension = "REPEAT"
    if bsdf:
        links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def add_box(name: str, position, size, mat, rotation_y: float = 0.0):
    bpy.ops.mesh.primitive_cube_add(location=position, rotation=(0, rotation_y, 0))
    obj = bpy.context.active_object
    obj.name = name
    obj.dimensions = size
    if mat:
        obj.data.materials.append(mat)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def add_cylinder(name: str, position, radius: float, depth: float, mat, vertices: int = 32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=position)
    obj = bpy.context.active_object
    obj.name = name
    if mat:
        obj.data.materials.append(mat)
    return obj


def add_wall(wall: dict, exterior_mat, interior_mat, height_override: float | None = None):
    x1, z1 = wall["start"]
    x2, z2 = wall["end"]
    dx, dz = x2 - x1, z2 - z1
    length = math.hypot(dx, dz)
    height = float(height_override if height_override is not None else wall["height"])
    mat = exterior_mat if wall.get("wall_type") == "exterior" else interior_mat
    return add_box(
        wall["id"],
        ((x1 + x2) / 2, height / 2, (z1 + z2) / 2),
        (length, height, wall.get("thickness", 0.16)),
        mat,
        -math.atan2(dz, dx),
    )


def add_room_surface(room: dict, floor_mat, ceiling_mat=None, ceiling_height: float = 2.8):
    vertices = [(x, 0, z) for x, z in room["polygon"]]
    if len(vertices) < 3:
        return
    faces = [list(range(len(vertices)))]
    mesh = bpy.data.meshes.new(f'{room["id"]}-floor-mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    floor = bpy.data.objects.new(f'{room["id"]}-floor', mesh)
    bpy.context.collection.objects.link(floor)
    floor.data.materials.append(floor_mat)
    if ceiling_mat:
        ceiling_mesh = mesh.copy()
        ceiling = bpy.data.objects.new(f'{room["id"]}-ceiling', ceiling_mesh)
        bpy.context.collection.objects.link(ceiling)
        ceiling.location.y = ceiling_height
        ceiling.scale.z = -1
        ceiling.data.materials.append(ceiling_mat)


def import_glb(asset: dict):
    mesh_path = asset.get("mesh_path")
    if not mesh_path or not Path(mesh_path).exists():
        return None
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=mesh_path)
    imported = [obj for obj in bpy.context.scene.objects if obj not in before]
    if not imported:
        return None
    parent = bpy.data.objects.new(f'{asset["id"]}-root', None)
    bpy.context.collection.objects.link(parent)
    for obj in imported:
        obj.parent = parent
    parent.location = asset["position"]
    parent.rotation_euler[1] = asset.get("rotation_y", 0.0)
    return parent


def add_opening(opening: dict, accent_mat, glass_mat, wall_height: float):
    x, z = opening["position"]
    width = float(opening.get("width", 0.9))
    rotation = math.radians(float(opening.get("rotation_deg", 0.0)))
    opening_type = opening.get("opening_type", "door")
    if opening_type == "window":
        sill = 0.9
        height = min(float(opening.get("height", 1.25)), wall_height - sill)
        add_box(f'{opening["id"]}-glass', (x, sill + height / 2, z), (width, height, 0.035), glass_mat, rotation)
        add_box(f'{opening["id"]}-head', (x, sill + height + 0.035, z), (width + 0.08, 0.07, 0.07), accent_mat, rotation)
    elif opening_type in {"sliding_door", "bifold_door"}:
        height = min(float(opening.get("height", 2.2)), wall_height)
        add_box(f'{opening["id"]}-glass', (x, height / 2, z), (width, height, 0.045), glass_mat, rotation)
        add_box(f'{opening["id"]}-rail', (x, height, z), (width + 0.08, 0.06, 0.08), accent_mat, rotation)
    elif opening_type == "door":
        height = min(float(opening.get("height", 2.1)), wall_height)
        add_box(f'{opening["id"]}-door', (x, height / 2, z), (max(0.05, width * 0.94), height, 0.045), accent_mat, rotation)


def add_procedural_object(item: dict, furniture_mat, accent_mat, metal_mat, porcelain_mat):
    object_type = str(item.get("object_type", "generic"))
    x, y, z = item.get("coordinates", (0, 0.5, 0))
    sx, sy, sz = item.get("size", (1, 1, 1))
    rotation = math.radians(float(item.get("rotation_deg", 0.0)))
    base = f'proc-{item.get("id", object_type)}'

    if object_type == "bed":
        add_box(base + "-base", (x, max(0.18, sy * 0.32), z), (sx, max(0.24, sy * 0.55), sz), furniture_mat, rotation)
        add_box(base + "-mattress", (x, max(0.42, sy * 0.78), z), (sx * 0.96, max(0.18, sy * 0.35), sz * 0.94), porcelain_mat, rotation)
    elif object_type == "sofa":
        add_box(base + "-seat", (x, sy * 0.38, z), (sx, sy * 0.42, sz), furniture_mat, rotation)
        add_box(base + "-back", (x, sy * 0.75, z - sz * 0.42), (sx, sy * 0.52, sz * 0.16), furniture_mat, rotation)
    elif object_type in {"coffee_table", "dining_table", "kitchen_island"}:
        add_box(base + "-top", (x, sy * 0.92, z), (sx, max(0.08, sy * 0.12), sz), accent_mat, rotation)
        for dx in (-0.4, 0.4):
            for dz in (-0.36, 0.36):
                add_box(base + f"-leg-{dx}-{dz}", (x + dx * sx, sy * 0.45, z + dz * sz), (0.08, sy * 0.86, 0.08), metal_mat, rotation)
    elif object_type in {"toilet", "sink"}:
        add_cylinder(base + "-bowl", (x, sy * 0.48, z), max(0.18, min(sx, sz) * 0.42), max(0.18, sy * 0.52), porcelain_mat)
        if object_type == "toilet":
            add_box(base + "-tank", (x, sy * 0.72, z - sz * 0.32), (sx * 0.72, sy * 0.52, sz * 0.28), porcelain_mat, rotation)
    elif object_type == "bathtub":
        add_box(base + "-tub", (x, sy * 0.45, z), (sx, sy * 0.9, sz), porcelain_mat, rotation)
        add_box(base + "-void", (x, sy * 0.62, z), (sx * 0.8, sy * 0.45, sz * 0.65), accent_mat, rotation)
    elif object_type in {"fridge", "stove", "washing_machine", "dryer", "lift", "tv_unit", "wardrobe"}:
        mat = metal_mat if object_type in {"fridge", "stove", "washing_machine", "dryer", "lift"} else furniture_mat
        add_box(base, (x, sy / 2, z), (sx, sy, sz), mat, rotation)
    elif object_type == "staircase":
        steps = 10
        for index in range(steps):
            step_depth = sz / steps
            step_height = sy / steps
            local_z = z - sz / 2 + step_depth * (index + 0.5)
            add_box(base + f"-{index}", (x, step_height * (index + 0.5), local_z), (sx, step_height, step_depth), furniture_mat, rotation)
    else:
        add_box(base, (x, sy / 2, z), (sx, sy, sz), furniture_mat, rotation)


def point_camera(camera, target) -> None:
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_isometric_camera(scene_data: dict):
    width = float(scene_data["width_m"])
    depth = float(scene_data["depth_m"])
    centre = (width / 2, 0.65, depth / 2)
    largest = max(width, depth, 4.0)
    bpy.ops.object.camera_add(location=(centre[0] + largest * 1.05, largest * 1.05, centre[2] + largest * 1.05))
    camera = bpy.context.active_object
    camera.name = "ArchitecturalIsometricCamera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = largest * 1.48
    point_camera(camera, centre)
    bpy.context.scene.camera = camera
    return camera


def add_camera_path(points, seconds: int):
    if len(points) < 2:
        points = [points[0], (points[0][0] + 0.5, points[0][1], points[0][2] + 0.5)]
    curve_data = bpy.data.curves.new("WalkthroughPath", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 24
    spline = curve_data.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for point, coordinate in zip(spline.bezier_points, points):
        point.co = coordinate
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    path = bpy.data.objects.new("WalkthroughPath", curve_data)
    bpy.context.collection.objects.link(path)

    bpy.ops.object.camera_add(location=points[0])
    camera = bpy.context.active_object
    bpy.context.scene.camera = camera
    follow = camera.constraints.new(type="FOLLOW_PATH")
    follow.target = path
    follow.forward_axis = "FORWARD_X"
    follow.up_axis = "UP_Z"
    follow.use_curve_follow = True
    path.data.path_duration = seconds * 30
    follow.offset_factor = 0.0
    follow.keyframe_insert(data_path="offset_factor", frame=1)
    follow.offset_factor = 1.0
    follow.keyframe_insert(data_path="offset_factor", frame=seconds * 30)
    return camera


def main() -> None:
    args = parse_args()
    scene_data = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    clear_scene()

    materials = scene_data.get("materials", {})
    floor_spec = materials.get("floor_global", {})
    wall_spec = materials.get("walls_global", {})
    exterior_spec = materials.get("exterior_walls", {})
    accent_spec = materials.get("accent", {})
    metal_spec = materials.get("fixture_metal", {})

    floor_mat = image_material("Floor", scene_data.get("floor_texture_path"), hex_rgba(floor_spec.get("hex_color", "#B99268")), float(floor_spec.get("roughness", 0.46)))
    wall_mat = image_material("Interior Walls", scene_data.get("wall_texture_path"), hex_rgba(wall_spec.get("hex_color", "#E8E5DE")), float(wall_spec.get("roughness", 0.82)))
    exterior_mat = material_from_spec("Exterior Walls", exterior_spec, "#9C9C96")
    accent_mat = material_from_spec("Accent", accent_spec, "#2E79C6")
    metal_mat = material_from_spec("Fixture Metal", metal_spec, "#A6ADB2")
    furniture_mat = material("Furniture Fabric", hex_rgba(accent_spec.get("hex_color", "#2E79C6")), 0.58, 0.0, 0.32)
    porcelain_mat = material("Porcelain", (0.91, 0.92, 0.90, 1), 0.28, 0.0, 0.55)
    glass_mat = material("Architectural Glass", (0.30, 0.55, 0.72, 0.32), 0.08, 0.0, 0.75)
    glass_mat.blend_method = "BLEND"
    ceiling_mat = material("Ceiling", (0.92, 0.92, 0.90, 1), 0.9, 0.0, 0.12)

    video_mode = args.mode == "video"
    ceiling_height = float(scene_data.get("ceiling_height_m", scene_data.get("wall_height_m", 2.8)))
    cutaway_height = float(scene_data.get("cutaway_height_m", min(1.65, ceiling_height)))
    wall_height = ceiling_height if video_mode else min(cutaway_height, ceiling_height)

    for room in scene_data.get("rooms", []):
        add_room_surface(room, floor_mat, ceiling_mat if video_mode else None, ceiling_height)
    for wall in scene_data.get("walls", []):
        add_wall(wall, exterior_mat, wall_mat, wall_height)
    for opening in scene_data.get("openings", []):
        add_opening(opening, accent_mat, glass_mat, wall_height)
    for item in scene_data.get("fixtures_and_furniture", []):
        add_procedural_object(item, furniture_mat, accent_mat, metal_mat, porcelain_mat)
    for asset in scene_data.get("assets", []):
        mat = metal_mat if asset.get("slot") == "fridge" else furniture_mat
        if import_glb(asset) is None:
            source_mat = image_material(f'{asset["id"]}-reference', asset.get("source_path"), tuple(mat.diffuse_color), float(mat.roughness))
            add_box(asset["id"], asset["position"], asset["size"], source_mat, asset.get("rotation_y", 0.0))

    world = bpy.context.scene.world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.055, 0.07, 0.085, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.42

    centre_x = scene_data["width_m"] / 2
    centre_z = scene_data["depth_m"] / 2
    bpy.ops.object.light_add(type="AREA", location=(centre_x, ceiling_height + 4.5, centre_z))
    light = bpy.context.active_object
    light.data.energy = 2200
    light.data.shape = "DISK"
    light.data.size = max(scene_data["width_m"], scene_data["depth_m"]) * 1.15

    if video_mode:
        camera_points = scene_data.get("camera_path") or [
            tuple(scene_data.get("first_person_start") or (2, 1.7, 2)),
            (scene_data["width_m"] - 2, 1.7, scene_data["depth_m"] - 2),
        ]
        camera = add_camera_path(camera_points, args.seconds)
        camera.data.lens = 24
    else:
        add_isometric_camera(scene_data)

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
