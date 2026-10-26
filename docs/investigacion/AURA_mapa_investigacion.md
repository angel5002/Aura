# AURA — Mapa de investigación para seleccionar papers

> Contexto para un proyecto de revisión bibliográfica asistida (Perplexity u otra herramienta). Pégalo
> al inicio del proyecto. Objetivo: encontrar, filtrar y mapear los trabajos que ayuden a mejorar la
> **detección de presencia** y a **independizar el sistema de la geometría** (no medir distancias),
> con el hardware real del proyecto.
> Fecha de corte del contexto: 26/10/2026.

---

## 1. Reglas para la herramienta de búsqueda

1. **Fuentes válidas:** artículos revisados por pares (IEEE, ACM, Elsevier, Springer, MDPI con
   cuidado, Nature/PubMed para lo clínico), documentación oficial (Espressif, IEEE 802.11) y
   preprints de arXiv **marcados como preprint**.
2. **Fuentes no válidas:** blogs sin autor, foros, sitios de tareas, Wikipedia como fuente única,
   resúmenes de IA sin enlace al artículo.
3. **Cada referencia con DOI o enlace oficial.** Si la herramienta no puede dar el DOI, marcarla como
   "sin verificar".
4. **No inventar números.** Todo resultado (precisión, error, alcance) debe venir del artículo, con la
   condición en que se midió (hardware, ancho de banda, antenas, ambiente, número de personas).
5. **Verificación posterior obligatoria:** cada DOI se comprueba en doi.org o Crossref antes de usarlo.
   Las herramientas de búsqueda con IA pueden mezclar autores, años y cifras.

## 2. Restricciones del hardware (filtro principal)

Un método solo es aplicable si funciona, o puede adaptarse, con esto:

| Característica | Valor en AURA |
|---|---|
| Chip | ESP32-C5 (FireBeetle 2), 1 núcleo RISC-V 240 MHz, sin PSRAM, ~60 KB libres en ejecución |
| Antenas | **1** (integrada, PCB, direccional) |
| CSI | LLTF, **26 subportadoras** de 12 bits (modo por defecto); 52 en modo de 8 bits |
| Banda / ancho | 2,4 GHz (también 5 GHz posible), **20 MHz** |
| Tasa de muestreo | ~100–180 paquetes CSI/s (ping al AP) |
| Fase | **no utilizable** directamente (una antena, desfases por paquete) → métodos de amplitud |
| Transmisor | router doméstico o hotspot de celular (no controlable), o otra ESP32 |
| Receptores | 1 hoy; hasta 3 placas disponibles |
| Procesamiento | en la placa (limitado) o en PC/laptop por la vía local |

Clasificar cada paper según su hardware: **ESP32** / tarjeta comercial (Intel 5300, Atheros, Nexmon)
/ SDR / radar. Los de ESP32 o de amplitud con una antena son los más transferibles.

## 3. Preguntas de investigación

**P1 — Presencia sin calibración.** ¿Qué métodos detectan presencia humana (incluida una persona
quieta) **sin entrenamiento con la habitación vacía** o con una calibración que se mantenga en el
tiempo? ¿Qué tasa de falsas alarmas reportan con la habitación vacía y durante cuánto tiempo?

**P2 — Respiración como indicador de presencia con amplitud y una antena.** ¿Qué alcance y qué zonas
ciegas reportan? ¿Qué selección de subportadoras usan? ¿Qué duración de ventana necesitan?

**P3 — Deriva y robustez temporal.** ¿Cómo tratan la deriva de la señal (cambios lentos del
ambiente, temperatura, muebles) sin reentrenar? ¿Detección de cambios, normalización, adaptación
continua?

**P4 — Independencia de la geometría.** ¿Cómo se evita depender de la posición exacta de transmisor y
receptor? (características invariantes al dominio, varios enlaces, prueba o mapa de cobertura,
autoevaluación de la calidad del enlace). ¿Qué precisión da la estimación de distancia entre equipos
con FTM/RTT en ESP32?

**P5 — Fuentes de falsas alarmas no humanas.** Mascotas, ventiladores, cortinas, robots, puertas, y
movimiento en habitaciones vecinas: ¿cómo se distinguen?

**P6 — Varios enlaces y fusión.** ¿Cuánto mejora la cobertura y la detección con 2–3 receptores
baratos? ¿Cómo se fusionan (votación, probabilística, aprendizaje)?

**P7 — Validación.** ¿Cómo diseñan la verdad de referencia (video, PIR, banda respiratoria,
metrónomo)? ¿Qué tamaño de muestra y qué métricas usan? (La revisión de Al-Rajab et al. 2026 reporta
mediana de 8 participantes: buscar estudios más grandes.)

