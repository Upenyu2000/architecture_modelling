from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import bpy


MATERIAL_SETTINGS: dict[str, tuple[float, float, float]] = {
    "fabric": (0.78, 0.0, 0.25),
    "leather": (0.34, 0.0, 0.52),
    "oak": (0.48, 0.0, 0.34),
    "walnut": (0.43, 0.0, 0.38),
    "stone": (0.52, 0.0, 0.4),
    "porcelain": (0.24, 0.0, 0.58),
    "chrome": (0.18, 0.9, 0.78),
    "painted_metal": (0.3, 0.72, 0.62),
}


def decode_style(item: dict[str, Any]) -> tuple[str, str, str, str | None]:
    parts = str(item.get("asset_id") or "").split("|")
    parts.extend([""] * (5 - len(parts)))
    style = parts[1] or "modern"
    material = parts[2] or "fabric"
    colour = parts[3] if len(parts[3]) == 7 and parts[3].startswith("#") else "#486B5A"
    return style, material, colour, parts[4] or None


def material_for(base, name: str, material_type: str, colour: str, image_path: str | None = None):
    roughness, metallic, specular = MATERIAL_SETTINGS.get(material_type, MATERIAL_SETTINGS["fabric"])
    fallback = base.hex_rgba(colour)
    if image_path and Path(image_path).exists():
        mat = base.image_material(name, image_path, fallback, roughness)
        bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.use_nodes else None
        if bsdf:
            if "Metallic" in bsdf.inputs:
                bsdf.inputs["Metallic"].default_value = metallic
            if "Specular IOR Level" in bsdf.inputs:
                bsdf.inputs["Specular IOR Level"].default_value = specular
        return mat
    return base.material(name, fallback, roughness, metallic, specular)


def bevel(obj, width: float = 0.035, segments: int = 3):
    if obj is None or not hasattr(obj, "modifiers"):
        return obj
    modifier = obj.modifiers.new(name="Softened edges", type="BEVEL")
    modifier.width = max(0.003, width)
    modifier.segments = max(1, segments)
    modifier.limit_method = "ANGLE"
    try:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    except Exception:
        pass
    finally:
        try:
            obj.select_set(False)
        except Exception:
            pass
    return obj


def box(base, name: str, position, size, mat, rotation: float = 0.0, radius: float = 0.035):
    return bevel(base.add_box(name, position, size, mat, rotation), min(radius, min(size) * 0.28), 3)


def cylinder(base, name: str, position, radius: float, depth: float, mat, vertices: int = 24):
    return base.add_cylinder(name, position, radius, depth, mat, vertices=vertices)


def _local(origin_x: float, origin_z: float, dx: float, dz: float, rotation: float) -> tuple[float, float]:
    return (
        origin_x + dx * math.cos(rotation) - dz * math.sin(rotation),
        origin_z + dx * math.sin(rotation) + dz * math.cos(rotation),
    )


def _part_position(x: float, y: float, z: float, dx: float, dz: float, rotation: float):
    px, pz = _local(x, z, dx, dz, rotation)
    return (px, y, pz)


def add_sofa(base, prefix, x, z, sx, sy, sz, rotation, fabric_mat, metal_mat):
    box(base, prefix + "-frame", _part_position(x, sy * 0.27, z, 0, 0, rotation), (sx * 0.9, sy * 0.3, sz * 0.82), fabric_mat, rotation, 0.1)
    for sign in (-1, 1):
        box(base, prefix + f"-arm-{sign}", _part_position(x, sy * 0.55, z, sign * sx * 0.43, 0, rotation), (sx * 0.14, sy * 0.64, sz * 0.9), fabric_mat, rotation, 0.1)
    seats = 3 if sx > 2.35 else 2
    seat_width = sx * 0.72 / seats
    for index in range(seats):
        offset = (index - (seats - 1) / 2) * seat_width
        box(base, prefix + f"-seat-{index}", _part_position(x, sy * 0.5, z, offset, sz * 0.08, rotation), (seat_width * 0.92, sy * 0.22, sz * 0.62), fabric_mat, rotation, 0.075)
        box(base, prefix + f"-back-{index}", _part_position(x, sy * 0.83, z, offset, -sz * 0.31, rotation), (seat_width * 0.94, sy * 0.54, sz * 0.2), fabric_mat, rotation, 0.085)
    for x_sign in (-1, 1):
        for z_sign in (-1, 1):
            px, pz = _local(x, z, x_sign * sx * 0.36, z_sign * sz * 0.31, rotation)
            cylinder(base, prefix + f"-leg-{x_sign}-{z_sign}", (px, sy * 0.09, pz), 0.04, sy * 0.18, metal_mat, 16)


