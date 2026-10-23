# Arquitectura de estado y alertas (alcance recortado para la entrega del 30/10)

```
Placa B (wifi_sensing) --USB--> C:\aura\analisis\puente.py (PC) --HTTPS--> Firebase (Spark) --> App Android
   líneas HMS:{json}            estado + latido + push al tema         Realtime DB + FCM     1 pantalla
```

Principios:
- **Solo viajan el estado y sus marcas de tiempo.** Nunca CSI ni valores crudos.
- **Plan Spark:** sin Cloud Functions ni facturación. Toda la lógica corre en `puente.py`, con
  `firebase-admin` y una cuenta de servicio.
- **Demo con una sola placa (B) y el hotspot de un celular.** Las placas A y C no se usan en la demo: su
  firmware (`csi_send`) transmite fijo en el canal 11. Quedan para la parte de investigación con
  `csi_send`/`csi_recv`.

### Recortes respecto del diseño anterior

| Eliminado | Reemplazo |
|---|---|
| Servicio en primer plano de vigilancia | La app compara el latido con la hora del servidor **solo mientras está abierta** |
| Historial del día en la app | — (las alertas quedan en RTDB para el informe) |
| Configuración del umbral en la app | Constante al inicio de `puente.py` |
| Tokens FCM por usuario | **Tema de FCM** `aura_hab1`: la app se suscribe y el puente publica |

---

## 1. Esquema de Realtime Database

```
/sensores/hab1/
    estado:  { estado: "CALIBRANDO" | "MOVIMIENTO" | "PRESENCIA_QUIETA" | "VACIA" | "SIN_DATOS",
               movimiento: bool, presencia: bool, desde: <ts servidor>, t_pc: <unix s> }
    latido:  { ts: <ts servidor>, ultimo_dato_placa: <unix s> }
    alertas/<pushId>: { tipo: "quietud" | "sensor_sin_datos", ts: <ts servidor>, mensaje, t_pc }
```

- Las `ts` se escriben como `{".sv": "timestamp"}` (hora del servidor de Firebase).
- La app solo **lee** `estado` y `latido`. No escribe nada en la base.
- `alertas` lo escribe el puente para dejar constancia en el informe; la app no lo muestra.

## 2. `puente.py` (PC)

Constantes al inicio del archivo (se editan ahí; no hay configuración en la app):

```python
PEER = "AP"                      # canal evaluado (BSSID del hotspot)
UMBRAL_QUIETUD_MIN = 2           # alerta (a): corto para la demo
SIN_DATOS_S = 30                 # alerta (b)
LATIDO_S = 60
TEMA_FCM = "aura_hab1"
SENSOR_ID = "hab1"
```

Funcionamiento:
1. Abre el puerto de la placa B igual que `capturar.py` (DTR/RTS en bajo) y lee líneas. Solo interpreta
   las `HMS:{...}` con `"type":"sample"` y `"peer":"AP"`. Usa `motion_status`, `presence_someone_status`,
   `presence_ready` e `init_stage_name`. El formato está verificado en
   `C:\aura\firmware\wifi_sensing\main\web_serial_monitor.c`, función `send_channel_sample`.
2. Deriva el estado:
   - `CALIBRANDO` mientras `init_stage_name != "STABLE"` o `presence_ready` sea falso.
   - `MOVIMIENTO` si `motion_status` es verdadero.
   - `PRESENCIA_QUIETA` si no hay movimiento pero `presence_someone_status` es verdadero.
   - `VACIA` en el resto de los casos.
3. **Escribe en RTDB solo cuando el estado cambia.** Además manda un **latido cada 60 s**.
   **Retención de MOVIMIENTO:** en S001, ACTIVE llegó en ráfagas de 40–500 ms (134 cambios en 3 min, con
   `active_filter_ms = 300`). Para no saturar la base ni la app, el puente mantiene `MOVIMIENTO` hasta
   `RETENCION_MOV_S = 10` segundos después del último `motion_status = true`.
4. **Alerta (a), quietud prolongada:** si el estado es `PRESENCIA_QUIETA` durante `UMBRAL_QUIETUD_MIN`
   minutos seguidos, escribe en `alertas` y publica un push al tema. Se dispara una vez por episodio y se
   rearma al salir de ese estado.
5. **Alerta (b), placa sin datos:** si no llega ninguna línea `HMS:` en `SIN_DATOS_S` segundos, o el
   puerto da error (cable suelto, placa colgada), publica el estado `SIN_DATOS` y la alerta
   `sensor_sin_datos` con su push. Luego intenta reabrir el puerto cada 5 s.
