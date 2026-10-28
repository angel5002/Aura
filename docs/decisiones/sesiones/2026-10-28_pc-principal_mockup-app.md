# Sesión 2026-10-28 — Mockup móvil de la app AURA (iteración 1)

- **Equipo:** PC principal (`DESKTOP-7O57OU0`, usuario `usuario`), ruta `C:\aura`, Claude Code.
- **Commit al inicio:** `adb7c0b`. El commit final se consulta con `git log`.
- **Fuente de verdad:** `docs/mockup/AURA_mockup_especificacion.pdf`.

## Objetivo
Construir el mockup de la app (9 pantallas, 390 × 844) como la carpeta estática `app/` que monta `servidor.py` de
Angel. Datos reales donde existen (movimiento, K002) y escenarios de demo rotulados en lo demás.

## Qué se hizo
- **Lectura:**
  - `CLAUDE.md`, `INDICE.md` y el último informe de sesión;
  - la especificación (texto y capturas), la propuesta condensada y los requerimientos del MVP de Angel;
  - la escena K002 (`analisis/escena_k002.py` y su plantilla).
- **Conflictos:** se propusieron 14 y Deisy los aprobó con 6 ajustes:
  - rótulo "Escenario ilustrativo" en Alerta;
  - la voz se registra en la ADR;
  - política de git;
  - fps como estimado;
  - video de la animación;
  - documento de propuestas para Angel.
- **Instalación (aprobada, local en `C:\aura\mockup`, versiones fijas):**
  - gsap 3.15.0, vite 8.3.4, @fontsource/inter 5.3.0, @playwright/test 1.64.1 y three 0.128.0;
  - Chromium de Playwright (revisión 1248), descargado porque la caché tenía la 1243.
- **Código en `mockup/`:**
  - `src/tokens.css` y `base.css`;
  - componentes: orbe con barras, chip, fila de módulo, hoja, banner, anillo, check, gráfico de señal, holograma;
  - las 9 pantallas, `motion.js` (GSAP + View Transitions + `prefers-reduced-motion`);
  - datos: `fuente.js` (vivo → K002 → escenarios), `techo.js` (honestidad), `escenarios.js`, `guion.js`, `k002.js`.
- **Holograma:** copia adaptada de la escena K002 en `mockup/holograma/`, con modo señal y modo gemelo y three r128 en
  local. El original de `analisis/` no se tocó.
- **Datos:** `scripts/preparar_datos.mjs` deriva `datos/procesados/mockup/k002_reproduccion.json` de `datos_k002.js`
  (5 804 muestras, 330 s, detectados 10/10; fuera de git).
- **Pruebas:** `pruebas/criterios.spec.js` (Playwright, 390 × 844, red externa bloqueada).
- **Documentos:**
  - ADR-0025 (Propuesta);
  - `docs/mockup/propuestas_para_angel.md`;
  - `mockup/README.md`;
  - `.gitignore`: `docs/mockup/referencias/`, `*.mp4`, y `mockup/.gitignore` con `app/`, `publico/` y salidas;
  - configuración `mockup-app` en `.claude/launch.json`.

