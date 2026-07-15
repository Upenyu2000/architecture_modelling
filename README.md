# Roomify CAD Studio 2.1 — Dream Home Visualizer

A local-first Electron, FastAPI, Three.js, Blender and FreeCAD desktop application for turning 2D floor plans into editable architectural geometry, parametric CAD/BIM documents, interactive walkthroughs and photorealistic presentation renders.

## Version 2.1: FreeCAD CAD and BIM workbench

Roomify CAD Studio now connects to a locally installed FreeCAD through `FreeCADCmd.exe` and, when requested, `FreeCAD.exe`.

The integration adds:

- An in-app FreeCAD connection status and executable selector.
- A parametric building model generated from the verified room, wall, door and window geometry.
- Open CASCADE solid and BRep construction for room slabs, walls and Boolean opening cuts.
- Editable wall height, wall thickness, ceiling height and cutaway height properties.
- Recompute, undo and redo controls backed by persistent scene snapshots.
- A hierarchical model tree for rooms, walls, openings, furniture and fixtures.
- Quantity and bill-of-material data for floor area, wall lengths, wall area, wall volume, openings and interior objects.
- Native editable `FCStd` output.
- STEP, IGES, BRep, STL and OBJ export.
- IFC, DXF and SVG import/export when the corresponding FreeCAD modules are available.
- FCStd, STEP, IGES, BRep, IFC, DXF, SVG, STL, OBJ, DAE, OFF and 3MF import.
- Conversion of imported CAD/BIM files into an editable FCStd document and an OBJ model usable by the existing drawing and rendering workflow.
- An explicit **Open in FreeCAD** action for continuing the model in the full FreeCAD desktop application.

The generated FCStd document contains a Building container, grouped architectural objects, custom properties and a Quantity Schedule spreadsheet.

## Roomify presentation workflow

The application also provides:

- PNG, JPG and PDF floor-plan upload with drag-and-drop progress.
- Deterministic wall, room, door and window extraction.
- Editable free-form room polygons and shared-wall portals.
- Furniture and fixture placement with uploaded reference assets.
- A live Three.js plan, cutaway and first-person walkthrough.
- Selectable room-centre or exact-coordinate first-person spawning.
- Solid room slabs, exterior collision boundaries and interactive doors.
- Nineteen architectural styles, including Modern, Scandinavian, Industrial, Mediterranean, Victorian and Neo-classical.
- A text-free orthographic top-down presentation render.
- A coordinated eye-level interior render from inside the building.
- Dining-room circulation optimisation.
- Preview, 1080p and 4K Blender output plus MP4 walkthroughs.
- Named save slots and local project storage.

## What runs inside the app

The app directly exposes the FreeCAD capabilities that support the architectural workflow:

- Parametric properties and recomputation.
- Open CASCADE solid/BRep generation.
- Model hierarchy and persistent history.
- Quantity schedules.
- Common CAD, mesh, BIM and 2D exchange formats.
- FreeCAD desktop handoff.

Specialist FreeCAD workbenches such as FEM, CAM/CNC, robotics, point-cloud processing, assemblies and advanced NURBS editing are not reimplemented in the Electron interface. Export or open the FCStd document in FreeCAD to continue with those specialist tools.

## Requirements

Required for local development:

- Windows 10 or 11.
- Node.js 22 or newer.
- Python 3.11 or newer.
- Git.

Optional tools:

- FreeCAD 1.x for parametric CAD/BIM import, export and desktop editing.
- Blender 4.2 or newer for photorealistic rendering and video walkthroughs.
- Tesseract OCR for room labels and dimensions.
- A compatible ONNX segmentation model for learned floor-plan parsing.

FreeCAD and Blender are external applications and are not redistributed inside the installer. The app auto-detects common Windows installation paths. Custom paths can be selected under **CAD, BIM, AI, OCR, training and render settings**.

## Run locally on Windows

```powershell
git clone https://github.com/Upenyu2000/architecture_modelling.git
cd architecture_modelling
git switch agent/release-2.1-freecad-cad-bim

Set-ExecutionPolicy -Scope Process Bypass
python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r backend\requirements.txt

npm install
npm run prepare:runtime
npm run typecheck
npm run test:ui-stability
npm run test:freecad
npm run test:presentation
npm run test:portal-stability
npm run dev
```

If FreeCAD is installed outside a standard path, open Settings and select:

```text
FreeCADCmd.exe
FreeCAD.exe
```

The command-line executable performs CAD/BIM operations. The desktop executable is used only after pressing **Open in FreeCAD**.

## FreeCAD file exchange

| Format | Import | Export | Notes |
|---|---:|---:|---|
| FCStd | Yes | Yes | Preferred editable parametric document |
| STEP / STP | Yes | Yes | Precise solid exchange |
| IGES / IGS | Yes | Yes | Surface and solid exchange |
| BRep / BRP | Yes | Yes | Open CASCADE boundary representation |
| IFC | Yes* | Yes* | Requires FreeCAD IFC support |
| DXF | Yes* | Yes* | Requires FreeCAD DXF support |
| SVG | Yes* | Yes* | Requires FreeCAD SVG support |
| STL | Yes | Yes | Tessellated manufacturing/printing mesh |
| OBJ | Yes | Yes | Mesh exchange and app preview conversion |
| DAE, OFF, 3MF | Yes | — | Converted to FCStd and OBJ |

`*` Availability is detected from the installed FreeCAD modules and unsupported choices are hidden from export controls.

## Build the Windows installer

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\build-windows.ps1
```

The build validates geometry, portals, interiors, presentation rendering preparation and the FreeCAD bridge, packages the FastAPI backend, verifies the packaged `/health` endpoint as version 2.1.0, builds Electron and creates the NSIS installer in `release/`.

## Validation commands

```powershell
npm run prepare:runtime
npm run typecheck
npm run test:ui-stability
npm run test:freecad
npm run test:presentation
npm run test:portal-stability
npm run build
```

The FreeCAD smoke test does not require FreeCAD to be installed. It verifies parametric properties, model-tree generation, quantity calculations, persistent undo/redo history, format declarations and the packaged headless bridge. Actual CAD conversion requires a local FreeCAD installation.

## Production boundaries

- Source floor-plan text is not projected into presentation renders.
- The deterministic scene remains the authority for geometry.
- CAD exports are design data, not signed construction documents.
- Structural analysis, building-code compliance and professional certification require qualified specialists.
- Remote image processing remains disabled unless the user explicitly configures and enables a private endpoint.
- FreeCAD, Blender and third-party model weights retain their own licences and installation requirements.
