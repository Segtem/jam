"""Funciones del Graph: un subgrafo con firma, expandido *inline* antes de compilar.

Es el Cluster de Grasshopper, el HDA de Houdini, el «Collapse to Function» de Blueprint. A los tres
les falta lo mismo cuando no lo tienen: **una firma**.

Las piezas:

  · dos verbos, `input` y `output`, que adentro del cuerpo marcan qué entra y qué sale, con nombre
    y tipo del vocabulario que ya existe (`A`, `P`, `F`, `M`, `MT`, …);
  · una **instancia** es un nodo cuyo verbo es `fn:<nombre>`, y sus pines son la firma del cuerpo;
  · `expandir()` reemplaza cada instancia por una copia del cuerpo y recablea el borde.

**Por qué la expansión es una transformación grafo→grafo y no algo dentro del compilador.** Después
de expandir, lo que queda es un grafo normal: `compilar` no se entera de que hubo funciones, y el
oráculo **sigue midiendo exactamente lo mismo**. Una función opaca, en cambio, le taparía el
interior al oráculo — que es lo único que este proyecto no puede permitirse. Además hace que esto
se pueda testear sin motor y sin compilador.

Los ids de los nodos expandidos son `<id de la instancia>__<id adentro del cuerpo>`. Legible en el
diagnóstico («de qué instancia salió este nodo») y sin choques por construcción.
"""

from __future__ import annotations

from .graph import JamGraph

PREFIJO = "fn:"
VERBOS_BORDE = ("input", "output")
PIN_IN, PIN_OUT = "in", "out"


class FuncionError(ValueError):
    """El cuerpo de una función o su uso no cumplen el contrato."""


def es_instancia(verb: str) -> bool:
    return verb.startswith(PREFIJO)


def nombre_de_instancia(verb: str) -> str:
    return verb[len(PREFIJO):]


def _nombre_borde(nid: str, nodo: dict) -> str:
    """El nombre del pin. Sin nombre no hay firma: un pin anónimo no se puede cablear."""
    nombre = str(nodo.get("params", {}).get("name") or "").strip()
    if not nombre:
        raise FuncionError(f"{nid}: un `{nodo['verb']}` sin `name` no puede ser un pin")
    return nombre


def _orden_visual(cuerpo: JamGraph, verb: str) -> list[tuple[str, dict]]:
    """Los pines salen ordenados como se ven: de arriba a abajo. Determinista, y es el orden que
    espera quien mira el nodo."""
    nodos = [(nid, n) for nid, n in cuerpo.nodes.items() if n["verb"] == verb]
    return sorted(nodos, key=lambda par: (par[1].get("y", 0.0), par[1].get("x", 0.0), par[0]))


def firma(cuerpo: JamGraph) -> dict:
    """{'entradas': [{'name','tipo'}...], 'salidas': [...]} — los pines que va a tener la instancia."""
    salida: dict[str, list[dict]] = {"entradas": [], "salidas": []}
    for verb, clave in (("input", "entradas"), ("output", "salidas")):
        vistos: set[str] = set()
        for nid, n in _orden_visual(cuerpo, verb):
            nombre = _nombre_borde(nid, n)
            if nombre in vistos:
                raise FuncionError(f"hay dos `{verb}` llamados «{nombre}»: el pin sería ambiguo")
            vistos.add(nombre)
            salida[clave].append({"name": nombre, "tipo": str(n.get("params", {}).get("type", "*"))})
    return salida


def _copiar(nodo: dict, dx: float = 0.0, dy: float = 0.0) -> dict:
    return {"verb": nodo["verb"], "params": dict(nodo.get("params", {})),
            "asset": nodo.get("asset"), "x": float(nodo.get("x", 0.0)) + dx,
            "y": float(nodo.get("y", 0.0)) + dy, "debug": bool(nodo.get("debug", False))}


