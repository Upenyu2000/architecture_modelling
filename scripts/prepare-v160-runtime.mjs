import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

await import('./generate-v154-room-editor.mjs');
await import('./prepare-v153-viewport.mjs');
await import('./generate-v154-scene-preview.mjs');
await import('./generate-v160-runtime.mjs');

const appPath = path.join(root, 'src', 'renderer', 'App.tsx');
let app = await readFile(appPath, 'utf8');
app = app.replace(
  /from '\.\/components\/ScenePreview(?:\.v154|\.v160)?';/,
  "from './components/ScenePreview.v160';",
);

if (!app.includes('1.6.0 guarded opening mutations')) {
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

  const guarded = `  // 1.6.0 guarded opening mutations: one request at a time, with errors surfaced by run().
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

  if (!app.includes(current)) throw new Error('1.6.0 app patch could not find opening mutation handlers.');
  app = app.replace(current, guarded);
}

await writeFile(appPath, app, 'utf8');
console.log('Prepared and activated Dream Home Visualizer 1.6.0 runtime components.');
