import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "VITE_");
  return {
  base: env.VITE_BASE_PATH || "/plataforma-react/",
  plugins: [react()],
  server: {
    port: 4173,
    strictPort: true,
    allowedHosts: true,
  },
  };
});