def expandir(g: JamGraph, biblioteca: dict[str, JamGraph], _pila: tuple[str, ...] = ()) -> JamGraph:
    """Devuelve un grafo equivalente sin instancias de función. No toca `g`.

    Anidar funciones está permitido; que una se contenga a sí misma, no — se detecta con la pila de
    nombres y es un error de compilación, no un cuelgue.
    """
    nuevo = JamGraph()
    instancias: set[str] = set()
    # (instancia, nombre de pin) → dónde enchufar de este lado del borde
    entradas: dict[tuple[str, str], list[tuple[str, str]]] = {}
    salidas: dict[tuple[str, str], tuple[str, str]] = {}
    # una función que devuelve su entrada tal cual: el pin de salida no tiene un nodo detrás
    pasa: dict[tuple[str, str], str] = {}

    for nid, n in g.nodes.items():
        if not es_instancia(n["verb"]):
            nuevo.nodes[nid] = _copiar(n)
            continue

        nombre = nombre_de_instancia(n["verb"])
        if nombre not in biblioteca:
            raise FuncionError(f"{nid}: no existe la función «{nombre}»")
        if nombre in _pila:
            camino = " → ".join(_pila + (nombre,))
            raise FuncionError(f"{nid}: la función «{nombre}» se contiene a sí misma ({camino})")

        instancias.add(nid)
        cuerpo = expandir(biblioteca[nombre], biblioteca, _pila + (nombre,))
        firma(cuerpo)  # valida nombres de pin antes de inlinear, para que el error diga la causa

        ren = {bid: f"{nid}__{bid}" for bid, bn in cuerpo.nodes.items()
               if bn["verb"] not in VERBOS_BORDE}
        for bid, nuevo_id in ren.items():
            nuevo.nodes[nuevo_id] = _copiar(cuerpo.nodes[bid], n.get("x", 0.0), n.get("y", 0.0))

        for a, ap, b, bp in cuerpo.edges:
            va, vb = cuerpo.nodes.get(a), cuerpo.nodes.get(b)
            if va is None or vb is None:
                continue
            entra = va["verb"] == "input"
            sale = vb["verb"] == "output"
            if entra and sale:
                pasa[(nid, _nombre_borde(b, vb))] = _nombre_borde(a, va)
            elif entra:
                entradas.setdefault((nid, _nombre_borde(a, va)), []).append((ren[b], bp))
            elif sale:
                salidas[(nid, _nombre_borde(b, vb))] = (ren[a], ap)
            else:
                nuevo.edges.append((ren[a], ap, ren[b], bp))

    # de dónde viene cada pin de entrada del grafo padre, para resolver los pasamanos
    fuente: dict[tuple[str, str], tuple[str, str]] = {}
    for a, ap, b, bp in g.edges:
        fuente[(b, bp)] = (a, ap)

    def origen(nid: str, pin: str) -> tuple[str, str] | None:
        """Quién alimenta la salida `pin` de la instancia `nid`, ya del lado de afuera."""
        if (nid, pin) in salidas:
            return salidas[(nid, pin)]
        if (nid, pin) in pasa:
            de_afuera = fuente.get((nid, pasa[(nid, pin)]))
            if de_afuera and de_afuera[0] in instancias:
                return origen(de_afuera[0], de_afuera[1])
            return de_afuera
        return None

    for a, ap, b, bp in g.edges:
        a_fn, b_fn = a in instancias, b in instancias
        if not a_fn and not b_fn:
            nuevo.edges.append((a, ap, b, bp))
        elif b_fn and not a_fn:
            for destino, dpin in entradas.get((b, bp), []):
                nuevo.edges.append((a, ap, destino, dpin))
        elif a_fn and not b_fn:
            src = origen(a, ap)
            if src:
                nuevo.edges.append((src[0], src[1], b, bp))
        else:
            src = origen(a, ap)
            if src:
                for destino, dpin in entradas.get((b, bp), []):
                    nuevo.edges.append((src[0], src[1], destino, dpin))

    return nuevo


def biblioteca_desde_json(mapa: dict[str, str]) -> dict[str, JamGraph]:
    """{nombre: json del cuerpo} → {nombre: JamGraph}. Los cuerpos se guardan como cualquier
    diagrama; una función no es un formato nuevo, es un `.jamgraph` con `input`/`output`."""
    return {nombre: JamGraph.from_json(texto) for nombre, texto in mapa.items()}


def biblioteca() -> dict[str, JamGraph]:
    """Las funciones disponibles = los presets cuyo contenido declara pines (`kind` «funcion»)."""
    import json as _json

    from . import preset
    salida: dict[str, JamGraph] = {}
    for p in preset.listar(kind="funcion"):
        cuerpo = (preset.cargar(p["nombre"]) or {}).get("graph")
        if cuerpo:
            salida[p["nombre"]] = JamGraph.from_json(_json.dumps(cuerpo))
    return salida


def hay_instancias(graph_json: str) -> bool:
    import json as _json
    try:
        nodos = (_json.loads(graph_json) or {}).get("nodes", {})
    except Exception:  # noqa: BLE001
        return False
    return any(es_instancia(str(n.get("verb") or n.get("kind") or "")) for n in nodos.values())


def expandir_json(graph_json: str, biblio: dict[str, JamGraph] | None = None) -> str:
    """El grafo del canvas, sin funciones. Si no hay ninguna instancia devuelve el JSON **tal cual**.

    Se llama en el borde (`jam.api`), antes de compilar o correr, para que todo lo de adentro —
    Preflight, runner, oráculo, inspector— siga viendo un grafo normal y no tenga que aprender qué
    es una función.
    """
    if not hay_instancias(graph_json):
        return graph_json
    g = expandir(JamGraph.from_json(graph_json), biblioteca() if biblio is None else biblio)
    return g.to_json()
