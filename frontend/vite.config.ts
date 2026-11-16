/// <reference types="vitest/config" />
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    port: 5730,
    strictPort: true,
    // JOBFINDER_API lets a second copy run side by side (used for testing); start.bat uses the default.
    proxy: { '/api': process.env.JOBFINDER_API ?? 'http://127.0.0.1:8730' },
  },
  test: {
    environment: 'node',
  },
})
