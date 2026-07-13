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
| POST | `/api/v1/projects/{id}/floorplan` | Upload PNG/JPG/PDF floor plan |
| POST | `/api/v1/projects/{id}/building-model` | Upload GLB/OBJ/STL/PLY building model |
| POST | `/api/v1/projects/{id}/drawings` | Queue floor-plan and elevation drawing generation |
| POST | `/api/v1/projects/{id}/assets/{category}/{slot}` | Upload a material or furniture reference |
| POST | `/api/v1/projects/{id}/analyze` | Extract structural wall centre lines/rooms and assemble scene manifest |
| PATCH | `/api/v1/projects/{id}/rooms/{room_id}` | Correct a room label |
| POST | `/api/v1/projects/{id}/render` | Queue preview/1080p/4K image render |
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
  "minimum_wall_length_m": 0.9
}
```

`wall_detection` accepts `clean`, `balanced` or `detailed`. Clean mode uses stronger length and thickness filtering. The returned scene includes `detection_preview_url`, which displays the exact structural centre lines used for wall extrusion.

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
  -> cleaned structural centre-line and room graph
  -> user verifies structure overlay
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
  -> base physically rendered frame
  -> diffusion refinement with structural controls
  -> segmentation/depth audit
  -> upscaler
  -> final output
```

A remote worker should accept signed project manifests rather than a free-form prompt. The API should send separate fields for scene graph, positive references, negative inventory, allowed object IDs, depth map, normal map, segmentation map, seed and denoise strength.
