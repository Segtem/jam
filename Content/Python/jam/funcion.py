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

import uuid

from .graph import JamGraph

PREFIJO = "fn:"
VERBOS_BORDE = ("input", "output")
PIN_IN, PIN_OUT = "in", "out"
# El mismo vocabulario corto que usan los cables del Graph. El borde de una función no acepta un
# texto arbitrario: un typo acá convertiría la firma en un tipo que ningún nodo puede conectar.
TIPOS_PIN = ["*", "A", "A[]", "AF", "B", "F", "H", "M", "MC", "MH", "MS", "MT", "N", "N[]", "P", "S", "T"]
# El código corto es protocolo y queda en presets/cables. La UI recibe una etiqueta aparte: cambiar
# `N` por `Número` en `opciones` rompería funciones ya guardadas y volvería ambiguo el intercambio
# con Slate. El código entre paréntesis conserva además el vocabulario de tooltips y diagnósticos.
ETIQUETAS_TIPOS_PIN = {
    "*": "Dato (cualquiera)",
    "A": "Asset (A)",
    "A[]": "Conjunto de assets (A[])",
    "AF": "Asset o frame (AF)",
    "B": "Booleano (B)",
    "F": "Flujo de frames (F)",
    "H": "Instancias HISM (H)",
    "M": "Malla dinámica (M)",
    "MT": "Material (MT)",
    "N": "Número (N)",
    "N[]": "Serie numérica (N[])",
    "MC": "Configuración MassEntity (MC)",
    "MS": "Receta MassEntity (MS)",
    "MH": "Población MassEntity viva (MH)",
    "P": "Flujo de puntos (P)",
    "S": "Curva (S)",
    "T": "Texto (T)",
}


class FuncionError(ValueError):
    """El cuerpo de una función o su uso no cumplen el contrato."""


def es_instancia(verb: str) -> bool:
    return verb.startswith(PREFIJO)


def nombre_de_instancia(verb: str) -> str:
    return verb[len(PREFIJO):]


def nuevo_id() -> str:
    """Identidad estable de una definición. El nombre humano puede cambiar sin romper instancias."""
    return "f_" + uuid.uuid4().hex


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
            tipo = str(n.get("params", {}).get("type", "*")).strip()
            if tipo not in TIPOS_PIN:
                raise FuncionError(f"{nid}: tipo de pin desconocido: «{tipo}»")
            if nombre in vistos:
                raise FuncionError(f"hay dos `{verb}` llamados «{nombre}»: el pin sería ambiguo")
            vistos.add(nombre)
            pin = {"name": nombre, "tipo": tipo}
            # Un `input` con VALOR POR DEFECTO es una perilla; sin él, un pin que hay que cablear.
            # No hace falta un verbo nuevo: es la misma declaración con un dato más. Y como en Jam
            # un parámetro YA es «campo + pin» (se grisea al cablearlo), una perilla sigue siendo
            # cableable — que es justo lo que hace un HDA y no un `.sbsar`.
            if verb == "input":
                crudo = n.get("params", {}).get("default", "")
                if str(crudo).strip() != "":
                    pin["default"] = str(crudo)
            salida[clave].append(pin)
    return salida


def es_cuerpo(cuerpo: JamGraph) -> bool:
    """Un `input`/`output` convierte al diagrama en definición: no es un grafo ejecutable solo."""
    return any(n.get("verb") in VERBOS_BORDE for n in cuerpo.nodes.values())


