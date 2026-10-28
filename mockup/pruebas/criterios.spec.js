// criterios.spec.js — los 10 criterios de aceptación de docs/mockup/AURA_mockup_especificacion.pdf.
// Cada prueba deja su evidencia en pruebas/salida/ (capturas, fps.json, contraste.json). Fuera de git.
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";
import { CAPTURAS, PANTALLAS, abrir, navegar, sinInternet } from "./util.js";

const APP = "app";
const archivosApp = (dir = APP) => readdirSync(dir).flatMap((f) => {
  const r = join(dir, f);
  return statSync(r).isDirectory() ? archivosApp(r) : [r];
});
const textoCompilado = () => archivosApp().filter((f) => /\.(js|html|css|json)$/.test(f)).map((f) => [f, readFileSync(f, "utf8")]);

// ---------- revisiones dentro de la página ----------
function revisarDesbordes() {
  const W = innerWidth, malos = [];
  if (document.documentElement.scrollWidth > W) malos.push(`documento: scrollWidth ${document.documentElement.scrollWidth}`);
  const cont = document.getElementById("pantalla");
  if (cont.scrollWidth > cont.clientWidth + 1) malos.push(`pantalla: scrollWidth ${cont.scrollWidth} > ${cont.clientWidth}`);
  for (const e of document.querySelectorAll("#app *")) {
    const r = e.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const texto = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (r.right > W + 0.5 || r.left < -0.5) malos.push(`fuera del ancho: <${e.tagName.toLowerCase()} class="${e.className}"> ${Math.round(r.left)}–${Math.round(r.right)}`);
    if (texto && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflowX !== "visible")
      malos.push(`texto cortado: "${e.textContent.trim().slice(0, 40)}"`);
  }
  return malos;
}

function revisarContraste() {
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  const lum = (c) => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
  const sobre = (fg, bg) => ({ r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1 });
  function fondo(e) {
    const capas = [];
    for (let x = e; x; x = x.parentElement) {
      const c = parse(getComputedStyle(x).backgroundColor);
      if (c && c.a > 0) { capas.push(c); if (c.a >= 1) break; }
    }
    let bg = capas.length && capas[capas.length - 1].a >= 1 ? capas.pop() : parse(getComputedStyle(document.body).backgroundColor);
    while (capas.length) bg = sobre(capas.pop(), bg);
    return bg;
  }
  const res = [];
  for (const e of document.querySelectorAll("#app *")) {
    if (!(e instanceof HTMLElement) || !e.offsetParent && getComputedStyle(e).position !== "fixed") continue;
    const texto = [...e.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent.trim()).join(" ").trim();
    if (!texto) continue;
    const r = e.getBoundingClientRect();
    if (!r.width || r.bottom < 0 || r.top > innerHeight * 3) continue;
    const bg = fondo(e), fg = sobre(parse(getComputedStyle(e).color), bg);
    const [a, b] = [lum(fg), lum(bg)].sort((x, y) => y - x);
    res.push({ texto: texto.slice(0, 40), ratio: Math.round(((a + 0.05) / (b + 0.05)) * 100) / 100 });
  }
  return res;
}

