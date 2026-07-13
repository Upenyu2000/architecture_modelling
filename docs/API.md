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
| POST | `/api/v1/projects/{id}/analyze` | Extract deterministic structural walls and rooms |
| POST | `/api/v1/projects/{id}/compile-architecture` | Apply optional ONNX/VLM refinement and compile openings, objects, collision and production JSON |
| GET | `/api/v1/projects/{id}/architecture.json` | Download the free-form production architecture schema |
| POST | `/api/v1/projects/{id}/manual-layout` | Start a blank editable layout over the uploaded plan |
| POST | `/api/v1/projects/{id}/rooms` | Add an initial room polygon |
| PATCH | `/api/v1/projects/{id}/rooms/{room_id}` | Rename a room |
| PATCH | `/api/v1/projects/{id}/rooms/{room_id}/geometry` | Replace a room with any valid 3–64 point polygon |
| DELETE | `/api/v1/projects/{id}/rooms/{room_id}` | Remove a room and rebuild shared/diagonal walls |
| POST | `/api/v1/projects/{id}/training-example` | Export the corrected plan, class mask and scene JSON into the local training workspace |
| PUT | `/api/v1/projects/{id}/materials` | Update PBR palette and cutaway settings |
| POST | `/api/v1/projects/{id}/render` | Queue preview/1080p/4K image render |
| POST | `/api/v1/projects/{id}/walkthrough` | Queue opening-aware Blender MP4 walkthrough |
| GET | `/api/v1/jobs/{job_id}` | Poll a render or drawing job |
| GET/PUT | `/api/v1/settings` | Local ONNX, OCR, training, vision and Blender settings |

## Structural analysis request

```json
{
  "plan_width_m": 14.0,
  "wall_height_m": 2.8,
  "wall_thickness_m": 0.16,
  "wall_detection": "clean",
  "minimum_wall_length_m": 0.9,
  "plan_type": "rendered",
  "detect_openings": true,
  "auto_furnish": true,
  "use_vision_ai": false
}
```

`plan_type` accepts `auto`, `blueprint` or `rendered`. Rendered mode suppresses coloured furniture, texture and uniform-background edges. `wall_detection` accepts `clean`, `balanced` or `detailed`.

The returned scene contains the cropped reference image, detection/model overlay, arbitrary room polygons, walls, materials and runtime metadata.

## Free-form manual room layout

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

Add an initial rectangle:

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

Replace it with a rhombus:

```json
PATCH /api/v1/projects/{id}/rooms/{room_id}/geometry
{
  "polygon": [[3.0, 0.8], [5.4, 3.0], [3.0, 5.2], [0.6, 3.0]]
}
```

Replace it with an L-shaped room:

```json
PATCH /api/v1/projects/{id}/rooms/{room_id}/geometry
{
  "polygon": [[1,1], [6,1], [6,3], [4,3], [4,7], [1,7]]
}
```

Rules:

- The polygon must contain 3–64 distinct points.
- Points are ordered around the boundary and the first point is not repeated at the end.
- Diagonal edges are valid.
- Self-crossing or overlapping edges are rejected.
- Every edit recalculates area, centroid, dimensions, shared walls, exterior walls, collision segments and camera waypoints.
- Opening and inferred-object data is cleared after geometry editing; compile the production scene again to recalculate it.

## Corrected training example

```json
POST /api/v1/projects/{id}/training-example
{
  "confirmed_rights": true
}
```

The endpoint refuses the request unless the caller confirms ownership or authorisation. It writes:

- the cropped source plan
- a discrete mask with background/wall/room/door/window IDs
- the authoritative free-form scene JSON
- a deterministic train/validation/test manifest record

The destination is the configured `training_workspace`, or the app’s local training workspace when none is configured.

## Production architecture export

`GET /api/v1/projects/{id}/architecture.json` returns:

```json
{
  "schema": "arch-ai-freeform-1.0",
  "project_metadata": {},
  "rooms": [
    {
      "room_id": "room-01",
      "room_type": "living_room",
      "vertices": [{"x": 1.2, "y": 0.5}, {"x": 6.8, "y": 1.2}, {"x": 5.5, "y": 5.8}]
    }
  ],
  "walls": [
    {
      "wall_id": "wall-01",
      "is_exterior": true,
      "path": [{"x": 1.2, "y": 0.5}, {"x": 6.8, "y": 1.2}],
      "height": 2.8,
      "thickness": 0.3
    }
  ],
  "openings": [],
  "fixtures": [],
  "materials": {},
  "viewport_compilation": {}
}
```

The export includes opening placement ratios, PBR map references, collision segments, first-person start/path and cutaway compilation data. Unverified pixel scale is written as `null`, not guessed.

## 3D-to-2D drawing request

```json
{
  "slice_height_m": 1.2,
  "up_axis": "y",
  "model_units": "auto",
  "include_dimensions": true
}
```

The drawing job produces floor-plan PNG/SVG/DXF, front/side elevation PNG/SVG and a ZIP manifest. `up_axis` accepts `y` or `z`; `model_units` accepts `auto`, `metres`, `millimetres`, `centimetres` or `feet`.

## Model settings

```json
PUT /api/v1/settings
{
  "segmentation_model_path": "D:/models/floorplan-segmentation.onnx",
  "segmentation_input_size": 512,
  "segmentation_threshold": 0.5,
  "training_workspace": "D:/ArchAITraining",
  "tesseract_executable": "C:/Program Files/Tesseract-OCR/tesseract.exe",
  "blender_executable": "C:/Program Files/Blender Foundation/Blender 4.4/blender.exe",
  "allow_remote_processing": false
}
```

The ONNX model uses a sidecar JSON defining labels, input size and normalization. Default classes are `background`, `wall`, `room`, `door`, `window`.

## Conditioning flow for advanced workers

```text
floorplan upload
  -> crop empty background and calibrate coordinates
  -> deterministic vector extraction
  -> optional local ONNX masks
  -> editable free-form room topology
  -> OCR and optional consented VLM refinement
  -> production architecture JSON
  -> Three.js cutaway/FPS and Blender depth/normal/semantic passes

asset upload
  -> background removal or approved image-to-3D adapter
  -> object mask, surface IDs and user-approved placement

material swatch
  -> diffuse/normal/roughness maps
  -> box/triplanar projection for angled/free-form geometry

render request
  -> opening-aware geometry render
  -> optional structurally constrained refinement
  -> segmentation/depth audit
  -> upscaler
```

A remote worker should accept signed scene manifests rather than a free-form prompt. Geometry remains authoritative; video or diffusion output must never move walls or invent unsupported objects.
