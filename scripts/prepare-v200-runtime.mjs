import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

await import('./prepare-v160-runtime.mjs');

function replaceOne(source, pattern, replacement, label) {
  if (!pattern.test(source)) throw new Error(`2.0 runtime patch could not find: ${label}`);
  return source.replace(pattern, replacement);
}

const appPath = path.join(root, 'src', 'renderer', 'App.tsx');
let app = (await readFile(appPath, 'utf8')).replace(/\r\n/g, '\n');

if (!app.includes("./components/PresentationStudio")) {
  app = replaceOne(
    app,
    /import \{ ArchitecturePanel \} from '\.\/components\/ArchitecturePanel';/,
    "import { ArchitecturePanel } from './components/ArchitecturePanel';\nimport { PresentationStudio } from './components/PresentationStudio';",
    'presentation studio import',
  );
}

app = app.replace(
  /<span>(?:Arch-AI Convert 1\.6\.1|Roomify Studio 2\.[01])<\/span>/,
  '<span>Roomify Studio 2.0</span>',
);

if (!app.includes('<PresentationStudio project={project} disabled={busy} />')) {
  app = replaceOne(
    app,
    /          <section className="output-panel">/,
    '          <PresentationStudio project={project} disabled={busy} />\n          <section className="output-panel">',
    'presentation studio placement',
  );
}

if (!app.includes('<span>Roomify Studio 2.0</span>')) {
  throw new Error('2.0 runtime patch could not update the visible application release label.');
}
await writeFile(appPath, app, 'utf8');

const apiPath = path.join(root, 'src', 'renderer', 'lib', 'api.ts');
let api = (await readFile(apiPath, 'utf8')).replace(/\r\n/g, '\n');
if (!api.includes('presentationRenders:')) {
  api = replaceOne(
    api,
    /  render: \(id: string, quality: 'preview' \| '1080p' \| '4k', engine: 'auto' \| 'technical' \| 'blender'\) =>/,
    `  presentationRenders: (
    id: string,
    style: string,
    quality: 'preview' | '1080p' | '4k',
    engine: 'auto' | 'blender',
  ) => request<Job>(\`/api/v1/projects/\${id}/presentation-renders\`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ style, quality, engine, auto_furnish: true, optimize_dining: true }),
  }),
  render: (id: string, quality: 'preview' | '1080p' | '4k', engine: 'auto' | 'technical' | 'blender') =>`,
    'presentation render API action',
  );
}
await writeFile(apiPath, api, 'utf8');

const typesPath = path.join(root, 'src', 'renderer', 'types.ts');
let types = (await readFile(typesPath, 'utf8')).replace(/\r\n/g, '\n');
if (!types.includes('metadata?: Record<string, unknown>;')) {
  types = replaceOne(
    types,
    /  output_path\?: string \| null;\n  output_url\?: string \| null;\n\}/,
    `  output_path?: string | null;
  output_url?: string | null;
  error?: string | null;
  metadata?: Record<string, unknown>;
}`,
    'job metadata fields',
  );
}
await writeFile(typesPath, types, 'utf8');

console.log('Prepared Roomify Studio 2.0 with dual presentation rendering, Roomify visual design and local Blender orchestration.');
