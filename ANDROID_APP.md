# Native Android application

The Android application lives in [`android/`](android/) and is built with Kotlin, Jetpack Compose and Material 3.

Its core pipeline is JSON-first:

```text
floor-plan image → offline structural analysis → SceneManifest JSON → verified 2D plan and isometric design
```

The source image is treated only as input and an optional alignment overlay. Walls, rooms, openings, furniture, materials and measurements are stored in portable JSON and every plan/design view is rebuilt from that JSON. Corrected JSON can be exported, re-imported and shared with the desktop application without re-reading the image.

See [`android/README.md`](android/README.md) for architecture, accuracy boundaries, Android Studio setup and build commands.
