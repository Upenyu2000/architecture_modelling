import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const androidRoot = path.join(root, 'android');
const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const packageJson = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));

function run(args) {
  execFileSync(npx, args, { cwd: root, stdio: 'inherit' });
}

if (!existsSync(path.join(root, 'dist', 'index.html'))) {
  throw new Error('Build the Vite renderer before preparing Android. Run npm run android:sync.');
}

if (!existsSync(androidRoot)) {
  run(['cap', 'add', 'android']);
}

run(['cap', 'sync', 'android']);

const manifestPath = path.join(androidRoot, 'app', 'src', 'main', 'AndroidManifest.xml');
let manifest = readFileSync(manifestPath, 'utf8');
if (!manifest.includes('android.permission.INTERNET')) {
  manifest = manifest.replace(/(<manifest[^>]*>)/, '$1\n    <uses-permission android:name="android.permission.INTERNET" />');
}
if (!manifest.includes('android:usesCleartextTraffic=')) {
  manifest = manifest.replace('<application', '<application\n        android:usesCleartextTraffic="true"\n        android:largeHeap="true"');
}
writeFileSync(manifestPath, manifest, 'utf8');

const appGradlePath = path.join(androidRoot, 'app', 'build.gradle');
let appGradle = readFileSync(appGradlePath, 'utf8');
const [major = '2', minor = '1', patch = '0'] = String(packageJson.version).split('.');
const versionCode = Number(major) * 10000 + Number(minor) * 100 + Number(patch);
appGradle = appGradle
  .replace(/versionCode\s+\d+/, `versionCode ${versionCode}`)
  .replace(/versionName\s+"[^"]+"/, `versionName "${packageJson.version}"`);
writeFileSync(appGradlePath, appGradle, 'utf8');

const stringsPath = path.join(androidRoot, 'app', 'src', 'main', 'res', 'values', 'strings.xml');
let strings = readFileSync(stringsPath, 'utf8');
strings = strings
  .replace(/<string name="app_name">[\s\S]*?<\/string>/, '<string name="app_name">Roomify Studio</string>')
  .replace(/<string name="title_activity_main">[\s\S]*?<\/string>/, '<string name="title_activity_main">Roomify Studio</string>');
writeFileSync(stringsPath, strings, 'utf8');

console.log(`Android project prepared for Roomify Studio ${packageJson.version}.`);
console.log('The generated android/ folder can now be opened in Android Studio or built with Gradle.');
