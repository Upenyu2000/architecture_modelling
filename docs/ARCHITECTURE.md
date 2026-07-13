# Architecture

## Process topology

```text
Electron main process
  ├─ starts bundled dreamhome-ai.exe on 127.0.0.1:8765
  ├─ hosts the React/Vite renderer
  └─ provides safe file-picker and Explorer IPC methods

React renderer
  ├─ uploads floor plans, building models and assets to the local API
  ├─ displays pipeline status and the structure-validation overlay
  ├─ renders scene.json with Three.js
  ├─ manages reset and persistent save slots
  ├─ requests still/video jobs
  └─ requests reverse 3D-to-2D drawing jobs

FastAPI service
  ├─ project, snapshot and asset storage
  ├─ OpenCV structural centre-line and room extraction
  ├─ Trimesh model sectioning and technical drawing export
  ├─ deterministic asset mapping
  ├─ technical 1080p/4K renderer
  ├─ Blender background renderer
  └─ optional local/remote AI adapters
```

## 2D plan to 3D structure

The shipped extractor avoids treating every visible edge as a wall:

1. Rasterise PNG, JPG or the first PDF page.
2. Create an adaptive dark-pixel mask with Otsu thresholding.
3. Use separate horizontal and vertical morphology kernels to isolate long structural regions.
4. Convert each thick region into one centre line.
5. Reject components that are too thin or too short for the selected Clean, Balanced or Detailed mode.
6. Merge collinear segments and keep connected structural runs.
7. Rebuild a clean room mask from only the accepted wall centre lines.
8. Bridge likely door gaps for room discovery without turning those virtual bridges into 3D walls.
9. Produce a structure overlay for human verification before rendering.
10. Extrude the accepted centre lines to the requested wall height.

This reduces duplicate parallel walls and suppresses labels, dimensions, furniture symbols and other non-structural linework.

## 3D model to 2D drawings

The reverse workflow is deterministic:

1. Upload a GLB, OBJ, STL or PLY building mesh.
2. Resolve units from the user setting, model metadata or conservative extent inference.
3. Select Y-up or Z-up orientation.
4. Intersect the mesh with a horizontal plane at the requested cut height.
5. Convert the cross-section into vector linework.
6. Fall back to a projected footprint when the section does not intersect usable geometry.
7. Generate floor-plan PNG, SVG and DXF files.
8. Project the mesh to generate front and side elevation PNG/SVG drawings.
9. Add overall dimensions and package the drawing set with a JSON manifest in a ZIP archive.

The drawing generator does not infer BIM semantics such as doors, windows, room names or material schedules from arbitrary meshes. Those require IFC/BIM metadata or a dedicated semantic model.

## Model suite

1. **Computer vision**: the shipped path uses adaptive thresholding, directional morphology, wall centre-line extraction, component thickness/length filtering, line merging and closed-room contours. A fine-tuned YOLOv8-seg checkpoint can be introduced without changing the API.
2. **Scale**: the user calibrates the known plan width. This is more reliable than pretending OCR dimensions are always correct. A production OCR service should extract dimension strings and require confidence/consistency checks before it overrides the calibrated scale.
3. **3D geometry**: walls are authoritative line segments extruded to a fixed height. Rooms are polygons. Furniture is represented as typed bounding boxes until an approved GLB exists.
4. **Technical drawings**: Trimesh performs deterministic cross-sections and projections. SVG and DXF preserve editable linework, while PNG provides immediate viewing.
5. **Image-to-3D**: TRELLIS or Hunyuan3D should run in an isolated CUDA environment. The desktop app invokes it through the `image_to_3d_command` template and expects a GLB output.
6. **Materials and diffusion**: a structural depth/normal pass from Blender should be used as ControlNet conditioning. User swatches are reference-only inputs. The generated texture is baked to selected surfaces, not used to regenerate the scene geometry.
7. **Upscaling**: render natively at the requested size when practical. Real-ESRGAN is a post-process for texture detail, not a substitute for geometry.
8. **Video**: Blender is the consistency authority. A video diffusion model may refine rendered frames only after optical-flow and depth consistency checks.

## Hallucination controls

- The verified wall and room graph is immutable during diffusion.
- The structure overlay exposes the exact geometry source before rendering.
- Every placed object must reference a user asset manifest entry.
- Object classes have fixed physical bounds and collision checks.
- Unrequested object classes are excluded from prompts and rejected from segmentation audits.
- Materials are applied only to explicitly selected object IDs.
- Prompt conditioning includes a negative inventory: `no extra furniture, no new doors, no moved walls, no altered windows`.
- Render output is compared with structural depth and segmentation passes; a failed geometry check is rejected.
- Reverse drawings are generated from mesh sections, not from free-form generative prompts.
- Remote processing is opt-in and disabled by default.

## Production deployment recommendation

Use the Windows app as the client and orchestration layer. Keep geometry parsing and technical drawing generation local. Put optional GPU-heavy generation behind a private RunPod endpoint or an organisation-controlled GPU service, with short-lived object storage URLs, per-project encryption, deletion policies, request signing and no model-provider retention. Blender rendering can remain local for privacy or run in the same private GPU worker.
