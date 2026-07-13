# Arch-AI floor-plan model training

This folder contains an optional, separate training environment. It is not installed inside the normal Windows application and it does not silently download third-party data.

The runtime model is a five-class semantic segmenter:

| Class ID | Class |
|---:|---|
| 0 | background |
| 1 | wall |
| 2 | room |
| 3 | door |
| 4 | window |

The trained model is exported to ONNX and loaded by the Windows app through OpenCV DNN. The model output is converted into editable free-form room polygons, wall paths and opening objects before the deterministic architecture compiler runs.

## Licensing gate

Read `datasets.json` before downloading anything. The preparation script enables only user-controlled or clearly permissive sources by default.

Important boundaries:

- The Figshare EPSAP dataset and Floor Plans 500 are marked CC BY 4.0 and require attribution.
- FloorPlanCAD annotations are CC BY-NC 4.0 and must not be included in a commercial model.
- `pseudo-floor-plan-12k` does not declare a licence on its dataset card. It is blocked unless `--accept-unverified-license` is explicitly supplied after permission has been verified.
- The MSD Kaggle terms and the actual ResPlan release licence must be captured before their data is mixed into a production checkpoint.
- RasterScan exposes an API/Docker workflow, not the proprietary recognition backend. This repository does not copy that implementation.
- Floor_Plan_LoRA is a generation model rather than a geometry detector. It can be used only as an optional, reviewed synthetic augmentation source.

Keep separate workspaces and checkpoints for commercial-compatible and research-only data.

## 1. Create the training environment

Windows PowerShell:

```powershell
cd C:\Users\upshl\architecture_modelling
python -m venv training\.venv
.\training\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r training\requirements.txt
```

## 2. Import user-owned seed plans

```powershell
python training\prepare_dataset.py `
  --workspace D:\ArchAITraining `
  --source local `
  --input D:\MyFloorPlans `
  --clear
```

The local importer creates weak wall and room masks. Review them before relying on them as ground truth.

## 3. Download and prepare the CC BY 4.0 Figshare data

```powershell
python training\prepare_dataset.py `
  --workspace D:\ArchAITraining `
  --source figshare
```

The script queries the official Figshare API, downloads the release archives and pairs the black-and-white plans with their colour-coded room masks.

## 4. Import a COCO export

Use this route for a Roboflow Floor Plans 500 export or another authorised COCO dataset:

```powershell
python training\prepare_dataset.py `
  --workspace D:\ArchAITraining `
  --source coco `
  --input D:\FloorPlans500\annotations.json `
  --images-root D:\FloorPlans500\images `
  --source-name roboflow_floor_plans_500
```

Polygon segmentations are preferred. Bounding boxes are accepted for door, window, wall and room/zone categories but are less precise.

## 5. Import vector or graph layouts

The generic vector importer accepts JSON records containing `rooms` or `spaces`, where each room has `vertices`, `polygon` or `points`:

```powershell
python training\prepare_dataset.py `
  --workspace D:\ArchAITraining `
  --source vector-json `
  --input D:\VerifiedResPlanExport `
  --source-name resplan_verified
```

This preserves irregular room shapes, including rhombuses, trapezoids, L-shapes and polygons with many vertices.

## 6. Optional unverified Hugging Face import

Do not use this command until the dataset owner has confirmed the intended licence:

```powershell
python training\prepare_dataset.py `
  --workspace D:\ArchAITraining `
  --source pseudo12k `
  --accept-unverified-license
```

## 7. Train and export ONNX

```powershell
python training\train_segmentation.py `
  --workspace D:\ArchAITraining `
  --output D:\ArchAITraining\models\v1 `
  --epochs 60 `
  --batch-size 6 `
  --image-size 512
```

Outputs:

```text
floorplan-segmentation-best.pt
floorplan-segmentation.onnx
floorplan-segmentation.json
training-history.json
training-summary.json
```

The sidecar JSON is required beside the ONNX file because it defines the class order, normalization and input size.

## 8. Enable the model in the Windows app

Open:

```text
AI, OCR, training and render settings
```

Choose `floorplan-segmentation.onnx` under **Local floor-plan segmentation model**, save settings, then analyse or compile a plan. The Detection tab will display a colour overlay from the model. The model does not bypass manual review: use **Edit rooms** to correct vertices and compile again.

## Recommended production training sequence

1. Start with the 20 user-supplied synthetic plans and the Figshare paired masks.
2. Add Floor Plans 500 for door/window supervision.
3. Manually review at least 300 validation masks, especially diagonal walls and doorway gaps.
4. Train a baseline and record per-class IoU.
5. Correct difficult samples in the free-form editor and export those corrections as future ground truth.
6. Add verified ResPlan/MSD vector data only after retaining their licence files.
7. Keep FloorPlanCAD in a separate non-commercial research checkpoint.
8. Promote a model only after it improves wall, room, door and window IoU on a held-out set of real plans.

## Model limitations

A segmentation model identifies pixels; the final architectural topology still comes from geometry cleanup, polygon validation, OCR, opening association and manual correction. No model trained solely on floor-plan images can infer construction-grade structural engineering, exact wall composition, hidden services or legal code compliance.
