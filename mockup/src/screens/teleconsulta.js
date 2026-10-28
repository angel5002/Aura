// 7 · Teleconsulta — hoja inferior con 3 horarios y confirmación (F8, ≤ 3 toques). Todo es simulación (pastilla en
// la hoja): sin nombres de clínicas, solo descripciones genéricas; la aclaración completa está en la hoja ⓘ.
import { pedirTeleconsulta } from "../data/fuente.js";
import { abrirHoja } from "../components/hoja.js";
import { crearCheck } from "../components/anillo.js";
import { chip, el, etiqueta, titulo } from "../components/ui.js";

export const HORARIOS = [
  { lugar: "Medicina general · videollamada", horario: "Hoy 18:00" },
  { lugar: "Policlínico cercano", horario: "Mañana 10:00" },
  { lugar: "Centro de salud del distrito", horario: "Mañana 11:00" },
];

export default {
  id: "teleconsulta",
  crear({ navegar }) {
    const fondo = el("div", { class: "teleconsulta-fondo" },
      etiqueta("Teleconsulta"),
      titulo("Agenda con tu médico"),
      el("p", { class: "cuerpo texto-2" }, "Elige un horario."));
    const confirmacion = el("div", { class: "confirmacion", hidden: true });
    const nodo = el("div", { class: "pantalla" }, fondo, confirmacion);
    let hoja = null;

    function abrir() {
      const opciones = HORARIOS.map((h) => el("button", { class: "opcion-horario", type: "button", "data-prueba": "horario", onclick: () => elegir(h) },
        el("span", { class: "opcion-lugar" }, h.lugar),
        el("span", { class: "opcion-hora tabular" }, h.horario)));
      hoja = abrirHoja(el("div", { class: "hoja-cuerpo" },
        el("div", { class: "fila-entre" }, el("p", { class: "subtitulo" }, "Horarios disponibles"), chip("simulacion")),
        opciones));
    }
    async function elegir(h) {
      const r = await pedirTeleconsulta(h.horario);
      hoja?.cerrar();
      const check = crearCheck(96);
      confirmacion.replaceChildren(check.lienzo,
        el("h1", { class: "titulo centrado", "data-prueba": "cita-confirmada" }, r.simulacion ? "Cita agendada (simulación)" : "Cita agendada"),
        el("p", { class: "cuerpo centrado" }, `${h.lugar} · ${h.horario}`),
        el("p", { class: "cuerpo centrado texto-2" }, "Tu médico recibirá tu reporte de AURA."),
        el("button", { class: "boton boton-sec ancho", type: "button", onclick: () => navegar("hoy") }, "Volver a Hoy"));
      fondo.hidden = true; confirmacion.hidden = false;
      check.dibujar();
    }
    return { nodo, mostrar() { abrir(); }, ocultar() { hoja?.cerrar(); } };
  },
};
