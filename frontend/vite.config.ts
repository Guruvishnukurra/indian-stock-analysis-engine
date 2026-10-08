import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// During development the dashboard calls the FastAPI backend through this
// proxy (same origin, no CORS). In production set VITE_API_URL instead.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
