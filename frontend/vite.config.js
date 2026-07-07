import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // React dev server forwards API calls to the FastAPI backend
      '/api': 'http://127.0.0.1:8121',
    },
  },
})
