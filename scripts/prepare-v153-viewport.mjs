import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sourcePath = path.join(root, 'src', 'renderer', 'components', 'ScenePreview.tsx');
const original = await readFile(sourcePath);

try {
  const normalized = original.toString('utf8').replace(/\r\n/g, '\n');
  await writeFile(sourcePath, normalized, 'utf8');
  await import('./generate-v153-scene-preview.mjs');
} finally {
  await writeFile(sourcePath, original);
}
