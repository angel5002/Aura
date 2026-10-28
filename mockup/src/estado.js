// estado.js — estado único de la app. Las pantallas se suscriben; los datos los escribe src/data/fuente.js.
export const estado = {
  conexion: "buscando",      // buscando | vivo | sin_servidor
  fuente: "demo",            // demo | vivo  (sello "DEMO · reproducción" siempre que sea demo)
  origenMov: "reproduccion", // reproduccion (K002) | via_local (campo `movimiento` del servidor, si existe)
  k002: null,                // metadatos de la reproducción, o null si esta copia no la trae
  muestra: null,             // { t, mov, suave, entrada, tasa, detectados, ultimoMovHace }
  gemelo: null,              // último mensaje gemelo (en vivo o generado por un escenario)
  alerta: null,              // { tipo: "CAIDA", segundos, desde } | { tipo: "FAMILIA_AVISADA" | "AYUDA_SOLICITADA", simulacion }
  escenario: "normal",       // normal | respiracion | caida
};

const oyentes = new Set();
export function cambiar(parcial) {
  Object.assign(estado, parcial);
  oyentes.forEach((f) => f(estado, parcial));
}
export function escuchar(f) {
  oyentes.add(f);
  return () => oyentes.delete(f);
}
