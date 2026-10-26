# ADR-0019: Diseño de un detector propio (WiDetect + respiración + estados)

- **Estado:** Propuesta (2026-10-26)
- **Fecha:** 2026-10-26
- **Decide:** ambos (se decide con los resultados de la fase 1)
- **Equipo donde se tomó:** conversación de diseño; registrada en la PC principal
- **Relacionadas:** reemplaza (en parte) a ADR-0012; ADR-0018

## Contexto
Con la presencia de esp-radar descartada (ADR-0018) no hay forma de distinguir una persona quieta de una sala
vacía.

## Decisión (propuesta)
Detector de movimiento sin calibración tipo WiDetect (autocorrelación de |H|²) + detector de respiración
(0,1–0,5 Hz) + máquina de estados `movimiento / presente_quieto / sin_evidencia`, **nunca `vacia`** sin evidencia.
Se aprueba, ajusta o descarta con los resultados de la fase 1 (la fase 1 aún no está definida en el repositorio).

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Autocalibración aprendiendo el vacío | Circular: necesita un detector de presencia fiable; una persona dormida se aprendería como fondo. |
| Novelty detection con sala vacía (OC-SVM) | Sigue necesitando sala vacía. |

## Consecuencias
- Con una antena no se usa la fase de la señal: alcance limitado y puntos ciegos para respiración.
- Requiere datos etiquetados con video y metrónomo.

## Evidencia
- Zhang et al., WiDetect, IMWUT 2019, DOI 10.1145/3351280.
- Wu et al., DeMan, IEEE JSAC 33(11):2329–2342, 2015.
- `docs/investigacion/AURA_mapa_investigacion.md`.

## Cómo revertir
Es una propuesta: si la fase 1 no la respalda, se marca como Descartada.
