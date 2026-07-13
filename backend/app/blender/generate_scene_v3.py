from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


V2_PATH = Path(__file__).with_name("generate_scene_v2.py")
SPEC = importlib.util.spec_from_file_location("arch_ai_blender_v2", V2_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load opening-aware Blender renderer from {V2_PATH}")
v2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v2)

INTERIOR_PATH = Path(__file__).with_name("interior_objects.py")
INTERIOR_SPEC = importlib.util.spec_from_file_location("arch_ai_blender_interiors", INTERIOR_PATH)
if INTERIOR_SPEC is None or INTERIOR_SPEC.loader is None:
    raise RuntimeError(f"Unable to load detailed interior generator from {INTERIOR_PATH}")
interiors = importlib.util.module_from_spec(INTERIOR_SPEC)
INTERIOR_SPEC.loader.exec_module(interiors)


def argument(name: str) -> str | None:
    if name not in sys.argv:
        return None
    index = sys.argv.index(name)
    return sys.argv[index + 1] if index + 1 < len(sys.argv) else None


scene_path = argument("--scene")
scene_data = json.loads(Path(scene_path).read_text(encoding="utf-8")) if scene_path else {}
assets = list(scene_data.get("assets", []))
asset_by_key = {
    f'{asset.get("category", "")}/{asset.get("slot", "")}': asset
    for asset in assets
}
asset_by_id = {str(asset.get("id", "")): asset for asset in assets}

original_add_box = v2.base.add_box
base_proxy = SimpleNamespace(**{
    name: getattr(v2.base, name)
    for name in dir(v2.base)
    if not name.startswith("__")
})
base_proxy.add_box = original_add_box


def reference_path(item: dict) -> str | None:
    _style, _material, _colour, reference_key = interiors.decode_style(item)
    if reference_key and reference_key in asset_by_key:
        return asset_by_key[reference_key].get("source_path")
    object_type = str(item.get("object_type") or item.get("slot") or "")
    candidate = next((
        asset for asset in assets
        if str(asset.get("slot", "")) in {object_type, "couch" if object_type == "sofa" else object_type}
    ), None)
    return candidate.get("source_path") if candidate else None


def detailed_object(item, furniture_mat, accent_mat, metal_mat, porcelain_mat):
    return interiors.add_detailed_object(
        base_proxy,
        item,
        furniture_mat,
        accent_mat,
        metal_mat,
        porcelain_mat,
        reference_path(item),
    )


def asset_aware_box(name, position, size, mat, rotation_y=0.0):
    asset = asset_by_id.get(str(name))
    if asset is None:
        return original_add_box(name, position, size, mat, rotation_y)
    item = {
        "id": asset.get("id", name),
        "object_type": asset.get("slot", "furniture"),
        "slot": asset.get("slot", "furniture"),
        "position": position,
        "size": size,
        "rotation_y": rotation_y,
        "asset_id": "|".join((
            str(asset.get("slot", "furniture")),
            "modern",
            "painted_metal" if str(asset.get("slot", "")).lower() in {"fridge", "stove", "washing_machine", "dryer"} else "fabric",
            "#A6ADB2" if str(asset.get("slot", "")).lower() in {"fridge", "stove", "washing_machine", "dryer"} else "#486B5A",
            f'{asset.get("category", "")}/{asset.get("slot", "")}',
        )),
    }
    materials = scene_data.get("materials", {})
    accent = v2.base.material_from_spec("Asset Accent", materials.get("accent", {}), "#2E79C6")
    metal = v2.base.material_from_spec("Asset Metal", materials.get("fixture_metal", {}), "#A6ADB2")
    porcelain = v2.base.material("Asset Porcelain", (0.92, 0.93, 0.91, 1), 0.24, 0.0, 0.58)
    return interiors.add_detailed_object(base_proxy, item, mat, accent, metal, porcelain, asset.get("source_path"))


v2.base.add_procedural_object = detailed_object
v2.base.add_box = asset_aware_box


if __name__ == "__main__":
    v2.main()
