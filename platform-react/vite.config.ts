import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/plataforma/",
  plugins: [react()],
  server: {
    port: 4173,
    strictPort: true,
    allowedHosts: true,
  },
});
