# Local API

Base URL: `http://127.0.0.1:8765`

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service readiness |
| GET | `/api/v1/projects` | List local projects |
| POST | `/api/v1/projects` | Create a local project |
| GET | `/api/v1/projects/{id}` | Read project state |
| POST | `/api/v1/projects/{id}/reset` | Clear active uploads, geometry, drawings and outputs while preserving save slots |
| GET/POST | `/api/v1/projects/{id}/save-slots` | List or create complete local build snapshots |
| POST | `/api/v1/projects/{id}/save-slots/{slot_id}/load` | Restore a saved build |
| DELETE | `/api/v1/projects/{id}/save-slots/{slot_id}` | Delete a saved build |
| POST | `/api/v1/projects/{id}/floorplan` | Upload PNG/JPG/PDF floor plan and crop uniform borders |
| POST | `/api/v1/projects/{id}/building-model` | Upload GLB/OBJ/STL/PLY building model |
| POST | `/api/v1/projects/{id}/drawings` | Queue floor-plan and elevation drawing generation |
| POST | `/api/v1/projects/{id}/assets/{category}/{slot}` | Upload a material or furniture reference |
| POST | `/api/v1/projects/{id}/analyze` | Extract structural walls and rooms using blueprint or rendered-plan mode |
| POST | `/api/v1/projects/{id}/manual-layout` | Start a blank editable room layout over the uploaded plan |
| POST | `/api/v1/projects/{id}/rooms` | Add a rectangular room to the active layout |
| PATCH | `/api/v1/projects/{id}/rooms/{room_id}` | Rename a room |
| PATCH | `/api/v1/projects/{id}/rooms/{room_id}/geometry` | Move, resize or reshape a room polygon |
| DELETE | `/api/v1/projects/{id}/rooms/{room_id}` | Remove a room and rebuild shared walls |
| POST | `/api/v1/projects/{id}/render` | Queue preview/1080p/4K aligned image render |
| POST | `/api/v1/projects/{id}/walkthrough` | Queue deterministic MP4 walkthrough |
| GET | `/api/v1/jobs/{job_id}` | Poll a render or drawing job |
| GET/PUT | `/api/v1/settings` | Local model and Blender settings |

## Structural analysis request

```json
{
  "plan_width_m": 14.0,
  "wall_height_m": 2.8,
  "wall_thickness_m": 0.16,
  "wall_detection": "clean",
  "minimum_wall_length_m": 0.9,
  "plan_type": "rendered"
}
```

`plan_type` accepts `auto`, `blueprint` or `rendered`. Rendered mode is intended for furnished top-down images and suppresses coloured furniture, texture and black-background edges. `wall_detection` accepts `clean`, `balanced` or `detailed`. Clean mode uses stronger length and thickness filtering.

The returned scene contains:

- `reference_image_url`: cropped plan aligned to scene coordinates
- `detection_preview_url`: automatic structural overlay
- `layout_mode`: `automatic` or `manual`
- room polygons and a deduplicated wall graph

## Manual room layout

Start a blank manual layout:

```json
POST /api/v1/projects/{id}/manual-layout
{
  "plan_width_m": 14.0,
  "wall_height_m": 2.8,
  "wall_thickness_m": 0.16,
  "clear_existing": true
}
```

Add a room:

```json
POST /api/v1/projects/{id}/rooms
{
  "name": "Bedroom 1",
  "x": 1.2,
  "z": 0.8,
  "width": 3.6,
  "depth": 4.1
}
```

Move, resize or reshape it by sending its complete polygon:

```json
PATCH /api/v1/projects/{id}/rooms/{room_id}/geometry
{
  "polygon": [[1.2, 0.8], [4.8, 0.8], [4.8, 4.9], [1.2, 4.9]]
}
```

After every room edit, the service recalculates the area and centroid and rebuilds the wall network. Overlapping shared room boundaries become one wall rather than duplicate parallel walls.

## 3D-to-2D drawing request

```json
{
  "slice_height_m": 1.2,
  "up_axis": "y",
  "model_units": "auto",
  "include_dimensions": true
}
```

The drawing job produces a ZIP package containing:

- floor-plan PNG, SVG and DXF
- front-elevation PNG and SVG
- side-elevation PNG and SVG
- drawing-set JSON manifest

`up_axis` accepts `y` or `z`. `model_units` accepts `auto`, `metres`, `millimetres`, `centimetres` or `feet`.

## Conditioning flow for an advanced diffusion worker

```text
floorplan upload
  -> crop empty background and calibrate scene coordinates
  -> automatic analysis or user-authored room graph
  -> immutable deduplicated wall graph
  -> Blender depth, normal, semantic-ID and edge passes
  -> ControlNet depth/line conditioning

asset upload
  -> background removal
  -> asset identity embedding / IP-Adapter reference
  -> approved GLB or bounding box
  -> object mask and surface IDs

material swatch
  -> seamless PBR synthesis
  -> diffuse/normal/roughness maps
  -> bind only to allowed surface IDs

render request
  -> aligned top-down or perspective base render
  -> diffusion refinement with structural controls
  -> segmentation/depth audit
  -> upscaler
  -> final output
```

A remote worker should accept signed project manifests rather than a free-form prompt. The API should send separate fields for scene graph, positive references, negative inventory, allowed object IDs, depth map, normal map, segmentation map, seed and denoise strength.
