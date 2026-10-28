// 3 · Gemelo digital — figura holográfica ilustrativa por zonas y lista de módulos con su chip.
// Cada zona se ilumina con el color de su chip (techo.js). No se pinta ningún `texto` con cifras del gemelo.
import { escuchar, estado } from "../estado.js";
import { MODULOS, coloresZonas, estadoDe } from "../data/techo.js";
import { crearHolograma } from "../components/holograma.js";
import { chip, el, etiqueta, filaModulo, rotulo, tarjeta, titulo } from "../components/ui.js";

function detalle(m) {
  if (m.id === "actividad") return estado.muestra ? (estado.muestra.mov ? "En movimiento" : "Sin movimiento") : null;
  if (m.id === "caidas") return estado.alerta?.tipo === "CAIDA" ? "Posible caída" : "Sin eventos";
  return m.lugar;
}

export default {
  id: "gemelo",
  crear({ escanear }) {
    const holo = crearHolograma("gemelo", "Gemelo digital ilustrativo");
    const lista = el("ul", { class: "lista-modulos" });
    const persona = el("p", { class: "rotulo" });
    function pintar() {
      lista.replaceChildren(...MODULOS.map((m) => filaModulo(m, estadoDe(m, estado.gemelo), detalle(m))));
      persona.textContent = estado.fuente === "demo" ? "Rosa · persona ficticia de la demo" : "";
      holo.enviar({ tipo: "zonas", colores: coloresZonas(estado.gemelo, estado.alerta) });
    }
    const nodo = el("div", { class: "pantalla" },
      el("div", { class: "fila-entre" }, etiqueta("Tu gemelo digital"), chip("prototipo")),
      titulo("Gemelo digital"),
      persona,
      el("div", { class: "holo-caja holo-gemelo" }, holo.iframe),
      rotulo("Representación ilustrativa: AURA no capta la forma ni la postura del cuerpo.", "rotulo-destacado"),
      el("button", { class: "boton boton-sec ancho", type: "button", onclick: () => holo.enviar({ tipo: "escanear" }) }, "Escanear de nuevo"),
      tarjeta({}, el("p", { class: "etiqueta" }, "Módulos"), lista));
    let soltar = null;
    return {
      nodo,
      mostrar() {
        holo.alListo(() => { pintar(); if (escanear) holo.enviar({ tipo: "escanear" }); });
        soltar = escuchar((_, p) => {
          const mov = String(estado.muestra?.mov);
          if ("gemelo" in p || "alerta" in p || "fuente" in p || ("muestra" in p && mov !== lista.dataset.mov)) { lista.dataset.mov = mov; pintar(); }
        });
        pintar();
      },
      ocultar() { soltar?.(); holo.pausar(true); },
    };
  },
};
