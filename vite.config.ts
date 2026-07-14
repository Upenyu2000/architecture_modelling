import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const generatedScenePreview = fileURLToPath(new URL('./src/renderer/components/ScenePreview.v153.tsx', import.meta.url));

export default defineConfig({
  base: './',
  plugins: [react()],
  resolve: {
    alias: [
      { find: './components/ScenePreview', replacement: generatedScenePreview },
    ],
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
