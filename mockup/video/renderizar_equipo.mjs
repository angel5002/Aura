// renderizar_equipo.mjs — video de presentación del equipo para chroma key (video/equipo.html), cuadro a cuadro.
//
//   node video/renderizar_equipo.mjs --cuadros 2 7 12   PNG con alfa + su versión sobre verde, para revisar
//   node video/renderizar_equipo.mjs                    PNG con alfa de los 900 cuadros → MP4 sobre verde y MOV ProRes 4444
//   node video/renderizar_equipo.mjs --verificar        solo las comprobaciones de los videos ya generados
//
// Las fotos son datos personales: están en datos/procesados/video_equipo/fotos_listas/ (fuera de git; las prepara
// video/preparar_fotos_equipo.py) y se entregan a la página interceptando /fotos-equipo/ (no se copian a mockup/).
// Todo local: se bloquea cualquier petición que no sea a 127.0.0.1. Salida en datos/procesados/video_equipo/.
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { chromium } from "@playwright/test";
import { MOCKUP, servirMockup } from "./servidor.mjs";

const SALIDA = resolve(MOCKUP, "..", "datos", "procesados", "video_equipo");
const FOTOS = join(SALIDA, "fotos_listas"), CUADROS = join(SALIDA, "cuadros_png");
const FPS = 60, ANCHO = 1920, ALTO = 1080, PUERTO = 4186, VERDE = "0x00B140";
const BIN = join(homedir(), "AppData", "Local", "Microsoft", "WinGet", "Links");
const FFMPEG = existsSync(join(BIN, "ffmpeg.exe")) ? join(BIN, "ffmpeg.exe") : "ffmpeg";
const FFPROBE = existsSync(join(BIN, "ffprobe.exe")) ? join(BIN, "ffprobe.exe") : "ffprobe";
const MP4 = join(SALIDA, "aura_equipo_verde.mp4"), MOV = join(SALIDA, "aura_equipo_alfa.mov");
// BT.709 de rango normal, declarado en el archivo: así el verde decodificado vuelve a medir #00B140
const COLOR709 = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"];

const args = process.argv.slice(2);
const cuadros = args[0] === "--cuadros" ? args.slice(1).map(Number) : null;
const ff = (a) => execFileSync(FFMPEG, ["-v", "error", "-y", ...a], { stdio: ["ignore", "inherit", "inherit"] });

async function capturar(instantes, rutaDe) {
  for (const n of ["josue", "hideki", "angel", "ida_luz"]) if (!existsSync(join(FOTOS, `${n}.png`))) throw new Error(`Falta ${n}.png en ${FOTOS}`);
  const servidor = await servirMockup(PUERTO);
  const navegador = await chromium.launch();
  const pagina = await navegador.newPage({ viewport: { width: ANCHO, height: ALTO }, deviceScaleFactor: 1 });
  const externas = [];
  await pagina.route("**/*", (r) => {
    const u = new URL(r.request().url());
    if (u.hostname === "127.0.0.1" && u.pathname.startsWith("/fotos-equipo/"))
      return r.fulfill({ body: readFileSync(join(FOTOS, u.pathname.split("/").pop())), contentType: "image/png" });
    if (u.hostname === "127.0.0.1" || u.protocol === "data:") return r.continue();
    externas.push(u.href);
    return r.abort();
  });
  pagina.on("pageerror", (e) => console.error("error en la página:", e.message));
  await pagina.goto(`http://127.0.0.1:${PUERTO}/video/equipo.html`);
  await pagina.evaluate(() => window.__listo);
  const info = await pagina.evaluate(() => window.__equipo);
  const inicio = Date.now();
  for (const [k, t] of instantes.entries()) {
    await pagina.evaluate((x) => window.__setTime(x), t);
    await pagina.screenshot({ path: rutaDe(t, k), omitBackground: true });
    if (k % 120 === 0 && instantes.length > 10) console.log(`cuadro ${k}/${instantes.length} (${Math.round((Date.now() - inicio) / 1000)} s)`);
  }
  await navegador.close();
  servidor.close();
  return { ...info, externas, segundos: Math.round((Date.now() - inicio) / 1000) };
}

