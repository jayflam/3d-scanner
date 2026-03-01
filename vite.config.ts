import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  server: {
    allowedHosts: ['devserver-fe-develop--spaceframeio.netlify.app']
  },
  optimizeDeps: {
    exclude: ['@mediapipe/tasks-vision'],
  },
  plugins: [
    react({
      babel: {
        plugins: [['babel-plugin-react-compiler']],
      },
    }),
  ],
})