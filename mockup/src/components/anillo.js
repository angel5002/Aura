// anillo.js — anillo de cuenta regresiva (45 s, lineal) y check de confirmación (trazo de 600 ms).
import { anilloCuenta, dibujarCheck } from "../motion.js";
import { el } from "./ui.js";

const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); return e; };
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.max(0, Math.ceil(s) % 60)).padStart(2, "0")}`;

export function crearAnillo(tam = 200) {
  const r = tam / 2 - 10;
  const lienzo = svg("svg", { viewBox: `0 0 ${tam} ${tam}`, width: tam, height: tam, class: "anillo", "aria-hidden": "true" });
  lienzo.append(svg("circle", { cx: tam / 2, cy: tam / 2, r, class: "anillo-fondo" }));
  const trazo = svg("circle", { cx: tam / 2, cy: tam / 2, r, class: "anillo-trazo", transform: `rotate(-90 ${tam / 2} ${tam / 2})` });
  lienzo.append(trazo);
  const cifra = el("span", { class: "cifra anillo-cifra", "data-prueba": "cuenta" }, "0:45");
  const caja = el("div", { class: "anillo-caja", style: `width:${tam}px;height:${tam}px` }, lienzo, cifra);
  let tween = null, reloj = 0;
  function iniciar(segundosRestantes, desde = performance.now(), alTerminar) {
    detener();
    const resta = Math.max(0, segundosRestantes - (performance.now() - desde) / 1000);
    tween = anilloCuenta(trazo, resta, alTerminar);
    const fin = performance.now() + resta * 1000;
    const tic = () => { const q = (fin - performance.now()) / 1000; cifra.textContent = mmss(Math.max(0, q)); return q; };
    tic();
    reloj = setInterval(() => { if (tic() <= 0) clearInterval(reloj); }, 250);
    return tween;
  }
  function detener() { tween?.kill(); tween = null; clearInterval(reloj); }
  return { caja, iniciar, detener, tween: () => tween, texto: () => cifra.textContent };
}

export function crearCheck(tam = 96) {
  const lienzo = svg("svg", { viewBox: "0 0 96 96", width: tam, height: tam, class: "check", "aria-hidden": "true" });
  lienzo.append(svg("circle", { cx: 48, cy: 48, r: 44, class: "check-circulo" }));
  const trazo = svg("path", { d: "M28 50 L42 63 L69 34", class: "check-trazo" });
  lienzo.append(trazo);
  return { lienzo, dibujar: () => dibujarCheck(trazo) };
}

export { mmss };
