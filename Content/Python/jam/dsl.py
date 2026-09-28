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
    """Convierte cada param al tipo de su default en REGISTRO. Devuelve (kwargs, errores).

    Cada error es una frase entera —qué falló, cuáles valen, el más parecido— y quien la recibe NO
    corre el verbo: seguir con el default es el silencio que dejaba `cownt=10` en verde.
    """
    from . import registro_core
    info = tools.REGISTRO.get(verbo, {})
    spec = info.get("params", {})
    out: dict = {}
    errores: list[str] = []
    for k, v in params.items():
        if k not in spec:
            errores.append(registro_core.param_desconocido(verbo, k, spec))
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
            errores.append(f"{k}: «{v}» no es {type(d).__name__}")
            continue
        fallo = registro_core.opcion_invalida(k, out[k], info)
        if fallo:
            errores.append(fallo)
    return out, errores


def ayuda() -> str:
    """Texto de ayuda generado desde el registro (siempre en sync con las herramientas reales).

    Lista SÓLO lo que corre acá. Listaba los 166 verbos, de los cuales 86 necesitan un cable y no
    pueden funcionar escritos: una ayuda que ofrece lo que no anda es peor que una ayuda corta,
    porque el que la lee culpa a lo que escribió. Los del Graph se cuentan al final, para que se
    sepa que existen y dónde viven.
    """
    from . import registro_core

    lineas = ["Jam DSL — un comando por línea:"]
    de_grafo = 0
    for nombre, info in tools.REGISTRO.items():
        if not registro_core.corre_en_consola(info):
            de_grafo += 1
            continue
        ps = " ".join(f"{k}=" for k in info["params"])
        lineas.append(f"  {nombre:<14}{ps:<34}— {info['doc']}")
    if de_grafo:
        lineas.append(f"  ({de_grafo} verbos más viven sólo en el Graph: necesitan un cable de "
                      "entrada. Jam ▸ Graph.)")
    lineas += [
        "  verify                                       — corre el oráculo de espacio sobre el nivel",
        "  confirm / discard                            — fija o borra el preview activo",
        "  search <texto>                               — lista assets del proyecto",
        "  help                                         — esta ayuda",
        "asset: 'scatter SM_Rock …' o 'asset=SM_Rock' (si lo omitís usa el del picker).",
    ]
    return "\n".join(lineas)
