import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

await import('./prepare-v200-runtime.mjs');

function replaceOne(source, pattern, replacement, label) {
  if (!pattern.test(source)) throw new Error(`2.1 FreeCAD runtime patch could not find: ${label}`);
  return source.replace(pattern, replacement);
}

const appPath = path.join(root, 'src', 'renderer', 'App.tsx');
let app = (await readFile(appPath, 'utf8')).replace(/\r\n/g, '\n');

if (!app.includes("./components/FreeCADWorkbench")) {
  app = replaceOne(
    app,
    /import \{ PresentationStudio \} from '\.\/components\/PresentationStudio';/,
    "import { PresentationStudio } from './components/PresentationStudio';\nimport { FreeCADWorkbench } from './components/FreeCADWorkbench';",
    'FreeCAD workbench import',
  );
}

app = app.replace(
  /<span>(?:Roomify Studio 2\.0|Roomify CAD Studio 2\.1)<\/span>/,
  '<span>Roomify CAD Studio 2.1</span>',
);

if (!app.includes('<FreeCADWorkbench project={project} disabled={busy} onProjectChange={setProject} />')) {
  app = replaceOne(
    app,
    /(          <ModelDrawingPanel project=\{project\} busy=\{busy\} onUpload=\{uploadBuildingModel\} onGenerate=\{generateDrawings\} \/>)/,
    `$1\n          <FreeCADWorkbench project={project} disabled={busy} onProjectChange={setProject} />`,
    'FreeCAD workbench placement',
  );
}

if (!app.includes('<span>Roomify CAD Studio 2.1</span>')) {
  throw new Error('2.1 runtime patch could not update the visible application release label.');
}
await writeFile(appPath, app, 'utf8');

const apiPath = path.join(root, 'src', 'renderer', 'lib', 'api.ts');
let api = (await readFile(apiPath, 'utf8')).replace(/\r\n/g, '\n');
if (!api.includes('freecadStatus:')) {
  api = replaceOne(
    api,
    /  presentationRenders: \(/,
    `  freecadStatus: () => request<Record<string, unknown>>('/api/v1/freecad/status'),
  freecadModelTree: (id: string) =>
    request<Record<string, unknown>>(\`/api/v1/projects/\${id}/freecad/model-tree\`),
  freecadQuantities: (id: string) =>
    request<Record<string, unknown>>(\`/api/v1/projects/\${id}/freecad/quantities\`),
  freecadParameters: (id: string) =>
    request<Record<string, unknown>>(\`/api/v1/projects/\${id}/freecad/parameters\`),
  updateFreecadParameters: (
    id: string,
    parameters: {
      wall_height_m: number;
      default_wall_thickness_m: number;
      ceiling_height_m: number;
      cutaway_height_m: number;
      unit_system: 'metric' | 'imperial';
    },
  ) => request<Project>(\`/api/v1/projects/\${id}/freecad/parameters\`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(parameters),
  }),
  freecadHistory: (id: string) =>
    request<Record<string, unknown>>(\`/api/v1/projects/\${id}/freecad/history\`),
  freecadUndo: (id: string) =>
    request<Project>(\`/api/v1/projects/\${id}/freecad/undo\`, { method: 'POST' }),
  freecadRedo: (id: string) =>
    request<Project>(\`/api/v1/projects/\${id}/freecad/redo\`, { method: 'POST' }),
  freecadExport: (
    id: string,
    format: string,
    includeFurniture: boolean,
    unitSystem: 'metric' | 'imperial',
  ) => request<Job>(\`/api/v1/projects/\${id}/freecad/export\`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ format, include_furniture: includeFurniture, unit_system: unitSystem }),
  }),
  freecadImport: async (id: string, file: File) => {
    const body = new FormData();
    body.append('file', file);
    return request<Job>(\`/api/v1/projects/\${id}/freecad/import\`, { method: 'POST', body });
  },
  freecadOpen: (id: string) =>
    request<Job>(\`/api/v1/projects/\${id}/freecad/open\`, { method: 'POST' }),
  presentationRenders: (`,
    'FreeCAD API actions',
  );
}
await writeFile(apiPath, api, 'utf8');

console.log('Prepared Roomify CAD Studio 2.1 with FreeCAD parametric BRep, BIM exchange, model history and quantity schedules.');
