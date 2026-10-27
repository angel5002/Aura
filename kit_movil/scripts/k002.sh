#!/data/data/com.termux/files/usr/bin/bash
# K002 con semaforo en la pantalla del celular (docs/ensayos/k002_cruces.md).
#
# Uso:   bash ~/kit_movil/scripts/k002.sh [codigo=K002] [IP=192.168.8.103] [duracion_s=330]
#
# - Lanza receptor_local.py en segundo plano (salida en datos/crudos/<codigo>_receptor.log).
# - Cero del horario = t_pc_unix del PRIMER datagrama A1 de la captura (el mismo cero que usa k002_cruces.py).
# - Semaforo a pantalla completa: AZUL quieta en el Punto 1 (cuenta regresiva); AMARILLO 3 s antes del cruce
#   (1 pitido); ROJO 1 s antes de cada horario 30, 55, ..., 255 s (2 pitidos) = cruzar ida y vuelta; AZUL otra vez
#   5 s despues del horario; VERDE al terminar el horario (300 s, 3 pitidos). Al final, el resumen de la captura.
# - termux-wake-lock al empezar; termux-wake-unlock SIEMPRE al terminar (duracion, error o Ctrl+C), como capturar.sh.
#   Ctrl+C detiene tambien la captura (el receptor guarda su resumen con fin "usuario").
# - Los pitidos usan el caracter de alerta de Termux (bell-character=beep en ~/.termux/termux.properties).
# - El wake-lock no mantiene la PANTALLA encendida: la suspension de pantalla debe ser mayor que la duracion.

set -u
set -m      # control de trabajos: el receptor queda en su propio grupo y SIGINT no le llega ignorado
DIR="$(cd "$(dirname "$0")" && pwd)"
CODIGO="${1:-K002}"
IP="${2:-192.168.8.103}"
DURACION="${3:-330}"
CRUDOS="$DIR/../datos/crudos"
CSV="$CRUDOS/${CODIGO}_local.csv"
LOG="$CRUDOS/${CODIGO}_receptor.log"

