// holograma.js — iframe con la escena Three.js de K002 (copia local en holograma/). Se pausa cuando su
// pantalla no está visible; la app le manda el t de la reproducción, los colores de las zonas o "escanear".
import { el } from "./ui.js";

export function crearHolograma(modo, titulo) {
  const iframe = el("iframe", { class: "holograma", src: `holograma/index.html?modo=${modo}`, title: titulo, loading: "eager" });
  let listo = false;
  const pendientes = [];
  const alListo = (f) => (listo ? f() : pendientes.push(f));
  const oyente = (e) => {
    if (e.source !== iframe.contentWindow || e.data?.tipo !== "holograma_listo") return;
    listo = true;
    pendientes.splice(0).forEach((f) => f());
  };
  addEventListener("message", oyente);
  const enviar = (m) => { if (listo) iframe.contentWindow?.postMessage(m, location.origin); };
  const pausar = (v) => {
    enviar({ tipo: "pausa", valor: v });
    if (v) removeEventListener("message", oyente);
  };
  return { iframe, enviar, alListo, pausar };
}
