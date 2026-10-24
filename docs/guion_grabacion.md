# Guion de grabación del video de AURA (modo solo local, captura por USB)

Versión del 23/10/2026. Reemplaza, para el video, a la sección "Demo en el local" de `guia_placas.md` (que
usaba `puente.py`). La nube **no** se usa en el video: queda como línea de desarrollo posterior
(`pendientes_nube.md`).

## Qué se muestra

AURA detecta **actividad humana** con el WiFi (CSI) de una sola placa: el panel pasa a **MOVIMIENTO** cuando
alguien se mueve en la habitación y vuelve a quieto cuando no hay movimiento. La presencia quieta solo se
muestra si antes se entrenó la habitación vacía; sin entrenamiento el panel dice `SIN_MOVIMIENTO` (nunca
"vacía").

## Material

- Placa B con **0.1.3 en modo solo local** (sin `fb_pass`: la nube no abre conexiones). Decisión del 24/10:
  45 min sin tormenta APROBADA; con tormenta de ARP, 0 asignaciones fallidas y 0 reinicios, pero mínimo de
  26,4 KB (FALLIDA por el criterio de 30 KB). **Antes de grabar, confirma que la PC 192.168.0.89 esté apagada**
  si el video se graba en casa.
- Cable USB-C de datos y la **laptop prestada** con el kit (`C:\aura\kit_captura`, ver su `GUIA.md`).
- Red del departamento (principal) o tu **hotspot** (respaldo, ya cargado en la placa).
- Cámara o celular para grabar, con trípode.

## Antes de grabar (en el departamento)

1. Instala el kit en la laptop (`GUIA.md`, pasos 1–2).
2. Carga el WiFi del departamento como red principal (`GUIA.md`, paso 3). Si el WiFi del departamento no
   está disponible o es inestable, no cargues nada: la placa pasa sola al hotspot tras 3 intentos fallidos
   (deja el hotspot encendido y cerca).
3. **Desconecta y vuelve a conectar la alimentación de la placa** (evita el reloj viejo tras un reinicio por
   USB).
4. Ubica la placa a ~1 m del suelo, con la habitación en línea entre la placa y el router (o el celular).
5. Pon a la vista de la cámara la pantalla de la laptop o un reloj (ayuda a sincronizar).
6. Inicia la captura **antes** de grabar (`GUIA.md`, paso 4), con un ID nuevo (`V001`, `V002`…), y espera
   **1 minuto** con la habitación vacía y sin moverte cerca: el detector calibra.

## Escenas (≈ 6 min por toma)

| t (min) | Escena | Qué se espera en el panel |
|---|---|---|
| 0:00 | **Palmada de sincronización**: frente a la cámara, a ~1 m de la placa, una palmada fuerte con movimiento amplio de brazos; luego 5 s quieto | pico de la señal suavizada → MOVIMIENTO breve |
| 0:10 | Sal de la habitación; habitación vacía 1 min | señal baja; no MOVIMIENTO |
| 1:10 | Entra caminando, recorre la habitación 1 min | MOVIMIENTO sostenido |
| 2:10 | Siéntate y quédate quieto 1 min | vuelve a quieto tras ~10 s (retención) |
| 3:10 | Gestos con los brazos sentado, 30 s | MOVIMIENTO intermitente |
| 3:40 | Sal de la habitación; vacía 1 min | quieto |
| 4:40 | **Palmada de cierre** (igual que la inicial) | pico |
| 4:50 | Fin de la toma | — |

Graba al menos **2 tomas**. Entre tomas no hace falta detener la captura.

## Después de grabar

1. Detén la captura (o deja que termine la duración) y copia `datos\crudos\` a tu memoria; bórralo de la
   laptop prestada (datos de una sesión con personas).
2. **Reconstruye el panel en modo reproducción** (`GUIA.md`, paso 5):
   `visor.py --reproducir datos\crudos\V001.csv --exportar cuadros_V001 --fps 10`.
   Cada cuadro lleva al pie el rótulo **"Reproducción de datos registrados durante la grabación"**.
3. **Sincroniza**: en el editor de video, alinea el pico de la palmada inicial del panel con la palmada del
   video; comprueba con la palmada de cierre (la diferencia debe ser < 0,5 s).
4. Monta el panel junto a la imagen de la cámara (pantalla dividida).

## Rotulado del video (obligatorio)

- Sobre el panel, durante todo el video: **"Reproducción de datos registrados durante la grabación"**.
- Al inicio, un cartel: "Detección de actividad con WiFi (CSI) en una sola placa ESP32-C5. El panel se
  reconstruyó a partir de los datos registrados por USB durante la grabación; no es una transmisión en vivo."
- No presentar como resultado la presencia quieta ni cifras de exactitud: el video muestra el funcionamiento,
  no una validación.
