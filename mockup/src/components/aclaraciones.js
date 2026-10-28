// aclaraciones.js — hoja que se abre con el ⓘ junto al sello DEMO de la cabecera (iteración 3). Reúne TODAS las
// aclaraciones que antes estaban repartidas por las pantallas: qué es real, qué es ejemplo, qué es ilustrativo,
// que AURA no diagnostica ni reemplaza al médico, K002 y firmware. Frases de 12 palabras o menos.
import { abrirHoja } from "./hoja.js";
import { el, subtitulo } from "./ui.js";

export const ACLARACIONES = [
  ["Qué es real", [
    "El movimiento son datos reales de la prueba K002.",
    "K002: 27/10/2026, firmware 0.1.3, placa B, una sola sala.",
    "En esa prueba se detectaron 10 de 10 cruces.",
    "Se reproducen en bucle: no hay un sensor en vivo.",
    "La señal y la escena de Señal usan esos mismos datos.",
  ]],
  ["Qué es ejemplo", [
    "Respiración, sueño, corazón y ánimo aún no se miden.",
    "El cambio en tus noches es un ejemplo de demostración.",
    "Caídas es un prototipo sin validar: siempre pregunta antes.",
    "El aviso a tu familia es simulado: no se envía nada.",
    "La teleconsulta es simulada: horarios y lugares no son reales.",
    "Los datos de Dispositivo son de ejemplo, salvo la prueba K002.",
    "El asistente responde con un guion fijo; no transcribe tu voz.",
  ]],
  ["Qué es ilustrativo", [
    "La figura es un dibujo: AURA no capta forma ni postura.",
    "Las ondas de la escena son un esquema, no a escala.",
    "La línea de tendencia de la alerta no tiene valores.",
  ]],
  ["Tu salud", [
    "AURA no diagnostica ni receta medicamentos.",
    "AURA no reemplaza a tu médico.",
    "Ante una urgencia, llama al 106 (SAMU).",
  ]],
];

export function abrirAclaraciones() {
  return abrirHoja(el("div", { class: "hoja-cuerpo", "data-prueba": "hoja-aclaraciones" },
    el("h2", { class: "titulo" }, "Qué estás viendo"),
    ACLARACIONES.flatMap(([titulo, frases]) => [subtitulo(titulo), el("ul", { class: "lista-aclaraciones" }, frases.map((f) => el("li", {}, f)))])));
}
