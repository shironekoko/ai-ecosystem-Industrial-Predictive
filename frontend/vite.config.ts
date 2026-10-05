import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    // Docker บน Windows: bind mount ไม่ส่ง file event เข้า container → ใช้ polling (เปิดด้วย VITE_USE_POLLING=true)
    watch: process.env.VITE_USE_POLLING === 'true' ? { usePolling: true, interval: 500 } : undefined,
    proxy: {
      '/api': {
        target: process.env.BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
