# Grabación de `aura_nodo` en la placa B

Firmware: `C:\aura\firmware\aura_nodo` v0.1.1, ya compilado (23/10: orden de arranque corregido, línea HMS atómica fuera de la pila, autoprueba de rollback reforzada). **Tras grabar: D0 (prueba de humo) antes de cualquier otra prueba.** Placa B: COM5, MAC `3c:dc:75:8a:6f:cc`.

**Autorización (23/10/2026):** borrado completo y grabación de `aura_nodo` en la placa B, **solo si
`read_mac` confirma `3c:dc:75:8a:6f:cc`** (paso 1). Después, pruebas en el orden de `plan_pruebas.md`
(D11 va después de D2). **Si D2 o D9 fallan, se detiene la secuencia y se informa antes de seguir.**

Variantes ya compiladas (23/10, con las mismas correcciones), para grabar por OTA si hace falta:

| Variante | Versión | Para qué |
|---|---|---|
| `build_rollback` | 0.1.1-rollback | D8d |
| `build_rx64` | 0.1.1-rx64 | D9 |
| `build_bajo_ram` | 0.1.1-bajoram | si falta RAM |

## 0. Antes de empezar (Firebase, lo haces tú)

1. Sigue `C:\aura\docs\guia_firebase.md` hasta el paso 6: dos usuarios, reglas publicadas y
   `C:\aura\secretos\firebase_web.json` creado.
2. Ten a mano: SSID y contraseña de la red principal, SSID y contraseña del hotspot de respaldo, y correo
   y contraseña **de la cuenta de la placa**.
3. Firewall de Windows: la primera vez que `receptor_local.py` escuche por UDP, Windows preguntará si
   permite Python. Elige **solo "Redes privadas"**. Lo decides y aceptas tú.

## 1. Comprobar la placa (solo lectura)

En la PowerShell de ESP-IDF, con **solo la placa B** conectada:

```powershell
esptool.py --chip esp32c5 --port COM5 read_mac
```

Debe decir `BASE MAC: 3c:dc:75:8a:6f:cc`.

## 2. Por qué hace falta un borrado completo

La tabla de particiones cambia: la NVS pasa a 0xB000–0x1AFFF (64 KB) y se agregan `otadata`, dos ranuras
OTA y `coredump`. La NVS de `wifi_sensing` (0xB000, 24 KB) y su `phy_init` quedan dentro de la nueva NVS
con un formato incompatible. **Además, la NVS anterior puede guardar el SSID y la contraseña del WiFi**
que se cargaron por menuconfig (el ejemplo conectaba con almacenamiento en flash). Un borrado completo
evita errores de NVS y elimina esa copia de la credencial.

## 3. Borrado completo (BORRA TODA LA FLASH: requiere tu autorización)

```powershell
idf.py -C C:\aura\firmware\aura_nodo -p COM5 erase-flash
```

Se pierde `wifi_sensing` (se puede volver a grabar desde `C:\aura\firmware\wifi_sensing`) y la NVS.

## 4. Grabación (requiere tu autorización)

```powershell
idf.py -C C:\aura\firmware\aura_nodo -p COM5 flash
```

Graba el cargador (con vuelta atrás) en 0x2000, la tabla en 0xA000, `otadata` inicial en 0x1B000 y la
aplicación en `ota_0` (0x20000). Debe terminar con tres o cuatro `Hash of data verified.` y `Done`.

## 5. Primer arranque, sin credenciales

```powershell
C:\aura\analisis\.venv\Scripts\python.exe C:\aura\analisis\capturar.py --puerto COM5 --id-sesion A001 --duracion 40 --reiniciar
```

Esperado: un mensaje HMS `{"type":"arranque","ver":"0.1.0","particion":"ota_0",...}` y el aviso
`sin credenciales WiFi en NVS`. Así se verifica la consola USB y el reinicio por RTS, que se corrigió y
todavía no se ha probado.

## 6. Cargar las credenciales en NVS (por USB, sin eco)

```powershell
C:\aura\analisis\.venv\Scripts\python.exe C:\aura\analisis\cargar_credenciales.py --puerto COM5 --reiniciar
```

- Pide cada valor sin mostrarlo: `wifi1_ssid`, `wifi1_pass`, `wifi2_ssid`, `wifi2_pass`, `fb_email` y
  `fb_pass` (los de la **placa**), y `local_key` (pulsa Enter y se genera una aleatoria).
- `fb_api_key` y `fb_db_url` los toma de `C:\aura\secretos\firebase_web.json`.
- Muestra solo "guardada" o "ERROR" por clave y al final la lista de claves definidas, sin valores.
- La clave local queda en `C:\aura\secretos\clave_local.txt` (fuera de git) para los comandos y la OTA.
- Para comprobar sin cambiar nada: `cargar_credenciales.py --puerto COM5 --listar`.

## 7. Verificación: prueba D1

```powershell
C:\aura\analisis\.venv\Scripts\python.exe C:\aura\analisis\pruebas\d01_arranque.py --puerto COM5
```

## 8. Después de migrar (decisión tuya)

`C:\aura\firmware\wifi_sensing\sdkconfig` todavía tiene la contraseña del WiFi que pusiste en menuconfig
(la T3 lo informa). Está fuera de git. Si ya no vas a volver a compilar `wifi_sensing`, conviene
reemplazarla por el valor por defecto con `idf.py -C C:\aura\firmware\wifi_sensing menuconfig`. No lo
hago sin tu permiso.
