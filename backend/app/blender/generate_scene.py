from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy


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


def material(name: str, color: tuple[float, float, float, float], roughness: float = 0.7, metallic: float = 0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def image_material(name: str, image_path: str | None, fallback, roughness: float = 0.65):
    if not image_path or not Path(image_path).exists():
        return material(name, fallback, roughness)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = roughness
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(image_path, check_existing=True)
    texture.extension = "REPEAT"
    links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def import_glb(asset):
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


def add_box(name: str, position, size, mat, rotation_y: float = 0.0):
    bpy.ops.mesh.primitive_cube_add(location=position, rotation=(0, rotation_y, 0))
    obj = bpy.context.active_object
    obj.name = name
    obj.dimensions = size
    obj.data.materials.append(mat)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def add_wall(wall, mat):
    x1, z1 = wall["start"]
    x2, z2 = wall["end"]
    dx, dz = x2 - x1, z2 - z1
    length = math.hypot(dx, dz)
    return add_box(
        wall["id"],
        ((x1 + x2) / 2, wall["height"] / 2, (z1 + z2) / 2),
        (length, wall["height"], wall["thickness"]),
        mat,
        -math.atan2(dz, dx),
    )


def add_room_floor(room, mat):
    vertices = [(x, 0, z) for x, z in room["polygon"]]
    if len(vertices) < 3:
        return
    mesh = bpy.data.meshes.new(f'{room["id"]}-mesh')
    mesh.from_pydata(vertices, [], [list(range(len(vertices)))])
    mesh.update()
    obj = bpy.data.objects.new(room["id"], mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)


def add_camera_path(points, seconds: int):
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
    follow.up_axis = "UP_Y"
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
    wall_mat = image_material("Walls", scene_data.get("wall_texture_path"), (0.82, 0.84, 0.81, 1), 0.78)
    floor_mat = image_material("Floor", scene_data.get("floor_texture_path"), (0.30, 0.20, 0.12, 1), 0.58)
    furniture_mat = material("Furniture", (0.08, 0.32, 0.18, 1), 0.52)
    metal_mat = material("Metal", (0.45, 0.48, 0.50, 1), 0.25, 0.75)

    for room in scene_data.get("rooms", []):
        add_room_floor(room, floor_mat)
    for wall in scene_data.get("walls", []):
        add_wall(wall, wall_mat)
    for asset in scene_data.get("assets", []):
        mat = metal_mat if asset.get("slot") == "fridge" else furniture_mat
        if import_glb(asset) is None:
            source_mat = image_material(f'{asset["id"]}-reference', asset.get("source_path"), tuple(mat.diffuse_color), float(mat.roughness))
            add_box(asset["id"], asset["position"], asset["size"], source_mat, asset.get("rotation_y", 0.0))

    world = bpy.context.scene.world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.06, 0.09, 0.07, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.5
    bpy.ops.object.light_add(type="AREA", location=(scene_data["width_m"] / 2, 7, scene_data["depth_m"] / 2))
    light = bpy.context.active_object
    light.data.energy = 1800
    light.data.shape = "DISK"
    light.data.size = max(scene_data["width_m"], scene_data["depth_m"])

    camera_points = scene_data.get("camera_path") or [(2, 1.6, 2), (scene_data["width_m"] - 2, 1.6, scene_data["depth_m"] - 2)]
    camera = add_camera_path(camera_points, args.seconds)
    camera.data.lens = 28

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.image_settings.file_format = "PNG"
    resolution = {"preview": (1280, 720), "1080p": (1920, 1080), "4k": (3840, 2160)}[args.quality]
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.filepath = str(Path(args.output))

    if args.mode == "video":
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.fps = 30
        scene.frame_start = 1
        scene.frame_end = args.seconds * 30
        bpy.ops.render.render(animation=True)
    else:
        scene.frame_set(max(1, args.seconds * 15))
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
