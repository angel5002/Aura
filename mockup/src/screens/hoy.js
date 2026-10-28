// 1 · Hoy — en lenguaje humano: una frase de estado y la línea de la prueba con los momentos de actividad.
// Datos reales: vía local (si el servidor manda `movimiento`) o la reproducción de K002. Sin tasa de CSI ni
// umbrales: el gráfico técnico vive en Señal y en el panel técnico.
import { escuchar, estado } from "../estado.js";
import { tK002 } from "../data/fuente.js";
import { duracionK002, momentos } from "../data/k002.js";
import { chip, el, etiqueta, rotulo, subtitulo, svg } from "../components/ui.js";

const PARTE_DEL_DIA = () => { const h = new Date().getHours(); return h < 12 ? "esta mañana" : h < 19 ? "esta tarde" : "esta noche"; };
function frase(m) {
  if (!m) return "Esperando datos";
  if (m.mov) return "Hay movimiento en la sala";
  if (m.ultimoMovHace !== null && m.ultimoMovHace < 20) return "Hubo movimiento hace un momento";
  return `Todo tranquilo ${PARTE_DEL_DIA()}`;
}
function sub(m) {
  if (!m) return "";
  if (m.mov) return "AURA lo está notando ahora mismo.";
  const s = m.ultimoMovHace;
  if (s === null) return "Todavía no hubo movimiento.";
  return s < 60 ? `Último movimiento hace ${Math.round(s)} segundos.` : `Último movimiento hace ${Math.round(s / 60)} minutos.`;
}

export default {
  id: "hoy",
  crear() {
    const titulo = el("h1", { class: "frase", "data-prueba": "estado-mov" }, "—");
    const bajada = el("p", { class: "cuerpo texto-2" }, "");
    const conteo = el("p", { class: "cuerpo" }, "");
    const dur = duracionK002();
    const linea = svg("svg", { class: "linea-svg", viewBox: `0 0 ${dur} 48`, preserveAspectRatio: "none", role: "img", "aria-label": "Momentos de actividad en la prueba K002" });
    linea.append(svg("rect", { class: "pista", x: 0, y: 19, width: dur, height: 10, rx: 5 }));
    for (const [a, b] of momentos()) linea.append(svg("rect", { class: "momento", x: a, y: 12, width: Math.max(2.2, b - a), height: 24, rx: 1.1 }));
    const ahora = svg("line", { class: "ahora", x1: 0, x2: 0, y1: 4, y2: 44, "vector-effect": "non-scaling-stroke" });   // se mueve con transform
    linea.append(ahora);
    const reproduccion = !!estado.k002 && estado.origenMov === "reproduccion";
    const sinDatos = !estado.k002 && estado.origenMov !== "via_local";

    const fila = (id, nombre, estadoChip) => el("li", { class: "fila-modulo", "data-modulo": id }, el("span", { class: "fila-nombre" }, nombre), chip(estadoChip));
    const nodo = el("div", { class: "pantalla" },
      etiqueta("Tu actividad de hoy"),
      el("div", { class: "estado-frase" }, titulo, bajada),
      reproduccion
        ? el("section", { class: "tarjeta linea-dia" },
          subtitulo("Momentos de actividad · prueba K002"),
          linea,
          el("div", { class: "escala" }, el("span", {}, "inicio"), el("span", {}, "2 min 45 s"), el("span", {}, "5 min 30 s")),
          conteo)
        : sinDatos ? el("p", { class: "cuerpo texto-2" }, "Esta copia de la app no trae la reproducción de K002 y no hay servidor: no hay datos que mostrar.") : null,
      el("section", { class: "bloque" },
        subtitulo("Qué mira AURA"),
        el("ul", { class: "lista-modulos" },
          fila("actividad", "Actividad en la sala", "activo"),
          fila("caidas", "Caídas", "prototipo"),
          fila("pulmones", "Respiración, sueño y presencia quieta", "en_investigacion"))),
      rotulo("Movimiento: datos reales de la prueba K002 (27/10/2026, firmware 0.1.3), reproducidos en bucle; en esa prueba "
        + "se detectaron 10 de 10 cruces. Respiración, sueño y presencia quieta no se miden todavía."));

    let cuadro = 0, soltar = null, previo = "";
    function pintar() {
      const m = estado.muestra;
      const f = frase(m), s = sub(m);
      if (f + s !== previo) { titulo.textContent = f; bajada.textContent = s; previo = f + s; }
      if (reproduccion && m?.t != null) {
        const n = momentos().filter(([a]) => a <= m.t).length;
        const txt = n === 1 ? "1 momento de actividad hasta ahora." : `${n} momentos de actividad hasta ahora.`;
        if (conteo.textContent !== txt) conteo.textContent = txt;
      }
    }
    return {
      nodo,
      mostrar() {
        soltar = escuchar((_, p) => { if ("muestra" in p || "fuente" in p) pintar(); });
        pintar();
        const bucle = () => { ahora.setAttribute("transform", `translate(${tK002().toFixed(2)} 0)`); cuadro = requestAnimationFrame(bucle); };
        if (reproduccion) cuadro = requestAnimationFrame(bucle);
      },
      ocultar() { soltar?.(); cancelAnimationFrame(cuadro); },
    };
  },
};
