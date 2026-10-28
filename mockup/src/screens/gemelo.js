// 3 · Gemelo digital — figura holográfica 3D con zonas de órganos dentro. Selector "Hoy (datos reales)" /
// "Escenario de demostración". Datos reales: figura en cian tenue, zonas apagadas ("sin medición"); solo el halo
// responde al movimiento real. Escenario: los pulmones en ámbar ("Respiración más rápida que tu normal") o las
// caídas en rojo, con la pantalla rotulada como escenario. Tocar una zona abre su ficha (qué mide, estado, por qué).
// No se pinta ningún `texto` con cifras del gemelo (techo.js).
import { escuchar, estado } from "../estado.js";
import { abrirHoja } from "../components/hoja.js";
import { crearHolograma } from "../components/holograma.js";
import { ICONOS_ORGANO, chip, el, etiqueta, rotulo } from "../components/ui.js";

const AMBAR = "#e8b04a", ROJO = "#f07a6a";
const FICHAS = {
  actividad: { nombre: "Actividad en la sala", estado: "activo", estadoTxt: "Medido · datos reales",
    mide: "Si hay movimiento en la sala, a partir de cómo cambia la señal WiFi entre el router y la placa.",
    porque: "Demostrado en la prueba K002 (27/10/2026): 10 de 10 cruces detectados. Es una sola prueba, en una sala." },
  caidas: { nombre: "Caídas", estado: "prototipo", estadoTxt: "En prueba",
    mide: "Un movimiento brusco seguido de inmovilidad.",
    porque: "Todavía no está validado. Por eso AURA siempre pregunta antes de avisar a alguien." },
  pulmones: { nombre: "Respiración", estado: "en_investigacion", estadoTxt: "Próximamente · sin medición",
    mide: "La respiración en reposo, cuando la persona está quieta.",
    porque: "Está en investigación: el detector propio todavía no está probado. AURA no muestra cifras de respiración." },
  cabeza: { nombre: "Sueño y ánimo", estado: "en_investigacion", estadoTxt: "Próximamente · sin medición",
    mide: "Sueño: horarios y despertares. Ánimo: rutina y preguntas breves.",
    porque: "El sueño depende de detectar a una persona quieta, que hoy no es fiable. El ánimo está fuera del alcance del sensor." },
  sueno: { nombre: "Sueño", estado: "en_investigacion", estadoTxt: "Próximamente · sin medición",
    mide: "Horarios de sueño y despertares.",
    porque: "Depende de detectar a una persona quieta, que hoy no es fiable." },
  corazon: { nombre: "Corazón", estado: "no_medido", estadoTxt: "No medido",
    mide: "El ritmo del corazón.",
    porque: "Está fuera del alcance del sensor WiFi actual." },
  animo: { nombre: "Ánimo", estado: "no_medido", estadoTxt: "No medido",
    mide: "Rutina y respuestas a preguntas breves.",
    porque: "Está fuera del alcance del sensor WiFi actual." },
};
const ESCENARIOS = {
  respiracion: { zona: "pulmones", color: AMBAR, clase: "", titulo: "Respiración más rápida que tu normal",
    nota: "Así se vería un cambio. La respiración todavía no se mide." },
  caida: { zona: "caidas", color: ROJO, clase: "danger", titulo: "Posible caída",
    nota: "Movimiento brusco seguido de inmovilidad. Caídas está en prueba." },
};

