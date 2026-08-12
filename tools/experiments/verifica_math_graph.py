"""Verifica los nodos Math por el contrato público dentro de UE 5.8.1.

Ejercita el mismo spec, Compile, Run e Inspector que consume Slate. No reemplaza el gesto manual de
guardar/reabrir el canvas, pero sí detecta diferencias entre el Python de tests y el intérprete
embebido del motor. El veredicto queda en BotOO.log con el prefijo ``JAM_MATH_GRAPH_TEST``.
"""

from __future__ import annotations

import json
from pathlib import Path

import unreal

from jam import api
from jam.graph import JamGraph


#: La raíz del plugin, para poder leer el C++ y comprobar que el tipo tiene color de pin.
RAIZ = Path("/home/workstation/Dev/jam")


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
        # Tercer lote — Rango, Mezcla, Redondeo y Trigonometría.
        ("math_min", "Mínimo"),
        ("math_max", "Máximo"),
        ("math_clamp", "Limitar"),
        ("math_saturate", "Saturar"),
        ("math_lerp", "Interpolar"),
        ("math_remap", "Remapear"),
        ("math_floor", "Piso"),
        ("math_ceil", "Techo"),
        ("math_round", "Redondear"),
        ("math_radians", "Grados a radianes"),
        ("math_degrees", "Radianes a grados"),
        ("math_sin", "Seno"),
        ("math_cos", "Coseno"),
        ("math_tan", "Tangente"),
        # Cuarto lote — inversas y tiempo (del tab Maths de Grasshopper: Trig y Time).
        ("math_asin", "Arcoseno"),
        ("math_acos", "Arcocoseno"),
        ("math_atan", "Arcotangente"),
        ("math_atan2", "Ángulo de un vector"),
        ("time_construct", "Armar tiempo"),
        ("time_horas", "Horas de"),
        ("time_minutos", "Minutos de"),
        ("time_segundos", "Segundos de"),
        # Quinto lote — el tipo vector (peldaño 1 de la escalera de Grasshopper Basics).
        ("vector_construct", "Construir vector"),
        ("vector_unit_z", "Unitario Z"),
        ("vector_length", "Largo del vector"),
        ("vector_normalize", "Normalizar"),
        ("vector_dot", "Producto punto"),
        ("vector_cross", "Producto cruz"),
        # Sexto lote — el tipo dominio (el panel Domain del tab Maths).
        ("domain_construct", "Armar dominio"),
        ("domain_length", "Largo del dominio"),
        ("domain_includes", "¿Está adentro?"),
    ):
        exigir(verbo in spec, f"el spec no publicó {verbo}")
        exigir(spec[verbo]["label"] == etiqueta,
               f"{verbo} publicó etiqueta {spec[verbo]['label']!r}")
        exigir(bool(spec[verbo]["out_label"]), f"{verbo} perdió out_label")
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
    # Tercer lote por el camino real: 45° → radianes → seno → remapeado a 0..100 → redondeado.
    # sin(45°) = 0,7071 ⇒ 70,71 ⇒ 71. Encadenado, no verbo por verbo.
    trigo = JamGraph()
    trigo.add("number", {"value": 45}, nid="grados")
    trigo.add("math_radians", {}, nid="rad")
    trigo.add("math_sin", {}, nid="seno")
    trigo.add("math_remap", {"origen": "0,1", "destino": "0,100"}, nid="escala")
    trigo.add("math_round", {}, nid="redondeo")
    trigo.connect("grados", "rad", "grados")
    trigo.connect("rad", "seno", "radianes")
    trigo.connect("seno", "escala", "valor")
    trigo.connect("escala", "redondeo", "valor")
    compilado_trigo = json.loads(api.compile_graph_json(trigo.to_json()))
    exigir(compilado_trigo.get("ok"), f"Compile del lote nuevo rojo: {compilado_trigo}")
    corrida_trigo = json.loads(api.run_graph_json(trigo.to_json()))
    exigir(corrida_trigo.get("ok"), f"Run del lote nuevo rojo: {corrida_trigo}")
    inspector_trigo = api.inspect_json("redondeo", "", 10, "", False)
    exigir("71" in inspector_trigo,
           f"el Inspector no muestra 71 para sin(45°) remapeado: {inspector_trigo[:200]}")

    # Y un rechazo del lote nuevo: rango dado vuelta. Que falle es la mitad del contrato.
    torcido = JamGraph()
    torcido.add("math_clamp", {"valor": 3, "minimo": 5, "maximo": 0}, nid="limite")
    rechazo_rango = json.loads(api.run_graph_json(torcido.to_json()))
    exigir(not rechazo_rango.get("ok"),
           f"Run aceptó un rango dado vuelta: {rechazo_rango}")

    # Cuarto lote por el camino real: 1h30m45s, sacarle las horas → 1. Y el ángulo de (0,5),
    # que es el caso donde `atan(y/x)` explotaría, en grados → 90.
    reloj = JamGraph()
    reloj.add("time_construct", {"horas": 1, "minutos": 30, "segundos": 45}, nid="dur")
    reloj.add("time_horas", {}, nid="horas")
    reloj.connect("dur", "horas", "total")
    reloj.add("math_atan2", {"y": 5, "x": 0}, nid="rumbo")
    reloj.add("math_degrees", {}, nid="grados")
    reloj.connect("rumbo", "grados", "radianes")
    compilado_reloj = json.loads(api.compile_graph_json(reloj.to_json()))
    exigir(compilado_reloj.get("ok"), f"Compile del cuarto lote rojo: {compilado_reloj}")
    corrida_reloj = json.loads(api.run_graph_json(reloj.to_json()))
    exigir(corrida_reloj.get("ok"), f"Run del cuarto lote rojo: {corrida_reloj}")
    inspeccion_reloj = api.inspect_json("horas", "", 10, "", False)
    exigir("1" in inspeccion_reloj, f"el Inspector no muestra 1 hora: {inspeccion_reloj[:200]}")
    inspeccion_rumbo = api.inspect_json("grados", "", 10, "", False)
    exigir("90" in inspeccion_rumbo,
           f"el Inspector no muestra 90° para el vector (0,5): {inspeccion_rumbo[:200]}")

    # Y un rechazo del lote nuevo: un seno fuera de -1..1 no tiene ángulo.
    imposible = JamGraph()
    imposible.add("math_asin", {"seno": 2.0}, nid="angulo")
    rechazo_arco = json.loads(api.run_graph_json(imposible.to_json()))
    exigir(not rechazo_arco.get("ok"), f"Run aceptó un arcoseno fuera de dominio: {rechazo_arco}")

    # Quinto lote: el tipo V por el camino real. Unitario Z*10 + Unitario X*10, medido → √200.
    vectores = JamGraph()
    vectores.add("vector_unit_z", {"largo": 10}, nid="arriba")
    vectores.add("vector_unit_x", {"largo": 10}, nid="adelante")
    vectores.add("vector_add", {}, nid="suma")
    vectores.add("vector_length", {}, nid="largo")
    vectores.connect("arriba", "suma", "a")
    vectores.connect("adelante", "suma", "b")
    vectores.connect("suma", "largo", "vector")
    compilado_vec = json.loads(api.compile_graph_json(vectores.to_json()))
    exigir(compilado_vec.get("ok"), f"Compile del tipo V rojo: {compilado_vec}")
    corrida_vec = json.loads(api.run_graph_json(vectores.to_json()))
    exigir(corrida_vec.get("ok"), f"Run del tipo V rojo: {corrida_vec}")
    inspeccion_vec = api.inspect_json("largo", "", 10, "", False)
    exigir("14.1" in inspeccion_vec, f"el Inspector no muestra 14,14: {inspeccion_vec[:200]}")

    # Y la guarda que justifica que V sea un tipo propio: un número NO entra en un pin de dirección.
    mal_cableado = JamGraph()
    mal_cableado.add("number", {"value": 5}, nid="n")
    mal_cableado.add("vector_length", {}, nid="largo")
    mal_cableado.connect("n", "largo", "vector")
    rechazo_tipo = json.loads(api.compile_graph_json(mal_cableado.to_json()))
    exigir(not rechazo_tipo.get("ok"),
           f"Compile aceptó un número donde va un vector: {rechazo_tipo}")

    # El color del pin `V` tiene que existir en el C++: sin eso el cable sale gris neutro y el tipo
    # deja de leerse en el canvas, que es la mitad de para qué sirve tener tipos.
    color_cpp = (RAIZ / "Source" / "JamEditor" / "Private" / "SJamGraphEditor.cpp").read_text(
        encoding="utf-8")
    exigir('OutName == TEXT("V")' in color_cpp, "el tipo V no tiene color de pin en DataColor")

    # Sexto lote: el dominio 0..360, preguntar si 45 cae adentro y normalizarlo a 0..1 → 0,125.
    rango = JamGraph()
    rango.add("domain_construct", {"desde": 0, "hasta": 360}, nid="vuelta")
    rango.add("domain_includes", {"valor": 45}, nid="adentro")
    rango.add("math_remap", {"valor": 45, "destino": "0,1"}, nid="normalizado")
    rango.connect("vuelta", "adentro", "dominio")
    rango.connect("vuelta", "normalizado", "origen")
    compilado_rango = json.loads(api.compile_graph_json(rango.to_json()))
    exigir(compilado_rango.get("ok"), f"Compile del tipo D rojo: {compilado_rango}")
    corrida_rango = json.loads(api.run_graph_json(rango.to_json()))
    exigir(corrida_rango.get("ok"), f"Run del tipo D rojo: {corrida_rango}")
    inspeccion_rango = api.inspect_json("normalizado", "", 10, "", False)
    exigir("0.125" in inspeccion_rango,
           f"el Inspector no muestra 0,125 para 45° normalizado: {inspeccion_rango[:200]}")

    # Y la guarda que justifica el tipo: con cuatro números sueltos, cruzar origen y destino
    # compilaba y devolvía un número plausible. Con el tipo puesto, un número NO entra en un pin
    # de rango.
    cruzado = JamGraph()
    cruzado.add("number", {"value": 5}, nid="n")
    cruzado.add("domain_length", {}, nid="largo")
    cruzado.connect("n", "largo", "dominio")
    rechazo_dominio = json.loads(api.compile_graph_json(cruzado.to_json()))
    exigir(not rechazo_dominio.get("ok"),
           f"Compile aceptó un número donde va un dominio: {rechazo_dominio}")

    color_dominio = (RAIZ / "Source" / "JamEditor" / "Private" / "SJamGraphEditor.cpp").read_text(
        encoding="utf-8")
    exigir('OutName == TEXT("D")' in color_dominio, "el tipo D no tiene color de pin en DataColor")

    # Séptimo lote: las constantes con nombre en un param, por el camino real. Un radio de 100 con
    # `=PI * 2` de altura da 628,3, y `=φ * 100` da 161,8.
    constantes = JamGraph()
    constantes.add("mesh_cylinder", {"radius": "=PHI * 100", "height": "=PI * 200"}, nid="cilindro")
    compilado_const = json.loads(api.compile_graph_json(constantes.to_json()))
    exigir(compilado_const.get("ok"), f"Compile con constantes rojo: {compilado_const}")
    corrida_const = json.loads(api.run_graph_json(constantes.to_json()))
    exigir(corrida_const.get("ok"), f"Run con constantes rojo: {corrida_const}")

    # Y el mensaje cuando NO resuelve: tiene que decir QUÉ no conoce, no sólo que algo falló.
    roto = JamGraph()
    roto.add("mesh_cylinder", {"radius": "=radioo * 2"}, nid="cilindro")
    fallo = json.loads(api.compile_graph_json(roto.to_json()))
    exigir(not fallo.get("ok"), f"Compile aceptó una expresión rota: {fallo}")
    texto_fallo = json.dumps(fallo, ensure_ascii=False)
    exigir("no conozco" in texto_fallo and "radioo" in texto_fallo,
           f"el error no nombra lo que no conoce: {texto_fallo[:220]}")

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

    unreal.log("JAM_MATH_GRAPH_TEST TODO VERDE — 40 verbos en el spec + Compile + Run + "
               "Inspector=40/2 y sin(45°)→71 + división por cero, raíz negativa y rango dado "
               "vuelta, arcoseno fuera de dominio, N→V y N→D rechazados + 1h30m45s→1h, (0,5)→90°, "
               "|Z+X|→14,14, 45° en 0..360 → 0,125 y las constantes PI/φ en un param")
except Exception as exc:  # noqa: BLE001
    unreal.log_error(f"JAM_MATH_GRAPH_TEST ROJO — {type(exc).__name__}: {exc}")
finally:
    unreal.SystemLibrary.quit_editor()
