// Noche — SOLO en el escenario simulado "bienestar_video" del video (no es una de las 9 pantallas del mockup):
// holograma de la sala en penumbra con la figura acostada y la franja 22:00–07:00 con los momentos de movimiento
// durante la noche. Todo es sintético (no viene del WiFi ni de K002); el video fija cada cuadro con cuadro(t).
import { crearHolograma } from "../components/holograma.js";
import { el, etiqueta, svg } from "../components/ui.js";

const NOCHE = { ini: 2, fin: 7, desde: 22, horas: 9 };   // s del video ↔ 22:00–07:00
const fraccion = (t) => Math.max(0, Math.min(1, (t - NOCHE.ini) / (NOCHE.fin - NOCHE.ini)));
function hora(t) {
  const m = Math.floor((NOCHE.desde + NOCHE.horas * fraccion(t)) * 60) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

export default {
  id: "noche",
  crear() {
    const holo = crearHolograma("senal", "Escena 3D de la sala de noche (escenario de demostración)");
    const reloj = el("p", { class: "tiempo-chico mono" }, "22:00");
    const franja = svg("svg", { class: "linea-svg", viewBox: "0 0 100 48", preserveAspectRatio: "none", role: "img",
      "aria-label": "Movimiento durante la noche, de 22:00 a 07:00" });
    const avance = svg("rect", { class: "noche-avance", x: 0, y: 19, width: 0, height: 10, rx: 5 });
    const cursor = svg("line", { class: "cursor-noche", x1: 0, x2: 0, y1: 4, y2: 44, "vector-effect": "non-scaling-stroke" });
    franja.append(svg("rect", { class: "pista", x: 0, y: 19, width: 100, height: 10, rx: 5 }), avance, cursor);
    let marcas = null;

    const nodo = el("div", { class: "pantalla" },
      etiqueta("Tu noche"),
      el("div", { class: "fila-entre" },
        el("span", { class: "sello-reproduccion" }, el("span", { class: "punto-reproduccion" }), "Escenario de demostración"), reloj),
      el("div", { class: "holo-caja holo-senal" }, holo.iframe, el("span", { class: "esquina-escena" }, "Esquema ilustrativo")),
      el("section", { class: "tarjeta linea-dia" },
        el("h2", { class: "titulo", "data-prueba": "resumen-noche" }, "Noche tranquila · 2 momentos de movimiento"),
        franja,
        el("div", { class: "escala" }, el("span", {}, "22:00"), el("span", {}, "07:00"))));

    return {
      nodo,
      mostrar() {},
      ocultar() { holo.pausar(true); },
      // video: escena y franja en el mismo t. false si la escena aún no está lista
      cuadro(t) {
        const E = holo.escena();
        if (!E?.noche) return false;
        E.fijar(t);
        if (!marcas) {
          marcas = E.noche.pulsos.map((c) => svg("rect", { class: "momento", x: fraccion(c) * 100 - 0.8, y: 12, width: 1.6, height: 24, rx: 0.8 }));
          franja.insertBefore(svg("g", {}), cursor).append(...marcas);
        }
        const q = fraccion(t) * 100;
        avance.setAttribute("width", q.toFixed(2));
        cursor.setAttribute("transform", `translate(${q.toFixed(2)} 0)`);
        E.noche.pulsos.forEach((c, k) => marcas[k].setAttribute("opacity", t >= c - 0.2 ? 1 : 0.2));
        reloj.textContent = hora(t);
        return true;
      },
    };
  },
};
