// techo.js — reglas de honestidad (especificación, "Reglas de honestidad"; ADR-0017, ADR-0018, ADR-0019).
// Cada módulo tiene un TECHO: el estado más alto que la app puede mostrar, diga lo que diga el mensaje.
// La app ignora `confianza` del contrato de Angel; si llega `estado`, se usa el más bajo de los dos.

export const ORDEN = ["no_medido", "en_investigacion", "prototipo", "activo"];

export const CHIP = {
  activo: { texto: "Activo", clase: "chip-activo", color: "#4ade80" },
  prototipo: { texto: "Prototipo", clase: "chip-prototipo", color: "#fbbf24" },
  en_investigacion: { texto: "En investigación", clase: "chip-muted", color: "#7c8ba1" },
  no_medido: { texto: "No medido", clase: "chip-muted", color: "#7c8ba1" },
  simulacion: { texto: "Simulación", clase: "chip-demo" },
  demo: { texto: "DEMO", clase: "chip-demo" },
};

// zona = zona del gemelo de Angel; cifras = false → nunca se pinta `texto` ni `z` de ese módulo
export const MODULOS = [
  { id: "actividad", nombre: "Actividad (movimiento)", zona: "aura", lugar: "aura", techo: "activo", cifras: false },
  { id: "caidas", nombre: "Caídas", zona: "piernas", lugar: "caderas y piernas", techo: "prototipo", cifras: false },
  { id: "pulmones", nombre: "Pulmones (respiración)", zona: "pulmones", lugar: "pecho", techo: "en_investigacion", cifras: false },
  { id: "sueno", nombre: "Sueño", zona: "cabeza", lugar: "cabeza", techo: "en_investigacion", cifras: false },
  { id: "corazon", nombre: "Corazón", zona: "corazon", lugar: "corazón", techo: "no_medido", cifras: false },
  { id: "animo", nombre: "Ánimo", zona: "cabeza", lugar: "cabeza", techo: "no_medido", cifras: false },
];
export const PRESENCIA_QUIETA = { id: "presencia", nombre: "Presencia quieta", techo: "en_investigacion" };

export function estadoDe(modulo, gemelo) {
  const delMensaje = gemelo?.zonas?.[modulo.zona]?.estado;
  if (!ORDEN.includes(delMensaje)) return modulo.techo;
  return ORDEN[Math.min(ORDEN.indexOf(delMensaje), ORDEN.indexOf(modulo.techo))];
}

// Color de cada zona del holograma = color de su chip; en una caída activa, piernas en rojo
export function coloresZonas(gemelo, alerta) {
  const porZona = {};
  for (const m of MODULOS) {
    const c = CHIP[estadoDe(m, gemelo)].color;
    // una zona con dos módulos (cabeza = sueño + ánimo) toma el estado más alto de los dos
    if (!porZona[m.zona] || ORDEN.indexOf(estadoDe(m, gemelo)) > ORDEN.indexOf(porZona[m.zona].e))
      porZona[m.zona] = { e: estadoDe(m, gemelo), c };
  }
  const colores = Object.fromEntries(Object.entries(porZona).map(([z, v]) => [z, v.c]));
  if (alerta?.tipo === "CAIDA") colores.piernas = "#ef4444";
  return colores;
}
