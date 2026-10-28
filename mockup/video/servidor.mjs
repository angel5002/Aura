// servidor.mjs — servidor estático de mockup/ solo en 127.0.0.1 (solo lectura, sin salir de la carpeta). Lo usan
// video/renderizar.mjs y la prueba de honestidad de los escenarios del video (pruebas/escenarios_video.spec.js).
import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { dirname, extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

export const MOCKUP = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const TIPOS = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".woff2": "font/woff2", ".woff": "font/woff", ".glb": "model/gltf-binary", ".svg": "image/svg+xml",
  ".png": "image/png", ".txt": "text/plain; charset=utf-8" };

export async function servirMockup(puerto) {
  const servidor = createServer((req, res) => {
    const ruta = normalize(join(MOCKUP, decodeURIComponent(new URL(req.url, "http://x").pathname)));
    if (req.method !== "GET" || !ruta.startsWith(MOCKUP + sep) || !existsSync(ruta) || !statSync(ruta).isFile()) { res.writeHead(404).end(); return; }
    res.writeHead(200, { "Content-Type": TIPOS[extname(ruta)] || "application/octet-stream" });
    createReadStream(ruta).pipe(res);
  });
  await new Promise((ok) => servidor.listen(puerto, "127.0.0.1", ok));
  return servidor;
}
