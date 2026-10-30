import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The FastAPI backend listens on 8000 (see api/main.py). The dev server proxies
// /api/* to it so the browser talks to one origin and CORS never bites.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});
