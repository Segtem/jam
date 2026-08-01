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


def herramientas(cuerpos: dict[str, JamGraph] | None = None) -> list[dict]:
    """Spec de los bordes y de cada función para el ribbon del Graph.

    Una función no entra en ``tools.REGISTRO``: es contenido del usuario y cambia mientras el editor
    está abierto. Viaja por el mismo formato, pero declara ``inputs``/``outputs`` nombrados porque
    reducir una firma a un único ``in``/``out`` perdería justamente el contrato que la hace útil.
    """
    borde = [
        {"verbo": "input", "cat": "Funciones", "grupo": "Firma",
         "doc": "entrada nombrada del cuerpo de una función", "source": True, "aridad": 0,
         "in_name": "", "out_name": "*", "asset_pin": False, "asset_row": False,
         "params": [
             {"nombre": "name", "default": "entrada", "tipo": "str", "data_type": "T",
              "opciones": []},
             {"nombre": "type", "default": "*", "tipo": "str", "data_type": "T",
              "opciones": []},
         ]},
        {"verbo": "output", "cat": "Funciones", "grupo": "Firma",
         "doc": "salida nombrada del cuerpo de una función", "source": False, "aridad": 1,
         "in_name": "*", "out_name": "", "asset_pin": False, "asset_row": False,
         "params": [
             {"nombre": "name", "default": "salida", "tipo": "str", "data_type": "T",
              "opciones": []},
             {"nombre": "type", "default": "*", "tipo": "str", "data_type": "T",
              "opciones": []},
         ]},
    ]
    if cuerpos is None:
        try:
            cuerpos = biblioteca()
        except (AttributeError, RuntimeError):
            # ``spec_all`` sigue siendo consultable en Python pelado: ahí no existe ``unreal.Paths``
            # y, por definición, tampoco hay presets locales del proyecto que enumerar.
            cuerpos = {}
    salida = list(borde)
    for nombre, cuerpo in cuerpos.items():
        f = firma(cuerpo)
        salida.append({
            "verbo": PREFIJO + nombre, "cat": "Funciones", "grupo": "Biblioteca",
            "doc": f"función «{nombre}» — se expande inline antes de Compile",
            "source": not f["entradas"], "aridad": 0 if not f["entradas"] else 1,
            "in_name": "", "out_name": "", "asset_pin": False, "asset_row": False,
            "inputs": f["entradas"], "outputs": f["salidas"], "params": [],
        })
    return salida


def _nombre_pin(preferido: str, base: str, usados: set[str]) -> str:
    """Nombre humano, estable y único dentro de un lado de la firma."""
    candidato = str(preferido or "").strip() or base
    nombre = candidato
    numero = 2
    while nombre in usados:
        nombre = f"{candidato}_{numero}"
        numero += 1
    usados.add(nombre)
    return nombre


