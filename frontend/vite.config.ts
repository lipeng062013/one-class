import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // AI 生图可能超过默认代理空闲时间
        timeout: 180_000,
        proxyTimeout: 180_000,
      },
      // GPT Image Playground proxy (must be outside /api/v1 — see backend image_playground router)
      '/image-api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        timeout: 180_000,
        proxyTimeout: 180_000,
      },
    },
  },
})
