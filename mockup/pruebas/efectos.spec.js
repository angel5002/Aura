// efectos.spec.js — iteración 4 (no es uno de los 10 criterios): latido de Emergencia, gemelo más notorio y Señal en
// rojo durante el movimiento. Deja capturas en pruebas/salida/capturas/ y un video por efecto en pruebas/salida/efectos/
// (fuera de git). El GIF/MP4 corto para Deisy se arma después con ffmpeg a partir de esos videos.
import { test, expect } from "@playwright/test";
import { mkdirSync, renameSync } from "node:fs";
import { CAPTURAS, abrir, sinInternet } from "./util.js";

const EFECTOS = "pruebas/salida/efectos";
mkdirSync(EFECTOS, { recursive: true });
const escena = (page, expr) => page.evaluate((e) => {
  const E = document.querySelector("iframe.holograma").contentWindow.AURA_ESCENA;
  return new Function("E", `return ${e}`)(E);
}, expr);
const captura = (page, nombre) => page.screenshot({ path: `${CAPTURAS}/${nombre}.png` });
// t de K002 dentro de un tramo con movimiento (cruce de las 29–32 s) y otro de quietud
const T_MOV = 30.35, T_QUIETO = 45;

test("efectos · emergencia late sin tapar texto", async ({ page }) => {
  await sinInternet(page);
  await abrir(page, "emergencia");
  const anim = await page.evaluate(() => [...document.querySelectorAll(".halo-latido, .eco-latido")].map((e) => {
    const a = e.getAnimations()[0];
    return a ? { dur: a.effect.getComputedTiming().duration, iter: a.effect.getComputedTiming().iterations } : null;
  }));
  expect(anim).toHaveLength(4);
  for (const a of anim) expect(a).toEqual({ dur: 1600, iter: Infinity });
  // Contraste en el peor momento del latido (halo a escala 1,04 y opacidad 1): para cada texto se toma el alfa máximo
  // del halo (gradiente radial de base.css) y de los círculos en la franja de distancias que ocupa su texto, se mezcla
  // ese rojo sobre el fondo y se calcula el contraste del color del texto. Debe ser ≥ 4,5:1.
  const choques = await page.evaluate(() => {
    const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    const lum = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
    const rgb = (c) => c.match(/[\d.]+/g).slice(0, 3).map(Number);
    const FONDO = [0x1a, 0x07, 0x09], ROJO = [240, 122, 106];
    const PARADAS = [[0, 0], [0.58, 0], [0.66, 0.42], [0.8, 0.12], [0.96, 0], [1, 0]];   // = .halo-latido
    const alfaHalo = (u) => { for (let k = 1; k < PARADAS.length; k++) { const [a, x] = PARADAS[k - 1], [b, y] = PARADAS[k];
      if (u <= b) return x + (y - x) * (u - a) / (b - a); } return 0; };
    const h = document.querySelector(".halo-latido").getBoundingClientRect();
    const cx = h.left + h.width / 2, cy = h.top + h.height / 2, R = (h.width / 2) * 1.04;
    const ecos = [...document.querySelectorAll(".eco-latido")].map((e) => (e.getBoundingClientRect().width / 2) * 1.02);
    const res = [];
    for (const e of document.querySelectorAll("#app *")) {
      const nodos = [...e.childNodes].filter((n) => n.nodeType === 3 && n.textContent.trim());
      if (!nodos.length || e.closest("[hidden]")) continue;
      const rg = document.createRange(); rg.setStartBefore(nodos[0]); rg.setEndAfter(nodos[nodos.length - 1]);
      const r = rg.getBoundingClientRect();
      if (!r.width) continue;
      const dx = Math.max(r.left - cx, 0, cx - r.right), dy = Math.max(r.top - cy, 0, cy - r.bottom);
      const dmin = Math.hypot(dx, dy), dmax = Math.max(...[[r.left, r.top], [r.right, r.top], [r.left, r.bottom], [r.right, r.bottom]].map(([x, y]) => Math.hypot(x - cx, y - cy)));
      let alfa = 0;
      for (let k = 0; k <= 40; k++) alfa = Math.max(alfa, alfaHalo(Math.min(1, (dmin + (dmax - dmin) * k / 40) / R)));
      if (ecos.some((re) => re >= dmin && re <= dmax)) alfa = Math.min(1, alfa + 0.3 * 0.9);
      const bg = FONDO.map((c, k) => c * (1 - alfa) + ROJO[k] * alfa), fg = rgb(getComputedStyle(e).color);
      const [a, b] = [lum(fg), lum(bg)].sort((x, y) => y - x);
      res.push({ texto: e.textContent.trim().slice(0, 40), alfa: Math.round(alfa * 100) / 100, ratio: Math.round(((a + 0.05) / (b + 0.05)) * 100) / 100 });
    }
    return res;
  });
  test.info().annotations.push({ type: "contraste_latido", description: JSON.stringify(choques) });
  expect(choques.filter((c) => c.ratio < 4.5), "contraste bajo el halo en su pico").toEqual([]);
  await page.waitForTimeout(500);
  await captura(page, "06b_emergencia_latido");
});

