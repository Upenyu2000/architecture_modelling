# Local API

Base URL: `http://127.0.0.1:8765`

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service readiness |
| GET | `/api/v1/projects` | List local projects |
| POST | `/api/v1/projects` | Create a local project |
| GET | `/api/v1/projects/{id}` | Read project state |
| POST | `/api/v1/projects/{id}/floorplan` | Upload PNG/JPG/PDF floor plan |
| POST | `/api/v1/projects/{id}/assets/{category}/{slot}` | Upload a material or furniture reference |
| POST | `/api/v1/projects/{id}/analyze` | Extract walls/rooms and assemble scene manifest |
| PATCH | `/api/v1/projects/{id}/rooms/{room_id}` | Correct a room label |
| POST | `/api/v1/projects/{id}/render` | Queue preview/1080p/4K image render |
| POST | `/api/v1/projects/{id}/walkthrough` | Queue deterministic MP4 walkthrough |
| GET | `/api/v1/jobs/{job_id}` | Poll a render job |
| GET/PUT | `/api/v1/settings` | Local model and Blender settings |

## Conditioning flow for an advanced diffusion worker

```text
floorplan upload
  -> immutable wall/room scene graph
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
