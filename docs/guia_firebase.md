# Guía de Firebase (plan Spark gratuito) — arquitectura de dos vías

**Esta guía la sigues tú.** Yo no creo cuentas ni proyectos a tu nombre. Al final me pasas solo datos
que no son secretos: el ID del proyecto, la URL de la base y los **dos UID**. **Nunca me pegues
contraseñas ni claves privadas.**

Los nombres de los botones de la consola cambian a veces. Si alguno no coincide, busca el más parecido o
envíame una captura.

Cambios respecto de la versión anterior (22/10/2026):
- La placa escribe directamente en Firebase con **su propia cuenta** (correo y contraseña). No hay
  `puente.py` ni clave de servicio.
- **No hay acceso anónimo.** La app y el visor usan **tu** cuenta.
- Las reglas distinguen **tu UID** y el **UID de la placa**.

---

## 1. Cuenta de Google del proyecto

1. Usa una cuenta **dedicada al proyecto**, no la personal. Por ejemplo: `aura.proyecto.<algo>@gmail.com`.
   Créala en <https://accounts.google.com/signup>.
2. Activa la **verificación en dos pasos** (Cuenta de Google → Seguridad).

## 2. Proyecto de Firebase

1. Entra a <https://console.firebase.google.com> con la cuenta del proyecto.
2. **Crear un proyecto**. Nombre: `aura-csi`. **Anota el ID del proyecto** que propone Firebase.
3. **Google Analytics: desactívalo.**
4. El proyecto queda en el **plan Spark (sin costo)**. **No agregues tarjeta ni cambies a Blaze.**

## 3. Realtime Database

1. **Compilación** → **Realtime Database** → **Crear una base de datos**.
2. Ubicación: **Estados Unidos (us-central1)**.
3. Reglas: **Comenzar en modo bloqueado**. Las definitivas se ponen en el paso 6.
4. **Anota la URL de la base** (por ejemplo, `https://aura-csi-1a2b3-default-rtdb.firebaseio.com`).

## 4. Authentication: correo y contraseña, con dos usuarios

1. **Compilación** → **Authentication** → **Comenzar**.
2. Pestaña **Método de acceso** → **Correo electrónico/contraseña** → **Habilitar** (solo la primera
   opción, no "vínculo por correo") → **Guardar**.
   - **No habilites "Anónimo".** Si ya estaba habilitado de la versión anterior, **inhabilítalo**.
3. Pestaña **Usuarios** → **Agregar usuario**, dos veces:

   | Usuario | Correo (ejemplo) | Contraseña | Para qué |
   |---|---|---|---|
   | **Tú** | `tu.correo@...` | una contraseña robusta | app, visor y scripts de la PC |
   | **La placa** | el correo que tú elijas (no hace falta que lo conozca nadie más) | una contraseña larga y aleatoria, **distinta** de la tuya | solo la placa |

   **Correo de la cuenta de la placa.** El sistema no depende de su dominio: lo que importa es el **UID**
   de la cuenta, que es el que aparece en las reglas. El correo y la contraseña solo se escriben en la
   placa (`cargar_credenciales.py`) y nunca en el repositorio ni en los registros.
   - Recomendación (opcional): un correo **sin buzón**, por ejemplo en un dominio reservado `.invalid`
     (RFC 2606 y RFC 6761). Así nadie puede restablecer la contraseña de la placa por correo. Si usas un
     correo con buzón, protege ese buzón.
   - La contraseña de la placa se cambia desde la consola (Authentication → Usuarios → la cuenta →
     Restablecer contraseña o Editar) y luego se carga con
     `cargar_credenciales.py --puerto COM5 --solo fb_pass`.
   - Si una placa se pierde: **Inhabilitar cuenta** en la consola.
   - Estado al 23/10/2026: la cuenta de `placa-b` es la del UID `RSZSiH4Q…Ex22` (el de las reglas).

4. **Dónde ver los UID:** en esa misma pestaña **Usuarios**, columna **"UID de usuario"** (una cadena
   larga). Pasa el mouse sobre ella y usa el botón de copiar. **Anota los dos.** Los UID no son secretos.
5. Pestaña **Configuración** → **Acciones del usuario** → **desmarca "Habilitar creación (registro)"** →
   Guardar. Así nadie puede crearse otra cuenta con la configuración de la app.

## 5. Clave de API web (no es secreta, pero no la publiques)

**Configuración del proyecto** (engranaje) → pestaña **General** → **Tus apps** → app web → objeto de
configuración. Guárdalo como JSON en `C:\aura\secretos\firebase_web.json` (fuera de git), con los
**nombres de la consola**:

```json
{"apiKey": "AIza...", "authDomain": "...", "databaseURL": "https://aura-csi-default-rtdb.firebaseio.com",
 "projectId": "aura-csi", "storageBucket": "...", "messagingSenderId": "...", "appId": "..."}
```

