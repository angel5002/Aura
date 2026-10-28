// video.js — modo del video de demostración (mockup/video/escenario.html): ?escenario=caida_video.
// ESCENARIO SIMULADO: no se carga la reproducción K002 ni se busca /ws. La señal y la caída son sintéticas (las da el
// holograma, AURA_ESCENA.senal) y el video fija el tiempo de cada cuadro con window.__aura.cuadro(t, extra):
// sin relojes propios, cada cuadro es reproducible. Fuera de este modo, la app no cambia.
export const ESCENARIO_VIDEO = new URLSearchParams(location.search).get("escenario") === "caida_video";
