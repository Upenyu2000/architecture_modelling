# Optional AI Model Setup

## Local image-to-3D

Install TRELLIS or Hunyuan3D in a dedicated CUDA environment. Configure a command that accepts an input image and writes a GLB, for example:

```text
C:\ai\trellis\run_asset.bat --input "{input}" --output "{output}"
```

The placeholders are replaced by the application. The process must return exit code 0 and create the requested output file.

## Optional YOLO blueprint model

Place an organisation-approved segmentation checkpoint under `models/floorplan-yolov8-seg.pt` and add `ultralytics` to the backend build. The current OpenCV extractor is the safe fallback and does not pretend to know door/window classes when confidence is unavailable.

## Blender

Install Blender 4.x and select `blender.exe` in Settings. The bundled Python script creates authoritative walls, room floors, proxy furniture, lighting and a camera path. For faster broad compatibility it defaults to Eevee. A production workstation can change the script to Cycles, enable GPU compute and use OpenImageDenoise.

## ControlNet and texture generation

Run this as a separate GPU service. Inputs should include the Blender depth map, line map, semantic mask and user references. Keep denoise low enough that the scene graph remains unchanged. Never use a text-only prompt to regenerate an architectural frame.

## Real-ESRGAN

Use after the geometry audit. Upscale only the accepted render and keep the original depth/ID passes so a post-upscale consistency check can flag shifted boundaries.
