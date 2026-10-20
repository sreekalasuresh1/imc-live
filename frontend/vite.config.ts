import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  resolve: { dedupe: ['react', 'react-dom'] },
  server: { 
    fs: { allow: ['.', '../shared', './src/foundation'] },
    port: 5173, 
    strictPort: true, 
    proxy: { '/api': { target: process.env.CLASSROOM_API_URL || 'http://localhost:3000' } } 
  }
});


