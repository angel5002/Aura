# Prueba en un salón de clases (25/10/2026)

Salón con alumnos, ruido de personas y de dispositivos: no se puede apagar nada ni vaciar el salón. La prueba es de
**MOVIMIENTO** de una persona observada, con marcas de teclado (E/S/M). **Sin entrenamiento de presencia** (el salón
nunca está vacío). Firmware: aura_nodo 0.1.3 en modo solo local (sin `fb_pass`).

## A. Red: hotspot del celular

En el salón no está el WiFi de la casa. La placa tiene `wifi1` = casa y `wifi2` = hotspot.

- **Comportamiento con la 0.1.3** (del código): si `wifi1` no existe, hace 3 intentos fallidos (cada uno es un
  escaneo de todos los canales de 2,4 y 5 GHz) con esperas de 2 y 4 s, pasa a `wifi2`, espera 8 s y conecta. En
  casa, aun con la red presente, la conexión tarda ~13 s (medido en `M1_013_local.csv`). **Estimación: 45–70 s
  hasta tener IP en el hotspot**, pendiente de medir mañana. Además, en el respaldo **busca la red de casa cada
  15 min** (escaneo de ~2–4 s que interrumpe el CSI un momento).
- **Recomendado para el salón**: cargar el **hotspot como `wifi1`** y la casa como `wifi2`. Así conecta directo y
  no hay escaneos periódicos. Después de clase se restaura el orden.

**Prueba de mañana temprano en casa** (en la PC del proyecto, con la placa por USB y el hotspot ENCENDIDO):

1. Medir el paso al hotspot sin tocar credenciales (simulación):
   `python C:\aura\analisis\prueba_hotspot.py --puerto COM5 --modo sim --ip 192.168.0.13`
   Informa a los cuántos segundos quedó en `respaldo`. Es una simulación (cada intento fallido dura 3 s fijos);
   el caso real puede tardar más.
2. Cargar el orden del salón (escribes tú, sin eco, dos veces cada valor):
   `python C:\aura\analisis\cargar_credenciales.py --puerto COM5 --solo wifi1_ssid` (SSID del hotspot), luego
   `--solo wifi1_pass`, `--solo wifi2_ssid` (casa), `--solo wifi2_pass` (casa).
3. Medir el arranque real con el hotspot como principal:
   `python C:\aura\analisis\prueba_hotspot.py --puerto COM5 --modo reinicio` (debe decir `principal`).
4. Opcional, el caso real sin red principal: apaga el hotspot, reinicia la placa y vuelve a encender el hotspot
   cuando quieras: la placa no lo verá hasta su siguiente intento; anota el tiempo.
5. **Después de clase**: repite el paso 2 con el orden original (casa en `wifi1`, hotspot en `wifi2`).

Ventaja del hotspot en el salón: la placa y la laptop quedan en una red propia, aisladas de los broadcasts de la
red del colegio (la tormenta de ARP del 23/10 llegó por la red de la casa).

## B. Montaje

- **Placa y celular (hotspot) a 1,5–2 m**, a la misma altura (~1 m), con línea de vista. Con 0,8 m (S002) la señal
  directa dominaba y el detector no distinguió movimiento: no bajes de ~1,5 m. Si el espacio lo permite, 2–3 m.
- **Celular FIJO** toda la prueba (soporte o pegado a un mueble), cargando y con la pantalla apagada. No se usa
  para otra cosa: moverlo cambia el canal tanto como una persona.
- **Persona observada** moviéndose cerca de la **línea que une placa y celular** (a menos de ~1 m de ella). El resto
  de los alumnos, en lo posible, fuera de esa franja.
- Placa alimentada por la laptop (USB de datos, para grabar) o por un **power bank** (plan con celular).
- Tras encender la placa, esperar **1 minuto** sin tocar el montaje (calibración: STABLE).

## C. Visor EN VIVO (laptop, para proyectar)

Muestra el mapa de calor del CSI (26 subportadoras), la señal del detector con sus umbrales de entrada y salida, y un
indicador grande con el estado y "movimiento: SÍ/no". Probado el 24/10 con la placa (vía local por `--ip` + USB a la
vez, 0 % de pérdida). Graba mientras muestra.

1. Laptop conectada al **mismo hotspot** que la placa.
2. IP de la placa: `python scripts\ip_placa_usb.py --reiniciar` (reinicia la placa: espera 1 min).
3. Visor: `python scripts\visor.py --vivo --ip <IP> --puerto auto --id-sesion C001`
   - Graba `datos\crudos\C001.csv` (USB) y `C001_local.csv` (CSI crudo).
   - **Teclas** (con la ventana del visor activa): **E** = la persona observada entra a la zona, **S** = sale,
     **M** = marca libre. Se guardan en `C001_marcas.csv` con la hora de cada pulsación y se ven arriba a la izquierda.
   - Sin red (plan B): `python scripts\visor.py --vivo --puerto auto --id-sesion C001` (señal y estado por USB, sin
     mapa de calor).
   - Para cerrar: cerrar la ventana (o Ctrl+W).
