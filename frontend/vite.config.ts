import { defineConfig } from "vite";

// The page is built into the Python package, which serves it as plain files; the built files are saved with the
// code, so installing the app needs no Node.
export default defineConfig({
  base: "/",
  build: {
    outDir: "../src/markdown_editor/web",
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
  },
});
