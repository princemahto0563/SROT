import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// The dev server proxies /api to the SROT backend so the console runs entirely
// on localhost with no CORS configuration and no external network access.
export default defineConfig(() => ({
  base: './',
  plugins: [react(), ...(process.env.SINGLEFILE ? [viteSingleFile()] : [])],
  server: {
    port: 5177,
    proxy: {
      '/api': { target: process.env.SROT_API || 'http://127.0.0.1:8077', changeOrigin: true },
    },
  },
  build: { chunkSizeWarningLimit: 4000, assetsInlineLimit: process.env.SINGLEFILE ? 100000000 : 4096 },
}))
