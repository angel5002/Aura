// pdf_capturas.mjs — PDF de capturas del mockup (docs/mockup/AURA_mockup_capturas.pdf), A4 horizontal.
//
//   npm run build && node scripts/pdf_capturas.mjs [--jpeg]
//
// Captura app/ a 390 × 844 con deviceScaleFactor 2 (9 pantallas y "Tu noche" del escenario simulado
// bienestar_video), arma una página HTML (fondo #05080F, IBM Plex; portada + 3 capturas por página) y la exporta con
// page.pdf de Playwright. --jpeg: imágenes JPEG 85 (si el PDF pasa de 15 MB se hace solo). Todo local.
import { execSync } from "node:child_process";
import { readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { chromium } from "@playwright/test";
import { MOCKUP, servirMockup } from "../video/servidor.mjs";

const PUERTO = 4187, BASE = `http://127.0.0.1:${PUERTO}`;
// Enlace público (GitHub Pages) y su QR (mockup/scripts/qr_pages.svg, hecho con segno 1.6.6: corrección M, módulos navy
// sobre blanco con margen de 4 módulos)
const PAGES = "https://angel5002.github.io/Aura/";
const QR = readFileSync(resolve(MOCKUP, "scripts", "qr_pages.svg"), "utf8");
const SALIDA = resolve(MOCKUP, "..", "docs", "mockup", "AURA_mockup_capturas.pdf");
const PANTALLAS = [["inicio", "Inicio"], ["hoy", "Hoy"], ["asistente", "Asistente"], ["gemelo", "Gemelo"], ["senal", "Señal"],
  ["alerta", "Alerta"], ["emergencia", "Emergencia"], ["teleconsulta", "Teleconsulta"], ["dispositivo", "Dispositivo"]];
const commit = execSync("git rev-parse --short HEAD", { cwd: MOCKUP }).toString().trim();
const hoy = new Date().toLocaleDateString("es-PE", { day: "numeric", month: "long", year: "numeric" });

const servidor = await servirMockup(PUERTO);
const navegador = await chromium.launch({ args: ["--ignore-gpu-blocklist", "--enable-gpu", "--use-angle=d3d11"] });
const ctx = await navegador.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "es-PE" });
await ctx.route("**/*", (r) => (new URL(r.request().url()).hostname === "127.0.0.1" ? r.continue() : r.abort()));
const pagina = await ctx.newPage();
const espera = (ms) => new Promise((ok) => setTimeout(ok, ms));

async function capturar(jpeg) {
  const fotos = [];
  const tomar = async (nombre) => {
    const b = await pagina.screenshot(jpeg ? { type: "jpeg", quality: 85 } : { type: "png" });
    fotos.push({ nombre, src: `data:image/${jpeg ? "jpeg" : "png"};base64,${b.toString("base64")}` });
  };
  for (const [id, nombre] of PANTALLAS) {
    await pagina.goto(`${BASE}/app/index.html?quedarse=1&r=${Date.now()}#/${id}`);
    await pagina.waitForFunction((p) => document.body.dataset.pantalla === p && document.querySelector("#pantalla > *"), id);
    if (id === "gemelo" || id === "senal") {
      await pagina.waitForFunction(() => document.querySelector("iframe.holograma")?.contentWindow?.AURA_ESCENA, null, { timeout: 20000 });
      await espera(2500);
    } else await espera(id === "emergencia" ? 1500 : 900);
    await tomar(nombre);
  }
  // "Tu noche": solo existe en el escenario simulado bienestar_video; se fija el cuadro de t = 5 s
  await pagina.goto(`${BASE}/app/index.html?escenario=bienestar_video&quedarse=1&r=${Date.now()}#/noche`);
  await pagina.waitForFunction(() => window.__aura?.cuadro && window.__aura.cuadro(5), null, { timeout: 20000, polling: 300 });
  await espera(1500);
  await pagina.evaluate(() => window.__aura.cuadro(5));
  await tomar("Tu noche (escenario simulado bienestar_video)");
  return fotos;
}

function html(fotos) {
  const grupos = [];
  for (let k = 0; k < fotos.length; k += 3) grupos.push(fotos.slice(k, k + 3));
  const fuente = (w) => `<link rel="stylesheet" href="${BASE}/node_modules/@fontsource/ibm-plex-sans/latin-${w}.css">`;
  return `<!doctype html><html lang="es"><head><meta charset="utf-8">${fuente(400)}${fuente(600)}<style>
    @page { size: A4 landscape; margin: 0; }
    html, body { margin: 0; background: #05080f; color: #f1f5f9; font-family: "IBM Plex Sans", sans-serif; }
    .hoja { width: 297mm; height: 210mm; box-sizing: border-box; page-break-after: always; display: flex; align-items: center; justify-content: center; }
    .portada { flex-direction: column; gap: 6mm; text-align: center; }
    .portada h1 { font: 600 40pt/1.1 "IBM Plex Sans"; letter-spacing: .04em; margin: 0; }
    .portada .dato { font: 400 14pt/1.4 "IBM Plex Sans"; color: #94a3b8; margin: 0; }
    .portada .aviso { font: 400 13pt/1.5 "IBM Plex Sans"; color: #e8b04a; max-width: 200mm; margin: 6mm 0 0; }
    .enlace { display: flex; align-items: center; gap: 8mm; margin-top: 8mm; text-align: left; }
    .enlace svg { width: 46mm; height: 46mm; display: block; border-radius: 2mm; }
    .enlace p { margin: 0; font: 400 12pt/1.5 "IBM Plex Sans"; color: #94a3b8; }
    .enlace a { font: 600 15pt/1.4 "IBM Plex Sans"; color: #5cc8d6; text-decoration: none; }
    .capturas { gap: 14mm; }
    figure { margin: 0; display: flex; flex-direction: column; align-items: center; gap: 4mm; }
    figure img { height: 172mm; border-radius: 4mm; border: .3mm solid rgba(92,200,214,.35); }
    figcaption { font: 600 12pt/1.3 "IBM Plex Sans"; color: #5cc8d6; text-align: center; max-width: 80mm; }
  </style></head><body>
  <section class="hoja portada"><h1>AURA · Mockup de la app</h1><p class="dato">${hoy} · commit ${commit}</p>
    <p class="aviso">Mockup con datos de demostración y escenarios simulados; solo la reproducción de K002 usa datos reales.</p>
    <div class="enlace">${QR}<div><p>Pruébalo en el navegador del celular:</p><a href="${PAGES}">${PAGES.replace("https://", "")}</a></div></div></section>
  ${grupos.map((g) => `<section class="hoja capturas">${g.map((f) => `<figure><img src="${f.src}"><figcaption>${f.nombre}</figcaption></figure>`).join("")}</section>`).join("")}
  </body></html>`;
}

async function exportar(jpeg) {
  const fotos = await capturar(jpeg);
  const p = await navegador.newPage();
  await p.goto(`${BASE}/video/servidor.mjs`);                 // cualquier URL local: así las fuentes cargan desde 127.0.0.1
  await p.setContent(html(fotos), { waitUntil: "networkidle" });
  await p.evaluate(() => document.fonts.ready);
  await p.pdf({ path: SALIDA, format: "A4", landscape: true, printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
  await p.close();
  return statSync(SALIDA).size / 1e6;
}

let mb = await exportar(process.argv.includes("--jpeg"));
if (mb > 15 && !process.argv.includes("--jpeg")) mb = await exportar(true);
await navegador.close();
servidor.close();
console.log(JSON.stringify({ pdf: SALIDA, mb: Math.round(mb * 10) / 10, commit, fecha: hoy }));
