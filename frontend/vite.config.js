import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Pinned to 5173 to match the FastAPI backend's CORS allow_origins
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
})
