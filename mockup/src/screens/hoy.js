// 1 · Hoy — una frase de estado ("Movimiento en la sala" / "Todo tranquilo"), cuánto hace del último movimiento y la
// línea del día con los momentos de actividad. Datos reales: vía local (si el servidor manda `movimiento`) o la
// reproducción de K002. Las aclaraciones (K002, firmware, qué no se mide) están en la hoja ⓘ de la cabecera.
import { escuchar, estado } from "../estado.js";
import { tK002 } from "../data/fuente.js";
import { duracionK002, momentos } from "../data/k002.js";
import { el, etiqueta, subtitulo, svg } from "../components/ui.js";
import { ESCENARIO_VIDEO } from "../data/video.js";

// Escenario simulado "bienestar_video" (solo el video): actividad en la sala de 7 días, sintética; las 3 últimas,
// más bajas (en ámbar). El video fija el crecimiento de las barras y la frase con cuadro(t, {barras, linea}).
const SEMANA = [["L", 0.78], ["M", 0.86], ["M", 0.74], ["J", 0.82], ["V", 0.5], ["S", 0.44], ["D", 0.4]];
const COSTUMBRE = 0.8;
function crearSemana() {
  const frase = el("h1", { class: "frase", "data-prueba": "frase-semana" }, "Estos días te moviste menos que de costumbre");
  const barras = SEMANA.map(([, v], k) => el("div", { class: `barra-dia${k >= 4 ? " menos" : ""}`, "data-valor": v }));
  const nodo = el("div", { class: "pantalla" },
    etiqueta("Tu semana"),
    el("section", { class: "tarjeta linea-dia" },
      subtitulo("Actividad en la sala"),
      el("div", { class: "barras-semana" }, el("div", { class: "costumbre", style: `bottom:${COSTUMBRE * 100}%` }),
        barras.map((b) => el("div", { class: "barra-pista" }, b))),
      el("div", { class: "dias-semana" }, SEMANA.map(([d]) => el("span", {}, d)))),
    frase);
  const suave = (q) => q * q * (3 - 2 * q);
  return {
    nodo, mostrar() {}, ocultar() {},
    cuadro(t, { barras: qb = 1, linea = 1 } = {}) {
      barras.forEach((b, k) => {
        const q = suave(Math.max(0, Math.min(1, qb * 1.6 - k * 0.1)));
        b.style.transform = `scaleY(${(SEMANA[k][1] * q).toFixed(4)})`;
      });
      frase.style.opacity = linea;
      return true;
    },
  };
}

const hace = (m) => {
  if (!m) return "";
  if (m.mov) return "ahora";
  const s = m.ultimoMovHace;
  if (s === null) return "sin movimiento aún";
  return s < 60 ? `hace ${Math.round(s)} s` : `hace ${Math.round(s / 60)} min`;
};

export default {
  id: "hoy",
  crear() {
    if (ESCENARIO_VIDEO === "bienestar_video") return crearSemana();
    const titulo = el("h1", { class: "frase", "data-prueba": "estado-mov" }, "—");
    const cuando = el("p", { class: "tiempo-chico tabular" }, "");
    const dur = duracionK002();
    const linea = svg("svg", { class: "linea-svg", viewBox: `0 0 ${dur} 48`, preserveAspectRatio: "none", role: "img", "aria-label": "Momentos de actividad de hoy" });
    linea.append(svg("rect", { class: "pista", x: 0, y: 19, width: dur, height: 10, rx: 5 }));
    for (const [a, b] of momentos()) linea.append(svg("rect", { class: "momento", x: a, y: 12, width: Math.max(2.2, b - a), height: 24, rx: 1.1 }));
    const ahora = svg("line", { class: "ahora", x1: 0, x2: 0, y1: 4, y2: 44, "vector-effect": "non-scaling-stroke" });   // se mueve con transform
    linea.append(ahora);
    const reproduccion = !!estado.k002 && estado.origenMov === "reproduccion";
    const sinDatos = !estado.k002 && estado.origenMov !== "via_local";

    const nodo = el("div", { class: "pantalla" },
      etiqueta("Tu actividad de hoy"),
      el("div", { class: "estado-frase" }, titulo, cuando),
      reproduccion
        ? el("section", { class: "tarjeta linea-dia" },
          subtitulo("Hoy"),
          linea,
          el("div", { class: "escala" }, el("span", {}, "inicio"), el("span", {}, "2 min 45 s"), el("span", {}, "5 min 30 s")))
        : sinDatos ? el("p", { class: "cuerpo texto-2" }, "Sin datos de movimiento en esta copia.") : null);

    let cuadro = 0, soltar = null, previo = "";
    function pintar() {
      const m = estado.muestra;
      const f = !m ? "Esperando datos" : m.mov ? "Movimiento en la sala" : "Todo tranquilo", c = hace(m);
      if (f + c !== previo) { titulo.textContent = f; cuando.textContent = c; previo = f + c; }
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
