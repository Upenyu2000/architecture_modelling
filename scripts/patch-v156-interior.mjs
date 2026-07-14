import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const target = path.join(root, 'src', 'renderer', 'components', 'InteriorDesignEditor.v157.tsx');
let source = await readFile(target, 'utf8');

function replaceOne(pattern, replacement, label) {
  if (!pattern.test(source)) throw new Error(`1.5.6 interior patch could not find: ${label}`);
  source = source.replace(pattern, replacement);
}

replaceOne(
  /const referenceUrl = draft\.reference_asset_key \? absoluteUrl\(project\.assets\[draft\.reference_asset_key\]\?\.url\) : undefined;/,
  `const referenceUrl = draft.reference_asset_key ? absoluteUrl(project.assets[draft.reference_asset_key]?.url) : undefined;
  const floorplanUrl = absoluteUrl(project.floorplan?.preview_url ?? scene.reference_image_url);`,
  'floor-plan URL fallback',
);

replaceOne(
  /if \(tool === 'add'\) \{\n      const room = roomAt\(point\);/,
  `if (tool === 'add') {
      const room = roomAt(point);
      if (scene.layout_mode === 'automatic' && !room) return;`,
  'outside-space placement guard',
);

replaceOne(
  /\{scene\.reference_image_url \? <image href=\{absoluteUrl\(scene\.reference_image_url\)\} x="0" y="0" width=\{scene\.width_m\} height=\{scene\.depth_m\} opacity="0\.48" preserveAspectRatio="xMidYMid meet" \/> : null\}/,
  `{floorplanUrl ? <image href={floorplanUrl} x="0" y="0" width={scene.width_m} height={scene.depth_m} opacity="0.58" preserveAspectRatio="none" /> : null}`,
  'full-plan SVG underlay',
);

await writeFile(target, source, 'utf8');
console.log(`Patched ${path.relative(root, target)} with the canonical floor-plan underlay and exterior placement guard.`);
