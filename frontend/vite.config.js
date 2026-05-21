import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 18000,
    proxy: {
      '/api': {
        target: 'http://localhost:18888',
        changeOrigin: true
      }
    }
  }
})
