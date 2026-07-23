"""Presets de Jam — una config guardada para reusar (como Dash), y su twist: recrea Y VERIFICA.

Un preset guarda cómo se usa una herramienta, más metadata (nombre, categoría, descripción, tags),
como JSON. Hay dos clases, que cubren las dos caras de Jam:

  · kind "tool"  → una línea de DSL: `scatter count=24 pattern=poisson spread=1.2`. Aplicarlo = correr
                   esa línea (con su preview y su oráculo).
  · kind "flow"  → un GRAFO de flow (source → máscaras → instance). Es el «Compound» de Dash: varias
                   piezas combinadas en una unidad reusable. Aplicarlo = correr el grafo.

Aplicar un preset pasa por el MISMO camino maduro que la UI (`jam.panel`), así hereda el preview
(Confirmar/Descartar) y el veredicto del oráculo — un preset no es un atajo que se saltea la
verificación, es un setup verificado. Como es puro JSON, los presets globales se versionan en el repo
del plugin y hasta un LLM puede escribirlos.

  scope 'global' → <plugin>/presets/*.json   (versionado, sirve en cualquier proyecto)
  scope 'local'  → <proyecto>/Saved/JamPresets/*.json  (por proyecto)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import unreal

from . import bridge


def _dir_global() -> Path:
    return Path(bridge.PLUGIN_ROOT) / "presets"


def _dir_local() -> Path:
    return Path(unreal.Paths.project_saved_dir()) / "JamPresets"


def _slug(nombre: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", nombre.lower()).strip("-")


# ---- almacenamiento (JSON en global/local) ----

def guardar(preset: dict) -> str:
    """Escribe el preset como JSON en global o local según `preset['scope']`. Devuelve la ruta."""
    scope = preset.get("scope", "local")
    d = _dir_global() if scope == "global" else _dir_local()
    d.mkdir(parents=True, exist_ok=True)
    ruta = d / f"{_slug(preset['nombre'])}.json"
    ruta.write_text(json.dumps(preset, indent=2, ensure_ascii=False), encoding="utf-8")
    unreal.log(f"[Jam] preset guardado ({scope}): {ruta}")
    return str(ruta)


def listar(kind: str | None = None, scope: str | None = None, categoria: str | None = None) -> list[dict]:
    """Lista presets (filtrando opcionalmente por kind/scope/categoría). Marca cada uno con su scope."""
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
            if (kind is None or p.get("kind", "tool") == kind) and \
               (categoria is None or p.get("categoria") == categoria):
                out.append(p)
    return out


def cargar(nombre: str) -> dict | None:
    """Busca un preset por nombre (local pisa a global si coinciden)."""
    slug = _slug(nombre)
    encontrado = None
    for p in listar():
        if _slug(p.get("nombre", "")) == slug:
            encontrado = p   # el orden global→local hace que local gane
    return encontrado


def borrar(nombre: str) -> bool:
    slug = _slug(nombre)
    for d in (_dir_local(), _dir_global()):
        f = d / f"{slug}.json"
        if f.exists():
            f.unlink()
            return True
    return False


# ---- construir un preset desde el estado actual (lo que hace el botón «guardar preset») ----

def desde_comando(nombre, comando, *, categoria="", descripcion="", tags=None, scope="local",
                  debe_ok=False) -> dict:
    """Preset de tool a partir de una línea de DSL (lo que la Dash Bar ya compone)."""
    return {"kind": "tool", "nombre": nombre, "categoria": categoria, "descripcion": descripcion,
            "tags": tags or [], "scope": scope, "command": comando, "oraculo": {"debe_ok": debe_ok}}


def desde_grafo(nombre, grafo, *, categoria="", descripcion="", tags=None, scope="local",
                debe_ok=False) -> dict:
    """Preset de flow (Compound) a partir de un grafo (dict o JSON string)."""
    if isinstance(grafo, str):
        grafo = json.loads(grafo)
    return {"kind": "flow", "nombre": nombre, "categoria": categoria, "descripcion": descripcion,
            "tags": tags or [], "scope": scope, "graph": grafo, "oraculo": {"debe_ok": debe_ok}}


# ---- aplicar (recrear + verificar, por el camino maduro de la UI) ----

def aplicar(preset) -> dict:
    """Aplica un preset (dict o nombre): lo corre por `jam.panel` (con preview + oráculo). Devuelve
    {ok, texto, nombre}. `ok` = el veredicto salió limpio (o cumple `oraculo.debe_ok`)."""
    if isinstance(preset, str):
        preset = cargar(preset)
    if not preset:
        return {"ok": False, "texto": "preset no encontrado", "nombre": "?"}

    from . import panel
    nombre = preset.get("nombre", "?")
    kind = preset.get("kind", "tool")
    if kind == "flow":
        salida = panel.ejecutar_flow_json(json.dumps(preset["graph"]))
        try:
            texto = json.loads(salida).get("report", salida)
        except Exception:  # noqa: BLE001
            texto = salida
    else:
        texto = panel.ejecutar_dsl(preset.get("command", ""))

    # veredicto limpio = hay ✓ y no hay ✗. `debe_ok` lo exige; si no, basta que no haya ✗.
    limpio = ("✓" in texto) and ("✗" not in texto)
    ok = limpio if preset.get("oraculo", {}).get("debe_ok") else ("✗" not in texto)
    return {"ok": ok, "texto": f"[{nombre}] {texto}", "nombre": nombre}


def listar_json(**filtros) -> str:
    """Los presets como JSON liviano (nombre/kind/categoria/descripcion/tags/scope) para la UI."""
    campos = ("nombre", "kind", "categoria", "descripcion", "tags", "scope")
    return json.dumps([{k: p.get(k) for k in campos} for p in listar(**filtros)], ensure_ascii=True)
