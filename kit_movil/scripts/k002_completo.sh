#!/data/data/com.termux/files/usr/bin/bash
# K002 completa con un solo comando (docs/ensayos/k002_cruces.md).
#
# Uso:   bash ~/kit_movil/scripts/k002_completo.sh [codigo=K002] [IP=192.168.8.103] [duracion_s=330]
#
# 1. bell-character = beep en ~/.termux/termux.properties (solo si hace falta, sin duplicar) + termux-reload-settings.
# 2. Pantalla BLANCA "VE AL PUNTO 1" con cuenta regresiva de 20 s, SIN capturar todavia (el celular esta del otro lado
#    de la linea: da tiempo a ir al Punto 1 sin cruzar con la captura iniciada).
# 3. k002.sh (captura + semaforo; el cero del horario sigue siendo el primer datagrama de la captura).
# 4. Si k002.sh termino bien, exportar.sh; si no, muestra el error y NO exporta.

set -u
DIR="$(cd "$(dirname "$0")" && pwd)"
CODIGO="${1:-K002}"
IP="${2:-192.168.8.103}"
DURACION="${3:-330}"
PROPIEDADES="$HOME/.termux/termux.properties"
ESPERA_S=20

# 1) Pitidos: una sola linea activa "bell-character = beep"
mkdir -p "$(dirname "$PROPIEDADES")"
touch "$PROPIEDADES"
if grep -Eq '^[[:space:]]*bell-character[[:space:]]*=[[:space:]]*beep[[:space:]]*$' "$PROPIEDADES"; then
    echo "k002_completo.sh: bell-character = beep ya estaba"
elif grep -Eq '^[[:space:]]*bell-character[[:space:]]*=' "$PROPIEDADES"; then
    sed -i -E 's/^[[:space:]]*bell-character[[:space:]]*=.*/bell-character = beep/' "$PROPIEDADES"
    echo "k002_completo.sh: bell-character cambiado a beep"
else
    echo 'bell-character = beep' >> "$PROPIEDADES"
    echo "k002_completo.sh: bell-character = beep agregado"
fi
termux-reload-settings

# 2) Cuenta regresiva en BLANCO, sin captura
python - "$ESPERA_S" <<'PYEOF'
import shutil, sys, time

ESPERA = int(sys.argv[1])
GLIFOS = {                                     # 5 filas x 4 columnas (mismo estilo que k002.sh)
    "0": ["####", "#  #", "#  #", "#  #", "####"], "1": ["  # ", " ## ", "  # ", "  # ", " ###"],
    "2": ["####", "   #", "####", "#   ", "####"], "3": ["####", "   #", " ###", "   #", "####"],
    "4": ["#  #", "#  #", "####", "   #", "   #"], "5": ["####", "#   ", "####", "   #", "####"],
    "6": ["####", "#   ", "####", "#  #", "####"], "7": ["####", "   #", "  # ", " #  ", " #  "],
    "8": ["####", "#  #", "####", "#  #", "####"], "9": ["####", "#  #", "####", "   #", "####"],
    "A": [" ## ", "#  #", "####", "#  #", "#  #"], "E": ["####", "#   ", "### ", "#   ", "####"],
    "L": ["#   ", "#   ", "#   ", "#   ", "####"], "N": ["#  #", "## #", "# ##", "#  #", "#  #"],
    "O": [" ## ", "#  #", "#  #", "#  #", " ## "], "P": ["### ", "#  #", "### ", "#   ", "#   "],
    "T": ["####", " #  ", " #  ", " #  ", " #  "], "U": ["#  #", "#  #", "#  #", "#  #", "####"],
    "V": ["#  #", "#  #", "#  #", " ## ", " ## "], " ": ["    "] * 5,
}


def grande(texto):
    filas = ["", "", "", "", ""]
    for c in texto:
        g = GLIFOS.get(c, GLIFOS[" "])
        for i in range(5):
            filas[i] += g[i].replace("#", "█") + " "
    return filas


def dibujar(n):
    cols, filas = shutil.get_terminal_size((40, 20))
    bloque = grande("VE AL") + [""] + grande("PUNTO 1") + [""] + grande(str(n))
    if max(len(f) for f in bloque) > cols:
        bloque = ["VE AL PUNTO 1", str(n)]
    sub = f"La captura empieza en {n} s. No cruces la linea."
    lineas = [""] * max(0, (filas - len(bloque) - 3) // 2) + bloque + ["", sub[:cols]]
    lineas += [""] * max(0, filas - len(lineas) - 1)
    sys.stdout.write("\033[H\033[107m\033[30m\033[1m"
                     + "\n".join(l.center(cols)[:cols] for l in lineas[: filas - 1]) + "\033[0m")
    sys.stdout.flush()


sys.stdout.write("\033[?25l\033[2J")
try:
    fin = time.time() + ESPERA
    previo = None
    while (falta := fin - time.time()) > 0:
        n = int(falta) + 1
        if n != previo:
            dibujar(n)
            previo = n
        time.sleep(0.05)
except KeyboardInterrupt:
    sys.stdout.write("\033[0m\033[?25h\033[2J\033[H")
    sys.stdout.flush()
    sys.exit(130)
sys.stdout.write("\033[0m\033[?25h\033[2J\033[H")
sys.stdout.flush()
PYEOF
RC=$?
if [ "$RC" -ne 0 ]; then
    echo "k002_completo.sh: cuenta regresiva interrumpida (codigo $RC); NO se inicio la captura"
    exit "$RC"
fi

# 3) Captura con semaforo
bash "$DIR/k002.sh" "$CODIGO" "$IP" "$DURACION"
RC=$?
if [ "$RC" -ne 0 ]; then
    echo "k002_completo.sh: ERROR: k002.sh termino con codigo $RC; NO se exporta."
    echo "Revisa ~/kit_movil/datos/crudos/${CODIGO}_receptor.log"
    exit "$RC"
fi

# 4) Exportar
bash "$DIR/exportar.sh" "$CODIGO"
exit $?
