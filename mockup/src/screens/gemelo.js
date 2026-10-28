// 3 · Gemelo digital — figura holográfica 3D con zonas de órganos dentro. Selector "Hoy" (datos reales) /
// "Ejemplo" (escenario de demostración). Datos reales: figura en cian tenue, zonas apagadas ("sin medición"); solo el halo
// responde al movimiento real. Escenario: los pulmones en ámbar ("Respiración más rápida que tu normal") o las
// caídas en rojo, con la pantalla rotulada como escenario. Tocar una zona abre su ficha (qué mide, estado, por qué).
// No se pinta ningún `texto` con cifras del gemelo (techo.js).
import { escuchar, estado } from "../estado.js";
import { abrirHoja } from "../components/hoja.js";
import { crearHolograma } from "../components/holograma.js";
import { ICONOS_ORGANO, chip, el, etiqueta, rotulo } from "../components/ui.js";

const AMBAR = "#e8b04a", ROJO = "#f07a6a";
// Ficha de dos líneas: qué mide · estado. El "por qué" de cada estado está en la hoja ⓘ de la cabecera.
const FICHAS = {
  actividad: { nombre: "Actividad", estado: "activo", estadoTxt: "Medido", mide: "Si hay movimiento en la sala." },
  caidas: { nombre: "Caídas", estado: "prototipo", estadoTxt: "En prueba", mide: "Un movimiento brusco seguido de quietud." },
  pulmones: { nombre: "Respiración", estado: "en_investigacion", estadoTxt: "Aún no se mide", mide: "La respiración en reposo." },
  cabeza: { nombre: "Sueño y ánimo", estado: "en_investigacion", estadoTxt: "Aún no se mide", mide: "Horarios de sueño, despertares y rutina." },
  sueno: { nombre: "Sueño", estado: "en_investigacion", estadoTxt: "Aún no se mide", mide: "Horarios de sueño y despertares." },
  corazon: { nombre: "Corazón", estado: "no_medido", estadoTxt: "No se mide", mide: "El ritmo del corazón." },
  animo: { nombre: "Ánimo", estado: "no_medido", estadoTxt: "No se mide", mide: "Tu rutina y respuestas breves." },
};
const ESCENARIOS = {
  respiracion: { zona: "pulmones", color: AMBAR, clase: "", titulo: "Respiración más rápida de lo habitual" },
  caida: { zona: "caidas", color: ROJO, clase: "danger", titulo: "Posible caída" },
};

export default {
  id: "gemelo",
  crear({ escanear }) {
    let modo = ["respiracion", "caida"].includes(estado.escenario) ? "escenario" : "real";
    let esc = estado.escenario === "caida" ? "caida" : "respiracion";

    function ficha(id) {
      const f = FICHAS[id];
      abrirHoja(el("div", { class: "hoja-cuerpo", "data-prueba": "hoja-organo" },
        el("h2", { class: "titulo" }, f.nombre),
        el("dl", { class: "hoja-datos" },
          el("dt", {}, "Qué mide"), el("dd", {}, f.mide),
          el("dt", {}, "Estado"), el("dd", {}, chip(f.estado, f.estadoTxt)))));
    }

    const holo = crearHolograma("gemelo", "Gemelo digital ilustrativo", { alTocarZona: ficha });
    const sel = el("div", { class: "selector", role: "group", "aria-label": "Qué mostrar" });
    const selEsc = el("div", { class: "selector selector-chico", role: "group", "aria-label": "Escenario" });
    const nota = el("div", { "aria-live": "polite" });
    const boton = (txt, activo, f, prueba) => el("button", { type: "button", "aria-pressed": String(activo), "data-prueba": prueba, onclick: f }, txt);

    function zonas() {
      const z = {};
      if (modo === "escenario") z[ESCENARIOS[esc].zona] = { color: ESCENARIOS[esc].color, nivel: 1, late: true };   // late con fuerza (iteración 4)
      else if (estado.alerta?.tipo === "CAIDA") z.caidas = { color: ROJO, nivel: 1 };
      holo.enviar({ tipo: "zonas", zonas: z });
      holo.enviar({ tipo: "actividad", mov: modo === "real" && !!estado.muestra?.mov });
    }
    const textoReal = () => { const m = estado.muestra; return m ? (m.mov ? "Movimiento ahora" : "Sin movimiento ahora") : "Sin datos de movimiento"; };
    function pintar() {
      sel.replaceChildren(
        boton("Hoy", modo === "real", () => { modo = "real"; pintar(); }, "modo-real"),
        boton("Ejemplo", modo === "escenario", () => { modo = "escenario"; pintar(); }, "modo-escenario"));
      selEsc.hidden = modo !== "escenario";
      selEsc.replaceChildren(
        boton("Respiración", esc === "respiracion", () => { esc = "respiracion"; pintar(); }, "esc-respiracion"),
        boton("Caída", esc === "caida", () => { esc = "caida"; pintar(); }, "esc-caida"));
      if (modo === "escenario") {
        const e = ESCENARIOS[esc];
        nota.replaceChildren(el("p", { class: `nota-escenario ${e.clase}`, "data-prueba": "nota-escenario" }, el("strong", {}, e.titulo)));
      } else nota.replaceChildren(el("p", { class: "rotulo centrado" }, textoReal()));
      zonas();
    }

    const proximos = ["pulmones", "sueno", "corazon", "animo"].map((id) => el("button", { type: "button", "aria-label": FICHAS[id].nombre, "data-modulo": id, onclick: () => ficha(id) },
      el("span", { class: "icono-organo", html: ICONOS_ORGANO[id] })));
    const nodo = el("div", { class: "pantalla" },
      etiqueta("Tu gemelo digital"),
      sel, selEsc,
      el("div", { class: "holo-caja holo-gemelo" }, holo.iframe),
      nota,
      el("section", { class: "tarjeta" },
        el("ul", { class: "grupos" },
          el("li", { class: "grupo" }, el("span", { class: "grupo-nombre" }, "Medido hoy"),
            el("span", { class: "grupo-items" }, el("button", { type: "button", "data-modulo": "actividad", onclick: () => ficha("actividad") }, el("span", { class: "punto chip-activo" }), "Actividad"))),
          el("li", { class: "grupo" }, el("span", { class: "grupo-nombre" }, "En prueba"),
            el("span", { class: "grupo-items" }, el("button", { type: "button", "data-modulo": "caidas", onclick: () => ficha("caidas") }, el("span", { class: "punto chip-prototipo" }), "Caídas"))),
          el("li", { class: "grupo" }, el("span", { class: "grupo-nombre" }, "Próximamente"), el("span", { class: "grupo-items" }, proximos)))),
      rotulo("Toca una zona para ver más.", "centrado"));

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
