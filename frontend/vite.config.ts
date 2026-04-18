import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api/videos': {
        target: 'http://localhost:8000',
        // Video streaming needs selfHandleResponse to avoid proxy buffering
        selfHandleResponse: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes, _req, res) => {
            // Pass through status, headers, and body without buffering
            res.writeHead(proxyRes.statusCode!, proxyRes.headers);
            proxyRes.pipe(res);
          });
        },
      },
      '/api': 'http://localhost:8000',
      '/output': 'http://localhost:8000',
    },
  },
})