test("efectos · gemelo: figura alta, escaneo y pulmones que laten", async ({ page }) => {
  await sinInternet(page);
  await abrir(page, "gemelo");
  const alto = await escena(page, "E.alturaFigura()");
  test.info().annotations.push({ type: "altura_figura", description: String(alto) });
  expect(alto, "fracción del alto de la tarjeta").toBeGreaterThanOrEqual(0.85);
  // La línea de escaneo pasa dentro de cada ciclo de 6 s
  let vista = 0;
  for (let i = 0; i < 30 && !vista; i++) { vista = await escena(page, "E.efectos().escaneo"); if (!vista) await page.waitForTimeout(200); }
  expect(vista, "escaneo visto en 6 s").toBeGreaterThan(0);
  await captura(page, "03d_gemelo_escaneo");
  await page.locator("[data-prueba=modo-escenario]").click();
  await page.waitForTimeout(2500);
  // Los pulmones laten: su opacidad cambia a lo largo de un ciclo de 1,5 s
  const ops = [];
  for (let i = 0; i < 8; i++) { ops.push((await escena(page, "E.zonas()")).pulmones.dibujo); await page.waitForTimeout(190); }
  expect(Math.max(...ops) - Math.min(...ops), `opacidades ${ops}`).toBeGreaterThan(0.15);
  expect((await escena(page, "E.zonas()")).pulmones.color).toBe("#e8b04a");
  await captura(page, "03e_gemelo_pulmones");
});

test("efectos · señal en rojo durante el movimiento y azul en quietud", async ({ page }) => {
  await sinInternet(page);
  await abrir(page, "senal");
  await page.evaluate((t) => window.__aura.irA(t), T_MOV);
  await page.waitForTimeout(450);
  const mov = await escena(page, "E.efectos()");
  await captura(page, "04b_senal_movimiento");
  expect(mov.rojo, "rojo en movimiento").toBeGreaterThan(0.8);
  expect(mov.bloom, "bloom en movimiento").toBeGreaterThan(1.0);
  await page.evaluate((t) => window.__aura.irA(t), T_QUIETO);
  await page.waitForTimeout(2500);
  const quieto = await escena(page, "E.efectos()");
  expect(quieto.rojo, "rojo en quietud").toBeLessThan(0.05);
  expect(quieto.bloom).toBeLessThan(0.7);
  await captura(page, "04c_senal_quieto");
});

// Video de los tres efectos (uno por pantalla), para ver el movimiento
test.describe("efectos · video", () => {
  test("video", async ({ browser }) => {
    const ctx = await browser.newContext({ baseURL: "http://localhost:4174", viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true,
      locale: "es-PE", recordVideo: { dir: EFECTOS, size: { width: 390, height: 844 } } });
    const page = await ctx.newPage();
    await sinInternet(page);
    await abrir(page, "emergencia");
    await page.waitForTimeout(4000);
    await page.evaluate(() => window.__aura.navegar("gemelo"));
    await page.waitForTimeout(3500);
    await page.locator("[data-prueba=modo-escenario]").click();
    await page.locator("[data-prueba=esc-respiracion]").click();   // los pulmones en ámbar (Emergencia dejó "caída")
    await page.waitForTimeout(6500);
    await page.evaluate(() => window.__aura.navegar("senal"));
    await page.waitForTimeout(2000);
    await page.evaluate(() => window.__aura.irA(29.0));
    await page.waitForTimeout(6000);
    const ruta = await page.video().path();
    await ctx.close();
    renameSync(ruta, `${EFECTOS}/efectos.webm`);
  });
});
