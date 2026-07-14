import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

await import('./generate-v154-room-editor.mjs');
await import('./prepare-v153-viewport.mjs');
await import('./generate-v154-scene-preview.mjs');

const appPath = path.join(root, 'src', 'renderer', 'App.tsx');
let app = await readFile(appPath, 'utf8');
app = app.replace(
  /from '\.\/components\/ScenePreview(?:\.v154)?';/,
  "from './components/ScenePreview.v154';",
);
await writeFile(appPath, app, 'utf8');

console.log('Prepared and activated Dream Home Visualizer 1.5.4 runtime components.');
