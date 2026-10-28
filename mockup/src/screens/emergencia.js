// 6 · Emergencia — escenario "caída": cuenta regresiva de 45 s, "Estoy bien" / "Necesito ayuda".
// Sin respuesta: "Familia avisada (simulación)", o Telegram solo si servidor.py está activo (lo envía él).
// Iteración 4: el anillo late (halo difuso + tres círculos tenues, cada 1,6 s; base.css).
import { escuchar, estado } from "../estado.js";
import { responderEmergencia } from "../data/fuente.js";
import { crearAnillo, crearCheck } from "../components/anillo.js";
import { el, etiqueta, rotulo } from "../components/ui.js";

export default {
  id: "emergencia",
  crear({ navegar, lanzarEscenario }) {
    const anillo = crearAnillo(196);
    const pregunta = el("div", { class: "emergencia-pregunta" },
      el("div", { class: "anillo-centro", "data-prueba": "latido" },
        el("div", { class: "halo-latido", "aria-hidden": "true" }),
        el("div", { class: "eco-latido", "aria-hidden": "true" }), el("div", { class: "eco-latido", "aria-hidden": "true" }), el("div", { class: "eco-latido", "aria-hidden": "true" }),
        anillo.caja, el("span", { class: "signo", "aria-hidden": "true" }, "!")),
      el("h1", { class: "titulo centrado" }, "¿Estás bien?"),
      el("p", { class: "cuerpo centrado texto-2" }, "Hubo un movimiento brusco y luego quietud en la sala."),
      el("button", { class: "boton boton-claro ancho", type: "button", "data-prueba": "estoy-bien", onclick: () => responderEmergencia("bien") }, "Estoy bien"),
      el("button", { class: "boton boton-peligro ancho", type: "button", "data-prueba": "necesito-ayuda", onclick: () => responderEmergencia("ayuda") }, "Necesito ayuda"),
      el("p", { class: "rotulo centrado" }, "Si no respondes, avisaremos a tu familia."));
    const resultado = el("div", { class: "emergencia-resultado", hidden: true });

    const nodo = el("div", { class: "pantalla pantalla-emergencia" },
      etiqueta("Posible caída · sala"),
      pregunta, resultado,
      rotulo("Ante una urgencia, llama al 106 (SAMU).", "centrado"));

    function mostrarResultado(texto, detalle) {
      anillo.detener();
      const check = crearCheck(88);
      resultado.replaceChildren(check.lienzo,
        el("h1", { class: "titulo centrado", "data-prueba": "resultado-emergencia" }, texto),
        el("p", { class: "cuerpo centrado texto-2" }, detalle),
        el("button", { class: "boton boton-sec ancho", type: "button", onclick: () => navegar("hoy") }, "Volver a Hoy"));
      pregunta.hidden = true; resultado.hidden = false;
      check.dibujar();
    }
    function aplicar() {
      const a = estado.alerta;
      if (a?.tipo === "CAIDA") {
        pregunta.hidden = false; resultado.hidden = true;
        const tw = anillo.tween();
        const resta = a.segundos - (performance.now() - a.desde) / 1000;
        if (!tw || Math.abs(tw.duration() - tw.time() - resta) > 2) window.__aura.anillo = anillo.iniciar(a.segundos, a.desde);
      } else if (a?.tipo === "FAMILIA_AVISADA" || a?.tipo === "AYUDA_SOLICITADA") {
        const sim = a.simulacion !== false;
        mostrarResultado(sim ? "Familia avisada (simulación)" : "Familia avisada",
          sim ? "Es un ejemplo: no se envió ningún mensaje."
              : "Avisamos a tu familia por Telegram.");
      } else if (a === null) {
        mostrarResultado("Alerta cancelada", "Qué bueno. No avisamos a nadie.");
      }
    }
    let soltar = null;
    return {
      nodo,
      mostrar() {
        if (estado.alerta?.tipo !== "CAIDA") lanzarEscenario("caida");
        aplicar();
        soltar = escuchar((_, p) => { if ("alerta" in p) aplicar(); });
      },
      ocultar() { soltar?.(); anillo.detener(); },
    };
  },
};