def colapsar(g: JamGraph, seleccion: set[str], nombre: str, *, registro: dict | None = None,
             biblio: dict[str, JamGraph] | None = None) -> tuple[JamGraph, JamGraph]:
    """Reemplaza ``seleccion`` por ``fn:nombre`` y devuelve ``(padre, cuerpo)``.

    Los cables que cruzan el borde se convierten en pines. Dos cables que comparten el mismo
    endpoint interior/exterior comparten pin cuando corresponde, de modo que el fan-out no cambia.
    Las posiciones del cuerpo son relativas a la instancia: expandirlo recupera el dibujo original.
    """
    seleccion = set(seleccion)
    if not seleccion:
        raise FuncionError("seleccioná al menos un nodo para colapsar")
    faltan = sorted(seleccion - set(g.nodes))
    if faltan:
        raise FuncionError(f"la selección referencia nodos inexistentes: {', '.join(faltan)}")
    if any(g.nodes[nid]["verb"] in VERBOS_BORDE for nid in seleccion):
        raise FuncionError("no se puede colapsar un pin input/output dentro de otra función")
    nombre = str(nombre or "").strip()
    if not nombre:
        raise FuncionError("la función necesita un nombre")

    if registro is None:
        from . import tools
        registro = tools.REGISTRO
    biblio = biblioteca() if biblio is None else biblio

    from .graph import _tipo_entrada, _tipo_salida

    firmas = {PREFIJO + n: firma(c) for n, c in biblio.items()}

    def tipo_salida(nid: str, pin: str) -> str | None:
        verb = g.nodes[nid]["verb"]
        if verb in firmas:
            return next((p["tipo"] for p in firmas[verb]["salidas"] if p["name"] == pin), None)
        return _tipo_salida(verb, registro) if pin == PIN_OUT else None

    def tipo_entrada(nid: str, pin: str) -> str | None:
        verb = g.nodes[nid]["verb"]
        if verb in firmas:
            return next((p["tipo"] for p in firmas[verb]["entradas"] if p["name"] == pin), None)
        return _tipo_entrada(verb, pin, registro)

    xs = [float(g.nodes[n]["x"]) for n in seleccion]
    ys = [float(g.nodes[n]["y"]) for n in seleccion]
    centro_x = (min(xs) + max(xs)) * 0.5
    centro_y = (min(ys) + max(ys)) * 0.5

    cuerpo = JamGraph()
    for nid in g.nodes:
        if nid in seleccion:
            cuerpo.nodes[nid] = _copiar(g.nodes[nid], -centro_x, -centro_y)

    internas = [e for e in g.edges if e[0] in seleccion and e[2] in seleccion]
    cuerpo.edges.extend(internas)

    entrantes = [e for e in g.edges if e[0] not in seleccion and e[2] in seleccion]
    salientes = [e for e in g.edges if e[0] in seleccion and e[2] not in seleccion]

    # Un input representa un endpoint EXTERIOR: si el mismo dato alimentaba dos nodos elegidos,
    # sigue entrando una vez y hace fan-out adentro del cuerpo.
    grupos_in: dict[tuple[str, str], list[tuple[str, str, str, str]]] = {}
    for e in entrantes:
        grupos_in.setdefault((e[0], e[1]), []).append(e)
    usados_in: set[str] = set()
    pines_in: dict[tuple[str, str], str] = {}
    for indice, (afuera, grupo) in enumerate(grupos_in.items(), 1):
        primero = grupo[0]
        tipo = tipo_salida(primero[0], primero[1]) or tipo_entrada(primero[2], primero[3])
        if not tipo:
            raise FuncionError(f"no pude resolver el tipo de {primero[0]}.{primero[1]}")
        pin = _nombre_pin(primero[3], "entrada", usados_in)
        bid = f"__entrada_{indice}"
        while bid in cuerpo.nodes:
            bid += "_"
        y = min(float(g.nodes[e[2]]["y"]) for e in grupo) - centro_y
        cuerpo.add("input", {"name": pin, "type": tipo}, nid=bid,
                   x=min(xs) - centro_x - 220.0, y=y)
        for _a, _ap, destino, dpin in grupo:
            cuerpo.connect(bid, destino, dpin)
        pines_in[afuera] = pin

    # Una salida representa un endpoint INTERIOR: el fan-out de ese resultado queda afuera.
    grupos_out: dict[tuple[str, str], list[tuple[str, str, str, str]]] = {}
    for e in salientes:
        grupos_out.setdefault((e[0], e[1]), []).append(e)
    usados_out: set[str] = set()
    pines_out: dict[tuple[str, str], str] = {}
    for indice, (adentro, grupo) in enumerate(grupos_out.items(), 1):
        primero = grupo[0]
        tipo = tipo_salida(primero[0], primero[1])
        if not tipo:
            raise FuncionError(f"no pude resolver el tipo de {primero[0]}.{primero[1]}")
        preferido = primero[1] if primero[1] != PIN_OUT else "salida"
        pin = _nombre_pin(preferido, "salida", usados_out)
        bid = f"__salida_{indice}"
        while bid in cuerpo.nodes:
            bid += "_"
        cuerpo.add("output", {"name": pin, "type": tipo}, nid=bid,
                   x=max(xs) - centro_x + 220.0, y=float(g.nodes[primero[0]]["y"]) - centro_y)
        cuerpo.connect(primero[0], bid, "in", primero[1])
        pines_out[adentro] = pin

    padre = JamGraph()
    for nid, nodo in g.nodes.items():
        if nid not in seleccion:
            padre.nodes[nid] = _copiar(nodo)
    instancia = "f1"
    numero = 1
    while instancia in g.nodes:
        numero += 1
        instancia = f"f{numero}"
    padre.add(PREFIJO + nombre, {}, nid=instancia, x=centro_x, y=centro_y)
    emitidas_in: set[tuple[str, str]] = set()
    for a, ap, b, bp in g.edges:
        a_sel, b_sel = a in seleccion, b in seleccion
        if not a_sel and not b_sel:
            padre.edges.append((a, ap, b, bp))
        elif not a_sel and b_sel:
            if (a, ap) not in emitidas_in:
                padre.edges.append((a, ap, instancia, pines_in[(a, ap)]))
                emitidas_in.add((a, ap))
        elif a_sel and not b_sel:
            padre.edges.append((instancia, pines_out[(a, ap)], b, bp))

    # Valida nombres duplicados/ausentes y, además, fija que la firma resultante sea la que el
    # ribbon va a publicar. Si esto falla no se debe escribir ningún preset.
    firma(cuerpo)
    return padre, cuerpo


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
