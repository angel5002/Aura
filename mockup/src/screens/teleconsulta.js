// 7 · Teleconsulta — hoja inferior con 3 horarios ficticios y confirmación (F8, ≤ 3 toques). Todo es simulación:
// lugares con nombres claramente ficticios, sin integración con clínicas ni seguros.
import { pedirTeleconsulta } from "../data/fuente.js";
import { abrirHoja } from "../components/hoja.js";
import { crearCheck } from "../components/anillo.js";
import { chip, el, etiqueta, rotulo, titulo } from "../components/ui.js";

export const HORARIOS = [
  { lugar: "Consultorio Demo Uno", tipo: "Teleconsulta · medicina general", horario: "Hoy 18:00" },
  { lugar: "Policlínico Ficticio Sur", tipo: "Presencial · a 1,2 km (simulado)", horario: "Mañana 10:00" },
  { lugar: "Centro Ejemplo Norte", tipo: "Teleconsulta · medicina general", horario: "Mañana 11:00" },
];

export default {
  id: "teleconsulta",
  crear({ navegar }) {
    const fondo = el("div", { class: "teleconsulta-fondo" },
      el("div", { class: "fila-entre" }, etiqueta("Teleconsulta"), chip("simulacion")),
      titulo("Agenda con tu médico"),
      el("p", { class: "cuerpo texto-2" }, "Elige un horario. Tu médico recibiría el reporte de AURA."));
    const confirmacion = el("div", { class: "confirmacion", hidden: true });
    const nodo = el("div", { class: "pantalla" }, fondo, confirmacion,
      rotulo("Simulación: no hay integración real con clínicas ni seguros. AURA no reemplaza la consulta con tu médico."));
    let hoja = null;

    function abrir() {
      const opciones = HORARIOS.map((h) => el("button", { class: "opcion-horario", type: "button", "data-prueba": "horario", onclick: () => elegir(h) },
        el("span", { class: "opcion-lugar" }, h.lugar),
        el("span", { class: "opcion-tipo" }, h.tipo),
        el("span", { class: "opcion-hora tabular" }, h.horario)));
      hoja = abrirHoja(el("div", { class: "hoja-cuerpo" },
        el("div", { class: "fila-entre" }, el("p", { class: "etiqueta" }, "Horarios disponibles"), chip("simulacion")),
        opciones,
        el("p", { class: "rotulo" }, "Cubierto por tu seguro: simulación.")));
    }
    async function elegir(h) {
      const r = await pedirTeleconsulta(h.horario);
      hoja?.cerrar();
      const check = crearCheck(96);
      confirmacion.replaceChildren(check.lienzo,
        el("h1", { class: "titulo centrado", "data-prueba": "cita-confirmada" }, r.simulacion ? "Cita agendada (simulación)" : "Cita agendada"),
        el("p", { class: "cuerpo centrado" }, `${h.lugar} · ${h.horario}`),
        el("p", { class: "cuerpo centrado texto-2" }, "Tu médico recibiría tu reporte de AURA. Avisamos a tu familia (simulación)."),
        el("button", { class: "boton boton-sec ancho", type: "button", onclick: () => navegar("hoy") }, "Volver a Hoy"));
      fondo.hidden = true; confirmacion.hidden = false;
      check.dibujar();
    }
    return { nodo, mostrar() { abrir(); }, ocultar() { hoja?.cerrar(); } };
  },
};
