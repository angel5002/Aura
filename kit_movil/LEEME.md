# Kit móvil de AURA (Termux en Android) — versión 0.1.2

Recibe la vía local de la placa en el **celular**, sin PC, dentro de la red **AURA-LAB** (router propio, sin
internet; ver `docs/red_aura.md` y ADR-0023, **Aceptada** el 2026-10-26). Graba el mismo CSV que la laptop (`<código>_local.csv`,
con el CSI crudo), que luego se reproduce en la PC con `visor.py --reproducir`.

**Estado: NO verificado en un celular.** Los tres scripts se probaron en la PC del proyecto (Windows). En Android
con Termux no se ha ejecutado nada todavía. La primera captura con el celular es la prueba del kit (sección 6).

## 1. Qué lleva y qué NO lleva

| Lleva | Origen |
|---|---|
| `scripts/receptor_local.py` | copia exacta de `analisis/receptor_local.py` |
| `scripts/aura_proto.py` | copia exacta de `analisis/aura_proto.py` |
| `scripts/verificar_captura.py` | copia exacta de `analisis/verificar_captura.py` (revisa los criterios de la prueba) |
| `docs/ensayos/kit_movil_criterios.md` | copia exacta de `docs/ensayos/kit_movil_criterios.md` (umbrales) |

