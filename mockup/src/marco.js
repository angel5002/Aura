// marco.js — en escritorio (ventana ≥ 600 px CSS) la app (390 × 844) se muestra dentro de un marco de celular
// genérico, el mismo de los videos: bisel redondeado, isla superior y barra de estado con la hora real e íconos
// genéricos (sin logos). Se escala con transform para caber siempre en la ventana (también con zoom del navegador),
// así el texto se vuelve a dibujar nítido. Las capas, hojas, alertas y la barra inferior viven dentro de #app, así que
// quedan dentro de la pantalla del marco. Con < 600 px (celular real, iframes de los videos, pruebas) o ?marco=0, la
// app ocupa la pantalla completa como siempre.
const ANCHO_MARCO = 418, ALTO_MARCO = 916, AIRE = 32;    // marco = 390 × 888 de pantalla + bisel de 14 px; aire alrededor
const consulta = matchMedia("(min-width: 600px)");
const pedido = new URLSearchParams(location.search).get("marco") !== "0";

function construir() {
  const app = document.getElementById("app");
  const escena = document.createElement("div");
  escena.className = "marco-escena";
  escena.innerHTML = `<div class="marco"><div class="marco-vidrio">
      <div class="marco-isla"></div>
      <div class="marco-estado" aria-hidden="true"><span class="marco-hora"></span><span class="marco-iconos">
        <span class="marco-barras"><i style="height:4px"></i><i style="height:6px"></i><i style="height:8px"></i><i style="height:11px"></i></span>
        <span class="marco-bateria"><i></i></span></span></div>
    </div></div>`;
  app.before(escena);
  escena.querySelector(".marco-vidrio").append(app);
  const hora = escena.querySelector(".marco-hora"), marco = escena.querySelector(".marco");
  const reloj = () => { hora.textContent = new Date().toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit", hour12: false }); };
  reloj(); setInterval(reloj, 15000);
  const escalar = () => {
    const e = Math.min(1, (innerHeight - AIRE) / ALTO_MARCO, (innerWidth - AIRE) / ANCHO_MARCO);
    marco.style.setProperty("--escala", Math.max(0.1, e).toFixed(4));
  };
  addEventListener("resize", escalar); escalar();
}

export function iniciarMarco() {
  if (!pedido) return;
  const aplicar = () => document.documentElement.classList.toggle("con-marco", consulta.matches);
  if (consulta.matches) construir();
  else consulta.addEventListener("change", function primera() { if (consulta.matches) { construir(); consulta.removeEventListener("change", primera); } });
  consulta.addEventListener("change", aplicar); aplicar();
}