def validar_cuerpo(cuerpo: JamGraph, biblio: dict[str, JamGraph] | None = None) \
        -> tuple[dict, dict[str, list[str]]]:
    """Valida firma y DAG sin inventar valores para las entradas de la función.

    Cada borde se reemplaza sólo durante Compile por un verbo sintético con SU tipo. Así el
    compilador normal verifica pines, tipos, cardinalidad, ciclos y parámetros del interior, pero
    nunca intenta ejecutar `input`/`output` como si fueran tools de escena.
    """
    try:
        contrato = firma(cuerpo)
    except FuncionError as exc:
        return {"entradas": [], "salidas": []}, {"_graph": [str(exc)]}

    try:
        expandido = expandir(cuerpo, biblioteca() if biblio is None else biblio) \
            if any(es_instancia(n.get("verb", "")) for n in cuerpo.nodes.values()) else cuerpo
    except FuncionError as exc:
        return contrato, {"_graph": [str(exc)]}

    from . import graph, tools
    comprobable = JamGraph()
    comprobable.edges = list(expandido.edges)
    registro = dict(tools.REGISTRO)
    for nid, nodo in expandido.nodes.items():
        copia = {"verb": nodo.get("verb", ""), "params": dict(nodo.get("params", {})),
                 "asset": nodo.get("asset"), "x": nodo.get("x", 0.0),
                 "y": nodo.get("y", 0.0), "debug": bool(nodo.get("debug", False))}
        if copia["verb"] in VERBOS_BORDE:
            tipo = str(copia["params"].get("type", "*"))
            es_entrada = copia["verb"] == "input"
            if es_entrada and tipo == "N":
                copia["verb"] = "number"
                copia["params"] = {"name": f"__entrada_{nid}", "value": 0.0,
                                   "min": 0.0, "max": 100.0}
                comprobable.nodes[nid] = copia
                continue
            if es_entrada and tipo == "T":
                copia["verb"] = "text"
                copia["params"] = {"name": f"__entrada_{nid}", "value": ""}
                comprobable.nodes[nid] = copia
                continue
            sintetico = f"__borde_funcion_{copia['verb']}_{nid}"
            registro[sintetico] = {
                "source": es_entrada, "aridad": 0 if es_entrada else 1,
                "in_name": "" if es_entrada else tipo,
                "out_name": tipo, "asset_required": False, "asset_pin": False,
                "asset_row": False, "params": {"name": "", "type": "*"},
            }
            copia["verb"] = sintetico
        comprobable.nodes[nid] = copia
    return contrato, graph.validar(comprobable, registro=registro)


def herramientas(cuerpos: dict[str, JamGraph] | None = None) -> list[dict]:
    """Spec de los bordes y de cada función para el ribbon del Graph.

    Una función no entra en ``tools.REGISTRO``: es contenido del usuario y cambia mientras el editor
    está abierto. Viaja por el mismo formato, pero declara ``inputs``/``outputs`` nombrados porque
    reducir una firma a un único ``in``/``out`` perdería justamente el contrato que la hace útil.
    """
    borde = [
        {"verbo": "input", "cat": "Funciones", "seccion": "Funciones", "grupo": "Firma",
         "doc": "entrada nombrada del cuerpo de una función. «por defecto» VACÍO deja un pin que "
                "hay que cablear; con un valor, la entrada pasa a ser una perilla editable en la "
                "ficha de la herramienta (y se puede cablear igual: el cable manda sobre el campo)",
         "source": True, "aridad": 0,
         "in_name": "", "out_name": "*", "asset_pin": False, "asset_row": False,
         "params": [
             {"nombre": "name", "default": "entrada", "tipo": "str", "data_type": "T",
              "opciones": []},
             {"nombre": "type", "default": "*", "tipo": "str", "data_type": "T",
              "opciones": TIPOS_PIN,
              "etiquetas_opciones": [ETIQUETAS_TIPOS_PIN[t] for t in TIPOS_PIN]},
             # Lo que convierte esta entrada en PERILLA. Vacío = pin que hay que cablear; con un
             # valor = control editable en la ficha de la herramienta (y cableable igual).
             #
             # La etiqueta es CORTA a propósito: la columna de params mide 104 px y el nombre se
             # dibuja a su izquierda, así que una etiqueta larga («valor por defecto (vacío = pin)»,
             # ~124 px) exprime el campo hasta dejarlo invisible. La explicación va en el `doc`,
             # que se ve en el tooltip del nodo y tiene todo el lugar del mundo.
             {"nombre": "default", "label": "por defecto", "default": "",
              "tipo": "str", "data_type": "T", "opciones": []},
         ]},
        {"verbo": "output", "cat": "Funciones", "seccion": "Funciones", "grupo": "Firma",
         "doc": "salida nombrada del cuerpo de una función", "source": False, "aridad": 1,
         "in_name": "*", "out_name": "", "asset_pin": False, "asset_row": False,
         "params": [
             {"nombre": "name", "default": "salida", "tipo": "str", "data_type": "T",
              "opciones": []},
             {"nombre": "type", "default": "*", "tipo": "str", "data_type": "T",
              "opciones": TIPOS_PIN,
              "etiquetas_opciones": [ETIQUETAS_TIPOS_PIN[t] for t in TIPOS_PIN]},
         ]},
    ]
    if cuerpos is None:
        try:
            definiciones = listar_definiciones()
        except (AttributeError, RuntimeError):
            # ``spec_all`` sigue siendo consultable en Python pelado: ahí no existe ``unreal.Paths``
            # y, por definición, tampoco hay presets locales del proyecto que enumerar.
            definiciones = []
    else:
        # Compatibilidad del borde puro y de sus tests: {nombre_o_id: JamGraph}. Las definiciones
        # reales llegan por `listar_definiciones` y sí separan id de etiqueta.
        definiciones = [
            {"funcion_id": identidad, "nombre": identidad, "cuerpo": cuerpo}
            for identidad, cuerpo in cuerpos.items()
        ]
    salida = list(borde)
    for definicion in definiciones:
        salida.append(herramienta(
            definicion["funcion_id"], definicion["nombre"], definicion["cuerpo"]))
    return salida