def add_bed(base, prefix, x, z, sx, sy, sz, rotation, wood_mat, textile_mat, porcelain_mat):
    box(base, prefix + "-frame", (x, sy * 0.2, z), (sx, sy * 0.3, sz), wood_mat, rotation, 0.035)
    box(base, prefix + "-mattress", (x, sy * 0.49, z), (sx * 0.96, sy * 0.34, sz * 0.92), porcelain_mat, rotation, 0.085)
    box(base, prefix + "-headboard", _part_position(x, sy * 0.92, z, 0, -sz * 0.46, rotation), (sx, sy * 1.05, sz * 0.09), wood_mat, rotation, 0.04)
    for sign in (-1, 1):
        box(base, prefix + f"-pillow-{sign}", _part_position(x, sy * 0.72, z, sign * sx * 0.26, -sz * 0.23, rotation), (sx * 0.38, sy * 0.22, sz * 0.28), textile_mat, rotation, 0.08)
    box(base, prefix + "-duvet", _part_position(x, sy * 0.66, z, 0, sz * 0.17, rotation), (sx * 0.9, sy * 0.09, sz * 0.52), textile_mat, rotation, 0.035)


def add_table(base, prefix, x, z, sx, sy, sz, rotation, top_mat, metal_mat, dining=False):
    box(base, prefix + "-top", (x, sy * 0.91, z), (sx, max(0.07, sy * 0.14), sz), top_mat, rotation, 0.035)
    leg_height = sy * 0.82
    for x_sign in (-1, 1):
        for z_sign in (-1, 1):
            px, pz = _local(x, z, x_sign * sx * 0.39, z_sign * sz * 0.34, rotation)
            cylinder(base, prefix + f"-leg-{x_sign}-{z_sign}", (px, leg_height / 2, pz), 0.055 if dining else 0.04, leg_height, metal_mat, 18)
    if dining:
        for side in (-1, 1):
            for offset in (-0.28, 0.28):
                cx, cz = _local(x, z, offset * sx, side * sz * 0.82, rotation)
                chair_rotation = rotation + (math.pi if side < 0 else 0)
                box(base, prefix + f"-chair-seat-{side}-{offset}", (cx, sy * 0.48, cz), (sx * 0.2, sy * 0.1, sz * 0.28), top_mat, chair_rotation, 0.035)
                bx, bz = _local(cx, cz, 0, sz * 0.1, chair_rotation)
                box(base, prefix + f"-chair-back-{side}-{offset}", (bx, sy * 0.73, bz), (sx * 0.2, sy * 0.48, sz * 0.08), top_mat, chair_rotation, 0.035)


def add_storage(base, prefix, x, z, sx, sy, sz, rotation, body_mat, metal_mat, wardrobe=False):
    box(base, prefix + "-body", (x, sy / 2, z), (sx, sy, sz), body_mat, rotation, 0.025)
    px, pz = _local(x, z, 0, sz * 0.51, rotation)
    box(base, prefix + "-seam", (px, sy * 0.5, pz), (0.018, sy * 0.86, 0.02), metal_mat, rotation, 0.006)
    for sign in (-1, 1):
        hx, hz = _local(x, z, sign * sx * 0.24, sz * 0.53, rotation)
        cylinder(base, prefix + f"-handle-{sign}", (hx, sy * 0.52, hz), 0.012, 0.22 if wardrobe else 0.1, metal_mat, 12)


