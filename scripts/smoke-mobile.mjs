import { readFileSync } from 'node:fs';

const packageJson = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const capacitorConfig = readFileSync(new URL('../capacitor.config.ts', import.meta.url), 'utf8');
const main = readFileSync(new URL('../src/renderer/main.tsx', import.meta.url), 'utf8');
const gate = readFileSync(new URL('../src/renderer/components/MobileBackendGate.tsx', import.meta.url), 'utf8');
const mobilePlatform = readFileSync(new URL('../src/renderer/lib/mobile-platform.ts', import.meta.url), 'utf8');
const mobileStyles = readFileSync(new URL('../src/renderer/mobile-2.1.css', import.meta.url), 'utf8');
const api = readFileSync(new URL('../src/renderer/lib/api.ts', import.meta.url), 'utf8');
const presentation = readFileSync(new URL('../src/renderer/components/PresentationStudio.tsx', import.meta.url), 'utf8');
const androidPrepare = readFileSync(new URL('./prepare-android.mjs', import.meta.url), 'utf8');
const androidWorkflow = readFileSync(new URL('../.github/workflows/build-android.yml', import.meta.url), 'utf8');
const asgi = readFileSync(new URL('../backend/app/asgi.py', import.meta.url), 'utf8');
const mobileApiTest = readFileSync(new URL('../backend/tests/smoke_mobile_api.py', import.meta.url), 'utf8');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(packageJson.version === '2.1.0', 'Android release version must be 2.1.0.');
assert(packageJson.dependencies['@capacitor/android'], 'Capacitor Android dependency is missing.');
assert(packageJson.dependencies['@capacitor/preferences'], 'Native preference storage is missing.');
assert(packageJson.dependencies['@capacitor/filesystem'], 'Native filesystem support is missing.');
assert(packageJson.dependencies['@capacitor/share'], 'Native sharing support is missing.');
assert(packageJson.scripts['android:sync'], 'Android sync script is missing.');
assert(packageJson.scripts['android:apk'], 'Local APK build script is missing.');
assert(capacitorConfig.includes("appId: 'com.upenyu.roomifystudio'"), 'Android application ID is missing.');
assert(capacitorConfig.includes("webDir: 'dist'"), 'Capacitor must package the Vite build.');
assert(main.includes('<MobileBackendGate>'), 'The Android rendering-server gate must wrap the application.');
assert(main.includes("./mobile-2.1.css"), 'Touch-first Android stylesheet must load last.');
assert(gate.includes('Rendering server address'), 'Android server setup form is missing.');
assert(gate.includes('API token'), 'Android API token field is missing.');
assert(gate.includes('testApiConnection'), 'Android server verification is missing.');
assert(mobilePlatform.includes('Preferences.set'), 'Server settings must persist through Capacitor Preferences.');
assert(mobilePlatform.includes('Filesystem.writeFile'), 'Generated files must be saved through the native filesystem.');
assert(mobilePlatform.includes('Share.share'), 'Generated files must open the Android share sheet.');
assert(mobileStyles.includes('env(safe-area-inset-top'), 'Android safe-area handling is missing.');
assert(mobileStyles.includes('@media (max-width: 900px)'), 'Responsive mobile workspace rules are missing.');
assert(api.includes('configureApiConnection'), 'Generated API client must support a configurable mobile server.');
assert(api.includes('Authorization'), 'Generated API client must support bearer authentication.');
assert(api.includes('access_token'), 'Authenticated image and render URLs are missing.');
assert(presentation.includes('downloadOrShare'), 'Presentation exports must use native Android sharing.');
assert(androidPrepare.includes("cap', 'add', 'android"), 'Android platform generation is missing.');
assert(androidPrepare.includes('android:usesCleartextTraffic'), 'Local-network HTTP support is missing.');
assert(androidWorkflow.includes('./gradlew assembleDebug'), 'CI must build an installable debug APK.');
assert(androidWorkflow.includes('Roomify-Studio-Android-APK'), 'CI APK artifact upload is missing.');
assert(asgi.includes('capacitor://localhost'), 'Backend CORS does not allow Capacitor.');
assert(asgi.includes('DREAMHOME_API_TOKEN'), 'Backend optional mobile API protection is missing.');
assert(asgi.includes('secrets.compare_digest'), 'API token comparison must be timing-safe.');
assert(mobileApiTest.includes('access-control-allow-origin'), 'Android API CORS smoke coverage is missing.');

console.log('Android smoke test passed: Capacitor packaging, server setup, optional token protection, touch layout, native file sharing and APK CI are present.');
