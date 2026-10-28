// orbe.js — orbe del asistente. En reposo respira (escala 1 → 1,04, 2,4 s, sine.inOut). Escuchando, las barras
// siguen el nivel real del micrófono (Web Audio, todo en el teléfono). El navegador solo da el micrófono en
// HTTPS o localhost; si no, las barras son de demostración y lo dice. No hay reconocimiento de voz (ADR-0025).
import { gsap, orbeRespira, reducido } from "../motion.js";
import { el } from "./ui.js";

const N_BARRAS = 9;

export function crearOrbe({ grande = false, alTocar } = {}) {
  const barras = Array.from({ length: N_BARRAS }, () => el("span", { class: "barra-voz" }));
  const nucleo = el("span", { class: "orbe-nucleo" }, grande ? el("span", { class: "barras" }, barras) : null);
  const boton = el("button", { class: `orbe ${grande ? "orbe-grande" : "orbe-flotante"}`, type: "button",
    "aria-label": grande ? "Escuchar" : "Abrir el asistente", onclick: () => alTocar?.() }, nucleo);
  let respiracion = orbeRespira(nucleo);
  let audio = null, cuadro = 0, fin = 0;

  function ponerBarras(niveles) {
    barras.forEach((b, i) => gsap.set(b, { scaleY: 0.15 + 0.85 * Math.min(1, niveles[i] || 0) }));
  }
  ponerBarras(Array(N_BARRAS).fill(0.1));

  // Devuelve "microfono" o "simulado" (para el rótulo). Dura `segundos` y se detiene sola.
  async function escuchar(segundos = 6) {
    detenerEscucha();
    boton.classList.add("escuchando");
    fin = performance.now() + segundos * 1000;
    let modo = "simulado", analizador = null, datos = null;
    if (window.isSecureContext && navigator.mediaDevices?.getUserMedia) {
      try {
        const flujo = await navigator.mediaDevices.getUserMedia({ audio: true });
        const ctx = new AudioContext();
        analizador = ctx.createAnalyser(); analizador.fftSize = 256;
        ctx.createMediaStreamSource(flujo).connect(analizador);
        datos = new Uint8Array(analizador.frequencyBinCount);
        audio = { flujo, ctx };
        modo = "microfono";
      } catch { modo = "simulado"; }
    }
    const paso = (ahora) => {
      if (ahora > fin) { detenerEscucha(); return; }
      if (analizador) {
        analizador.getByteFrequencyData(datos);
        const banda = Math.floor(datos.length / N_BARRAS);
        ponerBarras(barras.map((_, i) => { let s = 0; for (let k = 0; k < banda; k++) s += datos[i * banda + k]; return s / banda / 180; }));
      } else if (!reducido()) {
        const t = ahora / 1000;
        ponerBarras(barras.map((_, i) => 0.35 + 0.3 * Math.sin(t * 7 + i * 0.9) * Math.sin(t * 2.3 + i)));
      } else ponerBarras(Array(N_BARRAS).fill(0.4));
      cuadro = requestAnimationFrame(paso);
    };
    cuadro = requestAnimationFrame(paso);
    return modo;
  }
  function detenerEscucha() {
    cancelAnimationFrame(cuadro);
    boton.classList.remove("escuchando");
    if (audio) { audio.flujo.getTracks().forEach((t) => t.stop()); audio.ctx.close(); audio = null; }
    ponerBarras(Array(N_BARRAS).fill(0.1));
  }
  function destruir() { detenerEscucha(); respiracion?.kill(); respiracion = null; }
  return { boton, escuchar, detenerEscucha, destruir };
}
