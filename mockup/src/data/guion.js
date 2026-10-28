// guion.js — guion del asistente (intenciones de la tabla de F6, reescritas sin cifras de salud).
// Sin reconocimiento de voz en el mockup (ADR-0025): las frases se tocan. Nunca diagnostica ni recomienda
// fármacos; deriva al médico. Ante una emergencia, los botones de la pantalla de emergencia mandan.
import { estado } from "../estado.js";

const hace = (s) => (s === null || s === undefined ? null : s < 60 ? `hace ${Math.round(s)} s` : `hace ${Math.round(s / 60)} min`);

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
      const origen = estado.origenMov === "via_local" ? "en vivo" : "en la reproducción de la prueba K002";
      const ultimo = hace(m?.ultimoMovHace);
      const mov = m?.mov ? "Ahora mismo detecto movimiento" : ultimo ? `El último movimiento fue ${ultimo}` : "No he detectado movimiento todavía";
      return { texto: `${mov}, ${origen}. La respiración y el sueño todavía están en investigación: no los mido.`, accion: null };
    }
    case "sueno":
      return { texto: "Todavía no mido el sueño: ese módulo está en investigación. Puedo contarte el movimiento de hoy.", accion: null };
    case "holograma":
      return { texto: "Aquí está tu gemelo digital. Es una representación ilustrativa.", accion: "abrir_holograma" };
    case "explicar":
      return estado.escenario === "respiracion"
        ? { texto: "Es un escenario de demostración: AURA notó un cambio frente a tu normal. ¿Has tenido tos, fiebre o cansancio?", accion: "abrir_alerta" }
        : { texto: "Ahora no hay ningún aviso activo. Si algo cambia frente a tu normal, te lo pregunto primero.", accion: null };
    case "cita":
      return { texto: "Te muestro los horarios disponibles. Es una simulación.", accion: "abrir_teleconsulta" };
    case "medicacion":
      return { texto: "No puedo recomendar medicamentos. Si quieres, te ayudo a agendar con tu médico.", accion: "ofrecer_teleconsulta" };
    default:
      return { texto: "Puedo contarte el movimiento de hoy o mostrarte tu gemelo digital.", accion: null };
  }
}
