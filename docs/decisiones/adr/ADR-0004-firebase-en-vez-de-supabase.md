# ADR-0004: Firebase (plan Spark) como nube, en vez de Supabase

- **Estado:** Aceptada (2026-10-22)
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** Deisy
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
Se necesitaba enviar el estado por internet y notificaciones push a Android.

## Decisión
Usar Firebase: Realtime Database + Authentication + Cloud Messaging, plan Spark, sin tarjeta.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Supabase | Las push en Android pasan por FCM igual (guía oficial de Supabase); sumaría una segunda plataforma y Edge Functions. El plan gratuito pausa proyectos tras 7 días de baja actividad. |

## Consecuencias
- Una sola plataforma.
- Spark no tiene Cloud Functions: el push requiere un relé (PC) o pasar a Blaze (tarjeta; la alerta de presupuesto no detiene el gasto). Decisión de Blaze pendiente.
- Supabase queda como opción para historial SQL de investigación.

## Evidencia
- https://firebase.google.com/pricing
- https://supabase.com/docs/guides/platform/free-project-pausing

## Cómo revertir
Mover la vía nube a otro servicio; la vía local no depende de Firebase.
