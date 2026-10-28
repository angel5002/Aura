// 2 · Asistente — orbe de voz, transcripción y respuesta. Guion de frases (F6) sin reconocimiento de voz.
import { FRASES, responder } from "../data/guion.js";
import { aparecerTexto } from "../motion.js";
import { crearOrbe } from "../components/orbe.js";
import { burbuja, el, etiqueta, subtitulo } from "../components/ui.js";
import { ESCENARIO_VIDEO } from "../data/video.js";

// Escenario simulado "bienestar_video" (solo el video): primero se pregunta a la persona; la familia solo recibe lo
// que ella elige. El video fija qué se ve con cuadro(t, {pregunta, opciones, eco, opciones2, elegido, confirma}).
function crearPregunta() {
  const orbe = crearOrbe();
  const pregunta = burbuja("¿Cómo te sientes estos días?");
  const opciones = el("div", { class: "opciones-video" },
    el("button", { class: "boton boton-sec", type: "button" }, "Bien"),
    el("button", { class: "boton boton-sec", type: "button", "data-prueba": "quiero-conversar" }, "Me gustaría conversar"));
  const eco = burbuja("Me gustaría conversar", "persona");
  const llamar = el("button", { class: "boton boton-sec ancho", type: "button", "data-prueba": "llamar-familia" }, "Llamar a mi familia");
  const opciones2 = el("div", { class: "opciones-video columna" }, llamar,
    el("button", { class: "boton boton-sec ancho", type: "button" }, "Línea 113, opción 5 (MINSA)"));
  const confirma = burbuja("Le aviso a tu familia que quieres conversar.");
  const nodo = el("div", { class: "pantalla pantalla-asistente" },
    etiqueta("Asistente"),
    el("div", { class: "orbe-zona" }, orbe.boton),
    el("div", { class: "conversacion" }, pregunta, opciones, eco, opciones2, confirma));
  const ver = (e, q, ocupa = q > 0) => { e.style.opacity = q; e.style.display = ocupa ? "" : "none"; };
  return {
    nodo, mostrar() {}, ocultar() { orbe.destruir(); },
    cuadro(t, { pregunta: q0 = 1, opciones: q1 = 1, eco: q2 = 0, opciones2: q3 = 0, elegido = false, confirma: q4 = 0 } = {}) {
      ver(pregunta, q0, true);
      ver(opciones, q2 > 0 ? 0 : q1, q2 === 0);       // al elegir, los botones dejan paso a la respuesta
      ver(eco, q2); ver(opciones2, q3); ver(confirma, q4);
      llamar.classList.toggle("elegido", elegido);
      return true;
    },
    // rectángulos de los botones que se tocan en el video (para el indicador de toque)
    objetivos: () => Object.fromEntries(["quiero-conversar", "llamar-familia"].map((id) => {
      const r = nodo.querySelector(`[data-prueba=${id}]`).getBoundingClientRect();
      return [id, { x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width }];
    })),
  };
}

// Voz de respuesta: solo voces del propio teléfono (localService), nada sale a internet
function hablar(texto) {
  if (!("speechSynthesis" in window)) return;
  const voz = speechSynthesis.getVoices().find((v) => v.localService && v.lang.startsWith("es"));
  if (!voz) return;
  const u = new SpeechSynthesisUtterance(texto);
  u.voice = voz; u.lang = voz.lang;
  speechSynthesis.cancel(); speechSynthesis.speak(u);
}

export default {
  id: "asistente",
  crear({ navegar }) {
    if (ESCENARIO_VIDEO === "bienestar_video") return crearPregunta();
    const conversacion = el("div", { class: "conversacion", "aria-live": "polite" },
      burbuja("Hola. ¿Te cuento cómo va tu día?"));
    const nota = el("p", { class: "rotulo centrado" });   // vacía al entrar (iteración 4); solo dice qué hace el orbe al tocarlo
    const orbe = crearOrbe({
      alTocar: async () => {
        nota.textContent = "Escuchando…";
        const modo = await orbe.escuchar(6);
        nota.textContent = modo === "microfono"
          ? "La onda sigue tu voz. Elige una pregunta."
          : "Onda de ejemplo: el micrófono necesita HTTPS. Elige una pregunta.";
      },
    });

    function preguntar(f) {
      orbe.detenerEscucha();
      conversacion.append(burbuja(f.texto, "persona"));
      const r = responder(f.id);
      const b = burbuja(r.texto);
      conversacion.append(b);
      aparecerTexto(b.firstChild);
      b.scrollIntoView({ block: "end", behavior: "smooth" });
      hablar(r.texto);
      const accion = {
        abrir_holograma: () => navegar("gemelo", { escanear: true }),
        abrir_teleconsulta: () => navegar("teleconsulta"),
        ofrecer_teleconsulta: () => conversacion.append(el("button", { class: "boton boton-sec", type: "button", onclick: () => navegar("teleconsulta") }, "Ver horarios")),
        abrir_alerta: () => conversacion.append(el("button", { class: "boton boton-sec", type: "button", onclick: () => navegar("alerta") }, "Ver el aviso")),
      }[r.accion];
      if (accion) setTimeout(accion, r.accion === "ofrecer_teleconsulta" || r.accion === "abrir_alerta" ? 0 : 1200);
    }

    const nodo = el("div", { class: "pantalla pantalla-asistente" },
      etiqueta("Asistente"),
      el("div", { class: "orbe-zona" }, orbe.boton),
      nota,
      conversacion,
      subtitulo("Prueba a preguntar"),
      el("div", { class: "frases" }, FRASES.map((f) => el("button", { class: "frase-prueba", type: "button", onclick: () => preguntar(f) }, f.texto))));
    return { nodo, mostrar() {}, ocultar() { orbe.destruir(); if ("speechSynthesis" in window) speechSynthesis.cancel(); } };
  },
};
