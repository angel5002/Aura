// 4 · Señal — escena 3D de K002 (baldosas, ondas) y panel de señal. Señal y detección: DATOS REALES de K002.
import { escuchar, estado } from "../estado.js";
import { tK002 } from "../data/fuente.js";
import { muestraEn } from "../data/k002.js";
import { contar } from "../motion.js";
import { crearHolograma } from "../components/holograma.js";
import { crearSenal } from "../components/senal.js";
import { el, etiqueta, rotulo } from "../components/ui.js";

export default {
  id: "senal",
  crear() {
    const holo = crearHolograma("senal", "Escena 3D de la prueba K002");
    const estadoTxt = el("p", { class: "estado-senal", "data-prueba": "estado-senal" }, "—");
    const cruces = el("span", { class: "cifra", "data-valor": 0 }, "0");
    const tasa = el("span", { class: "tabular" }, "—");
    const tiempo = el("p", { class: "rotulo tabular" }, "—");
    const senal = crearSenal({ alto: 92 });
    const sinDatos = !estado.k002;

    const nodo = el("div", { class: "pantalla" },
      etiqueta("Señal WiFi · datos reales de K002"),
      el("div", { class: "fila-entre" },
        el("span", { class: "sello-reproduccion" }, el("span", { class: "punto-reproduccion" }), "Reproducción · K002 (27/10/2026)"), tiempo),
      el("div", { class: "holo-caja holo-senal" }, holo.iframe),
      rotulo("Ondas: ilustrativas · esquema, no a escala · Huawei–placa B: ~2 m (aprox., sin medir)."),
      sinDatos
        ? el("p", { class: "cuerpo texto-2" }, "Esta copia de la app no trae la reproducción de K002.")
        : el("section", { class: "tarjeta" },
          el("div", { class: "fila-entre" }, estadoTxt, el("div", { class: "derecha" }, el("div", {}, cruces, el("span", { class: "cifra-de" }, " / 10")),
            el("p", { class: "rotulo" }, "cruces detectados"))),
          el("p", { class: "cuerpo" }, "Tasa de CSI: ", tasa),
          senal.lienzo,
          el("p", { class: "rotulo" }, el("span", { class: "leyenda leyenda-senal" }, "señal del detector (últimos 20 s)"), " · ",
            el("span", { class: "leyenda leyenda-umbral" }, "umbral de entrada"))),
      rotulo("Señal y detección: datos reales de K002. La figura sigue el protocolo de la prueba; AURA no capta la forma ni la postura del cuerpo.", "rotulo-destacado"));

    let cuadro = 0, soltar = null, ultimoEnvio = 0, previo = {};
    function pintar(m) {                        // cada cuadro, con el mismo t que la escena; solo toca lo que cambia
      if (!m || m.t == null) return;
      const nuevo = { mov: m.mov, det: m.detectados, tasa: Math.round(m.tasa), t: m.t.toFixed(1) };
      if (nuevo.mov !== previo.mov) { estadoTxt.textContent = m.mov ? "MOVIMIENTO" : "quieto"; estadoTxt.classList.toggle("en-movimiento", m.mov); }
      if (nuevo.det !== previo.det) contar(cruces, m.detectados);
      if (nuevo.tasa !== previo.tasa) tasa.textContent = `${nuevo.tasa} /s`;
      if (nuevo.t !== previo.t) tiempo.textContent = `t = ${nuevo.t} s · tiempo real ×1`;
      previo = nuevo;
    }
    return {
      nodo,
      mostrar() {
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
    };
  },
};
