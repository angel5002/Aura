// Vite: compila el mockup a app/ (la carpeta estática que monta servidor.py de Angel).
// publico/ lo arma scripts/preparar_datos.mjs (holograma local + reproducción K002); está fuera de git.
import { readFileSync } from "node:fs";
import { defineConfig } from "vite";

const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"));

export default defineConfig({
  base: "./",
  define: { __VERSION__: JSON.stringify(pkg.version) },
  publicDir: "publico",
  build: { outDir: "app", emptyOutDir: true, assetsInlineLimit: 0, chunkSizeWarningLimit: 800 },
  server: { host: true, port: 5173 },
  preview: { host: true, port: 4173 },
});
