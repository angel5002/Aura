// 8 · Dispositivo y privacidad — placa, red AURA-LAB, prueba de cobertura, privacidad y panel técnico oculto
// (F10: escenarios del modo demo). Reales si hay servidor; si no, lo conocido del proyecto, rotulado.
import { escuchar, estado } from "../estado.js";
import { ESCENARIOS } from "../data/escenarios.js";
import { irA } from "../data/fuente.js";
import { chip, el, etiqueta, rotulo, tarjeta, titulo } from "../components/ui.js";

const CONEXION = { buscando: "buscando servidor AURA…", vivo: "conectado a servidor.py", sin_servidor: "sin servidor: modo demo" };

export default {
  id: "dispositivo",
  crear({ lanzarEscenario, navegar }) {
    const conexion = el("span", { class: "tabular" });
    const tecnico = el("dl", { class: "datos-tecnicos" });
    const panel = el("div", { class: "panel-tecnico", hidden: true, "data-prueba": "panel-tecnico" },
      el("p", { class: "subtitulo" }, "Panel técnico (equipo)"), tecnico,
      el("p", { class: "subtitulo" }, "Escenarios del modo demo"),
      el("div", { class: "escenarios" }, ESCENARIOS.map((e) => el("button", {
        class: "boton boton-sec", type: "button", "data-escenario": e.id,
        onclick: () => { lanzarEscenario(e.id); if (e.id === "caida") navegar("emergencia"); },
      }, e.nombre))),
      el("button", { class: "boton boton-sec ancho", type: "button", onclick: () => irA(24) }, "Reiniciar la reproducción K002"));
    const abrirPanel = el("button", { class: "enlace", type: "button", "data-prueba": "abrir-panel",
      onclick: () => { panel.hidden = !panel.hidden; abrirPanel.textContent = panel.hidden ? "Mostrar panel técnico" : "Ocultar panel técnico"; } },
      "Mostrar panel técnico");

    function pintar() {
      conexion.textContent = CONEXION[estado.conexion];
      const m = estado.muestra;
      const filas = [["Fuente", estado.fuente], ["Movimiento", estado.origenMov === "via_local" ? "vía local" : "reproducción K002"],
        ["Escenario", estado.escenario], ["t de K002", m?.t != null ? `${m.t.toFixed(1)} s` : "—"],
        ["Tasa de CSI", m?.tasa ? `${Math.round(m.tasa)} /s` : "—"]];
      tecnico.replaceChildren(...filas.flatMap(([k, v]) => [el("dt", {}, k), el("dd", { class: "tabular" }, v)]));
    }
    const nodo = el("div", { class: "pantalla" },
      etiqueta("Dispositivo y privacidad"),
      titulo("Tu sensor AURA"),
      tarjeta({},
        el("p", { class: "cuerpo fuerte" }, "Placa B · ESP32-C5"),
        el("p", { class: "cuerpo texto-2" }, "Firmware 0.1.3 · modo solo local · conexión: ", conexion),
        el("p", { class: "cuerpo fuerte separado" }, "Red AURA-LAB"),
        el("p", { class: "cuerpo texto-2" }, "Router propio de 2,4 GHz, sin internet. Los datos no salen de la casa."),
        el("div", { class: "fila-entre separado" }, el("p", { class: "cuerpo fuerte" }, "Prueba de cobertura"), chip("activo")),
        el("p", { class: "cuerpo texto-2" }, "K002 (27/10/2026): 10 de 10 cruces detectados, en una prueba."),
        el("p", { class: "rotulo" }, "Medido en una sola sala; la prueba en cada casa queda pendiente.")),
      el("section", { class: "bloque" },
        el("p", { class: "subtitulo" }, "Privacidad"),
        el("ul", { class: "lista-privacidad" },
          el("li", {}, "Sin cámaras y sin nada puesto en el cuerpo."),
          el("li", {}, "AURA no capta la forma ni la postura del cuerpo."),
          el("li", {}, "Los datos se quedan en casa; la nube está en pausa."),
          el("li", {}, "Ningún dato lleva tu nombre: se usan códigos."))),
      abrirPanel, panel,
      rotulo(`AURA mockup ${__VERSION__} · prototipo de interfaz`));
    let soltar = null;
    return {
      nodo,
      mostrar() { pintar(); soltar = escuchar((_, p) => { if ("conexion" in p || "fuente" in p || "escenario" in p || "muestra" in p) pintar(); }); },
      ocultar() { soltar?.(); },
    };
  },
};
