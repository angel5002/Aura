# ADR-0025: Stack del mockup de la app (GSAP + Vite + Inter local + escena K002) y alcance sin reconocimiento de voz

- **Estado:** Propuesta
- **Fecha:** 2026-10-28
- **Decide:** ambos (stack fijado por la especificación de Deisy; lote de instalación y ajustes aprobados por Deisy el
  28/10/2026; implementación y redacción de Claude; la ADR queda en Propuesta hasta su revisión)
- **Equipo donde se tomó:** PC principal (`DESKTOP-7O57OU0`, `C:\aura`)
- **Relacionadas:** ADR-0017 (alcance del hackathon), ADR-0018 (presencia "no disponible"), ADR-0019 (detector propio),
  ADR-0023 (red AURA-LAB)

## Contexto
Para el avance de la Científica Hack X y el MVP del 12/11 hace falta una app web móvil navegable (390 × 844). Debe
mostrar el flujo de AURA con datos reales donde existen (movimiento, K002) y escenarios de demo rotulados en todo lo
demás. Se entrega como la carpeta estática `app/` que monta `servidor.py` de Angel (F5). La fuente de verdad es
`docs/mockup/AURA_mockup_especificacion.pdf`. Restricciones:
- funcionar sin internet;
- no afirmar capacidades no demostradas (ADR-0017);
- ningún dato crudo en git;
- nada de servicios en la nube.

## Decisión
1. **Interfaz:** JavaScript sin framework, con **GSAP 3.15.0** como único motor de animación (DrawSVG y SplitText
   vienen en el paquete npm) y la **View Transitions API** para cambiar de pantalla cuando existe (si no, GSAP).
   Se compila con **Vite 8.3.4** a `mockup/app/` con rutas relativas (`base: "./"`).
2. **Tipografía:** **Inter** local (`@fontsource/inter@5.3.0`, latín, pesos 400, 600, 700 y 800), con cifras tabulares.
3. **Holograma:** copia adaptada de la escena K002 (`analisis/escena_k002/index.html` → `mockup/holograma/`) en un
   iframe. Usa three r128 y sus módulos de ejemplo copiados desde `three@0.128.0` (npm), sin CDN.
   Diferencias con el original:
   - lienzo del tamaño de la ventana, con nitidez máxima de 2×;
   - sin HUD: los rótulos los pone la app;
   - sin profundidad de campo, por el costo en el celular;
   - se pausa cuando su pantalla no se ve;
   - respeta `prefers-reduced-motion`;
   - modo `gemelo`, con zonas del color de su chip.

   El original de `analisis/` no se tocó.
4. **Pruebas:** `@playwright/test@1.64.1` con Chromium (revisión 1248, descargada porque la caché tenía la 1243).
5. **Datos:** se usa `/ws` si responde. Si no, la reproducción K002, un JSON derivado en
   `datos/procesados/mockup/` y fuera de git. Los escenarios "normal", "respiración" y "caída" se generan en el
   navegador con fuente = demo. La app ignora `confianza` y aplica un **techo de honestidad** por módulo
   (`mockup/src/data/techo.js`).
6. **Alcance de voz (decisión de Deisy, 28/10/2026):** el mockup **no usa reconocimiento de voz**. El asistente
   funciona con frases que se tocan. Las barras del orbe siguen el nivel real del micrófono (Web Audio, local) solo en
   HTTPS o localhost; si no, son barras de demostración y lo dicen. **Nota:** la F6 de Angel marca el reconocimiento
   de voz como **"Debe"** para el MVP (Web Speech API + HTTPS por ngrok). Hay que **acordarlo con él**: en Chrome
   para Android, ese reconocimiento manda el audio a servidores de Google (servicio en la nube) y exige HTTPS.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| React (u otro framework) | La especificación lo descarta: más peso y dependencias para 9 pantallas sin estado complejo. |
| Lottie | Exige animaciones de terceros con licencias variables (especificación). |
| Otra librería de animación junto a GSAP (Motion, anime.js) | Dos motores compitiendo por los mismos elementos (especificación). |
| Three.js actual (r17x) en lugar de r128 | La escena K002 ya está probada en r128. Migrarla queda para después del MVP (especificación). |
| Cargar three desde cdnjs o jsdelivr, como la escena original | Sin internet la escena no abriría (criterio 2). |
| Bajar los 9 archivos de three con curl en vez de npm | Menos reproducible. Con `three@0.128.0` en `package-lock.json` queda fijada la versión y su integridad. |
| Escena K002 "tal como está" en el iframe | Es un lienzo fijo de 1920 × 1080 con HUD propio: en 390 px quedaría una franja de 219 px con letra ilegible, y el gemelo necesita zonas de color. |
| Web Speech API (reconocimiento) en el mockup | Nube (Google) y HTTPS; prohibido para este mockup. Ver la nota del punto 6. |
| Fuentes de Google Fonts | Dependen de internet. |

## Consecuencias
- El mockup abre sin internet desde cualquier servidor estático (Vite preview, `servidor.py`, `python -m http.server`).
  No abre con doble clic (`file://`): los módulos JS no cargan así.
- `mockup/app/` y `mockup/publico/` quedan **fuera de git**: llevan la reproducción K002 y el modelo .glb. Una copia
  para Angel sale del equipo solo con autorización de Deisy.
- **Límite declarado:** los 45 fps en el celular **no están verificados**. Estimado en la PC
  (`mockup/pruebas/salida/fps.json`): 60 fps en las tres pantallas con la CPU normal. Con la CPU frenada ×4, la
  escena de Señal bajó a 42 fps en una corrida y la de Gemelo a 43 en otra. La medición en el celular queda para la
  iteración 2.
- `three.min.js` contiene el identificador inglés `diagnostics` (interno de WebGL). La palabra prohibida
  "diagnóstico" no aparece en el compilado (prueba 5).
- Obliga a acordar con Angel los cambios de contrato de `docs/mockup/propuestas_para_angel.md` y la voz (punto 6).

## Evidencia
- Especificación: `docs/mockup/AURA_mockup_especificacion.pdf`.
- Pruebas (medido): `mockup/pruebas/criterios.spec.js`, 10/10 aprobadas el 28/10/2026. Salidas en
  `mockup/pruebas/salida/` (fuera de git).
- Informe: `docs/decisiones/sesiones/2026-10-28_pc-principal_mockup-app.md`.
- Licencias:
  - GSAP: Standard "No Charge" License (gsap.com/standard-license).
  - Vite y three.js: MIT.
  - Inter: SIL OFL 1.1.
  - Modelo de la figura: Quaternius, CC0.

## Cómo revertir
Borrar `mockup/` (y `datos/procesados/mockup/`). La escena original de `analisis/escena_k002/` no depende del mockup.
Si se adopta otro stack, crear una ADR que reemplace a esta.
