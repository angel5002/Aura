// 8 · Dispositivo y privacidad — tarjeta "Tu instalación" con una mini escena 3D (router y placa de la escena K002),
// tres filas ícono + palabra (sensor, red, cobertura), privacidad en tres íconos y el panel técnico oculto (F10:
// escenarios del modo demo, firmware, K002). Reales si hay servidor; en demo, los valores son de ejemplo (hoja ⓘ).
import { escuchar, estado } from "../estado.js";
import { ESCENARIOS } from "../data/escenarios.js";
import { irA } from "../data/fuente.js";
import { crearHolograma } from "../components/holograma.js";
import { el, etiqueta, tarjeta, titulo } from "../components/ui.js";

const CONEXION = { buscando: "buscando servidor AURA…", vivo: "conectado a servidor.py", sin_servidor: "sin servidor: modo demo" };
// Cobertura de ejemplo por escenario de demo: la de K002 (10 de 10 cruces) en los tres
const COBERTURA_DEMO = { normal: "buena", respiracion: "buena", caida: "buena" };
const ICONOS = {
  sensor: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/></svg>',
  red: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 9a14 14 0 0 1 19 0M5.5 12.5a9.5 9.5 0 0 1 13 0M8.5 16a5 5 0 0 1 7 0"/><circle cx="12" cy="19.5" r="1"/></svg>',
  cobertura: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 20v-4M10 20v-8M15 20v-12M20 20V4"/></svg>',
  camara: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7h3l2-3h8l2 3h3v12H3z"/><circle cx="12" cy="13" r="3.5"/><path d="M3 21 21 3"/></svg>',
  casa: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 11 12 4l8.5 7v9h-6v-6h-5v6h-6z"/></svg>',
  nombre: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4.5-6 8-6s7 2 8 6M3 3l18 18"/></svg>',
};

export default {
  id: "dispositivo",
  crear({ lanzarEscenario, navegar }) {
    const holo = crearHolograma("instalacion", "Tu instalación: router y placa");
    const valor = { sensor: el("span", { class: "valor" }), red: el("span", { class: "valor" }, "AURA-LAB"), cobertura: el("span", { class: "valor" }) };
    const fila = (id, nombre) => el("li", { class: "fila-icono", "data-fila": id }, el("span", { html: ICONOS[id] }), el("span", {}, nombre), valor[id]);
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
      const vivo = estado.conexion === "vivo";
      valor.sensor.textContent = vivo || estado.fuente === "demo" ? "conectado" : "sin conexión";
      valor.cobertura.textContent = estado.fuente === "demo" ? COBERTURA_DEMO[estado.escenario] ?? "buena" : "sin medir";
      const m = estado.muestra;
      const filas = [["Placa", "B · ESP32-C5"], ["Firmware", "0.1.3 · solo local"], ["Conexión", CONEXION[estado.conexion]],
        ["Prueba", "K002 · 27/10/2026"], ["Resultado", "10 de 10 cruces"], ["Alcance", "medido en una sola sala"],
        ["Fuente", estado.fuente], ["Movimiento", estado.origenMov === "via_local" ? "vía local" : "reproducción K002"],
        ["Escenario", estado.escenario], ["t de K002", m?.t != null ? `${m.t.toFixed(1)} s` : "—"],
        ["Muestras", m?.tasa ? `${Math.round(m.tasa)} /s` : "—"], ["Versión", `mockup ${__VERSION__}`]];
      tecnico.replaceChildren(...filas.flatMap(([k, v]) => [el("dt", {}, k), el("dd", { class: "tabular" }, v)]));
    }
    const nodo = el("div", { class: "pantalla" },
      etiqueta("Dispositivo"),
      tarjeta({},
        titulo("Tu instalación"),
        el("div", { class: "holo-caja holo-instalacion" }, holo.iframe),
        el("ul", { class: "filas-icono" }, fila("sensor", "Sensor"), fila("red", "Red"), fila("cobertura", "Cobertura"))),
      el("section", { class: "bloque" },
        el("p", { class: "subtitulo" }, "Privacidad"),
        el("ul", { class: "privacidad" },
          el("li", { html: `${ICONOS.camara}<span>Sin cámaras</span>` }),
          el("li", { html: `${ICONOS.casa}<span>Datos en casa</span>` }),
          el("li", { html: `${ICONOS.nombre}<span>Sin nombres</span>` }))),
      abrirPanel, panel);
    // La mini escena se pausa cuando no se ve (fuera de la vista al desplazar, o al salir de la pantalla)
    const visor = new IntersectionObserver(([e]) => holo.enviar({ tipo: "pausa", valor: !e.isIntersecting }));
    let soltar = null;
    return {
      nodo,
      mostrar() {
        pintar();
        holo.alListo(() => visor.observe(holo.iframe));
        soltar = escuchar((_, p) => { if ("conexion" in p || "fuente" in p || "escenario" in p || "muestra" in p) pintar(); });
      },
      ocultar() { soltar?.(); visor.disconnect(); holo.pausar(true); },
    };
  },
};
