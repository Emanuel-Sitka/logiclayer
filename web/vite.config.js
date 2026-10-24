import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

// Everything - JavaScript, CSS, fonts - is inlined into one HTML file. The
// Python side keeps that file as a template and injects the knowledge base
// into it, so the page can be opened by double-clicking it and needs neither
// a web server nor an internet connection.
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  build: {
    outDir: "../logiclayer/viewer",
    emptyOutDir: true,
    assetsInlineLimit: 100000000,
    cssCodeSplit: false,
  },
});
