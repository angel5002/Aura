// preparar_datos.mjs — arma mockup/publico/ (fuera de git), que Vite copia tal cual dentro de app/.
//
//   node scripts/preparar_datos.mjs
//
// 1. Reproducción K002: lee datos/procesados/video_K002/escena/datos_k002.js (generado por
//    analisis/escena_k002.py a partir de datos/crudos/K002_local.csv) y escribe
//    datos/procesados/mockup/k002_reproduccion.json. Son datos de una prueba en casa: fuera de git.
// 2. Holograma: copia mockup/holograma/index.html, three r128 y sus módulos de ejemplo (desde node_modules,
//    three@0.128.0) y el modelo CC0 de Quaternius, para que la escena abra sin internet.
// Si falta la reproducción o el modelo, avisa y sigue: la app muestra "no disponible" en vez de inventar datos.

import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const MOCKUP = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const RAIZ = resolve(MOCKUP, "..");
const ESCENA = join(RAIZ, "datos", "procesados", "video_K002", "escena");
const SALIDA_DATOS = join(RAIZ, "datos", "procesados", "mockup");
const PUBLICO = join(MOCKUP, "publico");
const THREE = join(MOCKUP, "node_modules", "three");
const MODELO = join(ESCENA, "modelos", "quaternius_animated_human.glb");
const MODELO_SHA256 = "ce4d543e82e455d5a1253798c9759f12b9eec74929ddbca464447eeaa3a42c5d";  // = analisis/escena_k002.py

const VENDOR = [
  ["build/three.min.js", "three.min.js"],
  ["examples/js/shaders/CopyShader.js", "CopyShader.js"],
  ["examples/js/shaders/LuminosityHighPassShader.js", "LuminosityHighPassShader.js"],
  ["examples/js/postprocessing/EffectComposer.js", "EffectComposer.js"],
  ["examples/js/postprocessing/RenderPass.js", "RenderPass.js"],
  ["examples/js/postprocessing/ShaderPass.js", "ShaderPass.js"],
  ["examples/js/postprocessing/UnrealBloomPass.js", "UnrealBloomPass.js"],
  ["examples/js/loaders/GLTFLoader.js", "GLTFLoader.js"],
  ["LICENSE", "LICENSE-three.txt"],
];

function copiar(origen, destino) {
  mkdirSync(dirname(destino), { recursive: true });
  copyFileSync(origen, destino);
}

rmSync(PUBLICO, { recursive: true, force: true });
mkdirSync(PUBLICO, { recursive: true });
let avisos = 0;

// ---------- 1. reproducción K002 ----------
const fuenteK002 = join(ESCENA, "datos_k002.js");
if (existsSync(fuenteK002)) {
  const texto = readFileSync(fuenteK002, "utf8");
  const d = JSON.parse(texto.slice(texto.indexOf("=") + 1).trim().replace(/;\s*$/, ""));
  const datos = {
    prueba: "K002", fecha: "2026-10-27", firmware: "0.1.3",
    derivado_de: "datos/procesados/video_K002/escena/datos_k002.js (analisis/escena_k002.py)",
    duracion_s: Math.ceil(d.t[d.t.length - 1]),
    t: d.t, mov: d.mov, suave: d.suave, entrada: d.entrada, tasa_csi: d.tasa_csi,
    cruces: d.cruces, primer_positivo: d.primer_positivo,
  };
  mkdirSync(SALIDA_DATOS, { recursive: true });
  const json = JSON.stringify(datos);
  writeFileSync(join(SALIDA_DATOS, "k002_reproduccion.json"), json, "utf8");
  copiar(join(SALIDA_DATOS, "k002_reproduccion.json"), join(PUBLICO, "datos", "k002_reproduccion.json"));
  const det = d.primer_positivo.filter((p) => p !== null).length;
  console.log(`K002: ${d.t.length} muestras del detector, ${datos.duracion_s} s, detectados ${det}/10`);
} else {
  console.warn(`AVISO: falta ${fuenteK002} (correr: python analisis/escena_k002.py preparar). Sin reproducción K002.`);
  avisos++;
}

// ---------- 2. holograma ----------
copiar(join(MOCKUP, "holograma", "index.html"), join(PUBLICO, "holograma", "index.html"));
for (const [o, d] of VENDOR) copiar(join(THREE, o), join(PUBLICO, "holograma", "vendor", d));
if (existsSync(MODELO)) {
  const sha = createHash("sha256").update(readFileSync(MODELO)).digest("hex");
  if (sha !== MODELO_SHA256) { console.warn(`AVISO: el SHA-256 del modelo no coincide (${sha})`); avisos++; }
  copiar(MODELO, join(PUBLICO, "holograma", "modelos", "quaternius_animated_human.glb"));
} else {
  console.warn(`AVISO: falta el modelo ${MODELO}; el holograma no dibuja la figura.`);
  avisos++;
}
console.log(`publico/ listo (${avisos} avisos)`);
