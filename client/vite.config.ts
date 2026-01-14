import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";
import { fileURLToPath } from "url";
import { crx } from "@crxjs/vite-plugin";
import manifest from "./public/manifest.json";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  plugins: [
    react(),
    crx({
      manifest,
      contentScripts: {
        injectCss: true,
      },
    }),
  ],
  server: {
    port: 5173,
    strictPort: true,
    hmr: process.env.NODE_ENV !== "production",
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: process.env.NODE_ENV !== "production", // Enable unless production
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
});
