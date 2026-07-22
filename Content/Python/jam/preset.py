"""Presets de Jam — la configuración de una herramienta, guardada como JSON para reusar (como Dash).

Un preset guarda los parámetros de una tool + metadata (nombre, categoría, tags) para recrear un setup
en cualquier escena. **El twist de Jam:** guarda TAMBIÉN las expectativas del oráculo (`oraculo`), así
aplicar un preset = recrear el setup Y verificarlo. Y como es puro JSON (texto), los presets globales se
versionan en el repo del plugin y hasta un LLM puede escribirlos (1er escalón del DSL de la Fase ∞).

  scope 'global' → <plugin>/presets/*.json   (versionado, sirve en cualquier proyecto)
  scope 'local'  → <proyecto>/Saved/JamPresets/*.json  (por proyecto)

Tools soportadas hoy (las generativas): scatter · colocar · pared. El resto se suma extendiendo _TOOLS.
Si el `asset` del preset no existe en el proyecto, se resuelve a la primera malla de la biblioteca
(como hacen las demos), para que un preset global funcione en cualquier escena.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import unreal

from . import bridge, library


def _dir_global() -> Path:
    return Path(bridge.PLUGIN_ROOT) / "presets"


def _dir_local() -> Path:
    return Path(unreal.Paths.project_saved_dir()) / "JamPresets"


def _slug(nombre: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-")


def guardar(preset: dict) -> str:
    """Escribe el preset como JSON en global o local según `preset['scope']`. Devuelve la ruta."""
    scope = preset.get("scope", "local")
    d = _dir_global() if scope == "global" else _dir_local()
    d.mkdir(parents=True, exist_ok=True)
    ruta = d / f"{_slug(preset['nombre'])}.json"
    ruta.write_text(json.dumps(preset, indent=2, ensure_ascii=False), encoding="utf-8")
    unreal.log(f"[Jam] preset guardado ({scope}): {ruta}")
    return str(ruta)


def listar(tool: str | None = None, scope: str | None = None) -> list[dict]:
    """Lista presets (opcionalmente filtrando por tool y/o scope). Marca cada uno con su scope real."""
    out: list[dict] = []
    dirs = []
    if scope in (None, "global"):
        dirs.append(("global", _dir_global()))
    if scope in (None, "local"):
        dirs.append(("local", _dir_local()))
    for sc, d in dirs:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.json")):
            try:
                p = json.loads(f.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                unreal.log_error(f"[Jam] preset ilegible {f}: {e}")
                continue
            p["scope"] = sc
            if tool is None or p.get("tool") == tool:
                out.append(p)
    return out


def cargar(nombre: str) -> dict | None:
    """Busca un preset por nombre (local pisa a global si coinciden)."""
    slug = _slug(nombre)
    encontrado = None
    for p in listar():
        if _slug(p.get("nombre", "")) == slug:
            encontrado = p  # el orden global→local hace que local gane
    return encontrado


def _resolver_asset(params: dict) -> str | None:
    a = params.get("asset")
    if a and library.cargar_malla(a) is not None:
        return a
    libro = library.buscar(limit=1)
    return libro[0]["ruta"] if libro else None


# ---- appliers por tool (build + oráculo) ----

def _aplicar_scatter(preset: dict) -> dict:
    from . import oracle_scatter, scatter
    p = preset["params"]
    asset = _resolver_asset(p)
    centro = tuple(p.get("centro", [0, 0]))
    semi = tuple(p.get("semi", [500, 500]))
    cant = int(p.get("cantidad", 9))
    actores = scatter.esparcir(asset, centro, semi, cant, seed=int(p.get("seed", 0)))
    r = oracle_scatter.verificar(actores, centro, semi, cant)
    texto = oracle_scatter.verificar_texto(actores, centro, semi, cant)
    return {"ok": oracle_scatter.es_ok(r), "texto": texto, "actores": actores}


def _aplicar_colocar(preset: dict) -> dict:
    from . import oracle_placement, place
    p = preset["params"]
    asset = _resolver_asset(p)
    actor = place.colocar(asset, tuple(p.get("location", [0, 0, 0])))
    todos = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    r = oracle_placement.verificar(actor, todos)
    texto = oracle_placement.verificar_texto(actor, todos)
    return {"ok": r["bounds_ok"] and not r["interpenetra"], "texto": texto, "actores": [actor]}


def _aplicar_pared(preset: dict) -> dict:
    from . import oracle_pared, pared
    p = preset["params"]
    orc = preset.get("oraculo", {})
    asset = _resolver_asset(p)
    actor = pared.seleccionado_con_spline() or pared.crear_spline()
    build = pared.construir(actor, asset, alto=float(p.get("alto", 300)),
                            espesor=float(p.get("espesor", 40)),
                            largo_segmento=float(p.get("largo_segmento", 200)))
    tol = float(orc.get("tol_junta", 50))
    r = oracle_pared.verificar(build, tol=tol)
    texto = oracle_pared.verificar_texto(build, tol=tol)
    return {"ok": oracle_pared.es_ok(r), "texto": texto, "actores": build["segmentos"] + [actor]}


_TOOLS = {
    "scatter": _aplicar_scatter,
    "place": _aplicar_colocar,
    "spline": _aplicar_pared,   # «a lo largo de spline»: una pared es un preset de este tool
    # alias español por compatibilidad con presets viejos
    "colocar": _aplicar_colocar,
    "pared": _aplicar_pared,
}


def aplicar(preset) -> dict:
    """Aplica un preset (dict o nombre): construye con sus params y corre el oráculo de la tool.
    Devuelve {ok, texto, actores}."""
    if isinstance(preset, str):
        preset = cargar(preset)
    if not preset:
        return {"ok": False, "texto": "preset no encontrado", "actores": []}
    fn = _TOOLS.get(preset.get("tool"))
    if fn is None:
        return {"ok": False, "texto": f"tool «{preset.get('tool')}» aún no soportada en presets", "actores": []}
    nombre = preset.get("nombre", "?")
    res = fn(preset)
    res["texto"] = f"[{nombre}] {res['texto']}"
    return res
