// util.js — ayudas comunes de las pruebas del mockup.
import { mkdirSync } from "node:fs";

export const PANTALLAS = ["inicio", "hoy", "asistente", "gemelo", "senal", "alerta", "emergencia", "teleconsulta", "dispositivo"];
export const CAPTURAS = "pruebas/salida/capturas";
mkdirSync(CAPTURAS, { recursive: true });

// Sin internet: se aborta toda petición que no sea a localhost y se anota (criterio 2)
export async function sinInternet(page) {
  const externas = [];
  await page.route("**/*", (r) => {
    const u = new URL(r.request().url());
    if (["localhost", "127.0.0.1"].includes(u.hostname) || u.protocol === "data:" || u.protocol === "blob:") return r.continue();
    externas.push(u.href);
    return r.abort();
  });
  return externas;
}

export async function abrir(page, id, { quedarse = true } = {}) {
  await page.goto(`/?${quedarse ? "quedarse=1&" : ""}r=${Date.now()}#/${id}`);   // consulta única: recarga siempre
  await page.waitForFunction((p) => document.body.dataset.pantalla === p && document.querySelector("#pantalla > *"), id);
  await esperarQuieto(page, id);
}

// Espera a que terminen transiciones y animaciones de entrada (y a que el holograma esté listo)
export async function esperarQuieto(page, id) {
  if (id === "gemelo" || id === "senal") {
    await page.frameLocator("iframe.holograma").locator("canvas").waitFor();
    await page.waitForFunction(() => document.querySelector("iframe.holograma")?.contentWindow?.AURA_ESCENA, null, { timeout: 15000 });
    await page.waitForTimeout(2500);
  } else {
    await page.waitForTimeout(id === "teleconsulta" ? 900 : 700);
  }
}

export async function navegar(page, id) {
  await page.evaluate((p) => window.__aura.navegar(p), id);
  await page.waitForFunction((p) => document.body.dataset.pantalla === p, id);
  await esperarQuieto(page, id);
}
