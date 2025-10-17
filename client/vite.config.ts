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
    hmr: {
      port: 5174,
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true, // Enable sourcemaps for debugging
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
});
