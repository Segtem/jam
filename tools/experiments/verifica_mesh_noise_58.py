"""Verifica Ruido Perlin M → M por spec, Compile y Run reales en UE 5.8.1.

También compila el tutorial empaquetado y exige repetibilidad para el mismo seed. El veredicto queda
en ``BotOO.log`` con el prefijo ``JAM_MESH_NOISE_58``.
"""

from __future__ import annotations

import hashlib
import json
import os

import unreal

from jam import api, mesh, tools
from jam.graph import JamGraph


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


def firma_posiciones(dynamic_mesh) -> tuple[str, float, float, int]:
    posiciones = mesh._posiciones(dynamic_mesh)
    exigir(bool(posiciones), "la salida Perlin no tiene vértices")
    serial = json.dumps([[round(v, 6) for v in p] for p in posiciones], separators=(",", ":"))
    zs = [p[2] for p in posiciones]
    return hashlib.sha256(serial.encode("utf-8")).hexdigest(), min(zs), max(zs), len(posiciones)


def grafo_perlin() -> JamGraph:
    g = JamGraph()
    g.add("mesh_grid", {"width": 1200.0, "height": 1200.0,
                        "columns": 41, "rows": 41}, nid="grilla")
    g.add("mesh_noise", {"amplitud": 140.0, "frecuencia": 0.003,
                         "seed": 1977, "por_normal": True}, nid="ruido")
    g.connect("grilla", "ruido")
    return g


try:
    spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
    ruido = spec.get("mesh_noise")
    exigir(ruido is not None, "el spec no publicó mesh_noise")
    exigir(ruido["label"] == "Ruido Perlin", f"label inesperado: {ruido}")
    exigir(ruido["in_name"] == "M" and ruido["out_name"] == "M",
           f"firma inesperada: {ruido}")
    exigir(ruido["grupo"] == "Acabado", f"grupo inesperado: {ruido}")

    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ejemplo = os.path.join(raiz, "Resources", "Examples", "Terreno-con-ruido.jamgraph")
    with open(ejemplo, encoding="utf-8") as archivo:
        compilado_ejemplo = json.loads(api.compile_graph_json(archivo.read()))
    exigir(compilado_ejemplo.get("ok"), f"tutorial rojo: {compilado_ejemplo}")

    firmas = []
    for _ in range(2):
        g = grafo_perlin()
        compilado = json.loads(api.compile_graph_json(g.to_json()))
        exigir(compilado.get("ok"), f"Compile rojo: {compilado}")
        corrida = json.loads(api.run_graph_json(g.to_json()))
        exigir(corrida.get("ok"), f"Run rojo: {corrida}")
        exigir(corrida["nodes"]["ruido"]["estado"] == "ok",
               f"estado Perlin inesperado: {corrida}")
        firmas.append(firma_posiciones(tools.dato_producido_runtime("mesh_noise")))
        api.discard("graph")

    exigir(firmas[0] == firmas[1], f"mismo seed produjo resultados distintos: {firmas}")
    firma, z_min, z_max, vertices = firmas[0]
    exigir(z_max - z_min > 100.0, f"el ruido no deformó la grilla: z={z_min:g}..{z_max:g}")
    unreal.log(
        "JAM_MESH_NOISE_58 TODO VERDE — spec + tutorial + Compile + Run ×2 · "
        f"{vertices} vértices · z={z_min:.2f}..{z_max:.2f}cm · sha256 {firma[:12]}")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_MESH_NOISE_58 ROJO — {type(exc).__name__}: {exc}")
finally:
    api.discard("graph")
    unreal.SystemLibrary.quit_editor()
