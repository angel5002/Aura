# Reporte inicial del proyecto AURA (corte: 26/10/2026)

> Reconstruido a partir de las conversaciones de diseño del 22 al 26/10/2026 y de los informes de
> Claude Code de esos días. Los números se marcan como **medido**, **estimado** o **no verificado**.
> Claude Code debe contrastar las rutas de evidencia con el repositorio y anotar diferencias en la
> bitácora.

## 1. Propósito
Sensado WiFi (CSI) con ESP32-C5 para detectar actividad humana en casa sin cámaras ni dispositivos
puestos. Fines: investigación, docencia y la Científica Hack X 2026 (ODS 3, entrega 30/10/2026). Para el
hackathon el entregable es un **video de detección de movimiento en tiempo real**, no una demo en vivo
ni un MVP (ADR-0017).

## 2. Hardware
- 3 × DFRobot FireBeetle 2 ESP32-C5 (ESP32-C5 rev. v1.0, **4 MB de flash, sin PSRAM**, antena
  integrada, USB nativo Serial/JTAG, VID 303A). **Medido** con esptool en la placa B.
- Placa B `3C:DC:75:8A:6F:CC`: única con firmware AURA. A y C sin uso por ahora.
- Transmisor: router de casa (Castlenet Infinity 601 de Claro, Plume apagado, sin acceso de
  administrador) o hotspot del celular de Deisy.
- PC principal: escritorio HP por Ethernet (`192.168.0.132`), Windows; laptop de campo prestada.

## 3. Cronología resumida
| Fecha | Hito |
|---|---|
| 22/10 | Entorno: EIM, ESP-IDF v5.5.6 (`C:\esp`), venv Python. `wifi_sensing` compila y se graba en B; llega a STABLE. |
| 22/10 | Se descubre que la presencia de esp-radar requiere entrenamiento con sala vacía y se pierde al reiniciar. |
| 22/10 | Cambio de arquitectura: placa sin PC, dos vías (local + Firebase). Firebase configurado (4 cuentas, reglas por UID, T5 39/39). |
| 23/10 | `aura_nodo` 0.1.0 → 0.1.4. Bucle de reinicios en 0.1.0 (mutex), corregido. Diagnóstico de memoria: ráfagas de recepción WiFi. |
| 23/10 | Se identifica la PC `DESKTOP-VQMJ5PC` (192.168.0.89, MAC HP) como origen de tormentas ARP (mediana 1.398 (rango 350–2.163) broadcasts cada 10 s). |
| 23/10 | 0.1.4 falla D0 (memoria a 12 B, pánico). Se elige 0.1.3 en modo solo local para el video. Git iniciado. |
| 24/10 | Receptor por IP directa sin regla de firewall: 0 % de pérdida en 5 min. D11: CSI LLTF de 12 bits, 26 subportadoras. |
| 24/10 | S002 (sala vacía, ~5 min): movimiento 0,4 % de falsas alarmas; presencia 100 % falsa (deriva). |
| 24/10 | Kit 1.1.0 probado en laptop de campo con hotspot: placa en respaldo a 42 s, IP a 62,7 s; CSI ~140–180/s (registrado en la laptop de campo, pendiente de copiar al repo). |
| 24/10 | L001 en el salón: montaje inválido para cruce (celular y placa en la misma mesa) (registrado en la laptop de campo, pendiente de copiar al repo). |
| 24–26/10 | Revisión de literatura y nuevo plan de presencia (WiDetect + respiración) y de geometría. |

## 4. Resultados medidos que sostienen las decisiones
| Dato | Valor | Tipo | Fuente |
|---|---|---|---|
| Flash / PSRAM de B | 4 MB / no | medido | esptool (`flash_id`, eFuse `PSRAM_CAP=0`); `docs/arquitectura_dos_vias.md` |
| 0.1.3 solo local, sin tormenta (45 min) | 0 asignaciones fallidas, mínimo 34,5 KB, CSI 100,6/s | medido | `docs/resultados_pruebas*.md` |
| 0.1.3 solo local, con tormenta (20 min) | mínimo 26,4 KB en 2/120 intervalos → **FALLIDA** por criterio ≥ 30 KB; 0 fallos de asignación, 0 reinicios | medido | ídem |
| 0.1.2 (nube + 128 buffers RX) | 142 asignaciones fallidas, mínimo 48 B | medido | ídem |
| 0.1.4 | D0 FALLIDA (pánico por memoria con tormenta ARP) | medido | ídem |
| Receptor local por IP directa | 0,00 % de pérdida en 5 min, 100,5 CSI/s | medido | ídem |
| S002 sala vacía | movimiento 0,4 % (crudo) / 3,6 % (suavizado); presencia 100 % | medido, 1 sesión, sin verificación independiente de vacío | `docs/evaluacion_S002.md`; `registro_sesiones.csv` (fuera de git), S002 |
| Cambio a hotspot | 42,0 s a red de respaldo; 62,7 s hasta IP | medido, 1 vez | registrado en la laptop de campo, pendiente de copiar al repo |
| Formato CSI | LLTF, 26 subportadoras de 12 bits (106 B) | medido + coincide con parsers oficiales | D11 en `docs/resultados_pruebas.md` |

## 5. Decisiones registradas
Ver `INDICE.md` (ADR-0001 a ADR-0017).

## 6. Problemas abiertos
1. **Presencia quieta**: sin método fiable (ADR-0018; diseño propio en ADR-0019, antes ADR-0012).
2. **Nube**: atasco de la pila de red con CPU libre en 0.1.4, sin causa; corrección de hora SNTP tras
   reinicio por software (401 en `/crudo`); push sin PC (ADR-0010, `docs/pendientes_nube.md`).
3. **Memoria**: margen ajustado con tormentas de difusión en la red (ADR-0009).
4. **Geometría**: no exigir medición de distancias; diseñar prueba de cobertura (ADR-0020; FTM en ADR-0021; antes ADR-0014).
5. **Subportadoras físicas** del modo de 12 bits no documentadas; comparar con modo de 8 bits (ADR-0011).
6. **PC .89**: revisar con Microsoft Defender (análisis completo y sin conexión) por el barrido de red.
7. **Repositorio sin remoto**: definir copia de respaldo/remoto privado para migrar (pendiente).
8. `kit_captura/scripts/verificar_kit.py` espera la IP solo 60 s; el hotspot tardó 62,7 s → ampliar a 120 s (kit 1.1.1).

## 7. Lo que se puede y no se puede afirmar hoy
- **Sí:** detección de movimiento en tiempo real con una placa ESP32-C5 de bajo costo; operación en
  red local sin nube; envío a Firebase probado en pruebas de hasta 75 min.
- **No:** presencia de personas quietas, respiración, alertas de inactividad, funcionamiento autónomo
  prolongado con nube, uso clínico.
