# Architecture

## Process topology

```text
Electron main process
  ├─ starts bundled dreamhome-ai.exe on 127.0.0.1:8765
  ├─ hosts the React/Vite renderer
  └─ provides safe file-picker and Explorer IPC methods

React renderer
  ├─ uploads floor plans and assets to the local API
  ├─ displays pipeline status
  ├─ renders scene.json with Three.js
  └─ requests still/video jobs

FastAPI service
  ├─ project and asset storage
  ├─ OpenCV blueprint extraction
  ├─ deterministic asset mapping
  ├─ technical 1080p/4K renderer
  ├─ Blender background renderer
  └─ optional local/remote AI adapters
```

## Model suite

1. **Computer vision**: the shipped path uses adaptive image normalisation, binary wall masks, Canny edges, probabilistic Hough lines, line merging, morphological closure and room contours. A fine-tuned YOLOv8-seg checkpoint can be introduced without changing the API.
2. **Scale**: the user calibrates the known plan width. This is more reliable than pretending OCR dimensions are always correct. A production OCR service should extract dimension strings and require confidence/consistency checks before it overrides the calibrated scale.
3. **3D geometry**: walls are authoritative line segments extruded to a fixed height. Rooms are polygons. Furniture is represented as typed bounding boxes until an approved GLB exists.
4. **Image-to-3D**: TRELLIS or Hunyuan3D should run in an isolated CUDA environment. The desktop app invokes it through the `image_to_3d_command` template and expects a GLB output.
5. **Materials and diffusion**: a structural depth/normal pass from Blender should be used as ControlNet conditioning. User swatches are reference-only inputs. The generated texture is baked to selected surfaces, not used to regenerate the scene geometry.
6. **Upscaling**: render natively at the requested size when practical. Real-ESRGAN is a post-process for texture detail, not a substitute for geometry.
7. **Video**: Blender is the consistency authority. A video diffusion model may refine rendered frames only after optical-flow and depth consistency checks.

## Hallucination controls

- The wall and room graph is immutable during diffusion.
- Every placed object must reference a user asset manifest entry.
- Object classes have fixed physical bounds and collision checks.
- Unrequested object classes are excluded from prompts and rejected from segmentation audits.
- Materials are applied only to explicitly selected object IDs.
- Prompt conditioning includes a negative inventory: `no extra furniture, no new doors, no moved walls, no altered windows`.
- Render output is compared with structural depth and segmentation passes; a failed geometry check is rejected.
- Remote processing is opt-in and disabled by default.

## Production deployment recommendation

Use the Windows app as the client and orchestration layer. Keep geometry parsing local. Put optional GPU-heavy generation behind a private RunPod endpoint or an organisation-controlled GPU service, with short-lived object storage URLs, per-project encryption, deletion policies, request signing and no model-provider retention. Blender rendering can remain local for privacy or run in the same private GPU worker.
