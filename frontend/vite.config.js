import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    allowedHosts: [
      "aspen.dicp.sixseven.ltd",
      "localhost",
      "127.0.0.1"
    ],
    proxy: {
      "/api": {
        target: "http://192.168.3.202:38843",
        changeOrigin: true
      },
      "/health": {
        target: "http://192.168.3.202:38843",
        changeOrigin: true
      },
      "/download": {
        target: "http://192.168.3.202:38843",
        changeOrigin: true
      }
    }
  }
})
