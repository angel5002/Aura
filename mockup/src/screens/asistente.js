// 2 · Asistente — orbe de voz, transcripción y respuesta. Guion de frases (F6) sin reconocimiento de voz.
import { estado } from "../estado.js";
import { FRASES, responder } from "../data/guion.js";
import { aparecerTexto } from "../motion.js";
import { crearOrbe } from "../components/orbe.js";
import { burbuja, chip, el, etiqueta, rotulo, subtitulo } from "../components/ui.js";

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
    const conversacion = el("div", { class: "conversacion", "aria-live": "polite" },
      burbuja("Hola. Puedo contarte el movimiento de hoy, mostrarte tu gemelo digital o ayudarte a agendar con tu médico."));
    const nota = el("p", { class: "rotulo centrado" }, "Toca el orbe para probar el micrófono, o elige una frase.");
    const orbe = crearOrbe({
      alTocar: async () => {
        nota.textContent = "Escuchando…";
        const modo = await orbe.escuchar(6);
        nota.textContent = modo === "microfono"
          ? "La onda sigue tu micrófono. El mockup no transcribe la voz: elige una frase."
          : "Onda de demostración: el micrófono necesita HTTPS o localhost. Elige una frase.";
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
        ofrecer_teleconsulta: () => conversacion.append(el("button", { class: "boton boton-sec", type: "button", onclick: () => navegar("teleconsulta") }, "Ver horarios (simulación)")),
        abrir_alerta: () => conversacion.append(el("button", { class: "boton boton-sec", type: "button", onclick: () => navegar("alerta") }, "Ver el aviso")),
      }[r.accion];
      if (accion) setTimeout(accion, r.accion === "ofrecer_teleconsulta" || r.accion === "abrir_alerta" ? 0 : 1200);
    }

    const nodo = el("div", { class: "pantalla pantalla-asistente" },
      el("div", { class: "fila-entre" }, etiqueta("Asistente"), chip("prototipo")),
      el("div", { class: "orbe-zona" }, orbe.boton),
      nota,
      conversacion,
      subtitulo("Frases de prueba"),
      el("div", { class: "frases" }, FRASES.map((f) => el("button", { class: "frase-prueba", type: "button", onclick: () => preguntar(f) }, f.texto))),
      rotulo("Guion de demostración: AURA responde con reglas fijas, nunca recomienda medicamentos y deriva a tu médico. "
        + `Fuente del movimiento: ${estado.origenMov === "via_local" ? "vía local" : "reproducción K002"}.`));
    return { nodo, mostrar() {}, ocultar() { orbe.destruir(); if ("speechSynthesis" in window) speechSynthesis.cancel(); } };
  },
};
