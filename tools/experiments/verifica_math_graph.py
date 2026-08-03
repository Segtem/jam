"""Verifica los nodos Math por el contrato público dentro de UE 5.8.1.

Ejercita el mismo spec, Compile, Run e Inspector que consume Slate. No reemplaza el gesto manual de
guardar/reabrir el canvas, pero sí detecta diferencias entre el Python de tests y el intérprete
embebido del motor. El veredicto queda en BotOO.log con el prefijo ``JAM_MATH_GRAPH_TEST``.
"""

from __future__ import annotations

import json

import unreal

from jam import api
from jam.graph import JamGraph


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


try:
    spec = {item["verbo"]: item for item in json.loads(api.spec_all())["tools"]}
    for verbo, etiqueta in (
        ("math_add", "Sumar"),
        ("math_subtract", "Restar"),
        ("math_multiply", "Multiplicar"),
        ("math_divide", "Dividir"),
        ("math_negate", "Negar"),
        ("math_absolute", "Absoluto"),
        ("math_modulo", "Módulo"),
        ("math_power", "Potencia"),
        ("math_sqrt", "Raíz cuadrada"),
    ):
        exigir(verbo in spec, f"el spec no publicó {verbo}")
        exigir(spec[verbo]["label"] == etiqueta,
               f"{verbo} publicó etiqueta {spec[verbo]['label']!r}")
        exigir(spec[verbo]["out_label"] == "resultado", f"{verbo} perdió out_label")
        exigir(spec[verbo]["seccion"] == "Datos", f"{verbo} quedó fuera de Datos")

    # (7 + 3) × 4 = 40; cada operando entra por un cable de parámetro real.
    grafo = JamGraph()
    grafo.add("number", {"name": "primero", "value": 7}, nid="n1")
    grafo.add("number", {"name": "segundo", "value": 3}, nid="n2")
    grafo.add("math_add", {}, nid="sumar")
    grafo.add("number", {"name": "factor", "value": 4}, nid="factor")
    grafo.add("math_multiply", {}, nid="resultado")
    grafo.connect("n1", "sumar", "a")
    grafo.connect("n2", "sumar", "b")
    grafo.connect("sumar", "resultado", "a")
    grafo.connect("factor", "resultado", "b")

    # El round-trip es el borde que usan guardar y reabrir antes de tocar el filesystem del usuario.
    reabierto = JamGraph.from_json(grafo.to_json())
    compilado = json.loads(api.compile_graph_json(reabierto.to_json()))
    exigir(compilado.get("ok"), f"Compile rojo: {compilado.get('report')}")

    corrida = json.loads(api.run_graph_json(reabierto.to_json()))
    estados = {nid: dato.get("estado") for nid, dato in corrida.get("nodes", {}).items()}
    exigir(corrida.get("ok") is True and corrida.get("preview") is False,
           f"Run de valores declaró efectos de escena: {corrida}")
    exigir(estados and all(estado == "ok" for estado in estados.values()),
           f"Run rojo: estados={estados} reporte={corrida.get('report')}")
    inspeccion = json.loads(api.inspect_json("resultado"))
    exigir(inspeccion.get("ok"), f"Inspector rojo: {inspeccion}")
    exigir(inspeccion.get("columnas") == [{"nombre": "valor", "tipo": "num"}],
           f"columnas inesperadas: {inspeccion.get('columnas')}")
    exigir(inspeccion.get("filas") == [["40.000"]],
           f"resultado inesperado: {inspeccion.get('filas')}")

    division_rota = JamGraph()
    division_rota.add("math_divide", {"dividendo": 1, "divisor": 0}, nid="dividir")
    rechazado = json.loads(api.compile_graph_json(division_rota.to_json()))
    exigir(not rechazado.get("ok") and "cero" in rechazado.get("report", ""),
           f"Compile aceptó división por cero: {rechazado}")

    # sqrt((((-5) absoluto)^2) módulo 7) = sqrt(4) = 2.
    lote = JamGraph()
    lote.add("number", {"value": 5}, nid="cinco")
    lote.add("math_negate", {}, nid="negar")
    lote.add("math_absolute", {}, nid="absoluto")
    lote.add("math_power", {"exponente": 2}, nid="potencia")
    lote.add("math_modulo", {"modulo": 7}, nid="modulo")
    lote.add("math_sqrt", {}, nid="raiz")
    lote.connect("cinco", "negar", "valor")
    lote.connect("negar", "absoluto", "valor")
    lote.connect("absoluto", "potencia", "base")
    lote.connect("potencia", "modulo", "valor")
    lote.connect("modulo", "raiz", "radicando")
    compilado_lote = json.loads(api.compile_graph_json(lote.to_json()))
    exigir(compilado_lote.get("ok"), f"Compile lote rojo: {compilado_lote}")
    corrida_lote = json.loads(api.run_graph_json(lote.to_json()))
    exigir(corrida_lote.get("ok") and not corrida_lote.get("preview"),
           f"Run lote rojo o con Preview: {corrida_lote}")
    inspeccion_lote = json.loads(api.inspect_json("raiz"))
    exigir(inspeccion_lote.get("filas") == [["2.000"]],
           f"resultado del lote inesperado: {inspeccion_lote}")

    raiz_rota = JamGraph()
    raiz_rota.add("math_sqrt", {"radicando": -1}, nid="raiz")
    rechazado = json.loads(api.compile_graph_json(raiz_rota.to_json()))
    exigir(not rechazado.get("ok") and "negativo" in rechazado.get("report", ""),
           f"Compile aceptó raíz negativa: {rechazado}")

    unreal.log("JAM_MATH_GRAPH_TEST TODO VERDE — spec + Compile + Run + "
               "Inspector=40/2 + división por cero y raíz negativa rechazadas")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_MATH_GRAPH_TEST ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