// ---------- 1 · las 9 pantallas a 390 × 844 sin texto cortado ni desbordes (+ capturas) ----------
test("1 · recorrido de las 9 pantallas, capturas y desbordes", async ({ page }) => {
  await sinInternet(page);
  const informe = {};
  for (const [i, id] of PANTALLAS.entries()) {
    await abrir(page, id);
    if (id === "senal") await page.evaluate(() => window.__aura.irA(29.6));        // instante del primer cruce
    if (id === "senal") await page.waitForTimeout(1500);
    await page.screenshot({ path: `${CAPTURAS}/${String(i).padStart(2, "0")}_${id}.png` });
    // Captura completa: el contenido de la pantalla sin recortar por el alto del teléfono
    const alto = await page.evaluate(() => document.getElementById("pantalla").scrollHeight + 48 + 68);
    if (alto > 844) {
      await page.setViewportSize({ width: 390, height: alto });
      await page.waitForTimeout(400);
      await page.screenshot({ path: `${CAPTURAS}/${String(i).padStart(2, "0")}_${id}_completa.png` });
      await page.setViewportSize({ width: 390, height: 844 });
    }
    informe[id] = await page.evaluate(revisarDesbordes);
  }
  // Gemelo: escenario de demostración y ficha de una zona (capturas extra de la iteración 2)
  await abrir(page, "gemelo");
  await page.locator("[data-prueba=modo-escenario]").click();
  await page.waitForTimeout(2500);                                       // las zonas se encienden con suavidad
  await page.screenshot({ path: `${CAPTURAS}/03b_gemelo_escenario.png` });
  informe.gemelo_escenario = await page.evaluate(revisarDesbordes);
  await page.locator("[data-modulo=pulmones]").first().click();
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${CAPTURAS}/03c_gemelo_ficha.png` });
  informe.gemelo_ficha = await page.evaluate(revisarDesbordes);
  writeFileSync("pruebas/salida/desbordes.json", JSON.stringify(informe, null, 2));
  for (const [id, malos] of Object.entries(informe)) expect(malos, `desbordes en ${id}`).toEqual([]);
});

// ---------- 2 · sin internet, Inter local, modo demo activo ----------
test("2 · funciona sin internet desde app/ con Inter local y modo demo", async ({ page }) => {
  const externas = await sinInternet(page);
  const fuentes = [];
  page.on("request", (r) => { if (r.resourceType() === "font") fuentes.push(new URL(r.url()).hostname); });
  for (const id of PANTALLAS) await abrir(page, id);
  expect(externas, "peticiones fuera de localhost").toEqual([]);
  expect(fuentes.length).toBeGreaterThan(0);
  expect(new Set(fuentes)).toEqual(new Set(["localhost"]));
  expect(await page.evaluate(async () => { await document.fonts.ready; return document.fonts.check("600 16px Inter"); })).toBe(true);
  expect(await page.evaluate(() => window.__aura.estado.fuente)).toBe("demo");
  // Los HTML compilados no cargan nada de un CDN
  for (const [f, t] of textoCompilado().filter(([f]) => f.endsWith(".html"))) expect(t, f).not.toMatch(/cdnjs|jsdelivr|unpkg|googleapis/);
});

// ---------- 3 · ≥ 45 fps en Hoy, Gemelo y Señal (ESTIMADO en la PC; en el celular: no verificado) ----------
test("3 · cuadros por segundo (estimado en la PC, CPU frenada ×4)", async ({ page }) => {
  await sinInternet(page);
  const cdp = await page.context().newCDPSession(page);
  const res = {};
  for (const id of ["hoy", "gemelo", "senal"]) {
    await abrir(page, id);
    for (const freno of [1, 4]) {
      await cdp.send("Emulation.setCPUThrottlingRate", { rate: freno });
      await page.waitForTimeout(1000);
      const r = await page.evaluate(async () => {
        let n = 0; const t0 = performance.now();
        await new Promise((ok) => { const f = () => { n++; performance.now() - t0 < 5000 ? requestAnimationFrame(f) : ok(); }; requestAnimationFrame(f); });
        const fr = document.querySelector("iframe.holograma")?.contentWindow;
        let gpu = null;
        if (fr) { const c = fr.document.querySelector("canvas").getContext("webgl2") || fr.document.querySelector("canvas").getContext("webgl"); const x = c?.getExtension("WEBGL_debug_renderer_info"); gpu = x ? c.getParameter(x.UNMASKED_RENDERER_WEBGL) : null; }
        return { fps_pagina: Math.round((n * 1000) / (performance.now() - t0) * 10) / 10, fps_escena: fr ? Math.round(fr.AURA_ESCENA.fps() * 10) / 10 : null, gpu };
      });
      res[`${id}_cpu_x${freno}`] = r;
    }
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  }
  writeFileSync("pruebas/salida/fps.json", JSON.stringify(res, null, 2));
  test.info().annotations.push({ type: "fps", description: JSON.stringify(res) });
});

// ---------- 4 · sello "DEMO · reproducción" en todas las pantallas con fuente = demo, en los 3 escenarios ----------
test("4 · sello DEMO en las 9 pantallas y los 3 escenarios", async ({ page }) => {
  await sinInternet(page);
  for (const esc of ["normal", "respiracion", "caida"]) {
    await abrir(page, "dispositivo");
    await page.locator("[data-prueba=abrir-panel]").click();
    await page.locator(`[data-escenario=${esc}]`).click();
    await page.waitForTimeout(500);
    expect(await page.evaluate(() => window.__aura.estado.escenario)).toBe(esc);
    for (const id of PANTALLAS) {
      await navegar(page, id);
      expect(await page.evaluate(() => window.__aura.estado.fuente), `${esc}/${id}`).toBe("demo");
      await expect(page.locator("[data-prueba=sello-demo]"), `${esc}/${id}`).toBeVisible();
      await expect(page.locator("[data-prueba=sello-demo]")).toHaveText("DEMO · reproducción");
    }
  }
});

// ---------- 5 · sin cifras de respiración, sueño, corazón y ánimo; "diagnóstico" no aparece en el compilado ----------
test("5 · sin cifras de salud y sin la palabra diagnóstico", async ({ page }) => {
  await sinInternet(page);
  for (const esc of ["normal", "respiracion", "caida"]) {
    await abrir(page, "hoy");
    await page.evaluate((e) => window.__aura.lanzarEscenario(e), esc);
    for (const id of PANTALLAS) {
      await navegar(page, id);
      for (const m of ["pulmones", "sueno", "corazon", "animo"]) {
        for (const t of await page.locator(`[data-modulo=${m}]`).allTextContents()) expect(t, `${esc}/${id}/${m}`).not.toMatch(/\d/);
      }
      const texto = await page.locator("#app").innerText();
      expect(texto, `${esc}/${id}`).not.toMatch(/\d\s*(resp|rpm|lpm|bpm|latido|pulso|\/\s*100)/i);
      expect(texto, `${esc}/${id}`).not.toMatch(/diagn[oó]stic/i);
    }
  }
  // La palabra en español (con o sin tilde, también escapada). three.min.js trae el identificador inglés
  // `diagnostics` (propiedad interna de WebGLProgram, no se muestra): se informa aparte, no es la palabra prohibida.
  const ingles = [];
  for (const [f, t] of textoCompilado()) {
    expect(t, f).not.toMatch(/diagn[oó]stico/i);
    expect(t, f).not.toMatch(/diagn\\u00f3stico/i);
    if (/diagnostic/i.test(t)) ingles.push(f);
  }
  test.info().annotations.push({ type: "identificador_ingles_diagnostics", description: ingles.join(", ") });
});

// ---------- 6 · emergencia: 45 s, "Estoy bien" cancela, sin respuesta "Familia avisada (simulación)" ----------
test("6 · emergencia: anillo de 45 s, cancelar y aviso simulado", async ({ page }) => {
  test.setTimeout(150000);
  await sinInternet(page);
  await abrir(page, "emergencia");
  expect(await page.evaluate(() => window.__aura.anillo.duration())).toBeCloseTo(45, 0);
  await expect(page.locator("[data-prueba=cuenta]")).toHaveText(/0:4[45]/);
  await page.locator("[data-prueba=estoy-bien]").click();
  await expect(page.locator("[data-prueba=resultado-emergencia]")).toHaveText("Alerta cancelada");
  expect(await page.evaluate(() => window.__aura.estado.alerta)).toBeNull();
  // Sin respuesta: se espera el tiempo real de la cuenta
  await abrir(page, "emergencia");
  const t0 = Date.now();
  await expect(page.locator("[data-prueba=resultado-emergencia]")).toHaveText("Familia avisada (simulación)", { timeout: 50000 });
  const dur = (Date.now() - t0) / 1000;
  test.info().annotations.push({ type: "segundos_hasta_aviso", description: dur.toFixed(1) });
  expect(dur).toBeGreaterThan(43);
  expect(dur).toBeLessThan(47);
  // "Necesito ayuda" avisa de inmediato
  await abrir(page, "emergencia");
  await page.locator("[data-prueba=necesito-ayuda]").click();
  await expect(page.locator("[data-prueba=resultado-emergencia]")).toHaveText("Familia avisada (simulación)");
});

// ---------- 7 · teleconsulta en 3 toques o menos, con "Simulación" ----------
test("7 · teleconsulta en ≤ 3 toques con el rótulo Simulación", async ({ page }) => {
  await sinInternet(page);
  await abrir(page, "alerta");
  let toques = 0;
  await page.locator("[data-prueba=agendar]").click(); toques++;
  await page.locator("[data-prueba=horario]").first().waitFor();
  await expect(page.locator(".hoja .chip-demo")).toHaveText("Simulación");
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${CAPTURAS}/07b_teleconsulta_hoja.png` });
  await page.locator("[data-prueba=horario]").first().click(); toques++;
  await expect(page.locator("[data-prueba=cita-confirmada]")).toHaveText("Cita agendada (simulación)");
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${CAPTURAS}/07c_teleconsulta_confirmada.png` });
  expect(toques).toBeLessThanOrEqual(3);
  await expect(page.locator("#app")).toContainText("Simulación");
});

// ---------- 8 · prefers-reduced-motion: sin bucles y transiciones de 0 ms ----------
test.describe("8 · movimiento reducido", () => {
  test.use({ contextOptions: { reducedMotion: "reduce" } });
  test("sin bucles y transiciones de 0 ms", async ({ page }) => {
    await sinInternet(page);
    await page.addInitScript(() => {
      window.__vt = 0;
      const orig = document.startViewTransition?.bind(document);
      if (orig) document.startViewTransition = (f) => { window.__vt++; return orig(f); };
    });
    await abrir(page, "hoy");
    for (const id of PANTALLAS.slice(1)) {
      const dt = await page.evaluate(async (p) => { const t0 = performance.now(); await window.__aura.navegar(p); return performance.now() - t0; }, id);
      expect(dt, `cambio a ${id} (ms)`).toBeLessThan(100);
      await page.waitForTimeout(id === "gemelo" || id === "senal" ? 2000 : 300);
      const r = await page.evaluate(() => ({
        gsap: window.__aura.gsap.globalTimeline.getChildren(true, true, false).filter((t) => t.repeat() === -1).length,
        css: document.getAnimations().filter((a) => a.effect?.getComputedTiming().iterations === Infinity).length,
        escena: document.querySelector("iframe.holograma")?.contentWindow?.AURA_ESCENA?.reducido() ?? null,
      }));
      expect(r.gsap, `bucles GSAP en ${id}`).toBe(0);
      expect(r.css, `bucles CSS en ${id}`).toBe(0);
      if (r.escena !== null) expect(r.escena, `escena en ${id}`).toBe(true);
    }
    expect(await page.evaluate(() => window.__vt), "View Transitions con reduced-motion").toBe(0);
    expect(await page.evaluate(() => getComputedStyle(document.querySelector(".boton, .pestana")).transitionDuration)).toMatch(/^0s/);
  });
});

// ---------- 9 · contraste ≥ 4,5:1 en todo texto ----------
test("9 · contraste de texto ≥ 4,5:1 (WCAG 2.1 AA)", async ({ page }) => {
  await sinInternet(page);
  const informe = {};
  const revisar = async (nombre) => { informe[nombre] = await page.evaluate(revisarContraste); };
  for (const id of PANTALLAS) { await abrir(page, id); await revisar(id); }
  // Estados que no se ven al abrir: hoja de teleconsulta, banner, panel técnico, resultados
  await abrir(page, "dispositivo");
  await page.locator("[data-prueba=abrir-panel]").click();
  await revisar("dispositivo_panel");
  await page.locator("[data-escenario=respiracion]").click();
  await page.waitForTimeout(700);
  await revisar("banner");
  await abrir(page, "emergencia");
  await page.locator("[data-prueba=necesito-ayuda]").click();
  await page.waitForTimeout(900);
  await revisar("emergencia_resultado");
  await abrir(page, "asistente");
  await page.locator(".frase-prueba").first().click();
  await page.waitForTimeout(900);
  await revisar("asistente_respuesta");
  writeFileSync("pruebas/salida/contraste.json", JSON.stringify(informe, null, 2));
  const bajos = Object.entries(informe).flatMap(([p, l]) => l.filter((x) => x.ratio < 4.5).map((x) => `${p}: "${x.texto}" ${x.ratio}`));
  const total = Object.values(informe).reduce((s, l) => s + l.length, 0);
  test.info().annotations.push({ type: "textos_medidos", description: String(total) });
  expect(bajos).toEqual([]);
});

// ---------- 10 · nada de RuView; clínicas con nombres claramente ficticios ----------
test("10 · sin RuView y con clínicas ficticias", async ({ page }) => {
  for (const [f, t] of textoCompilado()) {
    expect(t, f).not.toMatch(/ru\s*view/i);
    expect(t, f).not.toMatch(/vitalia|vitaluz/i);
  }
  await sinInternet(page);
  await abrir(page, "teleconsulta");
  const lugares = await page.locator(".opcion-lugar").allTextContents();
  expect(lugares).toHaveLength(3);
  for (const l of lugares) expect(l).toMatch(/Demo|Ficticio|Ejemplo/);
});
