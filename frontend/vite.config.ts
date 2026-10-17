import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), {
    name: 'gsm-local-dev-identity',
    configureServer(server) {
      server.middlewares.use('/__gsm_dev', (_req, res) => {
        res.setHeader('Content-Type', 'application/json')
        res.end(JSON.stringify({application:'gsm-map-sandbox-vite',pid:process.pid,workspace:fileURLToPath(new URL('..',import.meta.url)),proxy:process.env.GSM_API_PROXY??'http://127.0.0.1:8000'}))
      })
    },
  }],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy: { '/api': process.env.GSM_API_PROXY ?? 'http://127.0.0.1:8000' } },
})
