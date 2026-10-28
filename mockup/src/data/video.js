// video.js — modos del video de demostración (mockup/video/escenario.html): ?escenario=caida_video | bienestar_video.
// ESCENARIOS SIMULADOS: no se carga la reproducción K002 ni se busca /ws. Todo lo que se ve es sintético (lo da el
// holograma o la propia pantalla) y el video fija el tiempo de cada cuadro con window.__aura.cuadro(t, extra):
// sin relojes propios, cada cuadro es reproducible. Fuera de estos modos, la app no cambia.
const pedido = new URLSearchParams(location.search).get("escenario");
export const ESCENARIO_VIDEO = ["caida_video", "bienestar_video"].includes(pedido) ? pedido : null;
