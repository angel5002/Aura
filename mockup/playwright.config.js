// Playwright: recorre las 9 pantallas a 390 × 844 y verifica los criterios de aceptación de la especificación.
// Sirve la carpeta compilada app/ (npm run build antes) y bloquea toda petición que no sea a localhost.
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "pruebas",
  outputDir: "pruebas/salida/resultados",
  workers: 1,
  timeout: 120000,
  reporter: [["list"], ["json", { outputFile: "pruebas/salida/resultado.json" }]],
  webServer: {
    command: "node node_modules/vite/bin/vite.js preview --port 4174 --strictPort",
    url: "http://localhost:4174",
    reuseExistingServer: false,
  },
  use: {
    baseURL: "http://localhost:4174",
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    locale: "es-PE",
    launchOptions: { args: ["--ignore-gpu-blocklist", "--enable-gpu", "--use-angle=d3d11"] },
  },
});
