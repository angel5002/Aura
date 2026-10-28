# Mockup de la app AURA

App web móvil (390 × 844) que se compila a `app/`, la carpeta estática que monta `servidor.py` de Angel. Especificación:
`docs/mockup/AURA_mockup_especificacion.pdf`; decisión del stack: `docs/decisiones/adr/ADR-0025-stack-mockup-app.md`.

## Comandos (en `C:\aura\mockup`)
| Comando | Qué hace |
|---|---|
| `npm run datos` | Arma `publico/`: reproducción K002 (desde `datos/procesados`), holograma y three r128 en local |
| `npm run build` | `datos` + compila a `app/` |
| `npm run dev` | Servidor de desarrollo con recarga (puerto 5173, visible en la red local) |
| `npm run preview` | Sirve `app/` compilado (puerto 4173, visible en la red local) |
| `npm run pruebas` | Playwright: las 9 pantallas y los 10 criterios (evidencia en `pruebas/salida/`) |
| `python pruebas/resumen.py` | Resumen de la última corrida |

`app/`, `publico/` y `pruebas/salida/` están fuera de git: llevan datos derivados de K002.

## Datos
En vivo si `/ws` responde (contrato de Angel). Si no, la reproducción K002 (datos reales) y los escenarios
"normal", "respiración" y "caída" (fuente = demo). Ajustes de contrato propuestos: `docs/mockup/propuestas_para_angel.md`.

## Rutas
`#/inicio`, `#/hoy`, `#/asistente`, `#/gemelo`, `#/senal`, `#/alerta`, `#/emergencia`, `#/teleconsulta`, `#/dispositivo`.
`?quedarse=1` deja quieta la pantalla de inicio (para capturas). Los escenarios se lanzan desde
Dispositivo → "Mostrar panel técnico".