## 4. Cadenas de búsqueda sugeridas

```
("channel state information" OR CSI OR "WiFi sensing") AND (presence OR occupancy OR "stationary human")
  AND (calibration-free OR "without calibration" OR "environment-independent" OR "domain-independent")

("WiFi" OR CSI) AND (respiration OR breathing) AND (presence OR "stationary") AND ("single antenna" OR amplitude)

(ESP32 OR "low-cost" OR "commodity") AND ("channel state information") AND (presence OR "motion detection" OR respiration)

("WiFi sensing" OR CSI) AND (drift OR "long-term" OR "concept drift" OR "temporal stability")

("fine timing measurement" OR FTM OR "round trip time") AND ESP32 AND (ranging OR distance OR accuracy)

("WiFi sensing" OR CSI) AND ("Fresnel zone" OR "coverage" OR "sensing area" OR "blind spot")

("WiFi sensing" OR CSI) AND ("false alarm" OR "non-human motion" OR pet) AND (home OR "real-world deployment")

("WiFi sensing" OR CSI) AND ("multi-link" OR "multiple receivers" OR fusion) AND (presence OR detection)
```

Período: 2015–2026, con prioridad 2020–2026. Idiomas: inglés y español.

## 5. Criterios de inclusión y exclusión

**Incluir:** CSI o RSSI WiFi; detección de presencia, movimiento o respiración; resultados
cuantitativos; descripción suficiente del hardware y del protocolo.

**Excluir:** solo radar mmWave o UWB (salvo como comparación); solo reconocimiento de gestos finos sin
relación con presencia; sin evaluación experimental; requiere hardware imposible de reproducir con
ESP32 (salvo como referencia teórica, marcado así).

## 6. Plantilla de extracción (una fila por paper)

| Campo | Qué anotar |
|---|---|
| Referencia | autores, año, revista/congreso, DOI |
| Tipo | revisión / método / sistema / dataset / estándar |
| Pregunta(s) que responde | P1–P7 |
| Hardware | chip/tarjeta, antenas, banda, ancho, subportadoras, tasa |
| Usa fase | sí / no |
| Requiere sala vacía o calibración | sí / no / cuánto |
| Método | en una frase |
| Escenario de evaluación | ambientes, personas, duración, referencia |
| Resultados | métrica + valor + condición |
| Transferibilidad a AURA | alta / media / baja + por qué |
| Código o datos públicos | sí / no / enlace |
| Verificación | DOI comprobado: sí / no |

## 7. Referencias semilla (ya identificadas)

Estado de verificación: **V** = DOI o enlace oficial comprobado en la conversación; **A** = cita
aportada pero DOI no comprobado; **P** = preprint.

| Referencia | Por qué importa | Estado |
|---|---|---|
| Zhang, Wu, Wang, Lai, Han, Liu. *WiDetect*. Proc. ACM IMWUT 3(3), art. 122, 2019. DOI 10.1145/3351280 | Movimiento sin calibración con amplitud (autocorrelación); umbral teórico | V |
| Wu, Yang, Zhou, Liu, Liu, Cao. *Non-invasive detection of moving and stationary human with WiFi* (DeMan). IEEE JSAC 33(11):2329–2342, 2015 | Respiración como indicador de presencia quieta | V (sin DOI anotado) |
| Zeng et al. *FarSense*. Proc. ACM IMWUT, 2019. DOI 10.1145/3351279 | Cociente de CSI entre dos antenas; alcance de respiración (no aplicable con 1 antena) | V |
| Zheng et al. *Zero-Effort Cross-Domain Gesture Recognition with Wi-Fi* (Widar3.0). MobiSys 2019. DOI 10.1145/3307334.3326081 | Características independientes del dominio (requiere varios receptores) | V |
| Wang et al. Modelo de zonas de Fresnel para respiración. UbiComp 2016. DOI 10.1145/2971648.2971744 | Geometría, puntos ciegos, sensibilidad por posición | V |
| Wang, Zhang et al. *A Survey on Wi-Fi Sensing Generalizability*. IEEE COMST 2026. arXiv:2503.08008 | Generalización: dispositivos, personas, ambientes (>200 trabajos) | V (arXiv) |
| Chen, Zhou, Lin. *Cross-Domain WiFi Sensing with CSI: A Survey*. ACM Computing Surveys 55(11), 2023 | Técnicas entre dominios | A |
| Hernandez, Bulut. *WiFi Sensing on the Edge*. IEEE COMST, 2023 | Procesamiento en dispositivos de borde, incluye ESP32 | A (DOI por comprobar) |
| Ma, Zhou, Wang. *WiFi Sensing with Channel State Information: A Survey*. ACM CSUR, 2019 | Revisión general de técnicas | A (DOI por comprobar) |
| Zubow, Petto, Dressler. Detección de presencia con OC-SVM entrenado solo con sala vacía, 2023 | Detección de novedad; muestra la dependencia de la sala vacía | V (PDF de los autores) |
| Despliegue de 280 dispositivos en hogares reales durante 2 años. arXiv:2506.04322 | Falsas alarmas por movimiento no humano en casas reales | P |
| IEEE Std 802.11bf-2025 (WLAN Sensing), aprobado el 28/05/2025 | Estándar de sensado WiFi | V |
| Espressif, ESP-IDF v6.0 (ESP32-C5): Wi-Fi Location / FTM | FTM en C5: iniciador en estación, respondedor en AP; precisión limitada | V (doc. oficial) |
| Zhao et al. *NeRF2*. MobiCom 2023. arXiv:2305.06118 | Modelos aprendidos de propagación (futuro) | V (arXiv) |
| Hoydis et al. *Sionna RT*. arXiv:2303.11103 | Trazado de rayos para planificar cobertura (futuro) | V (arXiv) |
| Al-Rajab et al. 2026, PeerJ Computer Science. DOI 10.7717/peerj-cs.3375 | Debilidad de la evidencia en sensado WiFi (muestras pequeñas, sin código) | A |

