#!/data/data/com.termux/files/usr/bin/bash
# Captura de la via local en el celular (Termux) con la pantalla apagada.
#
# Uso:   bash ~/kit_movil/scripts/capturar.sh <codigo> <IP_de_la_placa> [duracion_s]
# Ej.:   bash ~/kit_movil/scripts/capturar.sh K001 192.168.8.102 1800
#
# - termux-wake-lock al empezar: Android no suspende la CPU de Termux con la pantalla apagada.
# - termux-wake-unlock SIEMPRE al terminar: por duracion, por Ctrl+C o por error (trap EXIT).
#   Si Android cierra Termux a la fuerza, el trap no corre, pero el bloqueo muere con Termux.
# - La captura queda en ~/kit_movil/datos/crudos/<codigo>_local.csv y su resumen; el codigo de
#   salida es el del receptor (130 si se detuvo con Ctrl+C).

set -u
DIR="$(cd "$(dirname "$0")" && pwd)"

if [ $# -lt 2 ]; then
    echo "Uso: bash $0 <codigo> <IP_de_la_placa> [duracion_s, por defecto 1800]"
    exit 2
fi
CODIGO="$1"
IP="$2"
DURACION="${3:-1800}"

liberar() {
    termux-wake-unlock >/dev/null 2>&1 || true
    echo "capturar.sh: termux-wake-unlock hecho"
}
trap liberar EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

termux-wake-lock
echo "capturar.sh: termux-wake-lock activo; captura $CODIGO desde $IP durante $DURACION s"
python "$DIR/receptor_local.py" --id-sesion "$CODIGO" --duracion "$DURACION" --ip "$IP" --sin-bind
exit $?
