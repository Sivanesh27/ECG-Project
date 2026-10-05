import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: the browser talks to Vite (same origin) and /api is proxied to FastAPI, so the httpOnly session
// cookie is first-party and no CORS is involved.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': { target: process.env.VITE_API_TARGET || 'http://localhost:8000', changeOrigin: false } } },
  build: { chunkSizeWarningLimit: 1500 },
})