def add_appliance(base, prefix, object_type, x, z, sx, sy, sz, rotation, body_mat, metal_mat, glass_mat):
    box(base, prefix + "-body", (x, sy / 2, z), (sx, sy, sz), body_mat, rotation, 0.035)
    front_x, front_z = _local(x, z, 0, sz * 0.515, rotation)
    if object_type == "fridge":
        box(base, prefix + "-seam", (front_x, sy * 0.56, front_z), (sx * 0.9, 0.018, 0.02), metal_mat, rotation, 0.004)
        hx, hz = _local(x, z, sx * 0.32, sz * 0.54, rotation)
        cylinder(base, prefix + "-handle", (hx, sy * 0.58, hz), 0.018, sy * 0.42, metal_mat, 12)
    elif object_type == "stove":
        for index, (dx, dz) in enumerate(((-0.25, -0.23), (0.25, -0.23), (-0.25, 0.23), (0.25, 0.23))):
            px, pz = _local(x, z, dx * sx, dz * sz, rotation)
            bpy.ops.mesh.primitive_torus_add(major_radius=min(sx, sz) * 0.13, minor_radius=0.014, major_segments=28, minor_segments=10, location=(px, sy + 0.012, pz), rotation=(math.pi / 2, 0, rotation))
            bpy.context.active_object.name = prefix + f"-burner-{index}"
            bpy.context.active_object.data.materials.append(metal_mat)
        box(base, prefix + "-oven-glass", (front_x, sy * 0.48, front_z), (sx * 0.72, sy * 0.48, 0.025), glass_mat, rotation, 0.01)
    elif object_type in {"washing_machine", "dryer"}:
        bpy.ops.mesh.primitive_torus_add(major_radius=sx * 0.28, minor_radius=sx * 0.045, major_segments=42, minor_segments=12, location=(front_x, sy * 0.52, front_z), rotation=(math.pi / 2, 0, rotation))
        bpy.context.active_object.name = prefix + "-door-ring"
        bpy.context.active_object.data.materials.append(metal_mat)
        cylinder(base, prefix + "-door-glass", (front_x, sy * 0.52, front_z + 0.01), sx * 0.235, 0.02, glass_mat, 36)


def add_bathroom(base, prefix, object_type, x, z, sx, sy, sz, rotation, porcelain_mat, metal_mat, glass_mat):
    if object_type == "bathtub":
        box(base, prefix + "-back", _part_position(x, sy * 0.42, z, 0, -sz * 0.42, rotation), (sx, sy * 0.84, sz * 0.16), porcelain_mat, rotation, 0.07)
        box(base, prefix + "-front", _part_position(x, sy * 0.42, z, 0, sz * 0.42, rotation), (sx, sy * 0.84, sz * 0.16), porcelain_mat, rotation, 0.07)
        for sign in (-1, 1):
            box(base, prefix + f"-side-{sign}", _part_position(x, sy * 0.42, z, sign * sx * 0.43, 0, rotation), (sx * 0.16, sy * 0.84, sz * 0.7), porcelain_mat, rotation, 0.07)
        box(base, prefix + "-water", (x, sy * 0.25, z), (sx * 0.74, sy * 0.06, sz * 0.62), glass_mat, rotation, 0.02)
    elif object_type == "toilet":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=36, ring_count=20, location=(x, sy * 0.34, z + sz * 0.08), scale=(sx * 0.5, sy * 0.34, sz * 0.52))
        bowl = bpy.context.active_object
        bowl.name = prefix + "-bowl"
        bowl.data.materials.append(porcelain_mat)
        box(base, prefix + "-tank", _part_position(x, sy * 0.7, z, 0, -sz * 0.3, rotation), (sx * 0.72, sy * 0.5, sz * 0.34), porcelain_mat, rotation, 0.055)
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=18, location=(x, sy * 0.75, z), scale=(sx * 0.5, sy * 0.18, sz * 0.5))
        basin = bpy.context.active_object
        basin.name = prefix + "-basin"
        basin.data.materials.append(porcelain_mat)
        cylinder(base, prefix + "-pedestal", (x, sy * 0.39, z), sx * 0.2, sy * 0.64, porcelain_mat, 28)


