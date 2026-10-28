// fuente.js — de dónde salen los datos (especificación, "Datos del mockup"):
//   1. En vivo: si servidor.py responde en /ws, se usan sus mensajes {topico, datos} (contrato de Angel).
//   2. Reproducción K002: datos reales del detector, en bucle, para Hoy y Señal.
//   3. Escenarios de demo "normal", "respiracion" y "caida" (fuente = demo) para Gemelo, Alerta y Emergencia.
// `fuente` es "vivo" solo si hay servidor, llega movimiento en vivo y nada reciente vino con fuente = demo.
// El campo `movimiento` de `estado` NO existe hoy en el contrato: es la propuesta para Angel
// (docs/mockup/propuestas_para_angel.md). Mientras no llegue, Hoy usa la reproducción K002 y el sello sigue.
import { cambiar, estado } from "../estado.js";
import { cargarK002, duracionK002, muestraEn } from "./k002.js";
import { gemeloDemo } from "./escenarios.js";
import { ESCENARIO_VIDEO } from "./video.js";

const T_INICIAL = 24;                 // la reproducción arranca 6 s antes del primer cruce (t = 30 s)
const ESPERA_ALERTA = 45;             // s (F3)
let origenReloj = performance.now(), tOrigen = T_INICIAL;
let ws = null, movimientoVivo = null, demoHasta = 0, temporizadorAlerta = null;

export const tK002 = () => (tOrigen + (performance.now() - origenReloj) / 1000) % duracionK002();
export function irA(t) { tOrigen = t; origenReloj = performance.now(); }

function recalcularFuente() {
  const vivo = estado.conexion === "vivo" && movimientoVivo !== null && Date.now() > demoHasta;
  const fuente = vivo ? "vivo" : "demo";
  if (fuente !== estado.fuente) cambiar({ fuente, origenMov: vivo ? "via_local" : "reproduccion" });
}

// ---------- 1. en vivo ----------
function conectar() {
  cambiar({ conexion: "buscando" });
  let abierto = false;
  try {
    ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  } catch {
    sinServidor();
    return;
  }
  const corte = setTimeout(() => { if (!abierto) ws.close(); }, 2500);
  ws.onopen = () => { abierto = true; clearTimeout(corte); cambiar({ conexion: "vivo" }); recalcularFuente(); };
  ws.onmessage = (e) => {
    let m;
    try { m = JSON.parse(e.data); } catch { return; }
    recibir(m.topico, m.datos || {});
  };
  ws.onclose = () => { clearTimeout(corte); sinServidor(); };
}
function sinServidor() {
  ws = null;
  movimientoVivo = null;
  cambiar({ conexion: "sin_servidor" });
  recalcularFuente();
  setTimeout(conectar, 10000);
}

function recibir(topico, datos) {
  if (datos.fuente === "demo") demoHasta = Date.now() + 60000;
  if (topico === "estado" && typeof datos.movimiento === "boolean") {
    const ahora = Date.now() / 1000;
    if (datos.movimiento) movimientoVivo = ahora;
    else if (movimientoVivo === null) movimientoVivo = 0;
    cambiar({ muestra: { t: null, mov: datos.movimiento, ultimoMovHace: movimientoVivo ? ahora - movimientoVivo : null } });
  }
  if (topico === "gemelo") {
    if (datos.fuente === "demo") demoHasta = Date.now() + 60000;
    const a = datos.alerta;
    let alerta = null;
    if (a?.tipo === "CAIDA") alerta = { tipo: "CAIDA", segundos: a.segundos_restantes ?? ESPERA_ALERTA, desde: performance.now(), vivo: true };
    else if (a?.tipo) alerta = { tipo: a.tipo, simulacion: false };
    cambiar({ gemelo: datos, alerta });
  }
  recalcularFuente();
}

async function post(ruta, cuerpo) {
  const r = await fetch(ruta, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo ?? {}) });
  if (!r.ok) throw new Error(`${ruta}: ${r.status}`);
  return r.json();
}

// ---------- 3. escenarios ----------
export async function lanzarEscenario(nombre) {
  demoHasta = Date.now() + 60000;
  recalcularFuente();
  if (estado.conexion === "vivo") {
    try { await post(`demo/${nombre}`); cambiar({ escenario: nombre }); return; } catch { /* sin endpoint: local */ }
  }
  clearTimeout(temporizadorAlerta);
  const gemelo = gemeloDemo(nombre);
  let alerta = null;
  if (nombre === "caida") {
    alerta = { tipo: "CAIDA", segundos: ESPERA_ALERTA, desde: performance.now(), vivo: false };
    temporizadorAlerta = setTimeout(() => cambiar({ alerta: { tipo: "FAMILIA_AVISADA", simulacion: true } }), ESPERA_ALERTA * 1000);
  }
  cambiar({ escenario: nombre, gemelo, alerta });
}

export async function responderEmergencia(respuesta) {      // "bien" | "ayuda"
  if (estado.alerta?.vivo) {
    try { await post("emergencia/respuesta", { respuesta }); return; } catch { /* sigue en local */ }
  }
  clearTimeout(temporizadorAlerta);
  if (respuesta === "bien") cambiar({ alerta: null, escenario: "normal", gemelo: gemeloDemo("normal") });
  else cambiar({ alerta: { tipo: "FAMILIA_AVISADA", simulacion: true } });
}

export async function pedirTeleconsulta(horario) {
  if (estado.conexion === "vivo") {
    try { await post("teleconsulta", { horario }); return { simulacion: false }; } catch { /* simulada */ }
  }
  return { simulacion: true };
}

// ---------- arranque ----------
export async function iniciarFuente() {
  if (ESCENARIO_VIDEO) { cambiar({ k002: null, gemelo: gemeloDemo("normal") }); return; }   // escenario simulado: nada de K002
  const k002 = await cargarK002();
  cambiar({ k002, gemelo: gemeloDemo("normal") });
  setInterval(() => {
    if (estado.origenMov === "reproduccion" && k002) cambiar({ muestra: muestraEn(tK002()) });
  }, 100);
  if (k002) cambiar({ muestra: muestraEn(tK002()) });
  conectar();
}
