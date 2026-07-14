import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const generatedScenePreview = fileURLToPath(new URL('./src/renderer/components/ScenePreview.v153.tsx', import.meta.url));

export default defineConfig({
  base: './',
  plugins: [
    react(),
    {
      name: 'dream-home-version-1-5-3',
      transform(code, id) {
        if (!id.endsWith('/src/renderer/App.tsx')) return null;
        return code.replace('Arch-AI Convert 1.5', 'Arch-AI Convert 1.5.3');
      },
    },
  ],
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
