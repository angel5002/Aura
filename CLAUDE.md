# CLAUDE.md — Proyecto AURA (WiFi sensing con ESP32-C5)

Este archivo lo lee Claude Code al iniciar cada sesión en este repositorio. Tiene prioridad sobre
cualquier costumbre general. Si algo de aquí contradice una instrucción explícita de Deisy en la
sesión, manda la instrucción de Deisy, y se registra como decisión (ver sección 4).

Idioma: **responder siempre en español**, claro y sin jerga innecesaria.

---

## 1. Antes de hacer cualquier cosa: identifica dónde estás

El proyecto se trabaja en más de un equipo. **No asumas que estás en la PC principal.** Al iniciar la
sesión ejecuta `hostname`, `whoami` y comprueba qué rutas existen, y clasifica el equipo:

| Equipo | Cómo reconocerlo | Qué hay | Qué NO hay |
|---|---|---|---|
| **PC principal** (escritorio HP, Ethernet) | `hostname` = `DESKTOP-7O57OU0` y `whoami` = `desktop-7o57ou0\usuario`; existe `C:\aura` con `.git`, `C:\esp\v5.5.6\esp-idf` y `C:\aura\analisis\.venv` | repo completo, ESP-IDF v5.5.6, firmware, `secretos\`, datos crudos, Firebase CLI local | — |
| **Laptop de campo** (prestada, usuario `user`) | existe `C:\Users\user\Desktop\CSI-Aura\aura_kit` y NO existe `C:\aura` | solo el kit de captura (lee su `PARA_CLAUDE_CODE.md`) | ESP-IDF, firmware, secretos, git del proyecto |
| **Otro equipo / PC nueva** | ninguna de las anteriores | lo que se haya clonado | asumir nada; ver sección 7 (migración) |

Reglas según el equipo:
- **Solo en la PC principal** se compila o graba firmware y se tocan `secretos\`.
- En la laptop de campo se captura y visualiza; no se modifica el kit salvo pedido expreso.
- En cualquier equipo que no sea la PC principal: **dilo al inicio de tu primera respuesta**
  ("Estoy en: <equipo>, <ruta>") y no ejecutes nada que dependa de rutas de otro equipo.
- Registra el equipo en el informe de sesión (sección 5).

## 2. Qué es el proyecto (resumen)

AURA: sensado WiFi (CSI) con placas DFRobot FireBeetle 2 ESP32-C5 para detectar actividad humana en
casa sin cámaras ni dispositivos puestos. Tres fines: investigación (sensado aplicado a salud),
docencia (Ciencia de Datos, Física) y la Científica Hack X 2026 (ODS 3, entrega 30/10/2026).

Estado al 26/10/2026 (detalle en `docs/decisiones/0000_reporte_inicial.md`):
- **Movimiento:** funciona (0,4 % de falsas alarmas en crudo, una sesión de sala vacía).
- **Presencia quieta:** NO es fiable con esp-radar (100 % de falsos positivos por deriva). El visor la
  muestra como "no disponible" (ADR-0018). Se está diseñando un detector propio (ADR-0019, propuesta).
- **Firmware de referencia:** `aura_nodo` 0.1.3 en modo solo local (sin `fb_pass`).
- **Nube (Firebase):** diseñada y probada parcialmente; en pausa por un problema de memoria/pila de red
  sin causa identificada (ADR-0009, ADR-0010).

Placas: A `D0:CF:13:E8:FF:88`, **B `3C:DC:75:8A:6F:CC` (la única con firmware AURA)**, C `3C:DC:75:8A:6D:24`.

## 3. Reglas no negociables

**Seguridad y datos**
1. Pedir confirmación antes de **instalar** programas, **grabar** firmware, **borrar** flash o archivos.
2. Antes de grabar una placa: `read_mac` y comprobar la MAC esperada. Si no coincide, detenerse.
3. **Ningún secreto** en git, en `sdkconfig.defaults`, en registros ni en pantalla. Credenciales solo en
   la NVS de la placa (`cargar_credenciales.py`) y en `secretos\` (fuera de git). Nunca
   `idf.py save-defconfig` con credenciales cargadas.
4. Nunca pedir, mostrar ni registrar contraseñas. Deisy las escribe ella misma.
5. Datos crudos (`datos\crudos\`, `registro_sesiones.csv`) fuera de git: son datos de personas.
6. No subir datos a ninguna nube salvo lo diseñado para Firebase (resúmenes) y con autorización.
7. El scraper de ofertas de Deisy está **fuera de este proyecto**: no tocarlo ni proponer cambios.
8. Las cuentas (Google, Firebase u otras) las crea **Deisy**; Claude nunca crea cuentas.
9. En `registro_sesiones.csv` y en los nombres de archivo se usan **códigos**, nunca nombres de personas.
10. No crear archivos fuera de `C:\aura`, salvo en carpetas temporales del sistema. Usar siempre rutas
    absolutas bajo `C:\aura` (la carpeta donde se abre la sesión puede ser otra).

**Rigor**
11. Una prueba fallida se registra como **FALLIDA**. Nunca se cambia un criterio para que apruebe; si un
    criterio parece mal planteado, se propone el cambio y se registra como decisión.
12. Todo firmware nuevo pasa T1–T3, T3b y **D0 (prueba de humo en la placa)** antes de cualquier otra
    prueba. Cada versión se archiva en `firmware\versiones\<versión>` y se etiqueta en git.
13. **D0**: la placa arranca, no se reinicia durante 2 minutos e informa su memoria
    (`analisis\pruebas\d00_humo.py`, escuchando sin reiniciar por RTS).
14. Reiniciar la placa con el comando de consola `AURA REBOOT`, no con la secuencia RTS (acordado el 23/10/2026).
15. Distinguir siempre: **medido** / **estimado** / **inferido** / **no verificado**. Las pruebas con
    datos sintéticos demuestran que el código corre, no que funciona.
16. No afirmar capacidades no demostradas (presencia quieta, respiración, alertas sin PC).
17. No inventar formatos de datos: los lectores (parsers) se derivan de líneas reales de la placa o del
    código fuente.
18. Ante una falla: mostrar el error completo y proponer una solución; no reintentar en bucle.

**Trabajo con Deisy**
19. Sesiones a distancia: nunca programar horas ni iniciar cuentas regresivas sin su **"listo"**; el
    plan empieza al menos 2 minutos después.
20. Avisar con anticipación cualquier acción física que deba hacer ella, y esperar confirmación.
21. Los comandos de administrador (firewall, red, instalación como administrador) los ejecuta Deisy.
22. Editar CSV y archivos de texto con Python (UTF-8 sin BOM). PowerShell 5.1 agrega BOM o UTF-16.
23. Informes al final: breves, con qué se hizo, qué falló, qué falta y qué decisiones se registraron.

## 4. Registro de decisiones (obligatorio)

Objetivo: que cualquier persona (o Claude en otro equipo, meses después) sepa **qué se decidió, por qué,
qué se descartó y con qué evidencia**. Carpeta: `docs/decisiones/`.

### 4.1 Qué se registra como ADR (Architecture Decision Record)
Crea un ADR cuando la decisión cumpla **al menos una** de estas condiciones:
- cambia la arquitectura, el firmware, el formato de datos, la seguridad o la nube;
- elige entre alternativas con consecuencias (versión de una herramienta, plataforma, algoritmo,
  parámetro de memoria, protocolo de prueba, criterio de aceptación);
- descarta algo que se intentó (también es decisión, y es la más útil de recordar);
- la tomó Deisy explícitamente ("vamos con X", "no hagas Y");
- afecta lo que se puede afirmar en el hackathon, en clases o en una publicación.

No es ADR: renombrar una variable, arreglar un error tipográfico, un ajuste sin alternativas reales.
Eso va, si acaso, a la bitácora.

### 4.2 Cómo se registra
1. Copia `docs/decisiones/plantilla_adr.md` a `docs/decisiones/adr/ADR-NNNN-titulo-corto.md`
   (número correlativo, cuatro dígitos, título en minúsculas con guiones).
2. Llena todas las secciones. **Evidencia con rutas reales** (archivo de resultados, commit, sesión).
3. Estado:
   - `Propuesta`: la sugiere Claude y Deisy aún no la aprueba;
   - `Aceptada`: Deisy la aprobó (anota la fecha);
   - `Reemplazada por ADR-XXXX`: no se borra ni se reescribe; se crea otra y se enlazan;
   - `Descartada`: se evaluó y no se adoptó (dejar por qué).
4. Agrega una línea en `docs/decisiones/INDICE.md`.
5. Si la decisión se toma en un equipo que no es la PC principal y allí no está el repo, escríbela en
   el informe de sesión y, al volver a la PC principal, se pasa a ADR.
6. Nunca reescribas la historia de un ADR aceptado: si cambia, se reemplaza.

### 4.3 Bitácora
`docs/decisiones/bitacora.md`: una línea por evento menor (fecha, equipo, qué, por qué). Sirve para lo
que no llega a ADR pero conviene recordar (p. ej., "se reinició la placa con AURA REBOOT antes de D1").

## 5. Informe de sesión (al terminar cada sesión de trabajo)

Archivo: `docs/decisiones/sesiones/AAAA-MM-DD_<equipo>_<tema>.md`, con:
- equipo, ruta de trabajo y commit al inicio (el commit final se consulta con `git log`; no se hacen
  commits extra para anotar su hash);
- objetivo de la sesión y qué se hizo;
- resultados (con medido/estimado), pruebas aprobadas/fallidas;
- ADR creados o modificados;
- pendientes y riesgos abiertos.

Al iniciar una sesión, lee: este archivo, `docs/decisiones/INDICE.md`, el último informe de sesión y
`docs/pendientes_nube.md` si la tarea toca la nube.

## 6. Mapa del repositorio (PC principal)

| Ruta | Contenido |
|---|---|
| `firmware\aura_nodo\` | firmware propio (dos vías, OTA, NVS) |
| `firmware\versiones\` | binarios archivados por versión |
| `firmware\wifi_sensing\`, `csi_send\`, `csi_recv\` | copias de ejemplos de esp-csi (no se modifica `esp-csi\`) |
| `analisis\` | scripts de captura, análisis, pruebas (`pruebas\`) y `.venv` |
| `kit_captura\` | kit portátil para laptops con Windows |
| `firebase\` | reglas, emulador y pruebas T5 |
| `docs\` | guías, plan y resultados de pruebas, evaluación, decisiones |
| `secretos\` | **fuera de git**: credenciales y claves |
| `datos\crudos\`, `datos\procesados\` | **fuera de git** |

Notas técnicas de la PC principal:
- El `python.exe` de `analisis\.venv` es un lanzador: los sockets pertenecen al `python.exe` base de
  Python312, así que las reglas de firewall por programa deben apuntar a esa ruta.

## 7. Migración a otra PC

1. Clonar el repositorio (si no hay remoto, copiar con `git bundle`; ver ADR pendiente sobre remoto).
2. Instalar Python 3.12 (64 bits) y crear `analisis\.venv` con `requirements-lock.txt`.
3. Instalar ESP-IDF **v5.5.6** con EIM en `C:\esp` (ruta sin espacios, < 90 caracteres).
4. `secretos\` **no viaja por git**: copiarlo a mano por un medio seguro, o regenerar las claves.
5. Ejecutar `git safe.directory` si ESP-IDF se instaló como administrador.
6. Actualizar la tabla de la sección 1 con el nuevo equipo y registrar la migración en la bitácora.