4. Después: `python marcas_a_etiquetas.py --id-sesion C001` y `python evaluar_deteccion.py --sesiones C001`
   (en la PC del proyecto). E→S cuenta como "caminando"; S→E como "vacia", que aquí significa **"persona observada
   fuera de la zona"** (el salón sigue ocupado: es una prueba de movimiento, no de presencia).

## D. Etiquetado con teclas, guía de campo y plan B

- Teclas E/S/M en el visor en vivo (arriba) o, sin visor, en la captura de consola:
  `python scripts\capturar.py --id-sesion C001 --duracion 1800 --teclas` (con esa ventana activa).
- Guía de campo de una página: `kit_captura\GUIA_CAMPO.md`. Plan B: solo USB (capturar.py o el visor con `--puerto`).

## E. Con celular, sin laptop

| Opción | Qué necesitas | En vivo | Qué se guarda | Después |
|---|---|---|---|---|
| **1. USB OTG + terminal serie** | Adaptador/cable OTG USB-C a USB-C de datos; app de terminal serie con soporte **CDC/ACM** | Líneas de texto (HMS); sin gráficos | Archivo de texto con las líneas, **con hora** si la app la agrega | `convertir_log_celular.py` → `visor.py --reproducir` (señal y estado; sin mapa de calor) |
| **2. UDP (vía local) en el celular** | **Termux** (F-Droid) con Python; copiar `receptor_local.py` y `aura_proto.py` | Texto: tasas y pérdida | El mismo CSV que en la laptop (`*_local.csv`, con CSI crudo) | `visor.py --reproducir` directo (panel completo con mapa de calor) |
| **3. Celular solo como hotspot** | El hotspot y la placa con power bank | Nada en el celular | Nada (la placa no guarda datos) | Solo sirve junto con la laptop o con la opción 2 |

**Verificación de apps (24/10):**
- **Termux**: verificado. Código abierto (GPLv3), distribuido por F-Droid ([f-droid.org/packages/com.termux](https://f-droid.org/en/packages/com.termux/));
  F-Droid recomienda instalarlo con su cliente; versión sugerida 0.118.3 (29/05/2025). `pkg install python python-numpy`
  según guías comunitarias ([Termux-Science](https://github.com/juniperfdel/Termux-Science)): **confirmar mañana**.
- **Terminal serie USB**: la app **"Serial USB Terminal"** de Kai Morich existe ([ficha en BlueStacks](https://www.bluestacks.com/campaign/de.kai_morich.serial_usb_terminal/es));
  se basa en la librería abierta [usb-serial-for-android](https://github.com/mik3y/usb-serial-for-android), que detecta
  dispositivos **CDC/ACM** por tipo de interfaz y funciona por USB OTG sin root. **NO verificado**: que reconozca el
  USB nativo del ESP32-C5 (VID 303A) ni que guarde a archivo con hora (no pude leer su ficha de Google Play).
- **Apps de UDP**: no encontré una app de Android verificable que mande el `SUB` periódico que exige la placa y guarde
  lo recibido; **no recomiendo ninguna**. La opción UDP verificable es Termux + `receptor_local.py`.

**Plan de prueba en casa (≈20 min, antes de salir):**
1. *Opción 2 (Termux)*: con el celular en el WiFi de casa: instalar Termux desde F-Droid, `pkg install python
   python-numpy`, copiar `receptor_local.py` y `aura_proto.py` (p. ej. a `~/aura/scripts`), crear `~/aura/datos/crudos`
   y correr `python receptor_local.py --id-sesion T1 --duracion 60 --ip 192.168.0.13 --sin-bind`. Éxito: `csi ~100/s`,
   pérdida < 1 %. Copiar `T1_local.csv` a la PC y reproducirlo con el visor.
2. *Opción 1 (USB OTG)*: conectar la placa al celular con OTG, abrir la terminal, elegir el dispositivo (303A).
   Éxito: aparecen líneas `HMS:{...}`. Activar marcas de tiempo y guardar 1 min; convertir con
   `convertir_log_celular.py` y reproducir. Si la app no reconoce la placa o no guarda con hora: descartar la opción.
3. *Opción 3*: hotspot encendido, placa con power bank: comprobar con la opción 2 (Termux en el mismo celular, que es
   el router de esa red) que llegan datos.

## G. Ética en el salón

Ver el aviso para leer a los alumnos y la regla de participación en `guion_grabacion.md` (sección "Ética en el salón").

## H. Checklist: qué llevar

- [ ] Placa B (0.1.3, solo local; hotspot cargado como `wifi1` si se hizo la prueba A)
- [ ] 2 cables **USB-C de datos** (probados) + 1 adaptador OTG si se prueba el celular por USB
- [ ] Power bank cargado (≥ 10 000 mAh) y su cable
- [ ] Laptop HP con el kit instalado y probado (`kit_captura\GUIA.md`) + su cargador
- [ ] Celular con el hotspot configurado (mismo nombre y clave que cargaste en la placa) + su cargador
- [ ] Soporte o cinta para fijar el celular; cinta para fijar la placa
- [ ] Wincha o cinta métrica (para medir 1,5–2 m entre placa y celular)
- [ ] Hoja con el aviso a los alumnos y la lista de quienes aceptan participar
- [ ] Memoria USB para llevarte las capturas (y borrarlas de equipos ajenos)
