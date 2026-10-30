import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      ['/api', '/docs', '/openapi.json'].map((path) => [
        path,
        process.env.OPENFRAME_API_URL || 'http://127.0.0.1:8000',
      ]),
    ),
  },
  build: { outDir: 'dist' },
});
