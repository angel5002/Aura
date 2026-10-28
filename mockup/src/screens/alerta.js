// 5 · Alerta temprana — escenario de demo "respiración": un cambio en las noches, preguntas Sí / No y teleconsulta.
// Sin cifras de respiración. Bajo el título, una línea: "Ejemplo · la respiración aún no se mide"; el resto de las
// aclaraciones está en la hoja ⓘ de la cabecera (iteración 3).
import { estado } from "../estado.js";
import { mostrarBanner } from "../components/hoja.js";
import { el, etiqueta, svg, tarjeta, titulo } from "../components/ui.js";

// Tendencia suave sin valores ni pie: estable y luego sube en las tres últimas noches
function tendencia() {
  const t = svg("svg", { class: "tendencia", viewBox: "0 0 300 56", preserveAspectRatio: "none", "aria-hidden": "true" });
  t.append(svg("path", { d: "M4 40C40 38 70 42 105 39S170 41 195 37C220 33 240 24 262 20S290 14 296 13", "vector-effect": "non-scaling-stroke" }));
  return t;
}

export default {
  id: "alerta",
  crear({ navegar, lanzarEscenario }) {
    if (estado.escenario !== "respiracion") lanzarEscenario("respiracion");
    const respuesta = el("p", { class: "cuerpo", "aria-live": "polite" });
    const responder = (si) => {
      respuesta.textContent = si ? "Gracias. Te sugiero hablar con tu médico." : "Gracias. Seguiré atento a tus noches.";
    };
    const nodo = el("div", { class: "pantalla" },
      etiqueta("Cambio detectado"),
      el("div", { class: "estado-frase" },
        titulo("Notamos un cambio en tus noches"),
        el("p", { class: "rotulo", "data-prueba": "rotulo-ilustrativo" }, "Ejemplo · la respiración aún no se mide")),
      el("p", { class: "cuerpo" }, "Tu respiración en reposo estuvo más rápida de lo habitual tres noches seguidas."),
      tendencia(),
      tarjeta({},
        el("p", { class: "cuerpo" }, "¿Has tenido tos, fiebre o cansancio?"),
        el("div", { class: "dos-botones" },
          el("button", { class: "boton boton-sec", type: "button", onclick: () => responder(true) }, "Sí"),
          el("button", { class: "boton boton-sec", type: "button", onclick: () => responder(false) }, "No")),
        respuesta),
      el("button", { class: "boton boton-principal ancho", type: "button", "data-prueba": "agendar", onclick: () => navegar("teleconsulta") },
        "Agendar teleconsulta"),
      el("button", { class: "boton boton-sec ancho", type: "button",
        onclick: () => mostrarBanner({ titulo: "Reporte listo (simulación)", texto: "Así se compartiría con tu médico." }) },
        "Compartir reporte con mi médico"));
    return { nodo, mostrar() {}, ocultar() {} };
  },
};
