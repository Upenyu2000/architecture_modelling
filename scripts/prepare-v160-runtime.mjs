import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

await import('./generate-v154-room-editor.mjs');
await import('./prepare-v153-viewport.mjs');
await import('./generate-v154-scene-preview.mjs');

// Git may check out TypeScript files with CRLF on Windows. Normalise the two
// patch inputs before applying exact, fail-fast generated-runtime transforms.
for (const relativePath of [
  path.join('src', 'renderer', 'App.tsx'),
  path.join('src', 'renderer', 'components', 'OpeningEditor.tsx'),
]) {
  const target = path.join(root, relativePath);
  const content = await readFile(target, 'utf8');
  await writeFile(target, content.replace(/\r\n/g, '\n'), 'utf8');
}

await import('./generate-v160-runtime.mjs');
await import('./generate-v161-runtime.mjs');

const appPath = path.join(root, 'src', 'renderer', 'App.tsx');
let app = (await readFile(appPath, 'utf8')).replace(/\r\n/g, '\n');
app = app.replace(
  /from '\.\/components\/ScenePreview(?:\.v154|\.v160|\.v161)?';/,
  "from './components/ScenePreview.v161';",
);
app = app.replace(
  /<span>Arch-AI Convert 1\.(?:5|6(?:\.1)?)<\/span>/,
  '<span>Arch-AI Convert 1.6.1</span>',
);

if (!app.includes('guarded opening mutations')) {
  const current = `  const addOpening = async (payload: OpeningPayload) => {
    if (!project) return;
    const scene = await api.addOpening(project.id, payload);
    setProject((current) => current ? { ...current, scene, status: 'openings_updated' } : current);
    setNotice('Door, window or passage added. Open First Person and press E near an interactive door.');
  };

  const updateOpening = async (openingId: string, payload: Partial<OpeningPayload>) => {
    if (!project) return;
    const scene = await api.updateOpening(project.id, openingId, payload);
    setProject((current) => current ? { ...current, scene, status: 'openings_updated' } : current);
    setNotice('Opening updated and the portal wall cut-out was rebuilt.');
  };

  const deleteOpening = async (openingId: string) => {
    if (!project) return;
    const scene = await api.deleteOpening(project.id, openingId);
    setProject((current) => current ? { ...current, scene, status: 'openings_updated' } : current);
    setNotice('Opening removed.');
  };`;

  const guarded = `  // 1.6.1 guarded opening mutations: one request at a time, with errors surfaced by run().
  const addOpening = async (payload: OpeningPayload) => {
    if (!project) return;
    await run(async () => {
      const scene = await api.addOpening(project.id, payload);
      setProject((current) => current ? { ...current, scene, status: 'openings_updated' } : current);
      setNotice('One canonical portal was added and every linked wall cut-out was rebuilt.');
    });
  };

  const updateOpening = async (openingId: string, payload: Partial<OpeningPayload>) => {
    if (!project) return;
    await run(async () => {
      const scene = await api.updateOpening(project.id, openingId, payload);
      setProject((current) => current ? { ...current, scene, status: 'openings_updated' } : current);
      setNotice('Opening updated without duplicating the shared portal entity.');
    });
  };

  const deleteOpening = async (openingId: string) => {
    if (!project) return;
    await run(async () => {
      const scene = await api.deleteOpening(project.id, openingId);
      setProject((current) => current ? { ...current, scene, status: 'openings_updated' } : current);
      setNotice('Opening and all linked wall cut-outs removed.');
    });
  };`;

  if (!app.includes(current)) throw new Error('1.6.1 app patch could not find opening mutation handlers.');
  app = app.replace(current, guarded);
}

if (!app.includes('<span>Arch-AI Convert 1.6.1</span>')) {
  throw new Error('1.6.1 app patch could not update the visible release label.');
}

await writeFile(appPath, app, 'utf8');
console.log('Prepared and activated Dream Home Visualizer 1.6.1 runtime components.');
