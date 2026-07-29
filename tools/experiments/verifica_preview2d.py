"""El visor 2D sobre datos REALES de una corrida, y de paso un chequeo de los tutoriales.

`test_preview2d` cubre el renderizador entero sin editor. Lo que falta comprobar es el tramo que
necesita Unreal: leer los UVs de una malla de verdad y que `api.preview_2d` sepa qué dibujar según
lo que dejó el Run.

Se corren los dos tutoriales de materiales por el camino del botón Run (`api.run_graph_json`, sin
los `place` que un commandlet no puede spawnear) y se pide el preview de sus nodos. Si los
tutoriales no anduvieran, esto lo diría acá.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \\
        -script=<plugin>/tools/experiments/verifica_preview2d.py \\
        -RenderOffScreen -unattended -nosplash -stdout -AllowCommandletRendering
"""

from __future__ import annotations

import json
import os

import unreal

from jam import api


FALLAS = []
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EJEMPLOS = os.path.join(RAIZ, "Resources", "Examples")


def log(m: str) -> None:
    unreal.log(f"[PREVIEW] {m}")


def exigir(condicion: bool, descripcion: str) -> None:
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def correr(archivo: str) -> dict:
    """Corre un tutorial sin sus `place` (no hay nivel en un commandlet)."""
    with open(os.path.join(EJEMPLOS, archivo), encoding="utf-8") as f:
        datos = json.load(f)
    fuera = {nid for nid, n in datos["nodes"].items() if n.get("verb") == "place"}
    datos["nodes"] = {k: v for k, v in datos["nodes"].items() if k not in fuera}
    datos["edges"] = [e for e in datos["edges"] if e[0] not in fuera and e[2] not in fuera]
    reporte = json.loads(api.run_graph_json(json.dumps(datos)))
    malos = {nid: e["texto"] for nid, e in reporte["nodes"].items() if e["estado"] == "error"}
    exigir(not malos, f"«{archivo}» corre entero{'' if not malos else f' · {malos}'}")
    return reporte


def preview(nodo: str, **kwargs) -> dict:
    return json.loads(api.preview_2d(nodo, **kwargs))


def main() -> None:
    log("=" * 70)

    # ── 1. el tutorial de UVs, y el preview de su desplegado ──────────────────────
    correr("UVs-para-texturar.jamgraph")

    crudo = preview("proyectar", ancho=256, alto=256)
    exigir(crudo.get("ok"), f"preview del desplegado proyectado: {crudo.get('detalle') or crudo}")
    if crudo.get("ok"):
        exigir(os.path.getsize(crudo["ruta"]) > 1000,
               f"el PNG tiene contenido: {os.path.getsize(crudo['ruta'])} bytes en {crudo['ruta']}")
        exigir("ENCIMADAS" in crudo["detalle"],
               "y el detalle dice lo mismo que el oráculo: las islas están encimadas")

    limpio = preview("empaquetar", ancho=256, alto=256)
    exigir(limpio.get("ok") and "ENCIMADAS" not in limpio["detalle"],
           f"y el empaquetado se ve distinto: {limpio.get('detalle')}")

    # Un canal SIN UVs tiene que decir qué falta. Se pide el 5 y no el 0 porque las primitivas de
    # Geometry Script YA vienen con UV0 — suponer que una malla recién creada no tiene ninguna es
    # falso. Va acá y no más abajo porque cada Run reemplaza la última corrida entera.
    sin_uv = preview("escalera", canal=5)
    exigir(not sin_uv.get("ok") and "UVs" in sin_uv.get("error", ""),
           f"una malla sin desplegar avisa qué falta: {sin_uv.get('error', '')[:110]}")

    # ── 2. el tutorial de material, y el preview de su máscara ────────────────────
    correr("Primer-material.jamgraph")

    mascara = preview("a_rug", ancho=192, alto=192)
    exigir(mascara.get("ok"), f"preview de la máscara del grafo de material: {mascara}")
    if mascara.get("ok"):
        exigir(mascara["tipo"] == "MT", f"reconocido como grafo de material: {mascara['tipo']}")
        exigir(os.path.getsize(mascara["ruta"]) > 200,
               f"con su PNG: {os.path.getsize(mascara['ruta'])} bytes")

    # ── 3. lo que NO se previsualiza tiene que decir por qué ──────────────────────
    inexistente = preview("no_existe")
    exigir(not inexistente.get("ok") and "nodos" in inexistente,
           "un nodo que no corrió dice cuáles sí")

    # ── 4. los datos que ya se ven en el viewport no se dibujan, y se explica ─────
    caja = preview("caja")
    log(f"malla sin UVs («caja» del tutorial de material): {caja.get('error', caja)[:110]}")

    log("=" * 70)
    log("VEREDICTO: " + ("TODO VERDE" if not FALLAS else f"{len(FALLAS)} FALLA(S): {FALLAS}"))


main()
