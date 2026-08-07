#!/usr/bin/env bash
# Compila el C++ de Jam y comprueba que el binario haya quedado al día.
#
#     ./BUILD-JAM.sh              compila y verifica
#     ./BUILD-JAM.sh --solo-ver   sólo verifica, sin compilar
#
# Es un LANZADOR: toda la lógica vive en `tools/build.py`, una sola vez. Duplicarla acá dejaría dos
# versiones que se separan en silencio — el mismo error que tenían los tres lectores de ficha JSON.
#
# Sale 0 si el binario está al día, 1 si no, así que sirve para encadenar.
set -euo pipefail

# La carpeta del script, no el cwd: se puede ejecutar desde cualquier lado.
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PY="$(command -v python3 || command -v python || true)"
if [[ -z "$PY" ]]; then
    echo "✗ no encuentro python3 en el PATH" >&2
    exit 1
fi

exec "$PY" tools/build.py "$@"