**No lleva** la clave local (`secretos\clave_local.txt`) ni ningún otro archivo de `secretos\`: la recepción no la usa
(ADR-0023). No copies `secretos\` al celular. Sin la clave, desde el celular no se mandan comandos `CMD` ni OTA.

Dependencias: Python 3.10 o posterior y numpy. Nada más.

## 2. Instalar Termux (una vez)

1. Instala **Termux desde F-Droid** (`docs/guia_salon.md`, sección E). La versión de Google Play está desactualizada.
2. En Termux:
   ```
   pkg update
   pkg install python python-numpy
   termux-setup-storage
   ```
   `python-numpy` es el paquete de numpy de Termux según guías comunitarias (**no verificado**). Si no existe,
   prueba `pip install numpy` y anota lo que pasó. `termux-setup-storage` pide permiso para ver la carpeta
   Descargas del celular.

## 3. Copiar el kit al celular

1. Conecta el celular a la PC por USB en modo "Transferencia de archivos" y copia la carpeta `kit_movil` a
   **Descargas** (Download) del celular.
2. En Termux:
   ```
   cp -r ~/storage/downloads/kit_movil ~/kit_movil
   ```
   Las capturas quedan en `~/kit_movil/datos/crudos/` (la carpeta se crea sola).

## 4. Antes de cada captura

- La placa está encendida (power bank o cargador) y conectada a AURA-LAB. **Lee su IP en el panel del router**, en la
  lista de dispositivos conectados (MAC `3C:DC:75:8A:6F:CC`); el router no permite reservarla, así que puede cambiar
  entre sesiones (`docs/red_aura.md`, sección 3).
- El celular está conectado a **AURA-LAB**. Si Android avisa que la red no tiene internet, elige **mantener la
  conexión**. No hace falta apagar los datos móviles (inferido, no verificado).
- Excluye Termux de la optimización de batería (Ajustes de Android > Apps > Termux > Batería > Sin restricciones).
- No compartas la clave WiFi de AURA-LAB con alumnos ni con el público (`docs/red_aura.md`, sección 7).

## 5. Capturar

```
termux-wake-lock
cd ~/kit_movil/scripts
python receptor_local.py --id-sesion K001 --duracion 1800 --ip <IP_DE_LA_PLACA> --sin-bind
```

- `--id-sesion`: un **código**, nunca el nombre de una persona (regla 9 de `CLAUDE.md`). `K001` es solo un ejemplo.
- `--duracion` en segundos. Para terminar antes: **Ctrl + C** (tecla CTRL de la barra de Termux y luego `c`); el
  resumen se guarda igual.
- Usa siempre `--ip`: con la pantalla apagada Android puede no entregar los anuncios por broadcast (inferido).
- Cada 5 s se imprime la tasa por tipo y la pérdida. Si no aparece nada en 15 s, revisa la red y la IP.
- Al terminar: `termux-wake-unlock`.
- **Reiniciar la placa en el lugar = desenchufarla** y volver a enchufarla (`AURA REBOOT` solo funciona por USB desde
  la PC). Tras un reinicio, el receptor sigue grabando solo; no hace falta reiniciarlo.
- Si la placa cae al hotspot (wifi2), cambia de IP y el receptor deja de recibir: detenlo y vuelve a lanzarlo con la
  IP nueva.

### 5.a Prueba del kit (una sola vez, antes de usarlo en un salón)

Un **solo bloque de 30 min**, con el **celular como único receptor**, la **sala vacía** y el montaje de siempre
(placa y router en su sitio; nadie se mueve en la zona). Sin laptop.

1. Lee la IP de la placa en el panel del router.
2. `termux-wake-lock`, y en `~/kit_movil/scripts`:
   ```
   python receptor_local.py --id-sesion K001 --duracion 1800 --ip <IP_DE_LA_PLACA> --sin-bind
   ```
   Deja que termine solo (no uses Ctrl + C) y no cierres Termux.
3. Revisa con `verificar_captura.py` (sección 6) y lleva los datos a la PC (sección 7).

Criterios (fijados antes de la prueba): pérdida **< 1 %**, **0 huecos mayores de 5 s**, mediana de CSI/s en
ventanas de 10 s **≥ 80,32/s**, **0 reinicios** de la placa y **Termux sin cierres** durante el bloque. Los tres
primeros los evalúa `verificar_captura.py` desde `docs/ensayos/kit_movil_criterios.md`; los reinicios los informa
(épocas y arranques de la telemetría) y el cierre de Termux se ve en que el receptor no terminó solo (falta
`K001_local_resumen.json` o dura menos de 1800 s). Si algo falla, se registra **FALLIDO** y el diagnóstico
(router o celular) se hace después, p. ej. con la sección 5.b.

### 5.b Diagnóstico opcional (NO forma parte de la prueba ni de sus criterios): recibir a la vez con la laptop

Solo si la prueba del kit falla. Sirve para **separar el efecto del router del efecto del celular**. La placa acepta hasta 3 receptores a la vez y
envía cada datagrama, con el mismo número de secuencia, a todos (`firmware/aura_nodo/main/aura_local.c:100-118` y
`:169`; máximo en `firmware/versiones/0.1.3/sdkconfig.usado:731`; leído en el código, **nunca medido con dos
receptores a la vez**). Así las dos capturas son comparables datagrama a datagrama.

1. Conecta la laptop a **AURA-LAB** (WiFi).
2. En la laptop, con el kit de captura (`kit_captura`) o con `analisis/` en la PC principal, usa la misma IP de la
   placa y un código propio, p. ej.:
   ```
   python receptor_local.py --id-sesion K001L --duracion 1800 --ip <IP_DE_LA_PLACA> --sin-bind
   ```
   (`--sin-bind` evita la regla de firewall de Windows.) Lanza el celular y la laptop con pocos segundos de
   diferencia.
3. Después, en la PC principal, revisa los dos archivos juntos:
   ```
   python verificar_captura.py K001_local.csv K001L_local.csv
   ```
   - Los dos fallan igual → problema del **router, el canal o la placa**.
   - Solo falla el celular → problema del **celular** (WiFi del teléfono, Android, Termux).
   - Solo falla la laptop → problema de la laptop; el celular queda validado.

Límites: con dos receptores la placa envía el doble de datagramas (más tiempo de aire y CPU), lo que podría por sí
mismo aumentar la pérdida (inferido, no verificado; la telemetría `local_descartes` y `local_errores` lo mostraría).
El receptor de `kit_captura` es la versión anterior: graba el mismo CSV, pero su resumen de pérdida usa la regla de
reinicios antigua; usa siempre el resumen de `verificar_captura.py`.

## 6. Revisar la captura (criterios de la prueba del kit)

```
python verificar_captura.py ../datos/crudos/K001_local.csv
```

El verificador lee los umbrales de `docs/ensayos/kit_movil_criterios.md` (copia exacta del documento del
repositorio; es la única fuente). Hoy: pérdida **< 1 %**; **0 huecos mayores de 5 s por placa**; mediana de CSI/s
en ventanas de 10 s **≥ 80,32/s** (80 % de S002). También informa los reinicios y, de la telemetría de la placa,
`motivo_reinicio` y `encendido_s` por arranque (`encendido` = se cortó la alimentación o se desenchufó;
`brownout` = caída de tensión, p. ej. power bank débil; `panico`/`wdt` = fallo de software) y, solo como dato, la
memoria mínima por intervalo de 10 s (`heap_min_intervalo`).

Hora de la placa: tras un reinicio por software la placa conserva la hora anterior (F2, 26/10/2026), así que
`t_us` puede no ser 0 aunque AURA-LAB no tenga internet. No importa: la referencia es siempre `t_pc_unix`.

Un criterio no cumplido se registra como **FALLIDO**; el criterio no se cambia después de ver el resultado.

## 7. Llevar los datos a la PC

```
cp ~/kit_movil/datos/crudos/K001_local* ~/storage/downloads/
```

Copia los archivos por USB a `C:\aura\datos\crudos\` (fuera de git). En la PC:

```
C:\aura\analisis\.venv\Scripts\python.exe C:\aura\analisis\visor.py --reproducir C:\aura\datos\crudos\K001_local.csv
```

El visor usa la hora del celular (`t_pc_unix`) como referencia; sin internet la placa no tiene hora SNTP (`t_us` = 0).
Son datos de personas: cuando la copia en la PC esté comprobada, bórralos del celular (Descargas y `~/kit_movil/datos`).

## 8. Límites conocidos

- Sin verificar en Android: instalación de numpy, recepción con la pantalla apagada y pérdida por WiFi en el celular.
- Reinicios: se detectan porque `ts_ms` (tiempo desde el arranque) retrocede; si no llegan muestras, por la caída
  de la secuencia. No se ve un reinicio si la placa muere antes de enviar su primera muestra tras arrancar (retroceso
  menor que 0,5 s). Afecta solo al resumen de pérdida; el CSV no se ve afectado.
- La hora es la del celular al recibir; para alinear con un video, el video debe usar el mismo reloj.
- Este kit no tiene visor en vivo: en el celular solo se ven tasas y pérdida en texto.
