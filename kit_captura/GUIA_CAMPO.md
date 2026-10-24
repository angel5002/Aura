# Guía de campo (una página) — AURA en una laptop que no se probó antes

**Antes**: Python 3.12 de 64 bits instalado y `.venv` creado (GUIA.md, paso 1) y el kit en `C:\aura_kit`. Todo se ejecuta en PowerShell desde
`C:\aura_kit` con `.\.venv\Scripts\python.exe` (abreviado `py` abajo). **No hace falta ser administrador.**

**1. Verificar** — Placa conectada con cable USB-C **de datos** y laptop en la misma red que la placa:
`py scripts\verificar_kit.py` → debe terminar en `RESULTADO: TODO FUNCIONA` (si no, cada FALLA trae su solución).
El COM se detecta solo (VID 303A); con dos placas, añade `--puerto COMx`.

**2. Red** — Laptop y placa en la **misma red** (en el salón: el hotspot del celular).
IP de la placa: `py scripts\ip_placa_usb.py --reiniciar` → espera **1 min** (calibración).

**3. En vivo** (mapa de calor + señal + estado; graba todo):
`py scripts\visor.py --vivo --ip <IP> --puerto auto --id-sesion C001`
Teclas en la ventana: **E** entra a la zona · **S** sale · **M** marca libre.

**Si algo falla:**

| Problema | Qué hacer |
|---|---|
| No aparece `303A:1001` | Otro cable (muchos solo cargan) u otro puerto USB; desenchufar y volver a enchufar la placa |
| `ip_placa_usb.py` no encuentra la IP | La placa no conecta al WiFi: hotspot encendido y cerca, nombre/clave correctos (`cargar_credenciales.py --solo wifi1_ssid` / `wifi1_pass --reiniciar`); el respaldo tarda hasta ~1 min |
| El visor no muestra el mapa de calor | La laptop no está en la misma red que la placa (o la red aísla a los equipos): conecta la laptop al hotspot; si no se puede → **plan B** |
| Ventana de Seguridad de Windows | No hace falta permitir nada; ciérrala y mira si llegan datos |
| El visor se cierra o se cuelga | Volver a lanzarlo con **otro** `--id-sesion` (C002…): nunca se sobrescribe nada |

**Plan B — solo USB** (sin red, sin mapa de calor; señal y estado en vivo):
`py scripts\visor.py --vivo --puerto auto --id-sesion C001` — o sin ventana:
`py scripts\capturar.py --id-sesion C001 --duracion 1800 --teclas`

**Al terminar**: copiar `datos\crudos\` a tu memoria USB y borrarlo de la laptop ajena (datos de personas).
Montaje: placa y celular a **1,5–2 m**, celular fijo, la persona observada cerca de la línea que los une.
