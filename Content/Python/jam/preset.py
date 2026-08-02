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
import unicodedata
from pathlib import Path

import unreal

from . import bridge


def _dir_global() -> Path:
    return Path(bridge.PLUGIN_ROOT) / "presets"


def _dir_local() -> Path:
    return Path(unreal.Paths.project_saved_dir()) / "JamPresets"


def _slug(nombre: str) -> str:
    """Nombre de archivo estable. Las tildes y la ñ se transliteran en vez de perderse: sin esto
    «Árbol de dos niveles» quedaba como `rbol-de-dos-niveles.json`."""
    plano = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-")


# ---- almacenamiento (JSON en global/local) ----

def guardar(preset: dict) -> str:
    """Escribe el preset como JSON en global o local según `preset['scope']`. Devuelve la ruta."""
    scope = preset.get("scope", "local")
    d = _dir_global() if scope == "global" else _dir_local()
    d.mkdir(parents=True, exist_ok=True)
    # Una función nueva se guarda por identidad, no por etiqueta. Así renombrarla no crea otro
    # archivo ni rompe las instancias `fn:<funcion_id>`. Los presets viejos siguen por nombre.
    clave_archivo = preset.get("funcion_id") if preset.get("kind") == "funcion" else None
    ruta = d / f"{_slug(clave_archivo or preset['nombre'])}.json"
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


def borrar_funcion(funcion_id: str) -> bool:
    """Borra la definición por identidad; local gana si hubiera una colisión legada.

    No usa el nombre visible ni supone cómo se llama el archivo: ambas cosas pueden haber cambiado.
    """
    for d in (_dir_local(), _dir_global()):
        if not d.exists():
            continue
        for ruta in sorted(d.glob("*.json")):
            try:
                p = json.loads(ruta.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            identidad = str(p.get("funcion_id") or p.get("nombre") or "")
            if p.get("kind") == "funcion" and identidad == funcion_id:
                ruta.unlink()
                return True
    return False


# ---- construir un preset desde el estado actual (lo que hace el botón «guardar preset») ----

def desde_comando(nombre, comando, *, categoria="", descripcion="", tags=None, scope="local",
                  debe_ok=False) -> dict:
    """Preset de tool a partir de una línea de DSL (lo que la Dash Bar ya compone)."""
    return {"kind": "tool", "nombre": nombre, "categoria": categoria, "descripcion": descripcion,
            "tags": tags or [], "scope": scope, "command": comando, "oraculo": {"debe_ok": debe_ok}}


def kind_de_grafo(grafo) -> str:
    """`funcion` si declara pines; `flow` si TODOS los nodos son ops de flow; si no, `graph`.

    Es la MISMA detección que usa `api.run_graph_json()`, a propósito: un preset tiene que correr por
    el runner que le corresponde. Marcarlo siempre como `flow` hacía que un canvas de verbos —Place,
    Mesh, TreeGen— cayera en el evaluador de flow, donde cada verbo es una op desconocida.

    Una función se reconoce por lo mismo que la hace función: tiene `input`/`output`. No hay un botón
    aparte de «guardar como función» — se guarda un grafo y el contenido decide qué es.
    """
    from . import flow
    if isinstance(grafo, (dict, list)):
        grafo = json.dumps(grafo)
    nodos = (json.loads(grafo) or {}).get("nodes", {}) if grafo else {}
    if any((n.get("verb") or n.get("kind")) in ("input", "output") for n in nodos.values()):
        return "funcion"
    return "flow" if flow.Flow.from_json(grafo).solo_flow() else "graph"


def desde_grafo(nombre, grafo, *, categoria="", descripcion="", tags=None, scope="local",
                debe_ok=False, funcion_id="") -> dict:
    """Preset a partir de un grafo (dict o JSON string); el `kind` sale del contenido, no del botón."""
    if isinstance(grafo, str):
        grafo = json.loads(grafo)
    kind = kind_de_grafo(grafo)
    salida = {"kind": kind, "nombre": nombre, "categoria": categoria,
            "descripcion": descripcion, "tags": tags or [], "scope": scope, "graph": grafo,
            "oraculo": {"debe_ok": debe_ok}}
    if kind == "funcion" and funcion_id:
        salida["funcion_id"] = funcion_id
    return salida


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
    # Una función no se aplica: es un CUERPO con pines sueltos, y correrlo tal cual significaría
    # ejecutar `input`/`output` como si fueran verbos. Se usa instanciándola en un grafo.
    if kind == "funcion" or (preset.get("graph") and kind_de_grafo(preset["graph"]) == "funcion"):
        return {"ok": False, "nombre": nombre,
                "texto": f"[{nombre}] es una FUNCIÓN: no se aplica sola — "
                         f"instanciala en el grafo con el nodo «fn:{nombre}»"}
    if kind in ("flow", "graph"):
        grafo = preset.get("graph")
        if not grafo:
            return {"ok": False, "texto": f"[{nombre}] el preset {kind} no trae grafo", "nombre": nombre}
        # Un preset viejo puede declarar `flow` y contener verbos: se corrige leyendo el grafo, que es
        # la única fuente confiable del runner que hace falta.
        real = kind_de_grafo(grafo)
        grafo_json = json.dumps(grafo)
        if real == "flow":
            salida = panel.ejecutar_flow_json(grafo_json, owner="dash")
        else:
            salida = panel.ejecutar_grafo_json(grafo_json, owner="dash")
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