def herramienta(funcion_id: str, nombre: str, cuerpo: JamGraph,
                preset: dict | None = None) -> dict:
    """Spec de una llamada: verbo interno estable y etiqueta humana independiente."""
    f = firma(cuerpo)
    # Las entradas CON default se publican como perillas de la ficha; las que no, como pines.
    # Es la diferencia entre «esto lo tenés que conectar» y «esto lo podés ajustar» — la que hace
    # que una herramienta sea usable sin entender el grafo de adentro.
    perillas = [e for e in f["entradas"] if "default" in e]
    pines = [e for e in f["entradas"] if "default" not in e]
    from .jamtool_core import entrada_de_seleccion, superficies_de_funcion

    # Dónde se ve esta tool armada por el usuario. Por defecto sólo en el Graph: una función recién
    # colapsada es un paso intermedio de lo que alguien está construyendo, y llenar la barra con eso
    # repetiría el error que tenía el registro —estar ahí por omisión—. Publicarla es deliberado.
    superficies = sorted(superficies_de_funcion(preset or {}))
    return {
        "verbo": PREFIJO + funcion_id, "label": nombre,
        "cat": "Funciones", "seccion": "Funciones", "grupo": "Biblioteca",
        "superficies": superficies,
        # Por dónde entra la selección de la escena cuando corre desde la Dash Bar. En el Graph la
        # alimentan los cables; en la barra no hay cables.
        "entrada_seleccion": entrada_de_seleccion(f) or "",
        "doc": f"función «{nombre}» — se expande inline antes de Compile",
        "source": not pines, "aridad": 0 if not pines else 1,
        "in_name": "", "out_name": "", "asset_pin": False, "asset_row": False,
        "inputs": pines, "outputs": f["salidas"],
        "params": [{"nombre": e["name"], "label": e["name"], "default": e["default"],
                    "tipo": _tipo_de_control(e["tipo"], e["default"]),
                    "data_type": e["tipo"], "letra": "", "opciones": []}
                   for e in perillas],
    }


