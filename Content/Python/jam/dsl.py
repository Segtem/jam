"""DSL de Jam — una línea de texto = una herramienta con params. El norte del proyecto: lenguaje
para crear, oráculo para verificar.

    scatter asset=SM_Rock count=20 area=650 seed=7
    drop SM_Barrel
    spline height=350 thickness=30
    verify | confirm | discard | search muro | help

Los NOMBRES (verbos + params + keywords) están en inglés; la prosa (docs/veredictos) en español.
Sólo parsea y coacciona tipos; QUIÉN spawnea/previsualiza lo decide `jam.panel` (reusa el mismo
preview/confirm/discard del panel). Los verbos y sus params salen de `jam.tools.REGISTRO`, así
que agregar una herramienta al registro la habilita en la consola sin tocar este archivo.
"""

from __future__ import annotations

import shlex

from . import tools

# Alias cómodos para el que tipea rápido (nombre corto → param real).
_ALIAS = {"n": "count", "s": "seed", "h": "height", "t": "thickness"}


def parsear(linea: str) -> dict:
    """'scatter SM_Rock cantidad=20' → {'verbo','asset','params'} (params como strings sin coaccionar)."""
    try:
        toks = shlex.split((linea or "").strip())
    except ValueError:
        toks = (linea or "").split()
    if not toks:
        return {"verbo": "", "asset": None, "params": {}}
    verbo = toks[0].lower()
    asset = None
    params: dict[str, str] = {}
    for t in toks[1:]:
        if "=" in t:
            k, v = t.split("=", 1)
            k = k.strip().lower()
            if k in ("asset", "a"):
                asset = v
            else:
                params[_ALIAS.get(k, k)] = v
        else:
            asset = t  # token suelto = nombre de asset (conveniencia: 'scatter SM_Rock')
    return {"verbo": verbo, "asset": asset, "params": params}


def coaccionar(verbo: str, params: dict) -> tuple[dict, list[str]]:
    """Convierte cada param al tipo de su default en REGISTRO. Devuelve (kwargs, desconocidos)."""
    spec = tools.REGISTRO.get(verbo, {}).get("params", {})
    out: dict = {}
    desconocidos: list[str] = []
    for k, v in params.items():
        if k not in spec:
            desconocidos.append(k)
            continue
        d = spec[k]
        try:
            if isinstance(d, bool):
                out[k] = str(v).lower() in ("1", "true", "si", "sí", "yes", "on")
            elif isinstance(d, int):
                out[k] = int(float(v))
            elif isinstance(d, float):
                out[k] = float(v)
            else:
                out[k] = v
        except (TypeError, ValueError):
            desconocidos.append(f"{k}={v}?")
    return out, desconocidos


def ayuda() -> str:
    """Texto de ayuda generado desde el registro (siempre en sync con las herramientas reales)."""
    lineas = ["Jam DSL — un comando por línea:"]
    for nombre, info in tools.REGISTRO.items():
        ps = " ".join(f"{k}=" for k in info["params"])
        lineas.append(f"  {nombre:<14}{ps:<34}— {info['doc']}")
    lineas += [
        "  verify                                       — corre el oráculo de espacio sobre el nivel",
        "  confirm / discard                            — fija o borra el preview activo",
        "  search <texto>                               — lista assets del proyecto",
        "  help                                         — esta ayuda",
        "asset: 'scatter SM_Rock …' o 'asset=SM_Rock' (si lo omitís usa el del picker).",
    ]
    return "\n".join(lineas)
