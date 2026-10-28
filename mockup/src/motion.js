// motion.js — todas las animaciones de la interfaz (GSAP) con la tabla "Cómo se mueve cada cosa" de la
// especificación. Solo se animan transform y opacity. Con prefers-reduced-motion: sin bucles y 0 ms.
import { gsap } from "gsap";
import { DrawSVGPlugin } from "gsap/DrawSVGPlugin";
import { SplitText } from "gsap/SplitText";

gsap.registerPlugin(DrawSVGPlugin, SplitText);

export const MOV = {
  pantalla: { dur: 0.28, ease: "power2.out", desliza: 24 },
  hoja: { dur: 0.36, ease: "back.out(1.2)" },
  orbe: { dur: 4, ease: "sine.inOut", escala: 1.04 },        // respira lento (4 s por ciclo; iteración 2)
  banner: { dur: 0.42, ease: "power3.out" },
  cuenta: { dur: 45, ease: "none" },
  check: { dur: 0.6, ease: "power2.inOut" },
  cifras: { dur: 0.4, ease: "power1.out" },
};

const consulta = matchMedia("(prefers-reduced-motion: reduce)");
export const reducido = () => consulta.matches;
const bucles = new Set();                         // tweens con repeat: -1 (se matan si se activa reduced-motion)
consulta.addEventListener("change", () => {
  if (reducido()) bucles.forEach((t) => { t.kill(); gsap.set(t.targets(), { clearProps: "transform" }); });
});
const d = (s) => (reducido() ? 0 : s);

// Cambio de pantalla: View Transitions si existe; si no, GSAP (desliza 24 px y aparece, 280 ms, power2.out)
export async function transicionPantalla(cambiar, contenedor) {
  if (reducido()) { cambiar(); return; }
  if (document.startViewTransition) {
    const vt = document.startViewTransition(cambiar);
    await vt.finished.catch(() => {});
    return;
  }
  cambiar();
  await gsap.fromTo(contenedor, { y: MOV.pantalla.desliza, opacity: 0 },
    { y: 0, opacity: 1, duration: MOV.pantalla.dur, ease: MOV.pantalla.ease, clearProps: "transform,opacity" });
}

export function subirHoja(hoja, velo) {
  gsap.set(hoja, { yPercent: 100 });
  if (velo) gsap.fromTo(velo, { opacity: 0 }, { opacity: 1, duration: d(0.2) });
  return gsap.to(hoja, { yPercent: 0, duration: d(MOV.hoja.dur), ease: MOV.hoja.ease });
}
export function bajarHoja(hoja, velo) {
  if (velo) gsap.to(velo, { opacity: 0, duration: d(0.2) });
  return gsap.to(hoja, { yPercent: 100, duration: d(0.24), ease: "power2.in" });
}

export function orbeRespira(el) {
  if (reducido()) return null;
  const t = gsap.to(el, { scale: MOV.orbe.escala, duration: MOV.orbe.dur / 2, ease: MOV.orbe.ease, yoyo: true, repeat: -1 });
  bucles.add(t);
  return t;
}
export function detener(t) { if (t) { t.kill(); bucles.delete(t); } }

export function bajarBanner(el) {
  return gsap.fromTo(el, { yPercent: -140, opacity: 0 }, { yPercent: 0, opacity: 1, duration: d(MOV.banner.dur), ease: MOV.banner.ease });
}
export function subirBanner(el) {
  return gsap.to(el, { yPercent: -140, opacity: 0, duration: d(0.28), ease: "power2.in" });
}

// Anillo que se vacía: dura lo que falta de los 45 s (lineal). Es un temporizador, no un adorno: se mantiene
// con reduced-motion. Devuelve el tween para poder leer su duración en las pruebas.
export function anilloCuenta(trazo, segundosRestantes, alTerminar) {
  return gsap.fromTo(trazo, { drawSVG: `0% ${(segundosRestantes / MOV.cuenta.dur) * 100}%` },
    { drawSVG: "0% 0%", duration: segundosRestantes, ease: MOV.cuenta.ease, onComplete: alTerminar });
}

export function dibujarCheck(trazo) {
  return gsap.fromTo(trazo, { drawSVG: "0%" }, { drawSVG: "100%", duration: d(MOV.check.dur), ease: MOV.check.ease });
}

// Cifras que cuentan hasta el valor nuevo (400 ms, power1.out); cifras tabulares en CSS
export function contar(el, valor, formato = (v) => String(Math.round(v))) {
  const previo = Number(el.dataset.valor ?? valor);
  el.dataset.valor = valor;
  if (previo === valor || reducido()) { el.textContent = formato(valor); return; }
  const o = { v: previo };
  gsap.to(o, { v: valor, duration: MOV.cifras.dur, ease: MOV.cifras.ease, onUpdate: () => { el.textContent = formato(o.v); } });
}

// Texto que aparece por palabras (SplitText)
export function aparecerTexto(el) {
  if (reducido()) return;
  const s = SplitText.create(el, { type: "words" });
  gsap.from(s.words, { opacity: 0, y: 6, duration: 0.3, stagger: 0.03, ease: "power2.out", onComplete: () => s.revert() });
}

export { gsap };
