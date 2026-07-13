# Dream Home Visualizer — Standalone Windows App

A local-first Electron + Python desktop application that converts a 2D floor plan into a deterministic 3D house scene, maps user-uploaded materials and furniture, produces HD/4K renders, generates a Blender MP4 walkthrough, and converts uploaded 3D building models back into measured 2D drawing sets.

## What works in the repository

- Windows NSIS installer built with Electron Builder.
- PNG, JPG and PDF floor-plan ingestion.
- Clean structural centre-line extraction that suppresses text, furniture symbols and duplicate wall edges.
- Clean, Balanced and Detailed wall-detection modes plus a minimum wall-length control.
- Structure overlay showing the exact wall lines and room boundaries used by the 3D scene.
- User-controlled real-world scale and wall height.
- Flooring, wall, kitchen, living-room and bathroom upload tabs.
- Deterministic asset placement with a live Three.js scene preview.
- GLB, OBJ, STL and PLY building-model uploads for reverse 3D-to-2D conversion.
- Floor-plan sectioning at a configurable cut height and Y-up or Z-up axis selection.
- PNG, SVG and DXF floor plans, front and side elevation drawings, dimensions and a ZIP drawing package.
- Persistent named save slots for uploads, geometry, drawings, renders and walkthroughs.
- Reset control that clears the active project without deleting save slots.
- Local project storage under the Windows application-data directory.
- Fast technical PNG renders at preview, 1080p and 4K.
- Blender 4.x background rendering and 5–30 second MP4 walkthroughs.
- Optional command adapter for local TRELLIS or Hunyuan3D environments.
- Optional private remote endpoint adapter; remote upload is disabled by default.
- GitHub Actions workflow that builds the Windows installer.

## Important production boundary

The desktop application and the deterministic geometry pipeline are self-contained. Large generative models such as TRELLIS, Hunyuan3D, Stable Diffusion/ControlNet, Real-ESRGAN and video diffusion are not embedded in the installer because their model weights, CUDA requirements and licences make a normal Windows package impractical. The app exposes explicit local-command and private-endpoint adapters for those models and never uploads a user's home plan without a deliberate setting.

The reverse drawing workflow uses deterministic mesh cross-sections rather than an image-generation model. GLB is the preferred single-file model format. OBJ models that depend on separate MTL or texture files can still be sectioned, but their external materials are not needed for technical drawings.

## Build on Windows

Install Node.js 22+, Python 3.11+, and optionally Blender 4.x. Then run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\build-windows.ps1
```

The installer is created in `release/`.

## Development

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
npm install
npm run dev
```

## Recommended production model suite

| Stage | Default in this build | Optional production model |
|---|---|---|
| Floor-plan parsing | Directional morphology, wall centre lines, thickness filtering and closed-room contours | Fine-tuned YOLOv8-seg or Mask2Former blueprint model |
| Text and scale | Manual width calibration | PaddleOCR/Surya plus dimension-line parser |
| Furniture reconstruction | Deterministic proxy geometry | TRELLIS or Hunyuan3D 2.x in a dedicated CUDA environment |
| Scene assembly | Three.js preview + Blender Python | Blender Geometry Nodes/Cycles |
| 3D-to-2D drawings | Trimesh cross-sections with PNG/SVG/DXF exports | BIM/IFC semantic extraction for construction-document detail |
| Texture conditioning | Original user swatches | SDXL/Flux ControlNet depth with IP-Adapter reference conditioning |
| Upscaling | Native 1080p/4K render target | Real-ESRGAN or a latent upscaler |
| Walkthrough | Blender camera path, H.264 MP4 | Video diffusion only as a post-process, never as geometry authority |

See [Architecture](docs/ARCHITECTURE.md), [API](docs/API.md), and [AI model setup](docs/MODEL_SETUP.md).
