// Prueba T5: matriz de reglas de Realtime Database en el EMULADOR (no toca el proyecto real).
// Requiere (pendiente de autorizacion para instalar):  npm install  (en C:\aura\firebase)
// Ejecutar:  npx firebase emulators:exec --only database --project demo-aura "node pruebas/reglas.test.mjs"
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { initializeTestEnvironment, assertFails, assertSucceeds } from "@firebase/rules-unit-testing";

// Modo 1 (por defecto): plantilla con UID de prueba.
// Modo 2: AURA_REGLAS=<ruta> carga ESE archivo tal cual (sin sustituciones) y usa AURA_UID_USUARIO /
//         AURA_UID_PLACA como identidades: prueba exactamente lo que se va a publicar.
const RUTA = process.env.AURA_REGLAS;
const UID_USUARIO = RUTA ? process.env.AURA_UID_USUARIO : "uidUsuarioPrueba01";
const UID_PLACA = RUTA ? process.env.AURA_UID_PLACA : "uidPlacaPrueba0001";
if (RUTA && (!UID_USUARIO || !UID_PLACA)) {
  console.error("Con AURA_REGLAS hay que dar AURA_UID_USUARIO y AURA_UID_PLACA");
  process.exit(2);
}
const bytesReglas = RUTA ? readFileSync(RUTA) : null;
const reglas = RUTA
  ? bytesReglas.toString("utf8")
  : readFileSync(new URL("../database.rules.plantilla.json", import.meta.url), "utf8")
      .replaceAll("UID_USUARIO", UID_USUARIO).replaceAll("UID_PLACA", UID_PLACA);
const SHA = createHash("sha256").update(RUTA ? bytesReglas : reglas).digest("hex");
console.log(`Reglas: ${RUTA || "plantilla con UID de prueba"} | SHA-256 ${SHA}`);

const env = await initializeTestEnvironment({
  projectId: "demo-aura",
  database: { rules: reglas, host: "127.0.0.1", port: 9000 },
});

const SV = { ".sv": "timestamp" };
const estadoOk = { estado: "VACIA", mov: false, presencia: "vacia", entrenada: true, alerta: false, desde: 1761100000000, t: SV };
const latidoOk = { t: SV, up: 10, heap: 100000, heap_min: 80000, red: "principal", rssi: -50, ver: "0.1.0",
                   renov: 0, hms_s: 16.0, ts_p95: 61.0, reinicio: "encendido" };
const comandoResOk = { id: "-Nabc123", cmd: "RESET_BASELINE", ok: true, detalle: "ESP_OK", origen: "nube", t: SV };
const bloqueOk = { t0: 1761100000000, t1: 1761100010000, n: 160, mov: 0, pres: 0, ncsi: 1000, nsub: 52,
                   jit: "12,13,14", am: "1.0,2.0", ad: "0.1,0.2" };
const cmdOk = { cmd: "RESET_BASELINE", t: SV };
const BLOQUE = "1761100000000";

const anon = env.unauthenticatedContext().database();
const usuario = env.authenticatedContext(UID_USUARIO).database();
const placa = env.authenticatedContext(UID_PLACA).database();
const otro = env.authenticatedContext("uidOtroUsuario0001").database();

const resultados = [];
async function caso(n, descripcion, esperado, promesa) {
  let obtenido;
  try {
    await (esperado === "PERMITIDO" ? assertSucceeds(promesa) : assertFails(promesa));
    obtenido = esperado;
  } catch (e) {
    obtenido = esperado === "PERMITIDO" ? "DENEGADO" : "PERMITIDO";
  }
  resultados.push({ n, descripcion, esperado, obtenido, ok: obtenido === esperado });
  console.log(`${obtenido === esperado ? "OK   " : "FALLA"} ${n}. ${descripcion}: esperado ${esperado}, obtenido ${obtenido}`);
}

