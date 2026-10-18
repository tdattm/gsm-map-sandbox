import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'
import type { Connect } from 'vite'

const proxy=process.env.GSM_API_PROXY??'http://127.0.0.1:8000'
function identity(middlewares:Connect.Server,kind:string){
  // Opt-in profiler on our isolated diagnostic page only; no cross-tab tracing.
  middlewares.use((req,res,next)=>{if(req.url?.split('?')[0]==='/performance.html')res.setHeader('Document-Policy','js-profiling');next()})
  middlewares.use('/__gsm_dev',(_req,res)=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify({application:'gsm-map-sandbox-vite',pid:process.pid,workspace:fileURLToPath(new URL('..',import.meta.url)),proxy,kind}))})
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), {
    name: 'gsm-local-dev-identity',
    configureServer(server) {
      identity(server.middlewares,'development')
    },
    configurePreviewServer(server){identity(server.middlewares,'preview')},
  }],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  build: { rollupOptions: { input: { main: fileURLToPath(new URL('./index.html', import.meta.url)), performance: fileURLToPath(new URL('./performance.html', import.meta.url)) } } },
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy: { '/api': process.env.GSM_API_PROXY ?? 'http://127.0.0.1:8000' } },
  preview: { host:'127.0.0.1', strictPort:true, proxy:{'/api':proxy} },
})
