# Procedimiento: confirmar el bucle de CSI por retransmisión (casos 1, 2 y 3)

Hipótesis de Deisy (**inferida, en verificación**; bitácora 27/10/2026 09:51; ADR-0024, Propuesta): con un receptor por
WiFi, cada datagrama que la placa envía lo reemite el router por el aire con origen = router; la placa, en modo
promiscuo y sin filtro de destino, lo mide como CSI del router y genera otro datagrama (bucle). Sin receptor, o con
receptor por cable, no hay reemisión por el aire y la tasa debería quedar en ~100 CSI/s (ping de 100 Hz).

Criterios **fijados antes de ejecutar** (commit antes de la primera ejecución). Firmware: el que tenga la placa en ese
momento (hoy 0.1.3, sin filtro de destino). No se graba nada para esta prueba.

## Qué se mide

La tasa de CSI que cuenta **la propia placa**: en la telemetría por USB (cada 10 s),
`(csi_total₂ − csi_total₁) / (encendido_s₂ − encendido_s₁)`. No depende del receptor ni de su pérdida. La telemetría
dice además cuántos receptores hay suscritos (`local_subs`). Script: `analisis/pruebas/bucle_csi.py` (escucha el USB
**sin reiniciar** la placa; registra en `docs/resultados_pruebas.md`).

## Montaje (igual en los tres casos, sin cambios entre casos)

- Placa B conectada **por USB a la PC principal** (para leer la telemetría sin receptor); conectada a AURA-LAB. No
  se reinicia entre casos. Huawei encendido en su sitio.
- Nada más que cambie entre casos salvo el receptor. Los casos se hacen seguidos.
- Antes: comprobar que la placa sigue en AURA-LAB (telemetría `red=principal`) y su IP en el panel.

## Casos

| Caso | Receptor | Obligatorio | Lo que se espera si la hipótesis es cierta | Criterio (por caso) |
|---|---|---|---|---|
| 1 | **Ninguno** (Termux sin capturar, ninguna PC suscrita): `local_subs = 0` | sí | ~100 CSI/s (ping + balizas) | mediana ≤ **150** CSI/s |
| 2 | **Celular por WiFi** en AURA-LAB (`capturar.sh B2 <IP> 180`): `local_subs ≥ 1` | sí | ~400 CSI/s o más (bucle) | mediana ≥ **300** CSI/s |
| 3 | **PC por cable** a un puerto LAN del Huawei (`receptor_local.py --ip <IP> --sin-bind`): `local_subs ≥ 1` | no | ~100 CSI/s (sin reemisión por el aire) | mediana ≤ **150** CSI/s |

Validez de cada caso: **≥ 6 intervalos de 10 s** con la condición de `local_subs` del caso y **sin reinicio**
(`encendido_s` creciente). Si no se cumple: NO EJECUTADA (se repite; no se interpreta).

Comandos (PC principal, entorno `analisis\.venv`; cada uno escucha 120 s):

```
python C:\aura\analisis\pruebas\bucle_csi.py --caso 1 --id-sesion B1 --segundos 120
(lanzar en el celular: bash ~/kit_movil/scripts/capturar.sh B2 <IP> 180, esperar 20 s, y entonces)
python C:\aura\analisis\pruebas\bucle_csi.py --caso 2 --id-sesion B2u --segundos 120
(opcional, PC por cable al Huawei y receptor en la PC)
python C:\aura\analisis\pruebas\bucle_csi.py --caso 3 --id-sesion B3 --segundos 120
```

## Interpretación (fijada antes)

- **Hipótesis confirmada:** caso 1 APROBADO y caso 2 APROBADO, con mediana(2) / mediana(1) ≥ **2,5**. Si además se hizo
  el caso 3 y salió APROBADO, se confirma que el bucle es por la **reemisión por WiFi** y no por tener cualquier
  receptor.
- **Hipótesis refutada:** caso 2 con mediana ≤ 150 CSI/s (con un receptor WiFi no sube la tasa).
- **Otra causa:** caso 1 con mediana > 150 CSI/s (la tasa sube sin receptor: tráfico ajeno o del propio router;
  sigue valiendo el motivo (b) de ADR-0024).
- Cualquier otra combinación: no concluyente; se informa sin cambiar los umbrales.

## Evidencia previa (a posteriori; NO sustituye a los casos)

Leída con el mismo cálculo el 27/10/2026, antes de este commit, en capturas ya existentes con otro montaje:
- F2 (`datos/crudos/F2_auralab.csv`, 26/10, AURA-LAB, placa junto a la PC, `local_subs = 0`): **104,8 CSI/s** (16 intervalos).
- S002 (`datos/crudos/S002.csv`, 24/10, router de casa, receptor por cable, `local_subs = 1`): **100,3 CSI/s** (60 intervalos).
- K000 (`datos/crudos/K000_local.csv`, 27/10, AURA-LAB, celular por WiFi; telemetría recibida por la vía local):
  `csi_total` de 44 980 a 66 775 en 50 s = **~436 CSI/s**.

Apoyan la hipótesis, pero cambian el lugar de la placa, el momento y la red; por eso se hacen los casos seguidos con
el mismo montaje.

## Después

Anotar el resultado en la bitácora y en ADR-0024 (motivo (a): confirmado / refutado / no concluyente). La decisión
de grabar 0.1.5 la toma Deisy después de K001, de este procedimiento y de K002.
