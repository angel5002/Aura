// 1 · Hoy — estado de actividad (movimiento / sin movimiento), última actividad y acceso al asistente.
// Datos reales: vía local (si el servidor manda `movimiento`) o la reproducción de K002.
import { escuchar, estado } from "../estado.js";
import { MODULOS, PRESENCIA_QUIETA, estadoDe } from "../data/techo.js";
import { tK002 } from "../data/fuente.js";
import { contar } from "../motion.js";
import { crearSenal } from "../components/senal.js";
import { el, etiqueta, filaModulo, rotulo, tarjeta, titulo } from "../components/ui.js";

const hace = (s) => (s === null || s === undefined ? "sin movimiento aún" : s < 1.5 ? "ahora" : s < 60 ? `hace ${Math.round(s)} s` : `hace ${Math.floor(s / 60)} min`);

export default {
  id: "hoy",
  crear({ navegar }) {
    const estadoTxt = el("p", { class: "estado-grande", "data-prueba": "estado-mov" }, "—");
    const fuenteChip = el("span", { class: "chip chip-demo" }, "reproducción K002");
    const ultima = el("p", { class: "cuerpo" }, "—");
    const cruces = el("span", { class: "cifra", "data-valor": 0 }, "0");
    const senal = crearSenal({ alto: 84 });
    const bloqueK002 = el("div", { class: "bloque-k002" },
      el("div", { class: "fila-cifra" }, el("div", {}, cruces, el("span", { class: "cifra-de" }, " / 10")),
        el("p", { class: "rotulo" }, "cruces detectados en la prueba K002")),
      senal.lienzo,
      el("p", { class: "rotulo" }, el("span", { class: "leyenda leyenda-senal" }, "señal del detector (20 s)"), " · ",
        el("span", { class: "leyenda leyenda-umbral" }, "umbral de entrada"), " · ",
        el("span", { class: "leyenda leyenda-mov" }, "movimiento")));
    const sinDatos = el("p", { class: "cuerpo texto-2" }, "La reproducción de K002 no viene en esta copia de la app y no hay servidor: no hay datos que mostrar.");

    const mods = [...MODULOS.filter((m) => ["actividad", "caidas", "pulmones", "sueno"].includes(m.id)), PRESENCIA_QUIETA];
    const lista = el("ul", { class: "lista-modulos" }, mods.map((m) => filaModulo(m, m.zona ? estadoDe(m, estado.gemelo) : m.techo)));

    const nodo = el("div", { class: "pantalla" },
      etiqueta("Tu actividad de hoy"),
      titulo("Hoy"),
      tarjeta({ class: "tarjeta-estado" },
        el("div", { class: "fila-entre" }, el("p", { class: "etiqueta" }, "Estado ahora"), fuenteChip),
        estadoTxt, ultima, estado.k002 || estado.origenMov === "via_local" ? bloqueK002 : sinDatos),
      tarjeta({}, el("p", { class: "etiqueta" }, "Módulos"), lista),
      el("button", { class: "boton boton-principal ancho", type: "button", onclick: () => navegar("asistente") }, "Hablar con AURA"),
      rotulo("Movimiento: datos reales de la prueba K002 (27/10/2026, firmware 0.1.3), reproducidos en bucle. "
        + "En esa prueba se detectaron 10 de 10 cruces. Respiración, sueño y presencia quieta no se miden todavía."));

    let cuadro = 0;
    function pintar() {
      const m = estado.muestra;
      fuenteChip.textContent = estado.origenMov === "via_local" ? "vía local" : "reproducción K002";
      if (!m) return;
      estadoTxt.textContent = m.mov ? "En movimiento" : "Sin movimiento";
      estadoTxt.classList.toggle("en-movimiento", m.mov);
      ultima.textContent = `Última actividad: ${hace(m.mov ? 0 : m.ultimoMovHace)}`;
      if (m.detectados !== undefined) contar(cruces, m.detectados);
    }
    let soltar = null;
    return {
      nodo,
      mostrar() {
        soltar = escuchar((_, p) => { if ("muestra" in p || "fuente" in p) pintar(); });
        pintar();
        const bucle = () => { if (estado.origenMov === "reproduccion" && estado.k002) senal.dibujar(tK002()); cuadro = requestAnimationFrame(bucle); };
        cuadro = requestAnimationFrame(bucle);
      },
      ocultar() { soltar?.(); cancelAnimationFrame(cuadro); },
    };
  },
};
