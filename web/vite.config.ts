import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// `build.outDir` is left at its default `dist/` on purpose: the proxy image's build stage
// copies from there, and a Dockerfile should not have to know a value that could drift here.
// `publicDir` is the default `public/`, which is what carries `fonts/` through the build
// VERBATIM — no hashing, no rewriting — so `font_subset_check` keeps a fixed subject and the
// served URLs stay `/fonts/*.woff2` exactly as they were before the build step existed.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
})