// ---------- comprobaciones ----------
function sonda(ruta) {
  const r = spawnSync(FFPROBE, ["-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
    "stream=codec_name,profile,pix_fmt,width,height,r_frame_rate,nb_read_frames,color_space,color_range:format=duration,size", "-of", "json", ruta], { encoding: "utf8" });
  const j = JSON.parse(r.stdout);
  return { ...j.streams[0], duracion: Number(j.format.duration), tamano_mb: Math.round(Number(j.format.size) / 1e5) / 10 };
}
const crudo = (a) => execFileSync(FFMPEG, ["-v", "error", ...a, "-f", "rawvideo", "-"], { maxBuffer: 64e6 });
// Cuadro k del MP4 decodificado a RGB con su matriz BT.709, y alfa del PNG del mismo cuadro (la verdad de la tarjeta)
const rgbDelMp4 = (k) => crudo(["-i", MP4, "-vf", `select=eq(n\\,${k}),scale=in_color_matrix=bt709:in_range=tv:out_range=pc,format=rgb24`, "-frames:v", "1"]);
const alfaDelPng = (k) => crudo(["-i", join(CUADROS, `${String(k).padStart(5, "0")}.png`), "-vf", "format=rgba,alphaextract,format=gray"]);
// Mide un cuadro: verde lejos de las tarjetas (> 8 px), anillo de fondo pegado al borde (1–2 px) y píxeles del borde
// de la tarjeta con verde dominante (los que un keyer se comería)
function medirCuadro(k) {
  const v = rgbDelMp4(k), a = alfaDelPng(k), W = ANCHO, H = ALTO, VERDE_RGB = [0x00, 0xb1, 0x40];
  // distancia (en píxeles, tablero) al píxel de tarjeta más cercano, acotada a 9
  const dist = new Uint8Array(W * H).fill(9);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (a[y * W + x] === 255)
    for (let dy = -8; dy <= 8; dy++) for (let dx = -8; dx <= 8; dx++) {
      const yy = y + dy, xx = x + dx;
      if (yy < 0 || yy >= H || xx < 0 || xx >= W) continue;
      const i = yy * W + xx, dd = Math.max(Math.abs(dx), Math.abs(dy));
      if (a[i] === 0 && dd < dist[i]) dist[i] = dd;
    }
  let lejos = 0, cerca = 0, borde = 0, verdosos = 0;
  for (let i = 0; i < W * H; i++) {
    const r = v[i * 3], g = v[i * 3 + 1], b = v[i * 3 + 2];
    if (a[i] === 0) {
      const d = Math.max(Math.abs(r - VERDE_RGB[0]), Math.abs(g - VERDE_RGB[1]), Math.abs(b - VERDE_RGB[2]));
      if (dist[i] > 8) lejos = Math.max(lejos, d); else if (dist[i] <= 2) cerca = Math.max(cerca, d);
    } else if (a[i] === 255) {
      const x = i % W, y = (i / W) | 0;
      const junto = (x > 0 && a[i - 1] === 0) || (x < W - 1 && a[i + 1] === 0) || (y > 0 && a[i - W] === 0) || (y < H - 1 && a[i + W] === 0);
      if (!junto) continue;
      borde++;
      if (g > r + 40 && g > b + 40) verdosos++;
    }
  }
  return { cuadro: k, t: k / FPS, verde_lejos_desvio: lejos, verde_junto_al_borde_desvio: cerca, borde_px: borde, borde_verdoso_px: verdosos };
}
function verificar(info = {}) {
  const v = { mp4: sonda(MP4), mov: sonda(MOV) };
  const cuadrosMedidos = [30, 120, 300, 420, 600, 720, 870, 899].map(medirCuadro);   // incluye el verde limpio del final
  const lejos = Math.max(...cuadrosMedidos.map((c) => c.verde_lejos_desvio));
  return { ...v, verde_fondo: { desvio_max: lejos, ok: lejos <= 2 },
    bordes_ok: cuadrosMedidos.every((c) => c.borde_verdoso_px === 0), cuadros_medidos: cuadrosMedidos, ...info };
}
// Alfa de los 900 PNG: cuenta píxeles con alfa entre 1 y 254 (debe ser 0: nada semitransparente sobre el verde)
async function alfaBinario() {
  const archivos = readdirSync(CUADROS).filter((f) => f.endsWith(".png")).sort();
  let parciales = 0, conParcial = 0;
  for (const f of archivos) {
    const a = crudo(["-i", join(CUADROS, f), "-vf", "format=rgba,alphaextract,format=gray"]);
    let n = 0; for (const x of a) if (x !== 0 && x !== 255) n++;
    parciales += n; if (n) conParcial++;
  }
  return { cuadros: archivos.length, cuadros_con_alfa_parcial: conParcial, px_alfa_parcial: parciales };
}

