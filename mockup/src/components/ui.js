// ui.js — piezas pequeñas: crear elementos, chip de estado, fila de módulo, tarjeta, burbuja, iconos.
import { CHIP } from "../data/techo.js";

export function el(tag, attrs = {}, ...hijos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const h of hijos.flat()) if (h !== null && h !== undefined && h !== false) e.append(h instanceof Node ? h : String(h));
  return e;
}

const NS = "http://www.w3.org/2000/svg";
export function svg(tag, attrs = {}) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

export const etiqueta = (texto) => el("p", { class: "etiqueta" }, texto);   // mayúsculas espaciadas: una por pantalla
export const subtitulo = (texto) => el("p", { class: "subtitulo" }, texto);
export const titulo = (texto) => el("h1", { class: "titulo" }, texto);
export const rotulo = (texto, extra = "") => el("p", { class: `rotulo ${extra}` }, texto);

// Chip de estado (obligatorio en todo módulo): Activo, Prototipo, En investigación, No medido, Simulación, DEMO
export function chip(estadoChip, textoPropio) {
  const c = CHIP[estadoChip];
  return el("span", { class: `chip ${c.clase}`, "data-chip": estadoChip }, textoPropio || c.texto);
}

export function filaModulo(m, estadoMod, detalle) {
  return el("li", { class: "fila-modulo", "data-modulo": m.id },
    el("span", { class: `punto ${CHIP[estadoMod].clase}` }),
    el("span", { class: "fila-nombre" }, m.nombre, detalle ? el("span", { class: "fila-detalle" }, detalle) : null),
    chip(estadoMod));
}

export const tarjeta = (attrs, ...hijos) => el("section", { ...attrs, class: `tarjeta ${attrs.class || ""}` }, ...hijos);

export function burbuja(texto, quien = "aura") {
  return el("div", { class: `burbuja burbuja-${quien}` }, el("p", {}, texto));
}

export const ICONOS = {
  hoy: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/></svg>',
  gemelo: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="5" r="2.6"/><path d="M8 9.5h8l-1 6h-1.5L13 22h-2l-.5-6.5H9z"/></svg>',
  senal: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 13h3l2.5-6 4 11 3-8 2 3H22" fill="none" stroke-width="2" stroke-linejoin="round"/></svg>',
  dispositivo: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="3" width="14" height="18" rx="2.5"/><circle cx="12" cy="17" r="1.3" class="hueco"/></svg>',
  asistente: '<span class="orbe-icono" aria-hidden="true"></span>',
};

// Íconos de los módulos "Próximamente" (trazo, 24 × 24)
export const ICONOS_ORGANO = {
  pulmones: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v7M12 11c-1.5 1-3-1-4 0-3 3-4 8-2 9 3 1 5-1 5-4v-3M12 11c1.5 1 3-1 4 0 3 3 4 8 2 9-3 1-5-1-5-4v-3"/></svg>',
  sueno: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 14.5A7.5 7.5 0 0 1 9.5 5a7.5 7.5 0 1 0 9.5 9.5z"/></svg>',
  corazon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg>',
  animo: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M8.5 14.5c1 1.2 2.2 1.8 3.5 1.8s2.5-.6 3.5-1.8M9.5 10h0M14.5 10h0"/></svg>',
};
