# Dream Home Visualizer for Android

A native Kotlin and Jetpack Compose Android application that converts a floor-plan image into a portable JSON scene, then reconstructs the plan and design views from that JSON.

## Core rule: JSON is authoritative

The source image is never treated as the final floor plan. The Android pipeline is:

```text
PNG / JPG / WEBP
        ↓
white-border crop + grayscale + Otsu threshold
        ↓
long structural run detection
        ↓
wall-band collapse + room closure checks + opening-gap detection
        ↓
SceneManifest JSON
        ↓
2D verification view + editable room geometry + isometric design view
```

The JSON stores measured dimensions, arbitrary room polygons, wall centre lines, shared openings, materials, furniture and camera data. Exported JSON can be re-imported to reproduce the same geometry without analysing the image again.

## What is implemented

- Native Kotlin Android project using Jetpack Compose and Material 3.
- Android 8.0+ support (`minSdk 26`).
- Offline image selection through Android's document picker; no storage permission is required.
- Deterministic, on-device structural line extraction for rectilinear floor plans.
- Pixel-to-metre calibration using the known plan width.
- JSON model compatible with the desktop `SceneManifest` field names.
- Formal `roomify.scene.v1` JSON Schema in `app/src/main/assets/scene_manifest.schema.json`.
- JSON import, schema validation, mobile object-count limits, atomic local persistence and export.
- Source-image alignment overlay for checking detection accuracy.
- Tap-and-drag room correction without interrupting autosave.
- Room rename, add and delete controls.
- Isometric JSON-driven design preview with walls, openings, furniture and material colours.
- All 19 Roomify design styles.
- Safe 40 MB image and 10 MB JSON limits.
- Local-only storage by default; Android automatic cloud backup is disabled for floor-plan privacy.
- Unit tests for JSON round-tripping, schema compatibility, geometry movement and scene fingerprints.

## Accuracy boundary

Automatic image parsing intentionally prioritises long horizontal and vertical structural walls while suppressing short text and furniture marks. This is suitable for clean top-down architectural plans. Diagonal, curved, damaged or highly rendered plans should be corrected in the editor or imported as verified JSON.

The JSON format supports arbitrary polygons even when the initial on-device image parser does not detect them automatically. Once corrected, exported JSON is the accurate source used by every future plan and design render.

## Open in Android Studio

Use Android Studio Quail 2 Feature Drop 2026.1.2 or newer with:

- JDK 17
- Android SDK 37
- Android Gradle Plugin 9.3.0
- Gradle 9.5.0

Open the `android/` directory as the project, allow Gradle sync to finish, and run the `app` configuration on an emulator or Android device.

## Command-line build

From the repository root, with Gradle 9.5.0 installed:

```bash
gradle -p android testDebugUnitTest assembleDebug
```

The debug APK is produced at:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

## JSON compatibility

The Android model uses the same important keys as the desktop application:

```json
{
  "schema_version": "roomify.scene.v1",
  "project_id": "...",
  "width_m": 12.0,
  "depth_m": 8.0,
  "wall_height_m": 2.8,
  "walls": [],
  "rooms": [],
  "openings": [],
  "fixtures_and_furniture": [],
  "materials": {},
  "project_metadata": {}
}
```

Legacy desktop JSON without `schema_version` is accepted as `roomify.scene.v1`. A different declared schema version is rejected so newer or incompatible data is never silently interpreted as the current format. Unknown fields are ignored safely during decoding; re-export preserves every field supported by the shared Android SceneManifest model. Required geometry is validated before a scene can replace the last valid local project.

## Privacy

Floor plans can reveal the internal layout of a home. The application does not request internet or broad storage permissions, disables cleartext networking, keeps its working project in private app storage and disables automatic Android cloud backup. Use **Export JSON** when a deliberate portable copy is required.

## Next production upgrades

The current Android build is a complete JSON-first floor-plan editor and deterministic image parser. Production-grade recognition for messy plans can be added behind the existing `FloorPlanAnalyzer` interface using a quantised ONNX/TFLite segmentation model trained on the same five classes as the desktop pipeline: background, wall, room, door and window.