// ---------- principal ----------
mkdirSync(SALIDA, { recursive: true });
if (cuadros) {
  const dir = join(SALIDA, "cuadros_revision"); mkdirSync(dir, { recursive: true });
  const nombre = (t) => `t${String(t).padStart(2, "0")}s`;
  const info = await capturar(cuadros, (t) => join(dir, `${nombre(t)}_alfa.png`));
  for (const t of cuadros)
    ff(["-f", "lavfi", "-i", `color=c=${VERDE}:s=${ANCHO}x${ALTO},format=gbrp`, "-i", join(dir, `${nombre(t)}_alfa.png`), "-filter_complex", "[0][1]overlay=format=gbrp", "-frames:v", "1", join(dir, `${nombre(t)}_verde.png`)]);
  console.log(JSON.stringify({ cuadros, dir, ...info }, null, 2));
} else {
  let info = {};
  if (!args.includes("--verificar")) {
    rmSync(CUADROS, { recursive: true, force: true }); mkdirSync(CUADROS, { recursive: true });
    const n = 15 * FPS;
    info = await capturar([...Array(n).keys()].map((i) => i / FPS), (t, k) => join(CUADROS, `${String(k).padStart(5, "0")}.png`));
    const entrada = ["-framerate", String(FPS), "-i", join(CUADROS, "%05d.png")];
    // 1) MP4 sobre verde: verde plano + PNG con alfa; RGB → YUV 4:2:0 BT.709 con submuestreo de color por punto
    //    (los bordes están en píxeles pares: cada bloque 2×2 es todo tarjeta o todo verde)
    //    El verde se genera en RGB (gbrp): generado en YUV, ffmpeg lo pasaba por BT.601 y quedaba 4 niveles corrido
    ff(["-f", "lavfi", "-i", `color=c=${VERDE}:s=${ANCHO}x${ALTO}:r=${FPS},format=gbrp`, ...entrada, "-filter_complex",
      "[0][1]overlay=shortest=1:format=gbrp,scale=out_color_matrix=bt709:out_range=tv:flags=neighbor+full_chroma_int,format=yuv420p",
      "-c:v", "libx264", "-preset", "veryfast", "-crf", "1", "-x264-params", "aq-mode=0:deblock=-3,-3",   // sin ruido sobre el verde plano (medido: ±2 lejos, ≤3 junto al borde)
      "-pix_fmt", "yuv420p", ...COLOR709, "-movflags", "+faststart", MP4]);
    // 2) MOV ProRes 4444 con alfa
    ff([...entrada, "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-alpha_bits", "16", "-vendor", "apl0", MOV]);
    info.alfa = await alfaBinario();
  }
  const resultado = { generado: new Date().toISOString(), ...verificar(info), cuadros_png: CUADROS };
  writeFileSync(join(SALIDA, "generacion_equipo.json"), JSON.stringify(resultado, null, 2) + "\n", "utf8");
  console.log(JSON.stringify(resultado, null, 2));
}