## Resultados (criterios de la especificación)
| # | Criterio | Resultado | Cómo se midió |
|---|---|---|---|
| 1 | 9 pantallas a 390 × 844 sin texto cortado ni desbordes | **Cumple** (medido) | Prueba 1: captura de cada pantalla; revisa ancho del documento, del contenedor y de cada elemento, y texto con `scrollWidth > clientWidth` |
| 2 | Sin internet desde `app/`, Inter local, modo demo | **Cumple** (medido) | Prueba 2: toda petición fuera de localhost se aborta y se anota (0); fuentes solo de localhost; `document.fonts.check("600 16px Inter")`; fuente = demo; HTML compilado sin CDN |
| 3 | ≥ 45 fps en Hoy, Gemelo y Señal en el celular | **No verificado** | Estimado en la PC (Intel HD 530, Chromium con D3D11): 60 fps en las tres. Con la CPU frenada ×4, la página quedó en 52–60 fps; la escena de Señal bajó a 42,3 y la de Gemelo a 43 en distintas corridas. Falta medirlo en el celular (iteración 2) |
| 4 | Sello "DEMO · reproducción" en todas las pantallas con fuente = demo | **Cumple** (medido) | Prueba 4: 3 escenarios × 9 pantallas |
| 5 | Sin cifras de respiración, sueño, corazón y ánimo; sin "diagnóstico" en el compilado | **Cumple** (medido) | Prueba 5: filas de esos módulos sin dígitos y texto sin patrones de cifra de salud, en 3 escenarios × 9 pantallas; búsqueda de `diagnóstico` (con y sin tilde, y escapada) en `app/` |
| 6 | Emergencia: 45 s, "Estoy bien" cancela, sin respuesta "Familia avisada (simulación)" | **Cumple** (medido) | Prueba 6: tween de 45 s; cancelación; aviso a los 44,7 s reales; "Necesito ayuda" avisa de inmediato |
| 7 | Teleconsulta en ≤ 3 toques con "Simulación" | **Cumple** (medido) | Prueba 7: 2 toques desde Alerta |
| 8 | `prefers-reduced-motion`: sin bucles, transiciones de 0 ms | **Cumple** (medido) | Prueba 8: 0 tweens infinitos de GSAP, 0 animaciones CSS infinitas, 0 View Transitions, cambio de pantalla < 100 ms, escena en modo reducido |
| 9 | Contraste ≥ 4,5:1 en todo texto | **Cumple** (medido) | Prueba 9: 313 textos en 13 estados (9 pantallas, panel técnico, banner, resultado de emergencia, respuesta del asistente); mínimo 4,83:1 ("Necesito ayuda") |
| 10 | Nada de RuView; clínicas claramente ficticias | **Cumple** (medido) | Prueba 10: búsqueda en `app/`; las 3 opciones con "Demo", "Ficticio" o "Ejemplo" |

Corrida final: 10/10 aprobadas (`mockup/pruebas/salida/resultado.json`, fuera de git).

**Fallos en el camino (corregidos sin cambiar criterios):**
- La prueba 2 falló porque un comentario del holograma mencionaba "cdnjs" y "jsdelivr": se reescribió el comentario.
- La prueba 6 falló porque la ayuda de la prueba no recargaba la página al volver a Emergencia: se corrigió la ayuda.
- La prueba 5 falló porque la expresión `diagn[oó]stic` atrapaba el identificador inglés `diagnostics` de
  `three.min.js` (interno de WebGL, no se muestra). Se acotó a la palabra del criterio, `diagnóstico`, y el
  identificador inglés se informa como anotación de la prueba.

Revisión visual de las capturas y cambios hechos:
- en Señal, el panel y las baldosas ahora usan el mismo instante;
- el banner ya no salta al entrar a Alerta;
- la barra superior con el sello queda por encima de la hoja y del velo;
- el halo de "Actividad" se ve más.

## ADR
- ADR-0025 (Propuesta): stack del mockup y alcance sin reconocimiento de voz.

## Pendientes y riesgos
- **Animación del equipo:** `aura-animacion-v3-1080p60.mp4` no está en `docs/mockup/referencias/` (sigue el render de
  K002). No se pudieron sacar sus tiempos.
- **45 fps en el celular:** medirlo con la depuración remota de Chrome (iteración 2). En la PC, con la CPU ×4, Señal y
  Gemelo quedaron cerca del límite.
- **Con Angel:** propuestas de contrato y voz (F6 "Debe"), en `docs/mockup/propuestas_para_angel.md`.
- **No verificado:** el mockup no se abrió todavía en el celular (ni por la red de casa ni por AURA-LAB).
  Abrirlo desde otro equipo de la red puede requerir una regla de firewall para `node.exe` en el puerto 4173; la
  ejecuta Deisy.
- **Archivos y datos:**
  - `docs/mockup/referencias/K002_escena3d_1080p30.mp4` (145 MB) sigue en la carpeta, fuera de git.
  - `mockup/app/` lleva la reproducción K002 y el modelo: una copia para Angel sale solo con autorización.

