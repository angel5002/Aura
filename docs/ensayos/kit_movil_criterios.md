# Criterios de la prueba del kit móvil (celular con Termux en AURA-LAB)

Fuente **única** de los umbrales: `analisis/verificar_captura.py` (y su copia en `kit_movil/`) lee el bloque
`criterios` de este archivo; no tiene valores propios. Un cambio de umbral se hace aquí, **antes** de la prueba, con
commit y una línea en `docs/decisiones/bitacora.md`. Después de la prueba no se cambian (regla 11 de `CLAUDE.md`).

Relacionados: ADR-0023 (Aceptada, 2026-10-26), `docs/red_aura.md`, `kit_movil/LEEME.md`.

## Criterios (por placa; un archivo `<código>_local.csv` = una placa)

| # | Criterio | Umbral | Cómo se mide |
|---|---|---|---|
| 1 | Pérdida | **< 1 %** (estricto) | número de secuencia, mismo contador que `receptor_local.py` (épocas por reinicio) |
| 2 | Huecos | **0 huecos mayores de 5 s** | tiempo entre dos datagramas `A1` consecutivos según `t_pc_unix`, del primero al último |
| 3 | Tasa de CSI | **mediana de CSI/s en ventanas de 10 s ≥ 80 % de la de S002** | ventanas de 10 s completas desde el primer datagrama (`t_pc_unix`); la última, incompleta, no cuenta |
| 4 | Reinicios de la placa | **0** | ningún reinicio detectado por `ts_ms` (receptor: `ts_ms` de una muestra retrocede) **y** `encendido_s` de la telemetría nunca retrocede; sin telemetría: NO EVALUADO |
| 5 | Termux sin cierres | **sí** | existe `<código>_local_resumen.json`, el receptor terminó **por duración** (`"fin": "duracion"`, no `usuario` ni `error`) y hay **un solo** archivo de captura para la sesión (`<código>*_local.csv` en la misma carpeta) |

Protocolo de la prueba del kit (`kit_movil/LEEME.md`, 5.a): un solo bloque de 30 min (`--duracion 1800`), solo el
celular como receptor, sala vacía y el mismo montaje.

Además se informa, sin criterio: `t_us` = 0 (placa sin hora válida; tras un reinicio por software la placa puede
conservar la hora anterior, F2), reinicios por secuencia (respaldo), la memoria mínima por intervalo, el **% de
tiempo en MOVIMIENTO** (`motion_status` de las muestras; con la sala vacía se compara con S002: 0,25 % en su tramo
"vacía" de 290 s, 0,15 % en todo el archivo; aproximado) y, de la
telemetría de la placa, `motivo_reinicio` y `encendido_s`, para distinguir cortes de alimentación (`encendido`),
caídas de tensión (`brownout`) y fallos de software (`panico`, `wdt*`).

## Valores que lee el verificador

```criterios
perdida_menor_que_pct = 1.0
hueco_max_s = 5.0
ventana_tasa_s = 10.0
tasa_csi_factor_min = 0.80
tasa_csi_ref_s002 = 100.40
reinicios_max = 0
archivos_por_sesion = 1
```

`tasa_csi_ref_s002` = mediana de CSI/s de `datos/crudos/S002_local.csv` (24/10/2026, placa B, receptor en la PC por
la red de casa) en 61 ventanas completas de 10 s, calculada el 2026-10-26 con este mismo verificador
(`python analisis/verificar_captura.py datos/crudos/S002_local.csv`, con la referencia aún PENDIENTE). **Medido.**
Umbral resultante: 0,80 × 100,40 = **80,32 CSI/s**. Ojo: S002 se tomó con otro router (el de casa); en AURA-LAB la
tasa depende de cuánto responde el B315s al ping de la placa (no verificado).

## Historial

- 2026-10-26: huecos (0 > 5 s) agregados por Deisy antes de la prueba (commit `266000a`, en `docs/guia_salon.md`).
- 2026-10-26: **pérdida pasa de < 1 % a ≤ 2 %**, decidido por Deisy antes de la prueba (commit `57a3349`). El valor
  < 1 % venía de `docs/guia_salon.md` (plan de prueba en casa del 24/10).
- 2026-10-26: **pérdida vuelve a < 1 %**, decidido por Deisy antes de la prueba: es el estándar ya usado en el
  proyecto (D4 y D7a-sim en `docs/plan_pruebas.md`; plan de casa en `docs/guia_salon.md`) y el ≤ 2 % no tenía
  justificación. La clave pasa a `perdida_menor_que_pct` para que la comparación estricta quede explícita.
- 2026-10-26: tasa de CSI con umbral numérico (antes "~100/s", sin umbral), decidido por Deisy antes de la prueba.
- 2026-10-26: criterios 4 (0 reinicios) y 5 (Termux sin cierres) con su definición, decididos por Deisy antes de la
  prueba; `receptor_local.py` guarda en el resumen por qué terminó (`fin`) y la duración pedida.
- 2026-10-27: dato informativo (no criterio) del % de tiempo en MOVIMIENTO para comparar K001 (sala vacía) con S002,
  pedido por Deisy tras ver ~436 CSI/s en K000 (S002: ~100/s). Ningún umbral cambia.
