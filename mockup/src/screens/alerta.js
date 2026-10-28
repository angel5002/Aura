// 5 · Alerta temprana — escenario de demo "respiración": cambio detectado, preguntas Sí / No y teleconsulta.
// Sin cifras de respiración: la medición está en investigación (rótulo visible, pedido por Deisy el 28/10/2026).
import { estado } from "../estado.js";
import { mostrarBanner } from "../components/hoja.js";
import { chip, el, etiqueta, rotulo, tarjeta, titulo } from "../components/ui.js";

export default {
  id: "alerta",
  crear({ navegar, lanzarEscenario }) {
    if (estado.escenario !== "respiracion") lanzarEscenario("respiracion");
    const respuesta = el("p", { class: "cuerpo", "aria-live": "polite" });
    const responder = (si) => {
      respuesta.textContent = si
        ? "Gracias por contarme. Te sugiero hablar con tu médico; puedo agendar una teleconsulta."
        : "Gracias. Seguiré atento y te preguntaré otra vez si el cambio continúa.";
    };
    const nodo = el("div", { class: "pantalla" },
      etiqueta("Cambio detectado"),
      titulo("Algo cambió frente a tu normal"),
      el("p", { class: "aviso-ilustrativo", "data-prueba": "rotulo-ilustrativo" },
        "Escenario ilustrativo: la medición de respiración está en investigación"),
      tarjeta({},
        el("div", { class: "fila-entre" }, el("p", { class: "cuerpo fuerte" }, "Respiración nocturna en reposo"), chip("en_investigacion")),
        el("p", { class: "cuerpo texto-2" }, "En este escenario de demostración, AURA nota que tus noches se alejaron de tu normal varias veces seguidas."),
        el("div", { class: "patron", "aria-hidden": "true" }, el("span", { class: "patron-normal" }), el("span", { class: "patron-cambio" })),
        el("p", { class: "rotulo" }, "Esquema ilustrativo, sin escala ni valores.")),
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
        "Compartir reporte con mi médico"),
      rotulo("Teleconsulta y reporte: simulación. AURA no reemplaza la consulta con tu médico."));
    return { nodo, mostrar() {}, ocultar() {} };
  },
};
