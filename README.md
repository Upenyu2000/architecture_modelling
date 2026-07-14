# Dream Home Visualizer 1.6.0 — Standalone Windows App

A local-first Electron + Python desktop application that converts 2D floor plans into editable free-form architectural geometry, compiles synchronized cutaway and first-person 3D environments, maps PBR materials, creates HD/4K Blender output, generates walkthrough videos, and converts uploaded 3D building models back into measured 2D drawing sets.

## Version 1.6.0 stability upgrade

- A shared boundary now remains two independent room-owned walls while one canonical portal entity controls both wall cut-outs.
- The opening editor recognises `wall_ids`, highlights every wall owned by a shared portal, and no longer labels a valid shared door as unattached.
- Repeated clicks are guarded in both the editor and application request layer, preventing duplicate door submissions.
- The first-person position is stored above the rendered scene so door interaction, FOV changes, room transitions, and switching view modes do not reset the player to spawn.
- Portal collision now validates both distance along the doorway and perpendicular distance through the wall, keeping exterior white space non-traversable.
- The default first-person collision radius is reduced to 0.14 m while the default FOV remains 100 degrees with a 70–120 degree adjustment range.

## What works in the repository

- Windows NSIS installer built with Electron Builder.
- PNG, JPG and PDF floor-plan ingestion.
- Clean structural centre-line extraction that suppresses text, furniture symbols and duplicate wall edges.
- Optional local ONNX semantic segmentation for walls, rooms, doors and windows.
- Free-form room polygons with up to 64 editable vertices.
- Add, remove and drag individual room points; create rhombus, trapezoid, L-shaped, octagonal and irregular rooms.
- Room move/scale controls, configurable snapping and an aligned plan-reference layer.
- Validation that rejects self-crossing or overlapping polygon edges.
- Shared, diagonal and exterior walls rebuilt from confirmed room boundaries.
- One canonical door or passage across touching independent walls, with synchronized cut-outs and room links.
- Clean, Balanced and Detailed deterministic detection modes plus minimum wall-length control.
- Structure/model overlay showing the geometry used by the 3D scene.
- User-controlled scale, wall height, cutaway height and material properties.
- Flooring, wall, kitchen, living-room and bathroom upload tabs.
- Deterministic asset placement with a live Three.js cutaway and top-plan scene.
- Door/window gaps cut into wall geometry rather than painted over solid walls.
- First-person pointer-lock movement with acceleration, running, head motion, persistent position and door-aware collision.
- Adjustable 70–120 degree first-person FOV and reduced player collision radius for narrow corridors.
- PBR roughness/metalness plus optional diffuse and normal maps in Three.js.
- Opening-aware Blender wall generation, box/triplanar texture projection and window bounce lighting.
- GLB, OBJ, STL and PLY building-model uploads for reverse 3D-to-2D conversion.
- Floor-plan sectioning at a configurable cut height and Y-up or Z-up selection.
- PNG, SVG and DXF floor plans, front/side elevations, dimensions and a ZIP drawing package.
- Persistent named save slots for uploads, geometry, drawings, renders and walkthroughs.
- Reset control that clears the active project without deleting save slots.
- Local project storage under the Windows application-data directory.
- Fast technical PNG renders at preview, 1080p and 4K.
- Blender 4.2+ background rendering and 5–30 second MP4 walkthroughs.
- Optional command adapter for local TRELLIS or Hunyuan3D environments.
- Optional private remote endpoint adapter; remote upload is disabled by default.
- Corrected-project export to a local supervised training workspace.
- Licence-aware dataset preparation, PyTorch U-Net training, validation metrics and ONNX export.
- GitHub Actions validation for Python, Blender scripts, TypeScript, backend packaging and Windows installer creation.

## Floor-plan AI training

The normal Windows installer does not bundle PyTorch or third-party datasets. Training is isolated under `training/` so model development does not make the desktop installer several gigabytes.

The training pipeline supports:

