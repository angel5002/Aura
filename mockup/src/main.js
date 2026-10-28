// main.js — arranque, navegación (rutas #/pantalla), barra inferior, orbe flotante y sello "DEMO · reproducción".
import "./tokens.css";
import "./base.css";
import { escuchar, estado } from "./estado.js";
import { iniciarFuente, irA, lanzarEscenario, tK002 } from "./data/fuente.js";
import { gsap, transicionPantalla } from "./motion.js";
import { crearOrbe } from "./components/orbe.js";
import { mostrarBanner } from "./components/hoja.js";
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

const PANTALLAS = Object.fromEntries([inicio, hoy, asistente, gemelo, senal, alerta, emergencia, teleconsulta, dispositivo].map((p) => [p.id, p]));
const PESTANAS = [["hoy", "Hoy"], ["gemelo", "Gemelo"], ["senal", "Señal"], ["dispositivo", "Dispositivo"]];
const SIN_BARRA = new Set(["inicio", "emergencia"]);
const params = new URLSearchParams(location.search);

const contenedor = document.getElementById("pantalla");
const sello = document.getElementById("sello");
let actual = null, actualId = null;

// ---------- barra inferior y orbe flotante ----------
const barra = document.getElementById("barra");
const pestanas = PESTANAS.map(([id, nombre]) => el("a", { class: "pestana", href: `#/${id}`, "data-pantalla": id, html: `${ICONOS[id]}<span>${nombre}</span>` }));
barra.append(pestanas[0], pestanas[1], el("span", { class: "hueco-orbe" }), pestanas[2], pestanas[3]);
const orbe = crearOrbe({ alTocar: () => navegar("asistente") });
document.getElementById("orbe").append(orbe.boton);

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
escuchar((_, p) => {
  if ("fuente" in p) pintarSello();
  if ("escenario" in p && p.escenario === "respiracion" && actualId !== "alerta")
    mostrarBanner({ titulo: "Cambio detectado · DEMO", texto: "Toca para ver el escenario.", alTocar: () => navegar("alerta") });
  if ("alerta" in p && p.alerta?.tipo === "CAIDA" && actualId !== "emergencia") navegar("emergencia");
});
pintarSello();

// Interfaz para las pruebas (Playwright) y para window.AURA_HOLO de Angel
window.__aura = { estado, navegar, lanzarEscenario, irA, tK002, gsap, anillo: null };
window.AURA_HOLO = { setZona() {}, escanear: () => navegar("gemelo", { escanear: true }) };

// La primera pantalla espera la reproducción K002 (archivo local, ~140 kB); /ws se sigue buscando aparte
iniciarFuente().then(() => navegar(location.hash.replace("#/", "") || "inicio", { reemplazar: true }));
