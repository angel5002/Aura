#!/data/data/com.termux/files/usr/bin/bash
# Exporta una captura del celular a Download para pasarla a la PC por USB en modo "Transferencia de archivos"
# (MTP), SIN depuracion USB ni adb.
#
# Uso:   bash ~/kit_movil/scripts/exportar.sh <codigo>
# Ej.:   bash ~/kit_movil/scripts/exportar.sh K001
#
# Copia ~/kit_movil/datos/crudos/<codigo>_local.csv y <codigo>_local_resumen.json (si existe) a
# Download/aura_export/<codigo>/, escribe SHA256SUMS con sus SHA-256 y comprueba la copia.
# Requiere haber ejecutado una vez termux-setup-storage (permiso de archivos).
# En la PC: python C:\aura\analisis\verificar_export.py <carpeta copiada> [--copiar-a-crudos]
# Despues de pasarla y verificarla en la PC, BORRAR Download/aura_export/<codigo> (datos de personas).

set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
CRUDOS="$DIR/../datos/crudos"
DOWNLOAD="$HOME/storage/downloads"

if [ $# -ne 1 ]; then
    echo "Uso: bash $0 <codigo>"
    exit 2
fi
CODIGO="$1"
case "$CODIGO" in
    ""|*/*|.*) echo "ERROR: codigo invalido: '$CODIGO'"; exit 2 ;;
esac
if [ ! -d "$DOWNLOAD" ]; then
    echo "ERROR: no existe $DOWNLOAD. Ejecuta una vez: termux-setup-storage (y acepta el permiso de archivos)."
    exit 3
fi
CSV="$CRUDOS/${CODIGO}_local.csv"
RESUMEN="$CRUDOS/${CODIGO}_local_resumen.json"
if [ ! -f "$CSV" ]; then
    echo "ERROR: no existe $CSV"
    exit 4
fi
DESTINO="$DOWNLOAD/aura_export/$CODIGO"
if [ -e "$DESTINO" ]; then
    echo "ERROR: ya existe Download/aura_export/$CODIGO (no se sobrescribe). Si ya se paso a la PC, borrala primero."
    exit 5
fi
mkdir -p "$DESTINO" || { echo "ERROR: no se pudo crear $DESTINO"; exit 6; }

archivos=("$(basename "$CSV")")
cp "$CSV" "$DESTINO/" || { echo "ERROR: fallo la copia del CSV"; exit 6; }
if [ -f "$RESUMEN" ]; then
    cp "$RESUMEN" "$DESTINO/" || { echo "ERROR: fallo la copia del resumen"; exit 6; }
    archivos+=("$(basename "$RESUMEN")")
else
    echo "AVISO: no hay $(basename "$RESUMEN") (el receptor no termino normalmente); se exporta solo el CSV."
fi

# SHA-256 de los ORIGINALES (no de las copias), en el formato de sha256sum
( cd "$CRUDOS" && sha256sum "${archivos[@]}" ) > "$DESTINO/SHA256SUMS" || { echo "ERROR: fallo SHA256SUMS"; exit 6; }
# Comprobacion de la copia contra los originales
if ! ( cd "$DESTINO" && sha256sum -c --quiet SHA256SUMS ); then
    echo "ERROR: la copia en Download no coincide con el original; no la pases a la PC."
    exit 7
fi

echo "OK: exportado a Download/aura_export/$CODIGO (${#archivos[@]} archivo(s) + SHA256SUMS; copia comprobada)."
echo "En la PC, con el celular por USB en modo 'Transferencia de archivos':"
echo "  copia la carpeta  <telefono>/Download/aura_export/$CODIGO  completa a la PC."
echo "  Verificala: python C:\\aura\\analisis\\verificar_export.py <carpeta copiada> --copiar-a-crudos"
echo "  Despues BORRA Download/aura_export/$CODIGO del celular (datos de personas)."
