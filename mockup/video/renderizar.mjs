// renderizar.mjs — renderiza video/escenario.html cuadro a cuadro (tiempo determinista) y arma el MP4 con ffmpeg.
//
//   npm run build                                   (antes: el video usa la app compilada en app/)
//   node video/renderizar.mjs --cuadros 5 9 12 18   solo PNG de esos instantes, para revisar
//   node video/renderizar.mjs                       MP4 1920 × 1080, 60 fps (H.264, -preset veryfast)
//
// ESCENARIO SIMULADO ("caida_video"): nada viene de K002 ni del WiFi. Salida fuera de git, en
// datos/procesados/video_mockup/. Sirve mockup/ en un servidor local propio (solo localhost) y bloquea toda
// petición externa. Usa lo ya instalado: Playwright (Chromium), GSAP, el mockup y ffmpeg (winget).
import { spawn } from "node:child_process";
import { createReadStream, existsSync, mkdirSync, statSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { homedir } from "node:os";
import { dirname, extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const MOCKUP = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SALIDA = resolve(MOCKUP, "..", "datos", "procesados", "video_mockup");
const FPS = 60, ANCHO = 1920, ALTO = 1080, PUERTO = 4180;
const FFMPEG_WINGET = join(homedir(), "AppData", "Local", "Microsoft", "WinGet", "Links", "ffmpeg.exe");
const FFMPEG = existsSync(FFMPEG_WINGET) ? FFMPEG_WINGET : "ffmpeg";

const args = process.argv.slice(2);
const cuadros = args[0] === "--cuadros" ? args.slice(1).map(Number) : null;
if (!existsSync(join(MOCKUP, "app", "index.html"))) { console.error("Falta app/: correr antes npm run build"); process.exit(1); }
mkdirSync(SALIDA, { recursive: true });

// ---------- servidor estático de mockup/ (solo lectura, sin salir de la carpeta) ----------
const TIPOS = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".woff2": "font/woff2", ".woff": "font/woff", ".glb": "model/gltf-binary", ".svg": "image/svg+xml",
  ".png": "image/png", ".txt": "text/plain; charset=utf-8" };
const servidor = createServer((req, res) => {
  const ruta = normalize(join(MOCKUP, decodeURIComponent(new URL(req.url, "http://x").pathname)));
  if (req.method !== "GET" || !ruta.startsWith(MOCKUP + sep) || !existsSync(ruta) || !statSync(ruta).isFile()) { res.writeHead(404).end(); return; }
  res.writeHead(200, { "Content-Type": TIPOS[extname(ruta)] || "application/octet-stream" });
  createReadStream(ruta).pipe(res);
});
await new Promise((ok) => servidor.listen(PUERTO, "127.0.0.1", ok));

const navegador = await chromium.launch({ args: ["--ignore-gpu-blocklist", "--enable-gpu", "--use-angle=d3d11"] });
const pagina = await navegador.newPage({ viewport: { width: ANCHO, height: ALTO }, deviceScaleFactor: 1, locale: "es-PE" });
const externas = [];
await pagina.route("**/*", (r) => {
  const u = new URL(r.request().url());
  if (u.hostname === "127.0.0.1" || u.hostname === "localhost" || u.protocol === "data:" || u.protocol === "blob:") return r.continue();
  externas.push(u.href);
  return r.abort();
});
pagina.on("pageerror", (e) => console.error("error en la página:", e.message));
await pagina.goto(`http://127.0.0.1:${PUERTO}/video/escenario.html`);
await pagina.evaluate(() => window.__listo);
const { DURACION, CERO } = await pagina.evaluate(() => window.__escenario);

async function cuadro(t) {
  const ok = await pagina.evaluate((x) => window.__setTime(x), t);
  if (!ok) throw new Error(`el cuadro t = ${t} no quedó listo`);
}

let resumen;
if (cuadros) {
  const rutas = [];
  for (const t of cuadros) {
    await cuadro(t);
    const ruta = join(SALIDA, "cuadros", `t${String(t).padStart(2, "0")}s.png`);
    mkdirSync(dirname(ruta), { recursive: true });
    await pagina.screenshot({ path: ruta });
    rutas.push(ruta);
  }
  resumen = { tipo: "cuadros", instantes: cuadros, archivos: rutas };
} else {
  const mp4 = join(SALIDA, "aura_escenario_caida.mp4");
  const ff = spawn(FFMPEG, ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-",
    // JPEG llega en rango completo: se pasa a yuv420p de rango normal (tv) para que los editores no lo vean lavado
    "-vf", "scale=in_range=pc:out_range=tv,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", String(FPS), "-movflags", "+faststart", mp4],
    { stdio: ["pipe", "inherit", "inherit"] });
  const terminado = new Promise((ok, mal) => ff.on("close", (c) => (c === 0 ? ok() : mal(new Error(`ffmpeg terminó con ${c}`)))));
  const n = Math.round(DURACION * FPS), inicio = Date.now();
  for (let i = 0; i < n; i++) {
    await cuadro(i / FPS);
    const jpg = await pagina.screenshot({ type: "jpeg", quality: 95 });
    if (!ff.stdin.write(jpg)) await new Promise((ok) => ff.stdin.once("drain", ok));
    if (i % 120 === 0) console.log(`cuadro ${i}/${n} (${Math.round((Date.now() - inicio) / 1000)} s)`);
  }
  ff.stdin.end();
  await terminado;
  resumen = { tipo: "video", archivo: mp4, cuadros: n, fps: FPS, tamano: `${ANCHO}x${ALTO}`, segundos_render: Math.round((Date.now() - inicio) / 1000) };
}
await navegador.close();
servidor.close();

Object.assign(resumen, { generado: new Date().toISOString(), escenario: "caida_video (SIMULADO: sin datos de K002)",
  pagina: "mockup/video/escenario.html", cuenta_cero_s: Math.round(CERO * 100) / 100, peticiones_externas_bloqueadas: externas });
writeFileSync(join(SALIDA, resumen.tipo === "video" ? "generacion_video.json" : "generacion_cuadros.json"), JSON.stringify(resumen, null, 2) + "\n", "utf8");
console.log(JSON.stringify(resumen, null, 2));
