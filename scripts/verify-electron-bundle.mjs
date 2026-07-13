import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const targets = [
  path.join(root, 'dist-electron', 'main.cjs'),
  path.join(root, 'dist-electron', 'preload.cjs'),
];

for (const target of targets) {
  if (!fs.existsSync(target)) {
    throw new Error(`Electron bundle is missing: ${target}`);
  }

  const source = fs.readFileSync(target, 'utf8');
  const bundledElectronShim =
    source.includes('Electron failed to install correctly') ||
    /node_modules[\\/]electron[\\/]index\.js/i.test(source);

  if (bundledElectronShim) {
    throw new Error(
      `${path.basename(target)} incorrectly bundles Electron's npm installer shim. ` +
        'Electron must remain external in the main-process build.',
    );
  }

  if (!/require\(["']electron["']\)/.test(source)) {
    throw new Error(
      `${path.basename(target)} does not contain an external require("electron"). ` +
        'Check the tsup --external electron configuration.',
    );
  }
}

console.log('Electron bundle verification passed.');
