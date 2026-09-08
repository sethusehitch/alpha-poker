import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  root: resolve(import.meta.dirname),
  base: "./",
  publicDir: false,
  plugins: [react()],
  build: { outDir: resolve(import.meta.dirname, "../cli/alpha_poker_cli/viewer"), emptyOutDir: true },
});