6. **Push:** `firebase_admin.messaging.send(Message(topic=TEMA_FCM, notification=..., android=AndroidConfig(priority="high", notification=AndroidNotification(channel_id="alertas"))))`.
   Sin gestión de tokens.
7. Opciones de línea de comandos:
   - `--guardar-crudo`: guarda cada línea en `C:\aura\datos\crudos\<id>.csv` con el formato de
     `capturar.py`, para evaluar sin abrir el puerto dos veces.
   - `--recalibrar`: al arrancar envía `HMSCMD RESET_BASELINE` a la placa.
8. **Teclas mientras corre** (la consola de `puente.py`). Como el puente tiene el COM abierto, el
   monitor web no puede usarlo; los comandos a la placa se envían desde el propio puente:
   - **R** → escribe `HMSCMD RESET_BASELINE\n` en el puerto serie, publica el estado `CALIBRANDO` y
     anula cualquier alerta (a) en curso. Al llegar a STABLE **entrena la presencia** (`HMSCMD TRAIN_START AP`,
     ~20 s con la zona vacía, `HMSCMD TRAIN_STOP AP`). **Sin entrenamiento la presencia nunca se activa**:
     `esp-radar` devuelve `waveform_wander = 0` si no tiene muestras de entrenamiento
     (`csi_detection_compute_wander`, `esp_radar.c`), y los umbrales se guardan solo en RAM, así que hay
     que entrenar en cada arranque. Verificado en la sesión S001: 2.892 muestras con `wander_value = 0`. Confirma en pantalla con la respuesta de la placa
     `HMS:{"type":"ack","cmd":"RESET_BASELINE","ok":true,...}`, cuyo formato está verificado en
     `send_ack()` de `web_serial_monitor.c`. Si en 3 s no llega el `ack`, muestra
     "La placa no confirmó RESET_BASELINE".
   - **Q** → cierra el puerto y sale ordenadamente (último latido incluido).
   - Implementación en Windows: `msvcrt.kbhit()` y `msvcrt.getwch()` dentro del bucle de lectura, que
     no bloquea gracias a `timeout` en el puerto. No se necesitan bibliotecas extra.
9. Credenciales en `C:\aura\secretos\firebase-admin.json`. La URL de la base va en
   `C:\aura\secretos\config.json`. Ambos están fuera de git.

Dependencia nueva: `firebase-admin`. Se agregará a `requirements.txt` cuando lo autorices.

### Limitaciones declaradas de la lógica de alerta

- **La alerta (a) no distingue entre reposo y caída.** Una persona que lee, duerme o está desmayada
  produce el mismo patrón: presencia sin movimiento. La alerta solo dice "hay alguien que no se mueve
  desde hace N minutos". Para distinguir una caída haría falta otra señal (por ejemplo, la respiración, el
  PIR o el micrófono previstos para después).
- Si el detector de presencia **no** detecta a la persona quieta (falso negativo), el estado será
  `VACIA` y la alerta (a) no se dispara. Las sesiones `sentada_quieta` de `evaluar_deteccion.py` miden
  justamente esto.
- Con `UMBRAL_QUIETUD_MIN = 2` la alerta es deliberadamente sensible, para la demo. No es un valor
  clínico.

## 3. Desconexión: qué cubre la demo

| Falla | Detección | Cubierto en la demo |
|---|---|---|
| Placa colgada, cable suelto (PC viva) | `puente.py`, alerta (b), ~30 s, con push | Sí |
| PC apagada, puente caído o sin internet | La app, comparando `latido.ts` con la hora del servidor (`.info/serverTimeOffset`), **solo con la app abierta**; muestra "Sin conexión con el sensor" si pasan más de 3 min | Parcial |
| Lo mismo, con la app cerrada o en segundo plano | Nadie | **No. Limitación declarada** |

Con el plan Spark no hay un proceso en la nube que vigile el latido. Cubrir ese último caso requiere
Cloud Functions (plan Blaze), un vigilante en segundo plano en la app o que la placa escriba
directamente en Firebase. Las tres opciones quedan fuera del alcance del 30/10.

## 4. App Android (mínima)

- Kotlin + Jetpack Compose (Material 3), `minSdk 26`, `targetSdk 35`. Firebase BoM con `firebase-auth`,
  `firebase-database` y `firebase-messaging`. Se compila con Android Studio 2025.3 (JBR 21).
- **Autenticación anónima automática** (`FirebaseAuth.signInAnonymously()` al abrir la app), sin
  pantalla de login. Las reglas exigen `auth != null` para leer `/sensores`.
- **Pantalla única de estado:** el estado con color (MOVIMIENTO / PRESENCIA_QUIETA / VACÍA / CALIBRANDO /
  SIN DATOS), "desde hace X min", la antigüedad del último latido y el aviso "Sin conexión con el sensor"
  si supera 3 min (revisado cada 10 s mientras está abierta).