## Iteración 2 (mismo día)
- **Paso 1:** variantes A (claro cálido, con oscuro en Gemelo y Señal) y B (todo oscuro cálido) de Hoy y Gemelo, con
  Atkinson Hyperlegible Next y Fraunces, instaladas con confirmación. Deisy las **descartó**: se vuelve a la base
  visual de `cccda59`, solo refinada.
- **Limpieza (con confirmación):** desinstaladas las dos fuentes (`package.json` y lock iguales a `cccda59`); borrados
  `silueta.js`, `variantes.spec.js` y sus capturas.
- **Refinamiento:**
  - paleta `#5CC8D6` / `#6FCF97` / `#E8B04A` / `#F07A6A`;
  - brillos solo en el logo, el orbe y el holograma; cuadrícula y bordes más tenues;
  - títulos en 600; una etiqueta en mayúsculas por pantalla; pastillas tenues sin borde; DEMO solo en la cabecera;
  - el orbe como pestaña central, y en Asistente un resplandor que respira en 4 s con una onda;
  - Hoy en lenguaje humano;
  - Gemelo 3D con zonas de órganos, selector real/escenario, fichas y las tres líneas.
- **Pruebas:** Playwright 10/10. Contraste: 294 textos, mínimo 4,83:1. Emergencia: aviso a los 45,0 s.
  - **Fluidez:** 60 fps estimados en la PC, también con la CPU ×4. En el celular, no verificado.
- **Fallo en el camino:** la prueba 9 se quedó sin tiempo porque buscaba `.frase`, clase renombrada a
  `.frase-prueba` (el nombre `.frase` pasó al título de Hoy). Se corrigió el selector; el criterio no cambió.
- **Pendientes:**
  - medir los 45 fps en el celular;
  - abrir la app en el celular por la red de casa o AURA-LAB;
  - conseguir la animación del equipo, que no llegó;
  - las propuestas para Angel.

## Iteración 3 (mismo día): solo texto y tarjeta de Dispositivo
- **Hoja ⓘ en la cabecera**, junto al sello DEMO (`src/components/aclaraciones.js`). Reúne todo lo que salió de las
  pantallas, en frases de 12 palabras o menos:
  - qué es real: K002, 27/10/2026, firmware 0.1.3, placa B, una sola sala, 10/10, reproducción sin sensor en vivo;
  - qué es ejemplo;
  - qué es ilustrativo;
  - "AURA no diagnostica ni receta", "no reemplaza a tu médico" y el 106 (SAMU).
- **Pantallas:**
  - Hoy: "Movimiento en la sala" / "Todo tranquilo", con "hace N s", y la línea "Hoy".
  - Asistente: textos cortos; el guion también va en frases cortas.
  - Gemelo: selector "Hoy" / "Ejemplo" y fichas de dos líneas.
  - Alerta: título nuevo, línea "Ejemplo · la respiración aún no se mide" y tendencia sin pie.
  - Emergencia: textos cortos y solo la línea del 106.
  - Teleconsulta: descripciones genéricas en vez de nombres de clínicas.
  - Señal: pastilla "Prueba K002 · 27/10", tiempo "0:31" y "462 muestras/s".
  - Sin pastillas "Prototipo".
- **Dispositivo:**
  - tarjeta "Tu instalación" con la mini escena 3D: nuevo modo `instalacion` del holograma, que reutiliza los modelos
    de router y placa de K002; se pausa con IntersectionObserver y al salir de la pantalla;
  - filas Sensor / Red / Cobertura y privacidad en tres íconos;
  - firmware, K002 y "una sola sala" pasan al panel técnico.
- **Arreglo en el holograma:** un mensaje "seguir" sin pausa previa ya no arranca un segundo ciclo de dibujo.
- **Pruebas:** 10/10 criterios y la prueba nueva de honestidad. Contraste: 309 textos, mínimo 4,83:1.
  - **Fluidez:** 60 fps estimados en la PC. En el celular, no verificado.
- **Pruebas actualizadas, sin cambiar criterios:**
  - la 7 busca "(simulación)" en la confirmación;
  - la 10 verifica las tres descripciones genéricas, sin nombres de clínicas.
