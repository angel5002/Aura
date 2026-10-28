// senal.js — gráfico de la señal del detector (últimos 20 s de K002): señal suavizada, umbral de entrada y
// tramos en MOVIMIENTO. Datos reales; se dibuja en un lienzo con la nitidez del dispositivo (máx. 2x).
import { ventana } from "../data/k002.js";
import { el } from "./ui.js";

export function crearSenal({ alto = 96, conCruces = true, datos = ventana } = {}) {   // datos: ventana de K002 o del escenario
  const lienzo = el("canvas", { class: "senal", height: alto, "aria-label": "Señal del detector, últimos 20 segundos" });
  const ctx = lienzo.getContext("2d");
  function dibujar(t) {
    const w = lienzo.clientWidth, h = alto, dpr = Math.min(devicePixelRatio || 1, 2);
    if (!w) return;
    if (lienzo.width !== Math.round(w * dpr)) { lienzo.width = Math.round(w * dpr); lienzo.height = Math.round(h * dpr); }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const v = datos(t, 20);
    if (!v || v.t.length < 2) return;
    let max = 2;
    for (let k = 0; k < v.t.length; k++) max = Math.max(max, v.suave[k] * 1.1, v.entrada[k] * 1.1);
    const X = (tt) => ((tt - v.t0) / 20) * w, Y = (y) => h - 4 - (y / max) * (h - 8);
    ctx.fillStyle = "rgba(240,122,106,0.24)";
    for (let k = 0; k < v.t.length - 1; k++) if (v.mov[k]) ctx.fillRect(X(v.t[k]), 0, Math.max(1, X(v.t[k + 1]) - X(v.t[k])), h);
    if (conCruces) {
      ctx.strokeStyle = "rgba(148,163,184,0.5)"; ctx.setLineDash([4, 4]);
      for (const [c] of v.cruces) { ctx.beginPath(); ctx.moveTo(X(c), 0); ctx.lineTo(X(c), h); ctx.stroke(); }
    }
    ctx.strokeStyle = "#f07a6a"; ctx.lineWidth = 1.2; ctx.setLineDash([5, 4]); ctx.beginPath();
    v.t.forEach((tt, k) => (k ? ctx.lineTo(X(tt), Y(v.entrada[k])) : ctx.moveTo(X(tt), Y(v.entrada[k]))));
    ctx.stroke(); ctx.setLineDash([]);
    ctx.strokeStyle = "#5cc8d6"; ctx.lineWidth = 1.6; ctx.beginPath();
    v.t.forEach((tt, k) => (k ? ctx.lineTo(X(tt), Y(v.suave[k])) : ctx.moveTo(X(tt), Y(v.suave[k]))));
    ctx.stroke();
  }
  return { lienzo, dibujar };
}
