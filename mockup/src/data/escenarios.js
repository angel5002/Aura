// escenarios.js — escenarios de demo "normal", "respiracion" y "caida" (los mismos de reproducir.py de Angel).
// Sin servidor, la app genera aquí el mensaje gemelo que produciría gemelo.py, con fuente = demo.
// Los `texto` con cifras del contrato se conservan como llegarían, pero la app NO los pinta (techo.js).

const ZONAS_BASE = () => ({
  cabeza: { nivel: "verde", estado: "en_investigacion", texto: "" },
  pulmones: { nivel: "verde", estado: "en_investigacion", texto: "" },
  corazon: { nivel: "gris", estado: "no_medido", texto: "" },
  piernas: { nivel: "verde", estado: "prototipo", texto: "Sin eventos" },
  aura: { nivel: "verde", estado: "activo", texto: "" },
});

export function gemeloDemo(escenario) {
  const zonas = ZONAS_BASE();
  let alerta = null;
  if (escenario === "respiracion") zonas.pulmones.nivel = "ambar";
  if (escenario === "caida") {
    zonas.piernas = { nivel: "rojo", estado: "prototipo", texto: "Posible caída" };
    alerta = { tipo: "CAIDA", segundos_restantes: 45 };
  }
  return { ts: Date.now() / 1000, usuario: "Rosa", fuente: "demo", zonas, alerta };
}

export const ESCENARIOS = [
  { id: "normal", nombre: "Normal" },
  { id: "respiracion", nombre: "Respiración (cambio)" },
  { id: "caida", nombre: "Caída" },
];
