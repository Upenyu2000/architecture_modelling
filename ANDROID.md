# Roomify Studio for Android

Roomify Studio 2.1 uses Capacitor to package the existing React visualizer as a native Android application.

## Architecture

The Android application contains the complete mobile editor, floor-plan upload workflow, 3D viewport, project manager, presentation viewer and native save/share integration.

The FastAPI, computer-vision and Blender processes run on a separate rendering machine. This can be:

- a Windows computer on the same Wi-Fi network;
- a Linux rendering workstation;
- a secured HTTPS server with Blender installed.

Python and Blender are not bundled into the APK. The Android app connects to their API using the server address entered on first launch.

## Requirements

- Node.js 22 or newer
- Android Studio with the Android SDK
- Java 21
- Python 3.11 or newer on the rendering machine
- Blender 4.x on the rendering machine for photorealistic output

## Install dependencies

```powershell
npm install
```

## Start the rendering server on Windows

Create and prepare the backend environment first:

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Start the server so it can be reached by the phone:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-mobile-backend.ps1 `
  -ApiToken "replace-with-a-long-random-token"
```

The script prints addresses such as:

```text
http://192.168.1.20:8765
```

Keep the PowerShell window open. The computer and Android phone must be on the same private network unless the API has been deployed behind HTTPS.

Windows Firewall may ask whether Python can accept private-network connections. Allow private networks only.

## Build the Android project

```powershell
npm run android:sync
npm run android:open
```

`android:sync` performs the following steps:

1. prepares the generated Roomify 2.1 runtime;
2. builds the Vite web application;
3. creates the Capacitor Android project when it does not exist;
4. synchronises Capacitor plugins;
5. enables local-network HTTP access for development;
6. applies Android version 2.1.0.

Android Studio can then run the application on an emulator or connected Android device.

## Build an installable debug APK

On Windows:

```powershell
npm run android:apk
```

The APK is written to:

```text
android\app\build\outputs\apk\debug\app-debug.apk
```

GitHub Actions also builds an APK through the **Build Android APK** workflow and uploads an artifact named `Roomify-Studio-Android-APK`.

## First launch

1. Open Roomify Studio on the phone.
2. Enter the rendering server address printed by `run-mobile-backend.ps1`.
3. Enter the same API token passed to the PowerShell script.
4. Select **Connect to server**.
5. Upload a floor plan and use the app normally.

The server button at the bottom-right of the app can be used to verify, change or forget the saved server.

## Native Android behaviour

- Server settings are stored with Capacitor Preferences.
- Rendered PNG and ZIP outputs use the Android share sheet.
- Export files are written to the app cache before sharing, so broad storage permission is not required.
- Mobile inputs use 16-pixel text to prevent unwanted browser zoom.
- Layouts stack into a touch-first single-column interface on phones.
- Safe-area insets are respected on devices with display cut-outs or gesture navigation.

## Production deployment

For a server reachable over the internet:

- use HTTPS;
- set a long `DREAMHOME_API_TOKEN` environment variable;
- restrict inbound traffic with a firewall or reverse proxy;
- do not expose the unauthenticated development server publicly;
- place rendering jobs on a machine with sufficient memory and Blender installed.

The optional backend token protects API calls. Render and image URLs receive a scoped `access_token` query value because Android WebView image elements cannot attach bearer headers.

## Release signing

The repository builds a debug APK by default. Before publishing to Google Play:

1. create a private Android signing keystore;
2. keep the keystore and passwords outside Git;
3. configure signing in the generated `android/app/build.gradle`;
4. run `bundleRelease` to create an Android App Bundle;
5. test the signed build on physical devices.

Never commit a signing keystore or production API token to the repository.
