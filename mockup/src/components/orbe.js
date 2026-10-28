// orbe.js — orbe del asistente (pantalla Asistente). Resplandor difuso sin borde nítido que respira lento (escala
// 1 → 1,04, 4 s por ciclo, sine.inOut). Escuchando, una onda suave sigue el nivel real del micrófono (Web Audio, todo
// en el teléfono): la onda es un trazo fijo que solo se desplaza (translateX) y cambia de alto (scaleY), así que solo
// se anima transform. El navegador da el micrófono solo en HTTPS o localhost; si no, la onda es de demostración y lo
// dice. No hay reconocimiento de voz (ADR-0025).
import { gsap, orbeRespira, reducido } from "../motion.js";
import { el, svg } from "./ui.js";

const ANCHO = 132, PERIODO = 44;
function trazoOnda() {                            // tres periodos de seno: se desplaza un periodo y vuelve a empezar
  let d = "";
  for (let x = -PERIODO; x <= ANCHO + PERIODO; x += 2) d += `${d ? "L" : "M"}${x} ${24 + 14 * Math.sin((x / PERIODO) * 2 * Math.PI)}`;
  return d;
}

export function crearOrbe({ alTocar } = {}) {
  const ruta = svg("path", { d: trazoOnda() });
  const grupo = svg("g", {}); grupo.append(ruta);
  const onda = svg("svg", { class: "onda", viewBox: `0 0 ${ANCHO} 48`, "aria-hidden": "true" }); onda.append(grupo);
  const nucleo = el("span", { class: "orbe-nucleo" });
  const boton = el("button", { class: "orbe orbe-grande", type: "button", "aria-label": "Escuchar", onclick: () => alTocar?.() }, nucleo, onda);
  let respiracion = orbeRespira(nucleo);
  let audio = null, cuadro = 0, fin = 0, alto = 0.12, fase = 0;
  const poner = (a) => { alto += (a - alto) * 0.2; gsap.set(grupo, { scaleY: Math.max(0.06, alto), transformOrigin: "50% 50%", x: -fase }); };
  poner(0.12);

  // Devuelve "microfono" o "simulado" (para el rótulo). Dura `segundos` y se detiene sola.
  async function escuchar(segundos = 6) {
    detenerEscucha();
    fin = performance.now() + segundos * 1000;
    let modo = "simulado", analizador = null, datos = null;
    if (window.isSecureContext && navigator.mediaDevices?.getUserMedia) {
      try {
        const flujo = await navigator.mediaDevices.getUserMedia({ audio: true });
        const ctx = new AudioContext();
        analizador = ctx.createAnalyser(); analizador.fftSize = 256;
        ctx.createMediaStreamSource(flujo).connect(analizador);
        datos = new Uint8Array(analizador.fftSize);
        audio = { flujo, ctx };
        modo = "microfono";
      } catch { modo = "simulado"; }
    }
    const paso = (ahora) => {
      if (ahora > fin) { detenerEscucha(); return; }
      let nivel;
      if (analizador) {
        analizador.getByteTimeDomainData(datos);
        let s = 0; for (const v of datos) s += ((v - 128) / 128) ** 2;
        nivel = Math.min(1, Math.sqrt(s / datos.length) * 5);
      } else nivel = reducido() ? 0.4 : 0.45 + 0.25 * Math.sin(ahora / 420);
      if (!reducido()) fase = (fase + 1.2) % PERIODO;
      poner(0.15 + 0.85 * nivel);
      cuadro = requestAnimationFrame(paso);
    };
    cuadro = requestAnimationFrame(paso);
    return modo;
  }
  function detenerEscucha() {
    cancelAnimationFrame(cuadro);
    if (audio) { audio.flujo.getTracks().forEach((t) => t.stop()); audio.ctx.close(); audio = null; }
    alto = 0.12; poner(0.12);
  }
  function destruir() { detenerEscucha(); respiracion?.kill(); respiracion = null; }
  return { boton, escuchar, detenerEscucha, destruir };
}