- **Notificaciones:** la app pide `POST_NOTIFICATIONS` en Android 13+, crea el canal `alertas` y se
  suscribe al tema `aura_hab1` al iniciar sesión. Con la app en segundo plano, Android muestra el push
  solo. En primer plano, `onMessageReceived` lo muestra como notificación local.

**Estructura del proyecto** (`C:\aura\app\`):

```
C:\aura\app\
├── settings.gradle.kts
├── build.gradle.kts
├── gradle.properties
├── gradle\libs.versions.toml
├── gradle\wrapper\...
└── app\
    ├── build.gradle.kts                 plugins: android, kotlin, compose, google-services
    ├── google-services.json             (de Firebase; fuera de git)
    └── src\main\
        ├── AndroidManifest.xml          INTERNET, POST_NOTIFICATIONS, servicio FCM
        ├── res\                          ícono, strings (es), colores
        └── java\pe\aura\monitor\
            ├── AuraApp.kt               Application: canal "alertas"
            ├── MainActivity.kt          inicio anónimo, permiso de notificaciones, suscripción al tema
            ├── datos\EstadoRepositorio.kt   estado, latido y offset del servidor como Flow
            ├── ui\EstadoScreen.kt + EstadoViewModel.kt
            ├── ui\tema\
            └── notif\AuraMessagingService.kt   onMessageReceived (primer plano)
```

Paquete: **`pe.aura.monitor`**. Debe coincidir con el registrado en Firebase.

## 5. Seguridad

- Las reglas de RTDB cierran todo, salvo la **lectura** de `/sensores` para usuarios autenticados
  (`auth != null`; la app usa autenticación anónima). **Limitación declarada:** quien extraiga la
  configuración del APK puede obtener un usuario anónimo y leer el estado. Lo aceptamos porque solo hay
  estado y marcas de tiempo, sin datos personales. Nadie puede escribir sin la clave de servicio. El puente usa el SDK de administrador, que no pasa por las reglas. Las reglas exactas están en
  `C:\aura\docs\guia_firebase.md`.
- **Temas de FCM:** cualquier instalación de la app del mismo proyecto podría suscribirse al tema, pero
  **solo quien tiene la clave de servicio puede publicar**. Los mensajes no llevan datos personales
  (solo "quietud prolongada en hab1" o "sensor sin datos").
- `C:\aura\secretos\` y `google-services.json` están en `.gitignore`.

## 6. Estimación de esfuerzo recalculada (hoy es jueves 22/10; entrega el viernes 30/10)

| # | Componente | Esfuerzo | Depende de | Riesgo |
|---|---|---|---|---|
| 1 | ESP-IDF v5.5 con EIM (lo haces tú) | 0,5 d | — | Bajo |
| 2 | Compilar `wifi_sensing`, grabar B, probar con el hotspot | 0,5–1 d | 1 | **Alto**: la calidad real de la detección es incierta |
| 3 | Calibración y sesiones de evaluación (vacía / caminando / sentada quieta) | 1 d | 2 | Medio |
| 4 | Firebase: proyecto, usuario, reglas, app registrada, clave (lo haces tú) | 0,5 d | — | Bajo |
| 5 | `puente.py` (estado, latido, alertas a y b, push al tema, `--guardar-crudo`, `--recalibrar`) | 0,75 d | 2, 4 | Bajo |
| 6 | App: inicio anónimo, pantalla de estado, latido con la app abierta, permiso, tema | 1–1,25 d | 4 | Medio |
| 7 | Integración, ensayo en el local, video de respaldo | 0,75 d | 5, 6 | Medio |
| 8 | Documentación e informe | 0,5 d | todo | Bajo |
|   | **Total** | **≈ 5,5–6,5 días** | | **Holgura: ~1,5–2,5 días** |

Fuera de la ruta crítica, si sobra tiempo: la investigación con A y C (`csi_send`/`csi_recv`) y la
respiración.

**Calendario sugerido:**

| Día | Trabajo |
|---|---|
| Jue 22 | 1 (IDF) y 4 (Firebase) |
| Vie 23 | 2: compilar, grabar B, primera prueba con el hotspot. **Decisión de seguir o pasar a la alternativa** (`evaluacion_wifi_sensing.md`) |
| Sáb 24 | 5 (`puente.py`) y primeras sesiones de 3 |
| Dom 25 – Lun 26 | 6 (app) |
| Mar 27 | 7 (integración) y sesiones finales de 3 |
| Mié 28 | `evaluar_deteccion.py` con datos reales, video de respaldo |
| Jue 29 | Ensayo de la demo y 8 |
| Vie 30 | Entrega |