export default {
  id: "gemelo",
  crear({ escanear }) {
    let modo = ["respiracion", "caida"].includes(estado.escenario) ? "escenario" : "real";
    let esc = estado.escenario === "caida" ? "caida" : "respiracion";

    function ficha(id) {
      const f = FICHAS[id];
      const e = modo === "escenario" && ESCENARIOS[esc].zona === id ? ESCENARIOS[esc] : null;
      abrirHoja(el("div", { class: "hoja-cuerpo", "data-prueba": "hoja-organo" },
        el("h2", { class: "titulo" }, f.nombre),
        e ? el("p", { class: `nota-escenario ${e.clase}` }, el("strong", {}, e.titulo), el("span", { class: "rotulo" }, `Escenario de demostración. ${e.nota}`)) : null,
        el("dl", { class: "hoja-datos" },
          el("dt", {}, "Qué mide"), el("dd", {}, f.mide),
          el("dt", {}, "Estado"), el("dd", {}, chip(f.estado, f.estadoTxt)),
          el("dt", {}, "Por qué"), el("dd", {}, f.porque))));
    }

    const holo = crearHolograma("gemelo", "Gemelo digital ilustrativo", { alTocarZona: ficha });
    const sel = el("div", { class: "selector", role: "group", "aria-label": "Qué mostrar" });
    const selEsc = el("div", { class: "selector selector-chico", role: "group", "aria-label": "Escenario" });
    const rotuloEsc = el("p", { class: "rotulo-escenario", "data-prueba": "rotulo-escenario" }, "Escenario de demostración: no son datos de una persona.");
    const nota = el("div", { "aria-live": "polite" });
    const boton = (txt, activo, f, prueba) => el("button", { type: "button", "aria-pressed": String(activo), "data-prueba": prueba, onclick: f }, txt);

    function zonas() {
      const z = {};
      if (modo === "escenario") z[ESCENARIOS[esc].zona] = { color: ESCENARIOS[esc].color, nivel: 1 };
      else if (estado.alerta?.tipo === "CAIDA") z.caidas = { color: ROJO, nivel: 1 };
      holo.enviar({ tipo: "zonas", zonas: z });
      holo.enviar({ tipo: "actividad", mov: modo === "real" && !!estado.muestra?.mov });
    }
    const textoReal = () => {
      const m = estado.muestra;
      return (m ? (m.mov ? "Hay movimiento ahora: el halo lo muestra." : "Sin movimiento ahora.") : "Sin datos de movimiento.")
        + (estado.origenMov === "via_local" ? " Vía local." : " Prueba K002, reproducida.");
    };
    function pintar() {
      sel.replaceChildren(
        boton("Hoy (datos reales)", modo === "real", () => { modo = "real"; pintar(); }, "modo-real"),
        boton("Escenario de demostración", modo === "escenario", () => { modo = "escenario"; pintar(); }, "modo-escenario"));
      selEsc.hidden = rotuloEsc.hidden = modo !== "escenario";
      selEsc.replaceChildren(
        boton("Respiración", esc === "respiracion", () => { esc = "respiracion"; pintar(); }, "esc-respiracion"),
        boton("Caída", esc === "caida", () => { esc = "caida"; pintar(); }, "esc-caida"));
      if (modo === "escenario") {
        const e = ESCENARIOS[esc];
        nota.replaceChildren(el("p", { class: `nota-escenario ${e.clase}`, "data-prueba": "nota-escenario" }, el("strong", {}, e.titulo), el("span", { class: "rotulo" }, e.nota)));
      } else nota.replaceChildren(el("p", { class: "rotulo centrado" }, textoReal()));
      zonas();
    }

    const proximos = ["pulmones", "sueno", "corazon", "animo"].map((id) => el("button", { type: "button", "aria-label": FICHAS[id].nombre, "data-modulo": id, onclick: () => ficha(id) },
      el("span", { class: "icono-organo", html: ICONOS_ORGANO[id] })));
    const nodo = el("div", { class: "pantalla" },
      etiqueta("Tu gemelo digital"),
      sel, selEsc, rotuloEsc,
      el("div", { class: "holo-caja holo-gemelo" }, holo.iframe),
      nota,
      el("section", { class: "tarjeta" },
        el("ul", { class: "grupos" },
          el("li", { class: "grupo" }, el("span", { class: "grupo-nombre" }, "Medido hoy"),
            el("span", { class: "grupo-items" }, el("button", { type: "button", "data-modulo": "actividad", onclick: () => ficha("actividad") }, el("span", { class: "punto chip-activo" }), "Actividad"))),
          el("li", { class: "grupo" }, el("span", { class: "grupo-nombre" }, "En prueba"),
            el("span", { class: "grupo-items" }, el("button", { type: "button", "data-modulo": "caidas", onclick: () => ficha("caidas") }, el("span", { class: "punto chip-prototipo" }), "Caídas"))),
          el("li", { class: "grupo" }, el("span", { class: "grupo-nombre" }, "Próximamente"), el("span", { class: "grupo-items" }, proximos)))),
      rotulo("Representación ilustrativa: AURA no capta la forma ni la postura del cuerpo. Toca una zona de la figura para ver qué mide.", "rotulo-destacado"));

    let soltar = null, movPrevio = null;
    return {
      nodo,
      mostrar() {
        pintar();
        holo.alListo(() => { zonas(); if (escanear) holo.enviar({ tipo: "escanear" }); });
        soltar = escuchar((_, p) => {
          if ("alerta" in p) zonas();
          if (!("muestra" in p) || modo !== "real") return;
          const mov = !!estado.muestra?.mov;
          if (mov !== movPrevio) { movPrevio = mov; zonas(); }
          const t = textoReal();
          if (nota.firstChild && nota.firstChild.textContent !== t) nota.firstChild.textContent = t;
        });
      },
      ocultar() { soltar?.(); holo.pausar(true); },
    };
  },
};
