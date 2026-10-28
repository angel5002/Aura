// 0 · Inicio — logotipo AURA con halo y "Señales que cuidan" (1,5 s) y luego Hoy.
import { gsap, reducido } from "../motion.js";
import { el } from "../components/ui.js";

export default {
  id: "inicio",
  crear({ navegar, quedarse }) {
    const marca = el("h1", { class: "marca" }, "AURA");
    const lema = el("p", { class: "lema" }, "Señales que cuidan");
    const nodo = el("div", { class: "pantalla-inicio" }, marca, lema,
      el("p", { class: "rotulo inicio-pie" }, "Prototipo de interfaz · Científica Hack X 2026"));
    let id = 0;
    return {
      nodo,
      mostrar() {
        if (!reducido()) gsap.from([marca, lema], { opacity: 0, y: 12, duration: 0.6, stagger: 0.2, ease: "power2.out" });
        if (!quedarse) id = setTimeout(() => navegar("hoy", { reemplazar: true }), 1500);
      },
      ocultar() { clearTimeout(id); },
    };
  },
};
