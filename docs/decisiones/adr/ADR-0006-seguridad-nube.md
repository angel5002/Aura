# ADR-0006: Modelo de seguridad de la nube: cuenta por dispositivo y reglas por UID

- **Estado:** Aceptada (2026-10-22)
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** ambos
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
Con la placa en casas ajenas, los datos de actividad de una vivienda son datos personales (Ley 29733).

## Decisión
Cada placa entra con su propia cuenta (correo y contraseña de dispositivo); **nunca la clave de servicio en la placa**. Reglas: la placa escribe `/sensores` y `/crudo` y lee `/comandos`; la persona lee y escribe comandos; sin acceso anónimo; validaciones de estructura y tamaño; comandos con hora del servidor. La presencia sin entrenar no puede publicarse como `vacia`.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Lectura anónima | Cualquiera con el APK leería el estado de la casa. |
| Clave de servicio en la placa | Control total del proyecto si se extrae. |

## Consecuencias
- Credencial de la placa sin cifrado de flash (prototipo): se revoca inhabilitando la cuenta.
- Correos de dispositivo sin buzón real (p. ej., dominio `.invalid`) para evitar restablecimientos por terceros.
- A y C inhabilitadas hasta que tengan habitación propia.

## Evidencia
- `firebase/reglas_publicar.json` (SHA-256 d2ce131e…, comprobado el 26/10/2026); T5 39/39 contra ese archivo en `docs/resultados_pruebas.md` (23/10 01:04) y `docs/resultados_pruebas_observaciones.md` (T5 ejecutada).

## Cómo revertir
Rotar contraseñas desde la consola; regenerar reglas con `firebase/preparar_reglas.py`.
