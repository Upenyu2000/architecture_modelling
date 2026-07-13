# Dream Home Visualizer — Standalone Windows App

A local-first Electron + Python desktop application that converts a 2D floor plan into a deterministic 3D house scene, maps user-uploaded materials and furniture, produces HD/4K renders, and generates a Blender MP4 walkthrough.

## What works in the repository

- Windows NSIS installer built with Electron Builder.
- PNG, JPG and PDF floor-plan ingestion.
- OpenCV structural wall extraction and closed-room detection.
- User-controlled real-world scale and wall height.
- Flooring, wall, kitchen, living-room and bathroom upload tabs.
- Deterministic asset placement with a live Three.js scene preview.
- Local project storage under the Windows application-data directory.
- Fast technical PNG renders at preview, 1080p and 4K.
- Blender 4.x background rendering and 5–30 second MP4 walkthroughs.
- Optional command adapter for local TRELLIS or Hunyuan3D environments.
- Optional private remote endpoint adapter; remote upload is disabled by default.
- GitHub Actions workflow that builds the Windows installer.

## Important production boundary

The desktop application and the deterministic geometry pipeline are self-contained. Large generative models such as TRELLIS, Hunyuan3D, Stable Diffusion/ControlNet, Real-ESRGAN and video diffusion are not embedded in the installer because their model weights, CUDA requirements and licences make a normal Windows package impractical. The app exposes explicit local-command and private-endpoint adapters for those models and never uploads a user's home plan without a deliberate setting.

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
| Floor-plan parsing | OpenCV thresholding, Hough lines, room contours | Fine-tuned YOLOv8-seg or Mask2Former blueprint model |
| Text and scale | Manual width calibration | PaddleOCR/Surya plus dimension-line parser |
| Furniture reconstruction | Deterministic proxy geometry | TRELLIS or Hunyuan3D 2.x in a dedicated CUDA environment |
| Scene assembly | Three.js preview + Blender Python | Blender Geometry Nodes/Cycles |
| Texture conditioning | Original user swatches | SDXL/Flux ControlNet depth with IP-Adapter reference conditioning |
| Upscaling | Native 1080p/4K render target | Real-ESRGAN or a latent upscaler |
| Walkthrough | Blender camera path, H.264 MP4 | Video diffusion only as a post-process, never as geometry authority |

See [Architecture](docs/ARCHITECTURE.md), [API](docs/API.md), and [AI model setup](docs/MODEL_SETUP.md).
