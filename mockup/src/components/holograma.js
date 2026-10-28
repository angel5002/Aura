// holograma.js — iframe con la escena Three.js de K002 (copia local en holograma/). Se pausa cuando su
// pantalla no está visible; la app le manda el t de la reproducción, el estado de las zonas o "escanear", y el
// iframe avisa cuando se toca una zona del gemelo.
import { el } from "./ui.js";
import { ESCENARIO_VIDEO } from "../data/video.js";

export function crearHolograma(modo, titulo, { alTocarZona } = {}) {
  const extra = ESCENARIO_VIDEO && modo === "senal" ? `&escenario=${ESCENARIO_VIDEO}` : "";   // escenario simulado del video
  const iframe = el("iframe", { class: "holograma", src: `holograma/index.html?modo=${modo}${extra}`, title: titulo, loading: "eager" });
  let listo = false;
  const pendientes = [];
  const alListo = (f) => (listo ? f() : pendientes.push(f));
  const oyente = (e) => {
    if (e.source !== iframe.contentWindow) return;
    if (e.data?.tipo === "holograma_listo") { listo = true; pendientes.splice(0).forEach((f) => f()); }
    else if (e.data?.tipo === "zona_tocada") alTocarZona?.(e.data.zona);
  };
  addEventListener("message", oyente);
  const enviar = (m) => { if (listo) iframe.contentWindow?.postMessage(m, location.origin); };
  const pausar = (v) => {
    enviar({ tipo: "pausa", valor: v });
    if (v) removeEventListener("message", oyente);
  };
  return { iframe, enviar, alListo, pausar, escena: () => iframe.contentWindow?.AURA_ESCENA ?? null };
}
