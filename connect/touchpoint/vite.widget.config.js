// The /p/hr-widget/ extension: src/widget.js as an ES module, dist/widget/ext.js, with any
// chunks beside it, and widget/ (the project's manifest and the portal's stylesheet) copied
// as they are. scripts/deploy.sh publishes dist/widget/ to /projects/hr-widget/.

import { defineConfig } from "vite";

export default defineConfig({
  publicDir: "widget",
  // React reads process.env.NODE_ENV, which a library build leaves alone.
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    outDir: "dist/widget",
    emptyOutDir: true,
    target: "es2022",
    copyPublicDir: true,
    lib: { entry: "src/widget.js", formats: ["es"], fileName: () => "ext.js" },
  },
});