Los scripts usan `apiKey` y `databaseURL`; también aceptan `api_key` y `db_url`.
`analisis\fb_rest.py` (`cargar_config`) valida el formato. `cargar_credenciales.py` toma de ahí
`fb_api_key` y `fb_db_url` para cargarlos en la placa.

## 6. Reglas definitivas

1. Genera el archivo de reglas con los dos UID, en una PowerShell:

   ```powershell
   C:\aura\analisis\.venv\Scripts\python.exe C:\aura\firebase\preparar_reglas.py --uid-usuario TU_UID --uid-placa UID_DE_LA_PLACA --salida C:\aura\firebase\reglas_publicar.json
   ```

2. **Prueba ese archivo exacto en el emulador** antes de publicarlo (39 casos; registra su SHA-256):

   ```powershell
   C:\aura\analisis\.venv\Scripts\python.exe C:\aura\analisis\pruebas\t5_reglas.py --reglas C:\aura\firebase\reglas_publicar.json --uid-usuario TU_UID --uid-placa UID_DE_LA_PLACA
   ```

3. **Realtime Database** → pestaña **Reglas** → borra todo, pega el contenido de
   `C:\aura\firebase\reglas_publicar.json` **sin modificarlo** → **Publicar**. Si cambias algo, vuelve al
   paso 2.

Estado al 23/10/2026: `reglas_publicar.json` generado con el UID de la persona `26Iu3XfM…ZRQ2` y el de
`placa-b` `RSZSiH4Q…Ex22`. SHA-256 `d2ce131e75b537e1aa4334ff3f6d0b6718669222ba52483b07031daa0d2bad84`.
**T5: 39/39.** Pendiente de que lo publiques.

Qué permiten:

| Ruta | Lee | Escribe |
|---|---|---|
| `/sensores/<id>` (estado, latido, comando) | **solo tú** | **solo la placa** (con estructura validada) |
| `/crudo/<id>/<bloque>` | **solo tú** | **solo la placa**; tú puedes **borrar** bloques sueltos (no escribir datos) |
| `/comandos/<id>/<cmd>` | **solo la placa** | **solo tú**: comandos permitidos con `t` = hora del servidor |
| cualquier otra ruta | nadie | nadie |

**Comprobación rápida en el Simulador** de la pestaña Reglas (la matriz completa está en
`plan_pruebas.md`):
- **lectura** de `/sensores/hab1` sin autenticar: **denegada**;
- **lectura** de `/sensores/hab1` autenticado como tu UID: **permitida**;
- **escritura** en `/sensores/hab1/estado` como tu UID: **denegada**.

## 7. Registrar la app Android

1. **Configuración del proyecto** → **General** → **Tus apps** → ícono **Android**.
2. Nombre del paquete: **`pe.aura.monitor`**. Sobrenombre: `AURA Android`. SHA-1 vacío.
3. **Descargar google-services.json** y guardarlo en `C:\aura\secretos\google-services.json`.
4. Salta los pasos del SDK (**Siguiente** hasta terminar).

La app inicia sesión con **tu** correo y contraseña (pantalla de login), lee `/sensores/hab1` y escribe
`/comandos/hab1`.

## 8. Cloud Messaging y clave de servicio: NO se usan en esta arquitectura

- La placa no puede enviar push sin una clave de servicio, que **no debe** estar en el dispositivo. Por
  eso la alerta se ve en la app abierta. Es una limitación declarada en `arquitectura_dos_vias.md`.
- **No generes una clave de servicio.** Si ya generaste una para el diseño anterior, guárdala en
  `C:\aura\secretos\` o, mejor, **revócala**: Google Cloud Console → IAM y administración → Cuentas de
  servicio → `firebase-adminsdk-...` → Claves → borrar.

## 9. Qué me envías al terminar

```
ID del proyecto:   aura-csi-xxxxx
URL de la base:    https://aura-csi-xxxxx-default-rtdb.firebaseio.com
UID usuario (tú):  xxxxxxxxxxxxxxxxxxxxxxxxxxxx
UID placa:         yyyyyyyyyyyyyyyyyyyyyyyyyyyy
Confirmaciones:    correo/contraseña habilitado, anónimo deshabilitado, registro deshabilitado,
                   reglas publicadas, C:\aura\secretos\firebase_web.json creado
```

La contraseña de la placa **no me la pases**: la escribes tú en `cargar_credenciales.py`, que la pide sin
eco y la envía por USB a la NVS de la placa.

## Límites del plan Spark

- Realtime Database: 1 GB guardado, 10 GB/mes de descarga y 100 conexiones simultáneas. `/crudo` ocupa
  ~12 MB/día: descárgalo y bórralo después de cada sesión con `descargar_crudo.py` (sección 5 de
  `arquitectura_dos_vias.md`).
- Authentication por correo y contraseña: sin costo.
- No hay Cloud Functions: la lógica está en la placa.
