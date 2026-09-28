import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In development the React app runs on :5173 and proxies API calls to FastAPI on :8000.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/samples": "http://localhost:8000",
    },
  },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 800 },
});
