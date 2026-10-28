// escenarios_video.spec.js — honestidad de los escenarios del video (no es uno de los 10 criterios).
// Recorre video/escenario.html cuadro a cuadro (cada 0,25 s) en caida_video y bienestar_video y comprueba:
//   · son escenarios sintéticos: no se pide la reproducción K002 ni se abre /ws, y nada sale de localhost;
//   · rótulo fijo "Escenario de demostración" en todos los cuadros y el cierre del escenario al final;
//   · el Gemelo no aparece (ninguna pantalla "gemelo", ningún holograma en modo gemelo, sin zonas: la cabeza no se colorea);
//   · bienestar_video: ninguna palabra prohibida en pantalla; primero se pregunta a la persona: la familia solo
//     recibe el aviso después de que ella elige "Llamar a mi familia"; en la noche la figura solo cambia de pose en
//     los dos movimientos leves (3,1–3,7 s y 5,1–5,7 s) y entre ellos queda totalmente quieta (no se finge respiración).
// Sirve mockup/ con video/servidor.mjs (necesita app/ compilada, como el resto de las pruebas).
import { test, expect } from "@playwright/test";
import { servirMockup } from "../video/servidor.mjs";

const PUERTO = 4183;
const PROHIBIDAS = /aislamiento|aislad[ao]s?|depresi[oó]n|soledad|riesgo emocional|diagn[oó]stic|salud mental|calidad del sue[nñ]o|sue[nñ]o profundo|\bREM\b|\bfases?\b|respiraciones\s*\/\s*min/i;
const CIERRE = { caida_video: "Escenario de demostración · prototipo", bienestar_video: "Escenario de demostración · funciones en desarrollo" };
const AVISO = { caida_video: "Posible caída de Rosa en la sala. No responde.", bienestar_video: "Rosa quiere conversar contigo. ¿La llamas?" };

let servidor;
test.beforeAll(async () => { servidor = await servirMockup(PUERTO); });
test.afterAll(async () => { servidor?.close(); });

for (const nombre of ["caida_video", "bienestar_video"]) {
  test(`honestidad · escenario del video ${nombre}`, async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1, locale: "es-PE" });
    const page = await ctx.newPage();
    const pedidas = [], externas = [], sockets = [];
    await page.route("**/*", (r) => {
      const u = new URL(r.request().url());
      pedidas.push(u.pathname);
      if (u.hostname === "127.0.0.1" || u.protocol === "data:" || u.protocol === "blob:") return r.continue();
      externas.push(u.href);
      return r.abort();
    });
    page.on("websocket", (w) => sockets.push(w.url()));
    await page.goto(`http://127.0.0.1:${PUERTO}/video/escenario.html?escenario=${nombre}`);
    await page.evaluate(() => window.__listo);
    const { DURACION } = await page.evaluate(() => window.__escenario);

    const cuadros = [];
    for (let t = 0; t <= DURACION + 1e-9; t += 0.25) {
      cuadros.push(await page.evaluate((x) => {
        const ok = window.__setTime(x);
        const op = (e) => Number(getComputedStyle(e).opacity);
        const apps = [...document.querySelectorAll(".vidrio iframe")].map((f) => f.contentDocument);
        const asis = apps.find((d) => d.body.dataset.pantalla === "asistente");
        const holos = apps.flatMap((d) => [...d.querySelectorAll("iframe.holograma")]);
        const noche = holos.map((h) => h.contentWindow.AURA_ESCENA).find((E) => E?.noche);
        return {
          t: x, ok,
          texto: [document.body.innerText, ...apps.map((d) => d.body.innerText)].join("\n"),
          rotulo: document.querySelector(".rotulo-fijo").innerText.trim(), rotuloOp: op(document.querySelector(".rotulo-fijo")),
          pantallas: apps.map((d) => d.body.dataset.pantalla),
          holos: holos.map((h) => h.getAttribute("src")),
          zonas: holos.map((h) => Object.keys(h.contentWindow.AURA_ESCENA?.zonas?.() ?? {}).length),
          aviso: op(document.querySelector("#aviso")), avisoTexto: document.querySelector("#aviso-texto").textContent,
          cierre: op(document.querySelector("#cierre")), cierreTexto: document.querySelector("#cierre-lema").textContent,
          pregunta: asis ? op(asis.querySelector(".burbuja-aura")) : 0,
          elegido: asis ? asis.querySelector("[data-prueba=llamar-familia]").classList.contains("elegido") : false,
          pose: noche && x >= 1.75 && x < 7.5 ? noche.noche.pose() : null,
        };
      }, t));
    }
    await ctx.close();

    // sintético: sin K002, sin /ws, nada fuera de localhost
    expect(pedidas.filter((p) => /k002/i.test(p)), "pidió datos de K002").toEqual([]);
    expect(sockets, "abrió /ws").toEqual([]);
    expect(externas, "peticiones externas").toEqual([]);
    for (const c of cuadros) {
      expect(c.ok, `cuadro ${c.t} listo`).toBe(true);
      expect(c.rotulo, `rótulo fijo en ${c.t}`).toBe("Escenario de demostración");
      expect(c.rotuloOp, `rótulo visible en ${c.t}`).toBe(1);
      expect(c.pantallas, `sin Gemelo en ${c.t}`).not.toContain("gemelo");
      for (const h of c.holos) expect(h, "holograma").not.toMatch(/modo=gemelo/);
      for (const z of c.zonas) expect(z, `zonas coloreadas en ${c.t}`).toBe(0);
    }
    const ultimo = cuadros[cuadros.length - 1];
    expect(ultimo.cierre, "cierre visible al final").toBe(1);
    expect(ultimo.cierreTexto).toBe(CIERRE[nombre]);
    expect(ultimo.avisoTexto).toBe(AVISO[nombre]);

    if (nombre === "bienestar_video") {
      const malas = cuadros.filter((c) => PROHIBIDAS.test(c.texto)).map((c) => `${c.t}: ${c.texto.match(PROHIBIDAS)[0]}`);
      expect(malas, "palabras prohibidas en pantalla").toEqual([]);
      // orden: pregunta a la persona → ella elige "Llamar a mi familia" → recién entonces el aviso a la familia
      const tPregunta = cuadros.find((c) => c.pregunta > 0)?.t, tElige = cuadros.find((c) => c.elegido)?.t;
      const tAviso = cuadros.find((c) => c.aviso > 0)?.t;
      expect(tPregunta, "se pregunta a la persona").toBeDefined();
      expect(tElige, "ella elige llamar a su familia").toBeGreaterThan(tPregunta);
      expect(tAviso, "la familia recibe el aviso después").toBeGreaterThan(tElige);
      for (const c of cuadros) if (c.aviso > 0) expect(c.elegido, `aviso sin elección en ${c.t}`).toBe(true);
      // la figura dormida: idéntica dentro de cada tramo quieto y distinta tras cada movimiento
      const tramos = [[1.75, 3.1], [3.7, 5.1], [5.7, 7.5]].map(([a, b]) => cuadros.filter((c) => c.t >= a && c.t < b && c.pose).map((c) => c.pose));
      for (const [k, poses] of tramos.entries()) {
        expect(poses.length, `cuadros del tramo ${k}`).toBeGreaterThan(2);
        expect(new Set(poses).size, `figura quieta en el tramo ${k}`).toBe(1);
      }
      expect(tramos[1][0], "se acomoda las piernas").not.toBe(tramos[0][0]);
      expect(tramos[2][0], "se acomoda el brazo").not.toBe(tramos[1][0]);
    }
  });
}