**Contexto clínico** (no es el foco de esta revisión, pero define qué no afirmar): SleepFM (Thapa et
al., *Nature Medicine* 2026, DOI 10.1038/s41591-025-04133-4); PVC-RAM-1 (McGillion et al., *BMJ* 2021,
DOI 10.1136/bmj.n2209); HeartLogic (Boehmer et al., *JACC Heart Failure* 2017, DOI
10.1016/j.jchf.2016.12.011). Estado: A.

## 8. Prompts sugeridos para la herramienta

1. "Busca artículos revisados por pares de 2018 a 2026 sobre detección de presencia humana estacionaria
   con CSI de WiFi **sin calibración con habitación vacía**. Para cada uno dame: referencia con DOI,
   hardware (antenas, ancho de banda, subportadoras), si usa fase, método en una frase, escenario de
   evaluación y resultados con su condición. Excluye blogs y fuentes sin DOI."
2. "¿Qué trabajos usan ESP32 (cualquier variante) para detectar respiración o presencia con CSI? Da DOI,
   número de participantes, ambiente y error reportado."
3. "Encuentra trabajos que evalúen la deriva temporal del CSI en interiores durante horas o días y cómo
   la compensan sin reentrenar."
4. "¿Qué precisión de distancia reporta la literatura para FTM/RTT 802.11mc entre dispositivos
   comerciales en interiores, y específicamente con ESP32?"
5. "Busca estudios de detección de movimiento WiFi en hogares reales que reporten falsas alarmas por
   mascotas, ventiladores u otras fuentes no humanas y cómo las reducen."
6. "Compara métodos de fusión de varios enlaces WiFi (2–4 receptores) para detección de presencia:
   ganancia de cobertura y de precisión reportada."

Pedir siempre la salida en la tabla de la sección 6.

## 9. Qué se hace con el resultado

1. Verificar DOIs (Crossref) y descartar los que no existan o no coincidan.
2. Leer resumen y método de los de transferibilidad alta; leer completos los 5–10 mejores.
3. Por cada pregunta P1–P7, escribir 3–5 líneas de síntesis: qué funciona, en qué condiciones, qué
   falta.
4. Registrar en el repositorio de AURA (`docs/decisiones/`) las decisiones que salgan de la revisión
   (por ejemplo, el método de presencia elegido) como ADR, con las referencias como evidencia.
5. Identificar el **hueco**: por ejemplo, "presencia sin calibración con un enlace ESP32 de una antena
   y 26 subportadoras, evaluada en varias habitaciones con video como referencia". Ese hueco es la
   contribución publicable.

## 10. Datos propios disponibles para probar métodos

| Sesión | Qué contiene | Limitación |
|---|---|---|
| S002 | ~5 min sala vacía (casa), CSI crudo por vía local | 1 sesión, enlace 0,8 m, vacío no verificado por video |
| L001 | salón de clases, quieta y caminando | caminata no cruzó el enlace; otras personas presentes |
| A00x | observaciones de memoria y tormenta ARP | no son sesiones de detección |

Próximas capturas planificadas: habitación nueva en casa, con video de referencia, metrónomo y
condiciones repetidas en orden variado (ver `docs/decisiones/0000_reporte_inicial.md`).
