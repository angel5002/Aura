// k002.js — reproducción de la prueba K002 (datos reales del detector, firmware 0.1.3, 27/10/2026).
// El JSON lo genera scripts/preparar_datos.mjs en datos/procesados/mockup (fuera de git) y Vite lo copia a app/datos.
let D = null;

export async function cargarK002() {
  try {
    const r = await fetch("datos/k002_reproduccion.json");
    if (!r.ok) return null;
    D = await r.json();
    return { prueba: D.prueba, fecha: D.fecha, firmware: D.firmware, duracion: D.duracion_s, cruces: D.cruces.length };
  } catch {
    return null;
  }
}

function idx(t) {                                  // última muestra con t_i <= t (igual que la escena)
  let a = 0, b = D.t.length - 1;
  if (t < D.t[0]) return 0;
  while (a < b) { const m = (a + b + 1) >> 1; if (D.t[m] <= t) a = m; else b = m - 1; }
  return a;
}

export function muestraEn(t) {
  if (!D) return null;
  const i = idx(t);
  let j = i;
  while (j >= 0 && !D.mov[j]) j--;                 // última muestra en MOVIMIENTO antes de t
  const s = Math.floor(t);
  let n = 0, k = 0;
  for (let q = Math.max(0, s - 3); q < s; q++) if (q < D.tasa_csi.length) { n += D.tasa_csi[q]; k++; }
  return {
    t, mov: D.mov[i] === 1, suave: D.suave[i], entrada: D.entrada[i],
    tasa: k ? n / k : 0,
    detectados: D.primer_positivo.filter((p) => p !== null && p <= t).length,
    ultimoMovHace: j >= 0 ? t - D.t[j] : null,
  };
}

// Señal del detector en una ventana [t - ventana, t] (para los gráficos)
export function ventana(t, segundos = 20) {
  if (!D) return null;
  const i0 = idx(Math.max(0, t - segundos)), i1 = idx(t);
  return { t0: t - segundos, t: D.t.slice(i0, i1 + 1), suave: D.suave.slice(i0, i1 + 1),
           entrada: D.entrada.slice(i0, i1 + 1), mov: D.mov.slice(i0, i1 + 1),
           cruces: D.cruces.filter((c) => c >= t - segundos && c <= t).map((c) => [c, D.cruces.indexOf(c) + 1]) };
}

export const duracionK002 = () => (D ? D.duracion_s : 330);