case "$CODIGO" in
    ""|*/*|.*) echo "ERROR: codigo invalido: '$CODIGO'"; exit 2 ;;
esac
if [ -e "$CSV" ]; then
    echo "ERROR: ya existe $CSV (no se sobrescriben datos)"
    exit 5
fi
mkdir -p "$CRUDOS"

PID=""
terminar() {
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        kill -INT "$PID" 2>/dev/null           # el receptor guarda su resumen (fin "usuario")
        for _ in $(seq 50); do kill -0 "$PID" 2>/dev/null || break; sleep 0.2; done
        kill -0 "$PID" 2>/dev/null && kill -TERM "$PID" 2>/dev/null
    fi
    termux-wake-unlock >/dev/null 2>&1 || true
    printf '\033[0m\n'
    echo "k002.sh: termux-wake-unlock hecho"
}
trap terminar EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

termux-wake-lock
: > "$LOG"
# Receptor y semaforo escriben en el mismo registro: los dos en modo AÑADIR (>>), para no pisarse.
python "$DIR/receptor_local.py" --id-sesion "$CODIGO" --duracion "$DURACION" --ip "$IP" --sin-bind \
    >> "$LOG" 2>&1 &
PID=$!
echo "k002.sh: captura $CODIGO desde $IP durante $DURACION s; esperando el primer datagrama..."

T0=""
for _ in $(seq 100); do                     # hasta 20 s
    if [ -f "$CSV" ]; then
        T0="$(grep -m1 -E '^[0-9]+\.[0-9]+,"?A1 ' "$CSV" | cut -d, -f1)"
    fi
    [ -n "$T0" ] && break
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.2
done
if [ -z "$T0" ]; then
    echo "ERROR: no llego ningun datagrama en 20 s (revisa la IP y la red). Registro del receptor:"
    tail -5 "$LOG"
    exit 4
fi

python - "$T0" "$PID" 2>>"$LOG" <<'PYEOF'
import os, shutil, sys, time

T0, PID = float(sys.argv[1]), int(sys.argv[2])
CRUCES = [30 + 25 * k for k in range(10)]     # 30, 55, ..., 255 s
FIN_HORARIO = 300
AMARILLO_S, ROJO_S, ROJO_HASTA_S = 3, 1, 5
FONDO = {"AZUL": "\033[44m\033[97m", "AMARILLO": "\033[103m\033[30m", "ROJO": "\033[101m\033[97m",
         "VERDE": "\033[42m\033[97m"}
GLIFOS = {                                     # 5 filas x 4 columnas
    "0": ["####", "#  #", "#  #", "#  #", "####"], "1": ["  # ", " ## ", "  # ", "  # ", " ###"],
    "2": ["####", "   #", "####", "#   ", "####"], "3": ["####", "   #", " ###", "   #", "####"],
    "4": ["#  #", "#  #", "####", "   #", "   #"], "5": ["####", "#   ", "####", "   #", "####"],
    "6": ["####", "#   ", "####", "#  #", "####"], "7": ["####", "   #", "  # ", " #  ", " #  "],
    "8": ["####", "#  #", "####", "#  #", "####"], "9": ["####", "#  #", "####", "   #", "####"],
    "A": [" ## ", "#  #", "####", "#  #", "#  #"], "C": ["####", "#   ", "#   ", "#   ", "####"],
    "E": ["####", "#   ", "### ", "#   ", "####"], "F": ["####", "#   ", "### ", "#   ", "#   "],
    "I": ["### ", " #  ", " #  ", " #  ", "### "], "N": ["#  #", "## #", "# ##", "#  #", "#  #"],
    "P": ["### ", "#  #", "### ", "#   ", "#   "], "Q": [" ## ", "#  #", "#  #", "# ##", " ###"],
    "R": ["### ", "#  #", "### ", "# # ", "#  #"], "T": ["####", " #  ", " #  ", " #  ", " #  "],
    "U": ["#  #", "#  #", "#  #", "#  #", "####"], "Z": ["####", "   #", " ## ", "#   ", "####"],
    " ": ["    "] * 5,
}


def grande(texto):
    filas = ["", "", "", "", ""]
    for c in texto:
        g = GLIFOS.get(c, GLIFOS[" "])
        for i in range(5):
            filas[i] += g[i].replace("#", "█") + " "
    return filas


def estado(t):
    """(color, palabra, numero, subtitulo) para t segundos desde el primer datagrama."""
    if t >= FIN_HORARIO:
        return "VERDE", "FIN", None, "VERDE - fin del horario: ya puedes moverte. Esperando el cierre de la captura."
    for k, tc in enumerate(CRUCES, 1):
        if tc - AMARILLO_S <= t < tc - ROJO_S:
            return "AMARILLO", "PREPARA", None, f"AMARILLO - cruce {k} de 10 en {tc - t:.0f} s: preparate"
        if tc - ROJO_S <= t < tc + ROJO_HASTA_S:
            return "ROJO", "CRUZA", None, f"ROJO - cruce {k} de 10: ida y vuelta por la mitad de la linea"
    prox = next((tc for tc in CRUCES if tc > t), None)
    if prox is not None:
        k = CRUCES.index(prox) + 1
        return "AZUL", "QUIETA", int(prox - AMARILLO_S - t) + 1, f"AZUL - quieta en el Punto 1; cruce {k} de 10"
    return "AZUL", "QUIETA", int(FIN_HORARIO - t) + 1, "AZUL - quieta en el Punto 1 hasta el fin"


def dibujar(color, palabra, numero, sub):
    cols, filas = shutil.get_terminal_size((40, 20))
    bloque = grande(palabra) + [""] + (grande(str(numero)) if numero is not None else [])
    if max(len(f) for f in bloque) > cols:                    # pantalla estrecha: texto normal
        bloque = [palabra] + ([str(numero)] if numero is not None else [])
    lineas = [""] * max(0, (filas - len(bloque) - 3) // 2) + bloque + ["", sub[:cols]]
    lineas += [""] * max(0, filas - len(lineas) - 1)
    salida = "\033[H" + FONDO[color] + "\033[1m"
    salida += "\n".join(l.center(cols)[:cols] for l in lineas[: filas - 1])
    sys.stdout.write(salida + "\033[0m")
    sys.stdout.flush()


def pitar(n):
    for i in range(n):
        sys.stdout.write("\a"); sys.stdout.flush()
        if i < n - 1:
            time.sleep(0.25)


def vivo(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


previo = None
sys.stdout.write("\033[?25l\033[2J")                        # oculta el cursor y limpia
try:
    while True:
        t = time.time() - T0
        e = estado(t)
        if e != previo:
            if previo is None or e[0] != previo[0]:
                sys.stderr.write(f"[semaforo] t={t:6.1f} s {e[3]}\n")   # al registro (<codigo>_receptor.log)
                sys.stderr.flush()
                pitar({"AMARILLO": 1, "ROJO": 2, "VERDE": 3}.get(e[0], 0))
            dibujar(*e)
            previo = e
        if e[0] == "VERDE" and not vivo(PID):
            break
        time.sleep(0.1)
except KeyboardInterrupt:
    sys.stdout.write("\033[0m\033[?25h\n"); sys.stdout.flush()
    sys.exit(130)
sys.stdout.write("\033[0m\033[?25h\033[2J\033[H"); sys.stdout.flush()
PYEOF
RC_SEMAFORO=$?
if [ "$RC_SEMAFORO" -ne 0 ]; then
    if [ "$RC_SEMAFORO" -ne 130 ]; then
        echo "ERROR en el semaforo (codigo $RC_SEMAFORO). Ultimas lineas del registro:"
        tail -5 "$LOG"
    fi
    exit "$RC_SEMAFORO"                     # Ctrl+C u error: terminar() detiene la captura y libera el bloqueo
fi

wait "$PID"
RC=$?
PID=""
echo "=== Resumen de la captura $CODIGO ==="
sed -n '/--- Resumen ---/,$p' "$LOG"
exit "$RC"
