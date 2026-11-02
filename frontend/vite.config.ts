import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    allowedHosts: ["localhost", "127.0.0.1", "frontend"],
    hmr: { clientPort: Number(process.env.HMR_CLIENT_PORT || 8080) },
    proxy: {
      "/api/": {
        target: process.env.API_PROXY_TARGET || "http://backend:8000",
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