- User-owned local seed plans.
- The CC BY 4.0 Figshare synthetic floor-plan release.
- Authorised COCO exports such as Floor Plans 500.
- Vector/graph JSON with arbitrary room polygons.
- Explicitly gated research sources whose licences are missing, non-commercial or require separate verification.

It produces a five-class semantic model:

```text
background, wall, room, door, window
```

The resulting `floorplan-segmentation.onnx` file can be selected under **AI, OCR, training and render settings**. See [`training/README.md`](training/README.md) and [`training/datasets.json`](training/datasets.json).

After manually correcting a plan in **Edit rooms**, use **Add corrected plan to training set** to write the source image, class mask and authoritative scene JSON into the configured training workspace. This action requires confirmation that the plan may lawfully be used for training.

## Important production boundary

The deterministic geometry pipeline and optional ONNX inference are self-contained. Large generative models such as TRELLIS, Hunyuan3D, Stable Diffusion/ControlNet, Real-ESRGAN and video diffusion are not embedded because their weights, CUDA requirements and licences make a normal Windows installer impractical. The app exposes local-command and private-endpoint adapters and never uploads a home plan without explicit consent.

The application does not silently redistribute third-party datasets. FloorPlanCAD is non-commercial, some Hugging Face resources do not declare a licence, and MSD/ResPlan release terms must be retained and verified before a checkpoint is used commercially. The source registry enforces these boundaries.

The reverse drawing workflow uses deterministic mesh cross-sections rather than image generation. GLB is the preferred single-file format. OBJ models that depend on separate MTL or texture files can still be sectioned; those materials are not required for technical drawings.

This is an architectural visualisation and data-preparation tool, not a substitute for a licensed architect, structural engineer, building surveyor or code-compliance review.

## Run locally on Windows

Install Node.js 22+, Python 3.11+, Git, and optionally Blender 4.2 or newer. In PowerShell:

```powershell
git clone https://github.com/Upenyu2000/architecture_modelling.git
cd architecture_modelling
Set-ExecutionPolicy -Scope Process Bypass
python -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
npm install
npm run typecheck
npm run test:portal-stability
npm run dev
```

The Electron window starts after Vite, the Electron main process and the local Python API are ready. Blender is optional for development; without it, use the technical renderer.

## Build the Windows installer

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\build-windows.ps1
```

The build runs the geometry, opening, shared-portal, exterior-space and interior smoke tests, packages the Python backend, validates the backend health endpoint as version 1.6.0, builds Electron, and creates the installer in `release/`.

## Useful validation commands

```powershell
npm run prepare:runtime
npm run typecheck
npm run test:ui-stability
npm run test:portal-stability
npm run build
```

## Recommended production model suite

| Stage | Default in this build | Optional production model |
|---|---|---|
| Floor-plan parsing | OpenCV vectors plus optional local 5-class ONNX segmentation | Mask2Former/SegFormer trained on licence-compatible architectural masks |
| Free-form topology | Shapely polygon validation, shared-edge reconstruction and editable vertices | Graph neural topology correction trained on verified vector datasets |
| Text and scale | Manual calibration plus optional Tesseract OCR | PaddleOCR/Surya and a dimension-line parser |
| Furniture reconstruction | Deterministic proxy geometry | TRELLIS or Hunyuan3D in a dedicated CUDA environment |
| Scene assembly | Three.js game viewport plus Blender Python | Blender Geometry Nodes/Cycles or Unity/Unreal integration |
| 3D-to-2D drawings | Trimesh cross-sections with PNG/SVG/DXF | BIM/IFC semantic extraction for construction documents |
| Texture mapping | PBR material parameters, user maps and box/triplanar projection | Material synthesis with reviewed, licensed texture datasets |
| Upscaling | Native 1080p/4K render target | Real-ESRGAN or latent upscaler |
| Walkthrough | Collision-aware live FPS and Blender camera-path MP4 | Video diffusion only as post-processing, never as geometry authority |

See [Architecture](docs/ARCHITECTURE.md), [API](docs/API.md), [AI model setup](docs/MODEL_SETUP.md), and [Training](training/README.md).
