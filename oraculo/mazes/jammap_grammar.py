"""Conformidad sintáctica de JamMap — el lado ejecutable de `dsl-design/jammap.gbnf`.

`conforms(text)` responde: ¿toda línea es algo que el parser RECONOCE (header de piso, directiva @ bien
formada, fila de grilla o comentario), o hay líneas que el parser DESCARTARÍA EN SILENCIO (prosa, una
directiva malformada, una fila de grilla fuera de un piso)? Esas líneas silenciosamente-descartadas son el
modo de falla real del LLM: el mapa "parsea" pero salió otra cosa. Es el pre-check barato que más adelante
complementa la decodificación restringida (GBNF).

Importa los MISMOS regexes y el MISMO _GRID_CHARS que parse() → no puede driftar del parser.
"""
from __future__ import annotations

from .ascii_map import (
    _FLOOR_RE, _GRID_CHARS, _GRAVITY_RE, _GATE_RE, _HAZARD_RE, _PORTAL_RE, _SEAM_RE, _SPACE_RE,
    _SWITCH_RE,
)
from .couple import _CONSUME_RE, _POWER_RE
from .electric import _BREAKER_RE, _CAPACITY_RE, _DEMAND_RE, _ELEC_CHARS, _ELEC_HDR, _PRIORITY_RE
from .resource import (
    _RES_BUDGET, _RES_CAP, _RES_DRAIN, _RES_HDR, _RES_SOURCE, _RES_START,
)

# directiva → su regex; el orden no importa, el match sí. Incluye el canal RECURSO (aspecto aparte):
# sus directivas son tan reconocibles como las de nav → el LLM puede emitir '[Recurso]' sin falso "descartado".
_DIRECTIVES = {
    "@portal": _PORTAL_RE, "@gravity": _GRAVITY_RE, "@seam": _SEAM_RE,
    "@switch": _SWITCH_RE, "@gate": _GATE_RE, "@hazard": _HAZARD_RE,
    "@space": _SPACE_RE,                   # tipo de espacio declarado (contrato con JamPCG)
    "@capacity": _CAPACITY_RE,             # OJO: antes de '@cap' (prefijo) — capacidad de una fuente eléctrica
    "@drain": _RES_DRAIN, "@cap": _RES_CAP, "@start": _RES_START,
    "@budget": _RES_BUDGET, "@source": _RES_SOURCE,
    "@power": _POWER_RE,                   # ACOPLE cross-aspecto: carga eléctrica → flag de una @gate de nav
    "@breaker": _BREAKER_RE,               # acople 2-vías: un breaker que el jugador prende re-energiza cables
    "@consume": _CONSUME_RE,               # acople recurso↔eléctrico: carga alimentada quema/genera un recurso
    "@demand": _DEMAND_RE,                 # consumo de una carga eléctrica (modelo de sobrecarga)
    "@priority": _PRIORITY_RE,             # prioridad de una carga (load-shedding graceful bajo sobrecarga)
}


def conforms(text: str) -> tuple[bool, str]:
    """Devuelve (ok, motivo). ok=True si el texto es JamMap sintácticamente limpio (todo lo que el LLM
    escribió es reconocible por el parser, sin líneas descartadas). Espeja el bucle de parse()."""
    seen_floor = False
    in_floor = False                       # cur is not None: estamos dentro de un piso nav (acepta grilla nav)
    in_electric = False                    # dentro de un [Electrico N]: acepta grilla con alfabeto eléctrico
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s:
            continue
        if _FLOOR_RE.match(s):
            seen_floor = True
            in_floor = True
            in_electric = False
            continue
        if _ELEC_HDR.match(s):                 # bloque [Electrico N]: canal de potencia (grilla propia)
            in_floor = False
            in_electric = True
            continue
        if _RES_HDR.match(s):                  # bloque [Recurso N]: canal de directivas, sin grilla
            in_floor = False
            in_electric = False
            continue
        directive = next((d for d in _DIRECTIVES if s.startswith(d)), None)
        if directive is not None:
            if not _DIRECTIVES[directive].match(s):
                return False, f"línea {i}: directiva {directive} malformada (el parser la descartaría): {s!r}"
            in_floor = False               # como parse(): una directiva resetea cur → la grilla debe venir antes
            in_electric = False
            continue
        if line.lstrip().startswith("# "):  # comentario/leyenda
            continue
        if in_electric:                     # fila del canal eléctrico (alfabeto S/L/-/|/+/./#)
            if all(c in _ELEC_CHARS for c in line):
                continue
            bad = sorted({c for c in line if c not in _ELEC_CHARS})
            return False, f"línea {i}: fila eléctrica con chars inválidos {bad}: {s!r}"
        # fila de grilla nav: sólo válida DENTRO de un piso y con todos los chars glifos
        if all(c in _GRID_CHARS for c in line):
            if not in_floor:
                return False, f"línea {i}: fila de grilla fuera de un [Piso N] (el parser la descartaría): {s!r}"
            continue
        bad = sorted({c for c in line if c not in _GRID_CHARS})
        return False, f"línea {i}: ni header/directiva/comentario ni grilla — chars inválidos {bad}: {s!r}"

    if not seen_floor:
        return False, "no hay ningún [Piso N]"
    return True, "ok"