def _tipo_de_control(tipo_pin: str, default: str) -> str:
    """Qué control dibuja la ficha para esta perilla.

    El tipo del PIN dice qué dato viaja por el cable; el control dice cómo se edita a mano. Un `B`
    es un checkbox y un `N` un spinner aunque los dos se puedan cablear igual.
    """
    if tipo_pin == "B":
        return "bool"
    if tipo_pin in ("N", "N[]"):
        # Entero si el default no tiene coma: `count=24` merece un spinner sin decimales.
        return "float" if "." in str(default) else "int"
    return "str"


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
    # cuerpo YA EXPANDIDO por instancia: lo necesita el pase de perillas, y tiene que ser el
    # expandido porque es el que da los nombres de pin con los que se armó `entradas`.
    cuerpos: dict[str, JamGraph] = {}

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
        cuerpos[nid] = cuerpo
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

    # ---- perillas: el valor de la ficha baja a los params de adentro ----
    # Una entrada CON default es una perilla. Si nadie la cableó, su valor —el que se tipeó en la
    # ficha, o el default si no se tocó— se escribe como parámetro en cada nodo interno al que esa
    # entrada alimenta. Es la misma regla que rige cualquier param de Jam: el cable manda sobre el
    # campo. Acá simplemente no hay cable, así que manda el campo.
    cableadas = {(b, bp) for _a, _ap, b, bp in g.edges}
    for nid, cuerpo in cuerpos.items():
        instancia_params = g.nodes[nid].get("params", {})
        for entrada in firma(cuerpo)["entradas"]:
            if "default" not in entrada:
                continue   # es un pin: si no está cableado, eso lo diagnostica Compile
            pin = entrada["name"]
            if (nid, pin) in cableadas:
                continue   # lo manda el cable
            valor = instancia_params.get(pin, entrada["default"])
            for destino, dpin in entradas.get((nid, pin), []):
                if destino in nuevo.nodes:
                    nuevo.nodes[destino].setdefault("params", {})[dpin] = str(valor)

    return nuevo


def biblioteca_desde_json(mapa: dict[str, str]) -> dict[str, JamGraph]:
    """{nombre: json del cuerpo} → {nombre: JamGraph}. Los cuerpos se guardan como cualquier
    diagrama; una función no es un formato nuevo, es un `.jamgraph` con `input`/`output`."""
    return {nombre: JamGraph.from_json(texto) for nombre, texto in mapa.items()}


def biblioteca() -> dict[str, JamGraph]:
    """Cuerpos por identidad. Las funciones legadas conservan su nombre como identidad."""
    return {d["funcion_id"]: d["cuerpo"] for d in listar_definiciones()}


def listar_definiciones() -> list[dict]:
    """Definiciones disponibles con identidad, etiqueta y cuerpo.

    Un preset anterior a `funcion_id` sigue publicando exactamente `fn:<nombre>`; no se migra a
    escondidas porque eso dejaría huérfanos los grafos que ya lo llaman.
    """
    import json as _json

    from . import preset
    # `preset.listar` recorre global→local: reemplazar por identidad conserva la precedencia local
    # y evita publicar dos tools con el mismo verbo para una definición legada sombreada.
    por_id: dict[str, dict] = {}
    for p in preset.listar(kind="funcion"):
        cuerpo = p.get("graph")
        if cuerpo:
            identidad = str(p.get("funcion_id") or p["nombre"])
            por_id[identidad] = {
                "funcion_id": identidad,
                "nombre": str(p["nombre"]),
                "scope": p.get("scope", "local"),
                "descripcion": p.get("descripcion", ""),
                # Publicada = aparece en la Dash. Por defecto SÍ: la idea es que construir la
                # biblioteca vaya poblando la barra sola. Se puede apagar para las auxiliares, que
                # sirven adentro de otro grafo y sólo serían ruido en una barra de herramientas.
                "publicada": bool(p.get("publicada", True)),
                "cuerpo": JamGraph.from_json(_json.dumps(cuerpo)),
            }
    return list(por_id.values())


def obtener_definicion(funcion_id: str) -> dict:
    funcion_id = nombre_de_instancia(funcion_id) if es_instancia(funcion_id) else funcion_id
    for d in listar_definiciones():
        if d["funcion_id"] == funcion_id:
            return d
    raise FuncionError(f"no existe la función «{funcion_id}»")


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
