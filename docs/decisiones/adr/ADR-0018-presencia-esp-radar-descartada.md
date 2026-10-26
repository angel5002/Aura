# ADR-0018: Presencia de esp-radar descartada; el visor la muestra como "no disponible"

- **Estado:** Aceptada (2026-10-26)
- **Fecha:** 2026-10-26
- **Decide:** Deisy
- **Equipo donde se tomó:** conversación de diseño; registrada en la PC principal
- **Relacionadas:** reemplaza (en parte) a ADR-0012; ADR-0019

## Contexto
S002 (sala vacía, ~5 min, una sesión): la presencia de esp-radar dio 100 % de falsos positivos por deriva. Además,
su entrenamiento exige la sala vacía y se pierde al reiniciar la placa.

## Decisión
No usar la presencia de esp-radar. El visor la muestra como **"no disponible"** por defecto; `--con-presencia`
solo existe para análisis.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Seguir usando la presencia de esp-radar con reentrenamiento | 100 % de falsos positivos en S002; exige sala vacía en cada arranque. |
| Copiar y modificar esp-radar para guardar plantillas | Medio a un día de trabajo y sigue siendo caja negra. |

## Consecuencias
- No se afirma detección de presencia quieta (hackathon, clases, publicaciones).
- El estado mostrado se limita a calibrando / movimiento.
- El diseño de un detector propio sigue abierto en ADR-0019.

## Evidencia
- `docs/evaluacion_S002.md` (medido, 1 sesión, sin verificación independiente de vacío).
- `analisis/visor.py` (`--con-presencia`; por defecto "no disponible").

## Cómo revertir
Volver a mostrar la presencia de esp-radar con `--con-presencia` (no recomendado).