def add_detailed_object(base, item: dict[str, Any], furniture_mat, accent_mat, metal_mat, porcelain_mat, image_path: str | None = None):
    object_type = str(item.get("object_type") or item.get("slot") or "furniture").lower().replace(" ", "_")
    x, _y, z = map(float, item.get("coordinates") or item.get("position") or (0.0, 0.5, 0.0))
    sx, sy, sz = map(float, item.get("size") or (1.0, 1.0, 1.0))
    rotation_value = float(item.get("rotation_deg", math.degrees(float(item.get("rotation_y", 0.0)))))
    rotation = math.radians(rotation_value)
    prefix = f'proc-{item.get("id", object_type)}'
    _style, material_type, colour, _reference = decode_style(item)
    primary_mat = material_for(base, prefix + "-surface", material_type, colour, image_path)
    wood_mat = material_for(base, prefix + "-wood", "walnut", "#704A32", image_path if material_type in {"oak", "walnut"} else None)
    textile_mat = material_for(base, prefix + "-textile", "fabric", "#ECE8DF")
    glass_mat = base.material(prefix + "-glass", (0.3, 0.58, 0.72, 0.35), 0.08, 0.05, 0.7)

    if object_type in {"sofa", "couch", "sectional_sofa", "patio_sofa", "armchair", "chair", "office_chair", "dining_chair"}:
        if object_type in {"armchair", "chair", "office_chair", "dining_chair"}:
            sx = min(sx, 1.1)
            sz = min(sz, 1.05)
        add_sofa(base, prefix, x, z, sx, sy, sz, rotation, primary_mat, metal_mat)
    elif object_type == "bed":
        add_bed(base, prefix, x, z, sx, sy, sz, rotation, wood_mat, textile_mat, porcelain_mat)
    elif object_type in {"coffee_table", "dining_table", "desk", "outdoor_table"}:
        add_table(base, prefix, x, z, sx, sy, sz, rotation, primary_mat if material_type in {"oak", "walnut", "stone"} else wood_mat, metal_mat, dining=object_type == "dining_table")
    elif object_type in {"tv_unit", "wardrobe", "cabinetry", "vanity", "dresser", "nightstand", "sideboard", "shelving"}:
        add_storage(base, prefix, x, z, sx, sy, sz, rotation, primary_mat if material_type in {"oak", "walnut", "painted_metal"} else wood_mat, metal_mat, wardrobe=object_type in {"wardrobe", "shelving"})
    elif object_type in {"fridge", "stove", "washing_machine", "dryer"}:
        add_appliance(base, prefix, object_type, x, z, sx, sy, sz, rotation, primary_mat, metal_mat, glass_mat)
    elif object_type in {"toilet", "sink", "bathtub"}:
        add_bathroom(base, prefix, object_type, x, z, sx, sy, sz, rotation, porcelain_mat, metal_mat, glass_mat)
    elif object_type in {"kitchen_island", "countertop"}:
        box(base, prefix + "-body", (x, sy * 0.45, z), (sx * 0.88, sy * 0.86, sz * 0.84), wood_mat, rotation, 0.025)
        stone_mat = material_for(base, prefix + "-stone", "stone", "#D7D0C4", image_path if material_type == "stone" else None)
        box(base, prefix + "-top", (x, sy * 0.96, z), (sx, sy * 0.12, sz), stone_mat, rotation, 0.025)
    elif object_type == "light_fixture" or object_type == "lamp" or object_type == "pendant_light":
        cylinder(base, prefix + "-stem", (x, sy * 0.75, z), 0.025, sy * 0.5, metal_mat, 12)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, location=(x, sy * 0.4, z), scale=(sx * 0.42, sy * 0.34, sz * 0.42))
        shade = bpy.context.active_object
        shade.name = prefix + "-shade"
        shade.data.materials.append(primary_mat)
        bpy.ops.object.light_add(type="POINT", location=(x, sy * 0.4, z))
        bpy.context.active_object.data.energy = 55
        bpy.context.active_object.data.color = base.hex_rgba(colour)[:3]
    elif object_type == "planter":
        cylinder(base, prefix + "-pot", (x, sy * 0.32, z), min(sx, sz) * 0.42, sy * 0.62, primary_mat, 36)
        leaf_mat = material_for(base, prefix + "-leaf", "fabric", "#315E3A")
        for index in range(8):
            angle = index / 8 * math.pi * 2
            px = x + math.cos(angle) * sx * 0.17
            pz = z + math.sin(angle) * sz * 0.17
            bpy.ops.mesh.primitive_uv_sphere_add(segments=18, ring_count=10, location=(px, sy * (0.68 + (index % 3) * 0.1), pz), scale=(sx * 0.12, sy * 0.27, sz * 0.08))
            bpy.context.active_object.data.materials.append(leaf_mat)
    else:
        box(base, prefix + "-body", (x, sy * 0.45, z), (sx * 0.9, sy * 0.72, sz * 0.86), primary_mat, rotation, 0.06)
        box(base, prefix + "-top", (x, sy * 0.88, z), (sx, sy * 0.16, sz), accent_mat, rotation, 0.04)
    return prefix
