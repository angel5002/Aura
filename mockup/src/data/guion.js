// guion.js — guion del asistente (intenciones de la tabla de F6, reescritas sin cifras de salud y en frases de 12
// palabras o menos). Sin reconocimiento de voz en el mockup (ADR-0025): las preguntas se tocan. Nunca diagnostica
// ni recomienda fármacos; deriva al médico. Ante una emergencia, los botones de la pantalla de emergencia mandan.
import { estado } from "../estado.js";

const hace = (s) => (s === null || s === undefined ? null : s < 60 ? `hace ${Math.round(s)} segundos` : `hace ${Math.round(s / 60)} minutos`);

export const FRASES = [
  { id: "estado", texto: "¿Cómo estoy?" },
  { id: "sueno", texto: "¿Cómo dormí?" },
  { id: "holograma", texto: "Muéstrame mi escaneo" },
  { id: "explicar", texto: "¿Por qué me avisaste?" },
  { id: "cita", texto: "Agéndame una cita" },
  { id: "medicacion", texto: "¿Qué pastilla tomo para la tos?" },
];

export function responder(id) {
  const m = estado.muestra;
  switch (id) {
    case "estado": {
      const ultimo = hace(m?.ultimoMovHace);
      const mov = m?.mov ? "Ahora hay movimiento en la sala." : ultimo ? `Hubo movimiento ${ultimo}.` : "Aún no hubo movimiento.";
      return { texto: `${mov} Respiración y sueño aún no se miden.`, accion: null };
    }
    case "sueno":
      return { texto: "Aún no mido el sueño. Puedo contarte el movimiento de hoy.", accion: null };
    case "holograma":
      return { texto: "Aquí está tu gemelo digital.", accion: "abrir_holograma" };
    case "explicar":
      return estado.escenario === "respiracion"
        ? { texto: "Es un ejemplo: tus noches cambiaron. ¿Tuviste tos, fiebre o cansancio?", accion: "abrir_alerta" }
        : { texto: "Ahora no hay ningún aviso. Si algo cambia, te pregunto primero.", accion: null };
    case "cita":
      return { texto: "Te muestro los horarios disponibles.", accion: "abrir_teleconsulta" };
    case "medicacion":
      return { texto: "No puedo recomendar medicamentos. Te ayudo a agendar con tu médico.", accion: "ofrecer_teleconsulta" };
    default:
      return { texto: "Puedo contarte el movimiento de hoy o mostrarte tu gemelo.", accion: null };
  }
}
