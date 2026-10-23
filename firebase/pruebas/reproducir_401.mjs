// Reproduce en el EMULADOR (no toca el proyecto real) la escritura del primer bloque /crudo que dio 401 con 0.1.3
// (P3_013, 27 s, ruta /crudo/hab1/1792784291991), con la estructura y el tamano que arma aura_nube.c
// (publicar_bloque). El contenido real no se registro; se prueba el bloque tipico y cada variante que podria
// violar una regla, para saber que regla rechaza cada caso.
// Ejecutar (desde C:\aura\firebase):
//   npx firebase emulators:exec --only database --project demo-aura "node pruebas/reproducir_401.mjs"
import { readFileSync } from "node:fs";
import { initializeTestEnvironment, assertSucceeds } from "@firebase/rules-unit-testing";

const UID_PLACA = "RSZSiH4Qe5OXnuhwdhYvzYz9Ex22";
const reglas = readFileSync(new URL("../reglas_publicar.json", import.meta.url), "utf8");
const env = await initializeTestEnvironment({ projectId: "demo-aura", database: { rules: reglas, host: "127.0.0.1", port: 9000 } });
const placa = env.authenticatedContext(UID_PLACA).database();

// Mismo formato que publicar_bloque(): jit = jitter*1e4 (u16), am/ad = %.1f
const T0 = 1792784291991;
function bloque({ n = 178, nsub = 52, jitVal = 65535, amp = 812.4, t1 = T0 + 10500, extra = null } = {}) {
  const b = {
    t0: T0, t1, n, mov: 0, pres: 0, ncsi: 1060, nsub,
    jit: Array.from({ length: n }, () => jitVal).join(","),
    am: Array.from({ length: nsub }, () => amp.toFixed(1)).join(","),
    ad: Array.from({ length: nsub }, () => (amp / 10).toFixed(1)).join(","),
  };
  if (extra) Object.assign(b, extra);
  return b;
}

const casos = [
  ["tipico del primer bloque (n=178, nsub=52, jitter saturado 65535)", bloque()],
  ["t1 < t0 (reloj SNTP corregido hacia atras durante el bloque)", bloque({ t1: T0 - 1000 })],
  ["n = 513 (> 512)", bloque({ n: 513 })],
  ["nsub = 65 (> 64)", bloque({ nsub: 65 })],
  ["jit de 3201+ caracteres (n=512 con valores de 6 cifras)", bloque({ n: 512, jitVal: 123456 })],
  ["am/ad > 800 caracteres (amplitudes enormes, 1e13)", bloque({ amp: 1.2e13 })],
  ["am con amplitudes grandes pero normales (99999.9)", bloque({ amp: 99999.9 })],
  ["campo extra", bloque({ extra: { x: 1 } })],
];

let i = 0;
for (const [desc, b] of casos) {
  i++;
  const ruta = `crudo/hab1/${T0 + i}`;
  let res;
  try { await assertSucceeds(placa.ref(ruta).set(b)); res = "PERMITIDO"; } catch { res = "DENEGADO (401 Permission denied)"; }
  console.log(`${String(i).padStart(2)}. ${desc}: jit ${b.jit.length} car., am ${b.am.length} car. -> ${res}`);
}
await env.cleanup();
