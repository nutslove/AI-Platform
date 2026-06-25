import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend のベース URL。Docker Compose では service 名で解決する。
const backendUrl = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // /api を Backend にプロキシして CORS を回避する
    proxy: {
      "/api": {
        target: backendUrl,
        changeOrigin: true,
      },
    },
  },
});