// Sin autenticar: todo denegado
await caso(1, "sin auth lee /sensores/hab1", "DENEGADO", anon.ref("sensores/hab1").get());
await caso(2, "sin auth escribe /sensores/hab1/estado", "DENEGADO", anon.ref("sensores/hab1/estado").set(estadoOk));
await caso(3, "sin auth lee /crudo/hab1", "DENEGADO", anon.ref("crudo/hab1").get());
await caso(4, "sin auth escribe /comandos/hab1/c0", "DENEGADO", anon.ref("comandos/hab1/c0").set(cmdOk));
await caso(5, "sin auth lee /comandos/hab1", "DENEGADO", anon.ref("comandos/hab1").get());
await caso(6, "sin auth lee la raiz", "DENEGADO", anon.ref("/").get());
// Placa (escribe /sensores y /crudo, lee /comandos)
await caso(7, "placa escribe /sensores/hab1/estado", "PERMITIDO", placa.ref("sensores/hab1/estado").set(estadoOk));
await caso(8, "placa escribe /sensores/hab1/latido", "PERMITIDO", placa.ref("sensores/hab1/latido").set(latidoOk));
await caso(9, "placa escribe /sensores/hab1/comando", "PERMITIDO", placa.ref("sensores/hab1/comando").set(comandoResOk));
await caso(10, "placa escribe /crudo/hab1/<bloque>", "PERMITIDO", placa.ref(`crudo/hab1/${BLOQUE}`).set(bloqueOk));
await caso(11, "placa lee /comandos/hab1", "PERMITIDO", placa.ref("comandos/hab1").get());
await caso(12, "placa escribe /comandos/hab1/c1", "DENEGADO", placa.ref("comandos/hab1/c1").set(cmdOk));
await caso(13, "placa lee /sensores/hab1", "DENEGADO", placa.ref("sensores/hab1").get());
// Usuario (lee /sensores y /crudo, escribe /comandos)
await caso(14, "usuario lee /sensores/hab1", "PERMITIDO", usuario.ref("sensores/hab1").get());
await caso(15, "usuario lee /crudo/hab1", "PERMITIDO", usuario.ref("crudo/hab1").get());
await caso(16, "usuario escribe /comandos/hab1/c2", "PERMITIDO", usuario.ref("comandos/hab1/c2").set(cmdOk));
await caso(17, "usuario escribe /sensores/hab1/estado", "DENEGADO", usuario.ref("sensores/hab1/estado").set(estadoOk));
await caso(18, "usuario escribe /crudo/hab1/<bloque> (datos)", "DENEGADO", usuario.ref("crudo/hab1/1761100020000").set(bloqueOk));
await caso(19, "usuario lee /comandos/hab1", "DENEGADO", usuario.ref("comandos/hab1").get());
await caso(20, "usuario borra /crudo/hab1/<bloque>", "PERMITIDO", usuario.ref(`crudo/hab1/${BLOQUE}`).remove());
await caso(21, "usuario borra /crudo/hab1 completo", "DENEGADO", usuario.ref("crudo/hab1").remove());
await caso(22, "usuario borra /comandos/hab1/c2", "PERMITIDO", usuario.ref("comandos/hab1/c2").remove());
// Otro usuario autenticado
await caso(23, "otro UID lee /sensores/hab1", "DENEGADO", otro.ref("sensores/hab1").get());
await caso(24, "otro UID escribe /comandos/hab1/c3", "DENEGADO", otro.ref("comandos/hab1/c3").set(cmdOk));
// .validate: estructura y tamano
await caso(25, "estado con campo extra", "DENEGADO", placa.ref("sensores/hab1/estado").set({ ...estadoOk, x: 1 }));
await caso(26, "estado con valor no permitido", "DENEGADO", placa.ref("sensores/hab1/estado").set({ ...estadoOk, estado: "BAILANDO" }));
const { alerta, ...estadoSinAlerta } = estadoOk;
await caso(27, "estado sin un campo obligatorio", "DENEGADO", placa.ref("sensores/hab1/estado").set(estadoSinAlerta));
await caso(28, "bloque con jit de 5000 caracteres", "DENEGADO", placa.ref(`crudo/hab1/${BLOQUE}`).set({ ...bloqueOk, jit: "1".repeat(5000) }));
await caso(29, "bloque con clave no numerica", "DENEGADO", placa.ref("crudo/hab1/abc").set(bloqueOk));
await caso(30, "comando no permitido (FORMAT_FLASH)", "DENEGADO", usuario.ref("comandos/hab1/c4").set({ cmd: "FORMAT_FLASH", t: SV }));
await caso(31, "comando con t que no es la hora del servidor", "DENEGADO", usuario.ref("comandos/hab1/c5").set({ cmd: "RESET_BASELINE", t: 123 }));
await caso(32, "comando con campo extra", "DENEGADO", usuario.ref("comandos/hab1/c6").set({ ...cmdOk, x: 1 }));
await caso(33, "latido con version de 40 caracteres", "DENEGADO", placa.ref("sensores/hab1/latido").set({ ...latidoOk, ver: "v".repeat(40) }));
await caso(34, "sensor con id invalido", "DENEGADO", placa.ref("sensores/Hab-1!/estado").set(estadoOk));
await caso(35, "comando SET_CFG valido", "PERMITIDO", usuario.ref("comandos/hab1/c7").set({ cmd: "SET_CFG AP motion_sensitivity=0.4", t: SV }));
// Presencia explicita: nunca "vacia" sin entrenamiento
await caso(36, "presencia 'vacia' sin entrenar", "DENEGADO", placa.ref("sensores/hab1/estado").set({ ...estadoOk, estado: "SIN_MOVIMIENTO", entrenada: false, presencia: "vacia" }));
await caso(37, "presencia 'no_disponible' sin entrenar", "PERMITIDO", placa.ref("sensores/hab1/estado").set({ ...estadoOk, estado: "SIN_MOVIMIENTO", entrenada: false, presencia: "no_disponible" }));
await caso(38, "estado VACIA sin entrenar", "DENEGADO", placa.ref("sensores/hab1/estado").set({ ...estadoOk, estado: "VACIA", entrenada: false, presencia: "no_disponible" }));
await caso(39, "presencia con valor no permitido", "DENEGADO", placa.ref("sensores/hab1/estado").set({ ...estadoOk, presencia: "quizas" }));

await env.cleanup();
const fallas = resultados.filter((r) => !r.ok).length;
writeFileSync(new URL("./resultado_t5.json", import.meta.url),
  JSON.stringify({ reglas: RUTA || "plantilla", sha256: SHA, uid_usuario: UID_USUARIO, uid_placa: UID_PLACA,
                   fallas, total: resultados.length, resultados }, null, 2));
console.log(`\nT5: ${resultados.length - fallas}/${resultados.length} casos con el resultado esperado`);
process.exit(fallas ? 1 : 0);
