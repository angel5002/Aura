// 4 · Señal — escena 3D de K002 (baldosas, ondas) y panel de señal. Señal y detección: DATOS REALES de K002.
import { escuchar, estado } from "../estado.js";
import { tK002 } from "../data/fuente.js";
import { muestraEn } from "../data/k002.js";
import { contar } from "../motion.js";
import { crearHolograma } from "../components/holograma.js";
import { crearSenal } from "../components/senal.js";
import { el, etiqueta } from "../components/ui.js";
import { ESCENARIO_VIDEO } from "../data/video.js";

export default {
  id: "senal",
  crear() {
    const holo = crearHolograma("senal", "Escena 3D de la prueba K002");
    const estadoTxt = el("p", { class: "estado-senal", "data-prueba": "estado-senal" }, "—");
    const cruces = el("span", { class: "cifra", "data-valor": 0 }, "0");
    const tiempo = el("p", { class: "tiempo-chico mono" }, "—");
    // Escenario del video: señal sintética del holograma (muestreada a 10 Hz), sin cruces ni datos de K002
    const ventanaEscenario = (t, s) => {
      const f = holo.escena()?.senal;
      if (!f) return null;
      const v = { t0: t - s, t: [], suave: [], entrada: [], mov: [], cruces: [] };
      for (let tt = Math.max(0, Math.ceil((t - s) * 10) / 10); tt <= t + 1e-9; tt += 0.1) {
        const m = f(tt); v.t.push(tt); v.suave.push(m.suave); v.entrada.push(m.entrada); v.mov.push(m.mov);
      }
      return v;
    };
    const senal = ESCENARIO_VIDEO ? crearSenal({ alto: 92, conCruces: false, datos: ventanaEscenario }) : crearSenal({ alto: 92 });
    const sinDatos = !estado.k002 && !ESCENARIO_VIDEO;

    const nodo = el("div", { class: "pantalla" },
      etiqueta("Señal WiFi"),
      el("div", { class: "fila-entre" },
        el("span", { class: "sello-reproduccion" }, el("span", { class: "punto-reproduccion" }), ESCENARIO_VIDEO ? "Escenario de demostración" : "Prueba K002 · 27/10"), tiempo),
      el("div", { class: "holo-caja holo-senal" }, holo.iframe, el("span", { class: "esquina-escena" }, "Esquema ilustrativo")),
      sinDatos
        ? el("p", { class: "cuerpo texto-2" }, "Esta copia de la app no trae la reproducción de K002.")
        : el("section", { class: "tarjeta" },
          el("div", { class: "fila-entre" }, estadoTxt, ESCENARIO_VIDEO ? el("p", { class: "rotulo derecha" }, "señal simulada")
            : el("div", { class: "derecha" }, el("div", {}, cruces, el("span", { class: "cifra-de" }, " / 10")),
              el("p", { class: "rotulo" }, "cruces detectados"))),
          senal.lienzo,
          el("p", { class: "rotulo" }, el("span", { class: "leyenda leyenda-senal" }, "señal, últimos 20 s"), " · ",
            el("span", { class: "leyenda leyenda-umbral" }, "umbral"))));

    let cuadro = 0, soltar = null, ultimoEnvio = 0, previo = {};
    function pintar(m) {                        // cada cuadro, con el mismo t que la escena; solo toca lo que cambia
      if (!m || m.t == null) return;
      const nuevo = { mov: m.mov, det: m.detectados, t: m.t.toFixed(1) };   // muestras/s: en el panel técnico (iteración 4)
      if (nuevo.mov !== previo.mov) { estadoTxt.textContent = m.mov ? "MOVIMIENTO" : "quieto"; estadoTxt.classList.toggle("en-movimiento", m.mov); }
      if (nuevo.det !== previo.det && !ESCENARIO_VIDEO) contar(cruces, m.detectados);
      if (nuevo.t !== previo.t) { const seg = Math.floor(m.t); tiempo.textContent = `${Math.floor(seg / 60)}:${String(seg % 60).padStart(2, "0")}`; }
      previo = nuevo;
    }
    return {
      nodo,
      mostrar() {
        if (ESCENARIO_VIDEO) return;           // el video dibuja cada cuadro con cuadro(t)
        soltar = escuchar((_, p) => { if ("fuente" in p) pintar(muestraEn(tK002())); });
        pintar(muestraEn(tK002()));
        holo.alListo(() => holo.enviar({ tipo: "t", t: tK002() }));
        const bucle = (ahora) => {
          const t = tK002();
          if (!sinDatos) { senal.dibujar(t); pintar(muestraEn(t)); }
          if (ahora - ultimoEnvio > 500) { ultimoEnvio = ahora; holo.enviar({ tipo: "t", t }); }
          cuadro = requestAnimationFrame(bucle);
        };
        cuadro = requestAnimationFrame(bucle);
      },
      ocultar() { soltar?.(); cancelAnimationFrame(cuadro); holo.pausar(true); },
      // video: escena, panel y gráfico en el mismo t (sincrónico). false si la escena aún no está lista
      cuadro(t) {
        const E = holo.escena();
        if (!E?.senal) return false;
        E.fijar(t);
        const m = E.senal(t);
        pintar({ t, mov: m.mov, detectados: 0 });
        senal.dibujar(t);
        return true;
      },
    };
  },
};
