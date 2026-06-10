import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://amr_flask_server:8001',
        changeOrigin: true,
      }
    }
  }
})
