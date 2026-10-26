# ADR-0012: Descartar la presencia de esp-radar y diseñar un detector propio

- **Estado:** Reemplazada por ADR-0018 y ADR-0019 (2026-10-26). Antes: Propuesta (2026-10-24).
- **Reemplazo:** el descarte de la presencia de esp-radar pasa a ADR-0018 (Aceptada); el diseño del detector propio, a ADR-0019 (Propuesta). Este texto no se modifica.
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** ambos
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
S002 (sala vacía, ~5 min): presencia 100 % falsa por deriva; además el entrenamiento exige sala vacía y se pierde al reiniciar.

## Decisión
El visor muestra la presencia como "no disponible". Plan: detector de movimiento sin calibración tipo WiDetect (autocorrelación de |H|²) + detector de respiración (0,1–0,5 Hz) + máquina de estados `movimiento / presente_quieto / sin_evidencia`, **nunca `vacia`** sin evidencia.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Autocalibración aprendiendo el vacío | Circular: necesita un detector de presencia fiable; una persona dormida se aprendería como fondo. |
| Copiar y modificar esp-radar para guardar plantillas | Medio a un día de trabajo y sigue siendo caja negra. |
| Novelty detection con sala vacía (OC-SVM) | Sigue necesitando sala vacía. |

## Consecuencias
- Con una antena no se usa la fase: alcance limitado y puntos ciegos para respiración.
- Requiere datos etiquetados con video y metrónomo.

## Evidencia
- Zhang et al., WiDetect, IMWUT 2019, DOI 10.1145/3351280.
- Wu et al., DeMan, IEEE JSAC 33(11):2329–2342, 2015.

## Cómo revertir
Volver a mostrar la presencia de esp-radar con `--con-presencia` (no recomendado).
