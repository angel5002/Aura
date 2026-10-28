# Propuestas para Angel: ajustes al contrato de datos del MVP

28/10/2026 · de Deisy (redactado con Claude Code, PC principal) · sobre "Requerimientos y construcción del MVP de AURA",
sección "Contratos de datos", y la especificación del mockup (`docs/mockup/AURA_mockup_especificacion.pdf`).

El mockup ya funciona con el contrato tal como está. Estos cambios hacen que la app pueda mostrar datos en vivo **sin
afirmar lo que AURA todavía no mide**. Ninguno rompe lo que ya hay: son campos nuevos o un texto.

## 1. `estado` por zona en lugar de `confianza`
**Hoy:** `gemelo.zonas.<zona>.confianza` vale "alta" en caídas (`piernas`) y en presencia (`aura`), justo lo menos
probado.

**Propuesta:** agregar `estado` a cada zona, con uno de estos valores:
- `activo`
- `prototipo`
- `en_investigacion`
- `no_medido`

La app ya ignora `confianza`. Si llega `estado`, la app muestra el **más bajo** entre ese valor y su propia tabla de
honestidad:

| Zona | Módulo | Estado máximo que muestra la app |
|---|---|---|
| `aura` | Actividad (movimiento) | `activo` |
| `piernas` | Caídas | `prototipo` |
| `pulmones` | Respiración | `en_investigacion` |
| `cabeza` | Sueño / Ánimo | `en_investigacion` / `no_medido` |
| `corazon` | Corazón | `no_medido` |

```json
"pulmones": {"nivel": "ambar", "estado": "en_investigacion", "texto": ""}
```

## 2. `fuente` también en el mensaje `gemelo`
**Hoy:** `estado` y `evento` traen `fuente` ("vivo" o "demo"), pero `gemelo` no. La app no puede saber si el gemelo
que llega viene de un escenario de demo.

**Propuesta:** que `gemelo.py` copie al gemelo la `fuente` del último `estado` o `evento` que lo cambió. El sello
"DEMO · reproducción" depende de ese dato. Mientras no llegue, la app trata como demo todo lo que siga, durante 60 s, a
un mensaje con `fuente` = "demo".

## 3. Campo `movimiento` en `estado` (lo único demostrado)
**Hoy:** ningún mensaje lleva el movimiento, que es lo que AURA demostró (K002: 10 de 10 cruces, firmware 0.1.3).
`en_vivo3.py` publica `estado_cama`, `estado_paso` y `fr_rpm`, que no están validados.

**Propuesta:** agregar un campo opcional, alimentado por el receptor local de la placa B (`motion_status` del detector):

```json
{"ts": 1761800000.1, "fuente": "vivo", "movimiento": true, "fuente_mov": "via_local"}
```

Con ese campo, la pantalla Hoy muestra "vía local" en lugar de la reproducción K002. Mientras no exista, Hoy usa la
reproducción y el sello DEMO sigue visible. La app no inventa el formato: lee el campo solo si llega como booleano.

## 4. Nota del reporte de teleconsulta
**Hoy:** `POST /teleconsulta` responde `"nota": "Generado por AURA, no es un diagnóstico."`, y la F8 lo pide así.

**Propuesta:** cambiarla por **"Generado por AURA. No reemplaza la consulta con tu médico."** La especificación exige
que la palabra "diagnóstico" no aparezca en ninguna pantalla (evita el régimen de dispositivos médicos, Ley 29459).
Por ahora, la app no muestra `nota`.

## 5. Reconocimiento de voz (F6, "Debe") — para conversarlo
El mockup **no** usa reconocimiento de voz (ADR-0025, decisión de Deisy):
- en Chrome para Android, la Web Speech API manda el audio a servidores de Google;
- exige HTTPS, que en el plan actual sale de ngrok, otro servicio en la nube.

El asistente del mockup funciona con frases que se tocan, y las barras del orbe siguen el micrófono solo en localhost
o HTTPS. Hay que acordar contigo si el MVP mantiene la voz como "Debe" y con qué alternativa local, o si baja a
"Debería".

## 6. Otros detalles que la app ya resuelve
- `/ws` manda `{topico, datos}`: la app desempaqueta ese sobre y atiende `gemelo`, `estado` y `evento`.
- Respuestas de emergencia por `POST /emergencia/respuesta` con `{"respuesta": "bien" | "ayuda"}`. Escenarios por
  `POST /demo/{escenario}`. Ambos solo si hay servidor; si no, la app los simula y lo rotula.
- `window.AURA_HOLO.escanear()` existe y abre el gemelo con la animación de escaneo. `setZona` queda sin efecto: el
  color de cada zona lo decide la tabla de honestidad.
- Los textos de las zonas con cifras ("17.5 resp/min", "Sueño 62/100") **no se muestran**.
- "Rosa" se mantiene como persona ficticia de la demo, rotulada así.
