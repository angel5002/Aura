// hoja.js — hoja inferior (sube con leve rebote, 360 ms, back.out(1.2)) y banner de notificación (baja, 420 ms).
import { bajarBanner, bajarHoja, subirBanner, subirHoja } from "../motion.js";
import { el } from "./ui.js";

export function abrirHoja(contenido, { alCerrar } = {}) {
  const capa = document.getElementById("capas");
  const velo = el("div", { class: "velo", onclick: () => cerrar() });
  const hoja = el("div", { class: "hoja", role: "dialog", "aria-modal": "true" }, el("span", { class: "asa" }), contenido);
  capa.append(velo, hoja);
  subirHoja(hoja, velo);
  let abierta = true;
  function cerrar() {
    if (!abierta) return;
    abierta = false;
    bajarHoja(hoja, velo).then(() => { velo.remove(); hoja.remove(); alCerrar?.(); });
  }
  return { hoja, cerrar };
}

let bannerActual = null;
export function mostrarBanner({ titulo, texto, alTocar, segundos = 6 }) {
  bannerActual?.remove();
  const b = el("button", { class: "banner", type: "button", onclick: () => { cerrar(); alTocar?.(); } },
    el("span", { class: "banner-marca" }, "AURA"),
    el("span", { class: "banner-cuerpo" }, el("strong", {}, titulo), el("span", {}, texto)));
  document.getElementById("capas").append(b);
  bannerActual = b;
  bajarBanner(b);
  const id = setTimeout(cerrar, segundos * 1000);
  function cerrar() {
    clearTimeout(id);
    if (!b.isConnected) return;
    subirBanner(b).then(() => b.remove());
  }
  return cerrar;
}
