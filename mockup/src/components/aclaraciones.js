// aclaraciones.js — hoja que se abre con el ⓘ junto al sello DEMO de la cabecera. Iteración 4: cuatro líneas, con el
// texto que pidió Deisy. El detalle de K002 (firmware, placa, una sola sala, 10 de 10) está en el panel técnico.
import { abrirHoja } from "./hoja.js";
import { el } from "./ui.js";

export const ACLARACIONES = [
  "Real: el movimiento (prueba K002, 27/10).",
  "Ejemplo: respiración, sueño, corazón, ánimo y caídas.",
  "Simulado: avisos, teleconsulta y asistente.",
  "AURA no diagnostica ni reemplaza a tu médico.",
];

export function abrirAclaraciones() {
  return abrirHoja(el("div", { class: "hoja-cuerpo", "data-prueba": "hoja-aclaraciones" },
    el("h2", { class: "titulo" }, "Qué estás viendo"),
    el("ul", { class: "lista-aclaraciones" }, ACLARACIONES.map((f) => el("li", {}, f)))));
}
