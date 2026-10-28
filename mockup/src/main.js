// main.js — arranque, navegación (rutas #/pantalla), barra inferior (el orbe es la pestaña central: no flota sobre
// el contenido) y sello "DEMO · reproducción" en la cabecera (el único sello DEMO de la app).
import "./tokens.css";
import "./base.css";
import { escuchar, estado } from "./estado.js";
import { iniciarFuente, irA, lanzarEscenario, tK002 } from "./data/fuente.js";
import { gsap, transicionPantalla } from "./motion.js";
import { ESCENARIO_VIDEO } from "./data/video.js";
import { mostrarBanner } from "./components/hoja.js";
import { abrirAclaraciones } from "./components/aclaraciones.js";
import { ICONOS, el } from "./components/ui.js";
import inicio from "./screens/inicio.js";
import hoy from "./screens/hoy.js";
import asistente from "./screens/asistente.js";
import gemelo from "./screens/gemelo.js";
import senal from "./screens/senal.js";
import alerta from "./screens/alerta.js";
import emergencia from "./screens/emergencia.js";
import teleconsulta from "./screens/teleconsulta.js";
import dispositivo from "./screens/dispositivo.js";
import noche from "./screens/noche.js";

// "noche" existe solo en el escenario simulado "bienestar_video" del video (no es una de las 9 pantallas)
const LISTA = [inicio, hoy, asistente, gemelo, senal, alerta, emergencia, teleconsulta, dispositivo, ...(ESCENARIO_VIDEO === "bienestar_video" ? [noche] : [])];
const PANTALLAS = Object.fromEntries(LISTA.map((p) => [p.id, p]));
const PESTANAS = [["hoy", "Hoy"], ["gemelo", "Gemelo"], ["asistente", "AURA"], ["senal", "Señal"], ["dispositivo", "Dispositivo"]];
const SIN_BARRA = new Set(["inicio", "emergencia"]);
const params = new URLSearchParams(location.search);

const contenedor = document.getElementById("pantalla");
const sello = document.getElementById("sello");
let actual = null, actualId = null;

// ---------- barra inferior ----------
const barra = document.getElementById("barra");
const pestanas = PESTANAS.map(([id, nombre]) => el("a", { class: `pestana${id === "asistente" ? " pestana-orbe" : ""}`, href: `#/${id}`,
  "data-pantalla": id, "aria-label": id === "asistente" ? "Asistente AURA" : null, html: `${ICONOS[id]}<span>${nombre}</span>` }));
barra.append(...pestanas);

// ---------- navegación ----------
export async function navegar(id, opciones = {}) {
  if (!PANTALLAS[id]) id = "hoy";
  const hash = `#/${id}`;
  if (location.hash !== hash) history[opciones.reemplazar ? "replaceState" : "pushState"](null, "", hash);
  if (id === actualId && !opciones.forzar) return;
  actual?.ocultar();
  actualId = id;
  const nueva = PANTALLAS[id].crear({ navegar, lanzarEscenario, escanear: opciones.escanear, quedarse: params.has("quedarse") });
  actual = nueva;
  document.body.dataset.pantalla = id;
  await transicionPantalla(() => {
    contenedor.replaceChildren(nueva.nodo);
    contenedor.scrollTop = 0;
    document.body.classList.toggle("sin-barra", SIN_BARRA.has(id));
    pestanas.forEach((p) => p.classList.toggle("activa", p.dataset.pantalla === id));
  }, contenedor);
  nueva.mostrar();
}
addEventListener("popstate", () => navegar(location.hash.replace("#/", "") || "hoy"));
addEventListener("hashchange", () => navegar(location.hash.replace("#/", "") || "hoy"));

// ---------- sello DEMO y reacciones a los datos ----------
function pintarSello() { sello.hidden = estado.fuente !== "demo"; }
if (ESCENARIO_VIDEO) sello.textContent = "DEMO · escenario";
document.getElementById("info").addEventListener("click", () => abrirAclaraciones());
escuchar((_, p) => {
  if ("fuente" in p) pintarSello();
  if ("escenario" in p && p.escenario === "respiracion" && !["alerta", "gemelo"].includes(actualId))
    mostrarBanner({ titulo: "Notamos un cambio en tus noches", texto: "Toca para verlo.", alTocar: () => navegar("alerta") });
  if ("alerta" in p && p.alerta?.tipo === "CAIDA" && actualId !== "emergencia") navegar("emergencia");
});
pintarSello();

// Interfaz para las pruebas (Playwright) y para window.AURA_HOLO de Angel
window.__aura = { estado, navegar, lanzarEscenario, irA, tK002, gsap, anillo: null };
if (ESCENARIO_VIDEO) Object.assign(window.__aura, {
  // Congela los bucles propios (GSAP en su inicio; animaciones CSS en pausa): desde aquí manda el video
  congelar() {
    gsap.globalTimeline.getChildren(true, true, false).forEach((tw) => { if (tw.repeat() === -1) tw.pause(0); });
    gsap.globalTimeline.pause();
  },
  // Un cuadro del video en el tiempo t (s): animaciones CSS (p. ej. el latido) en t y la pantalla actual dibuja t
  cuadro(t, extra = {}) {
    document.getAnimations().forEach((a) => { a.pause(); a.currentTime = t * 1000; });
    return actual?.cuadro?.(t, extra) ?? true;
  },
  objetivos: () => actual?.objetivos?.() ?? null,
});
window.AURA_HOLO = { setZona() {}, escanear: () => navegar("gemelo", { escanear: true }) };

// La primera pantalla espera la reproducción K002 (archivo local, ~140 kB); /ws se sigue buscando aparte
iniciarFuente().then(() => navegar(location.hash.replace("#/", "") || "inicio", { reemplazar: true }));
