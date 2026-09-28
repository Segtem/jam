"""El texto de un grafo: la segunda vista del mismo `JamGraph`. Cerebro puro, sin `unreal`.

Tarea `dsl-grafos`, diseño elegido: `tareas/20260924-121231-dsl-grafos/investigacion/claude.md`.
Una línea por nodo, en el orden del documento:

    x = series_range end=720 count=7
    polyline = curve_polyline x=@x y=@y z=@z
    smooth = curve_smooth @polyline iterations=3 strength=0.45
    merge = mesh_merge @trunk_pipe @branch_pipe
    deco = matrix_decompose matriz=@m
    tallo = curve_line_sdl direccion=@deco.eje_z largo="=alto * 0.9"
    normals = mesh_normals @pipe +bypass

`nombre = verbo [posicional] @entradas… clave=valor… +banderas`. El nombre ES el id del nodo; `@x`
es un cable desde la salida principal de `x` y `@x.pin` desde una salida extra; `@x` suelto va al pin
`in`, `clave=@x` a un parámetro. El layout (posiciones, reroutes, comentarios) no va en el texto:
queda en el `.jamgraph` y se une por nombre.

Hay UNA forma canónica, la que escribe `imprimir` (como gofmt). `leer` acepta un poco más —orden de
parámetros, `0.10`, un default escrito— y `imprimir(leer(t))` lo lleva a esa forma. Qué significa
«el mismo grafo» lo dice `normal`: dos grafos son el mismo si su forma normal es igual.
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata

from .graph import PIN_ASSET, PIN_IN, PIN_OUT, JamGraph

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
#: Texto que se escribe sin comillas: rutas `/Game/…`, anclas, nombres de asset.
PALABRA = re.compile(r"[A-Za-z0-9_./:-]+\Z")
_NUMERO = re.compile(r"-?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?\Z")
_VERDAD = ("1", "true", "si", "sí", "yes", "on")
_MENTIRA = ("0", "false", "no", "off")
#: Tipos de valor rico: se escriben como tupla `(a, b, c)` y se guardan como el canvas, «a,b,c».
_TUPLAS = ("V", "D", "MX")
#: Tipos de los nodos de valor (`math_core.VALORES[…]["tipos"]`) → tipo del literal.
_TIPO_VALOR = {"N": "float", "T": "str", "B": "bool"}
#: Los bordes de una función (`funcion.VERBOS_BORDE`): no están en el registro, pero son verbos.
_BORDES = {"input": {"name": "", "type": "*"}, "output": {"name": "", "type": "*"}}


#: Lo que un LLM necesita para escribir un grafo sin haberlo visto nunca (lo sirve `jam-mcp`).
SINTAXIS = """\
Un grafo de Jam es texto: una línea por nodo.
    nombre = verbo [posicional] @entrada… clave=valor… +bypass +debug
- nombre: letras, dígitos y «_»; es el id del nodo y lo que se ve en el canvas.
- @x: cable desde la salida principal del nodo x al pin «in»; @x.pin desde una salida extra.
  Varios @ seguidos entran en orden (verbos variádicos como mesh_merge).
- clave=@x: cable a un parámetro. clave=valor: número, true/false, (x, y, z), texto o "entre comillas".
- "=expr": expresión con variables (los nodos number/math por su nombre), p. ej. largo="=alto * 0.9".
- posicional: el asset en los verbos que colocan uno (place SM_Rock), el valor de number/text.
- Los parámetros que no escribís valen su default. Sin comentarios.
Ejemplo:
    caja = mesh_box size_x=200
    suave = mesh_normals @caja
    hornear = mesh_to_static @suave name=SM_Caja
    colocar = place @hornear view=true
"""


class ErrorTexto(ValueError):
    """Un texto que no describe un grafo. Dice dónde, qué y cómo seguir."""

    def __init__(self, linea: int, columna: int, mensaje: str):
        self.linea, self.columna, self.mensaje = linea, columna, mensaje
        super().__init__(f"línea {linea}, columna {columna}: {mensaje}")


class Expr(str):
    """Una expresión «=…»: se escribe siempre entre comillas, para que no la confunda una PALABRA."""


# ---------------------------------------------------------------- vocabulario

def vocabulario() -> dict[str, dict]:
    """verbo → {params: {clave: default}, tipos: {clave: tipo}, posicional, variadico, valor}.

    El mismo universo que acepta el canvas: el registro neutro, los nodos de valor, las ops que sólo
    existen en Flow y los bordes de función. Una instancia `fn:…` no está: su firma es del usuario.
    """
    from . import flow
    from .math_core import VALORES
    from .registro import REGISTRO

    vocab: dict[str, dict] = {}
    for verbo, info in REGISTRO.items():
        vocab[verbo] = _spec(info.get("params", {}), info.get("data_params", {}),
                             "asset" if info.get("asset_row") else ("name" if verbo == "asset" else None),
                             info.get("aridad") == -1)
    for verbo, info in VALORES.items():
        tipos = {k: (_TIPO_VALOR.get(t) or ("tupla" if t in _TUPLAS else "str"))
                 for k, t in info.get("tipos", {}).items()}
        params = dict(info.get("params", {}))
        posicional = "value" if "value" in params else ("expr" if "expr" in params else None)
        vocab[verbo] = {"params": params, "tipos": tipos, "posicional": posicional,
                        "variadico": False, "valor": "name" in params}
    for verbo, meta in flow.OPS_META.items():
        vocab.setdefault(verbo, _spec(meta.get("params", {}), {}, None, False))
    for verbo, params in _BORDES.items():
        vocab.setdefault(verbo, _spec(params, {}, None, False))
    return vocab


def _spec(params: dict, data_params: dict, posicional, variadico: bool) -> dict:
    tipos = {}
    for k, d in params.items():
        dato = data_params.get(k, "")
        if dato in _TUPLAS or isinstance(d, tuple):
            tipos[k] = "tupla"
        elif isinstance(d, bool):
            tipos[k] = "bool"
        elif isinstance(d, int):
            tipos[k] = "int"
        elif isinstance(d, float):
            tipos[k] = "float"
        else:
            tipos[k] = "str"
    return {"params": dict(params), "tipos": tipos, "posicional": posicional,
            "variadico": variadico, "valor": False}


# ---------------------------------------------------------------- valores

def _num(x: float) -> str:
    """El número más corto que conserva el valor: `720`, `0.45`, `-80`. `repr` y no `.6g`: `.6g`
    pierde precisión y la ida y vuelta dejaría de ser exacta."""
    x = float(x)
    if x.is_integer() and abs(x) < 1e16:
        return str(int(x))
    return repr(x)


def _tupla(v):
    if isinstance(v, (tuple, list)):
        partes = list(v)
    else:
        partes = [p for p in str(v).strip().strip("()[]").replace(",", " ").split() if p]
    try:
        return tuple(float(p) for p in partes) if partes else None
    except (TypeError, ValueError):
        return None


def valor(tipo: str, v):
    """El valor TIPADO de un parámetro: lo que compara la forma normal. `"0.10"`, `"0.1"` y `0.1`
    son el mismo float; «n*2» en un pin numérico es la expresión «=n*2», como ya lo evalúa el
    Compile (graph.py, `_resolver_parametro`)."""
    if isinstance(v, str) and v.strip().startswith("="):
        return Expr(v.strip())
    if tipo == "bool":
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        return True if s in _VERDAD else False if s in _MENTIRA else str(v)
    if tipo in ("int", "float"):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return int(v) if tipo == "int" else float(v)
        s = str(v).strip()
        if _NUMERO.match(s):
            return int(float(s)) if tipo == "int" else float(s)
        return Expr("=" + s) if s else s
    if tipo == "tupla":
        t = _tupla(v)
        return t if t is not None else str(v)
    return v if isinstance(v, str) else str(v)


def escribir(v) -> str:
    """Un valor tipado como literal del texto."""
    if isinstance(v, Expr):
        return json.dumps(str(v), ensure_ascii=False)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return _num(v)
    if isinstance(v, tuple):
        return "(" + ", ".join(_num(x) for x in v) + ")"
    # Sin comillas si cabe en PALABRA, aunque parezca un número: el lector tipa por el PIN, así que
    # `name=123` en un pin de texto se lee «123», igual que `"123"`.
    s = str(v)
    return s if PALABRA.match(s) else json.dumps(s, ensure_ascii=False)


def _guardar(v) -> str:
    """Un valor tipado como lo guarda el canvas: todo string (SJamGraphEditor, `BuildJson`)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return _num(v)
    if isinstance(v, tuple):
        return ",".join(_num(x) for x in v)
    return str(v)


# ---------------------------------------------------------------- forma normal

def _params_normales(nid: str, nodo: dict, spec: dict | None, cableados: set[str]) -> dict:
    """Los parámetros que cuentan: tipados, sin los que están en su default y sin los cableados
    (el cable manda: graph.py descarta el literal)."""
    crudos = dict(nodo.get("params", {}))
    if nodo.get("asset") and not crudos.get(PIN_ASSET):
        crudos[PIN_ASSET] = nodo["asset"]
    if spec is None:
        return {k: str(v) for k, v in crudos.items() if k not in cableados}
    if spec["valor"] and not str(crudos.get("name", "")).strip():
        # Un nodo de valor sin `name` se llama como el nodo. Es la regla del Compile
        # (`name or nid`, graph.py) y la que escribe el texto.
        crudos["name"] = nid
    salida = {}
    for k, v in crudos.items():
        if k in cableados:
            continue
        tipo = spec["tipos"].get(k, "str")
        tv = valor(tipo, v)
        if k == "name" and spec["valor"] and tv == nid:
            continue
        if k == PIN_ASSET and k not in spec["params"]:
            if str(tv).strip():
                salida[k] = str(tv)
            continue
        if k in spec["params"] and tv == valor(tipo, spec["params"][k]):
            continue
        salida[k] = tv
    return salida


def normal(g: JamGraph, vocab: dict | None = None) -> tuple:
    """La forma normal: lo que tiene que sobrevivir a la ida y vuelta. Dos grafos son el mismo si
    `normal` da igual. No cuentan `x`, `y`, `compact`, reroutes, comentarios ni vista."""
    vocab = vocabulario() if vocab is None else vocab
    entrantes = _entrantes(g)
    nodos = []
    for nid, n in g.nodes.items():
        spec = vocab.get(n.get("verb", ""))
        cableados = {pin for pin in entrantes.get(nid, {}) if pin != PIN_IN}
        params = _params_normales(nid, n, spec, cableados)
        nodos.append((nid, n.get("verb", ""), tuple(sorted(params.items(), key=lambda kv: kv[0])),
                      bool(n.get("bypass")), bool(n.get("debug"))))
    aristas = []
    for nid, pines in entrantes.items():
        spec = vocab.get(g.nodes.get(nid, {}).get("verb", ""))
        for pin, fuentes in pines.items():
            # El orden sólo cuenta en la entrada de un variádico: `mesh_merge` recibe la lista así.
            orden = fuentes if (pin == PIN_IN and spec and spec["variadico"]) else sorted(fuentes)
            aristas.append((nid, pin, tuple(orden)))
    return tuple(nodos), tuple(sorted(aristas))


def _entrantes(g: JamGraph) -> dict[str, dict[str, list[tuple[str, str]]]]:
    salida: dict[str, dict[str, list[tuple[str, str]]]] = {}
    for a, ap, b, bp in g.edges:
        salida.setdefault(b, {}).setdefault(bp, []).append((a, ap))
    return salida


# ---------------------------------------------------------------- impresor

def _ref(origen: str, pin: str) -> str:
    return "@" + origen + ("" if pin == PIN_OUT else "." + pin)


def imprimir(g: JamGraph, vocab: dict | None = None) -> str:
    """El texto canónico del grafo: una línea por nodo, en el orden del documento."""
    vocab = vocabulario() if vocab is None else vocab
    entrantes = _entrantes(g)
    lineas = []
    for nid, n in g.nodes.items():
        if not IDENT.match(nid):
            raise ValueError(f"el nodo «{nid}» no tiene un nombre escribible: tiene que ser "
                             "letras, dígitos y «_», sin empezar por dígito")
        verbo = n.get("verb", "")
        spec = vocab.get(verbo)
        pines = entrantes.get(nid, {})
        params = _params_normales(nid, n, spec, {p for p in pines if p != PIN_IN})
        partes = [f"{nid} =", verbo if re.fullmatch(r"[\w:.-]+", verbo) else json.dumps(verbo)]
        posicional = spec["posicional"] if spec else None
        if posicional and posicional in params and posicional not in pines:
            partes.append(escribir(params.pop(posicional)))
        partes += [_ref(a, ap) for a, ap in pines.get(PIN_IN, [])]
        # ponytail: una instancia `fn:` va en orden alfabético porque su firma vive en la biblioteca
        # del usuario (preset, impuro); ordenarla por firma cuando el texto resuelva funciones.
        orden = list(spec["params"]) if spec else []
        resto = sorted((set(params) | set(pines)) - set(orden) - {PIN_IN})
        for k in orden + resto:
            if k in pines and k != PIN_IN:
                partes += [f"{k}={_ref(a, ap)}" for a, ap in pines[k]]
            elif k in params:
                partes.append(f"{k}={escribir(params[k])}")
        partes += [f"+{b}" for b in ("bypass", "debug") if n.get(b)]
        lineas.append(" ".join(partes))
    return "".join(linea + "\n" for linea in lineas)


# ---------------------------------------------------------------- lector

_CABECERA = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)\s*")


def leer(texto: str, vocab: dict | None = None) -> JamGraph:
    """Texto → `JamGraph`. Levanta `ErrorTexto` con línea y columna en el primer error.

    No juzga el grafo —tipos, pines, parámetros desconocidos—: eso lo hace el Compile, y con el mismo
    mensaje que para un grafo del canvas. Acá se ataja sólo lo que impide ARMAR el grafo.
    """
    vocab = vocabulario() if vocab is None else vocab
    g = JamGraph()
    lineas_de: dict[str, int] = {}
    pendientes = []   # (linea, columna, origen, pin_origen, destino, pin_destino)
    for numero, linea in enumerate(texto.splitlines(), start=1):
        if not linea.strip():
            continue
        m = _CABECERA.match(linea)
        if not m:
            raise ErrorTexto(numero, 1, "cada línea es «nombre = verbo …»; falta el nombre del "
                                        "nodo y el «=» (por ejemplo «roca = scatter SM_Rock»)")
        nid = m.group(1)
        if nid in lineas_de:
            raise ErrorTexto(numero, 1, f"«{nid}» ya está en la línea {lineas_de[nid]}: cada nodo "
                                        "tiene un nombre propio")
        lineas_de[nid] = numero
        tokens = list(_tokens(linea, m.end(), numero))
        if not tokens:
            raise ErrorTexto(numero, m.end() + 1, f"falta el verbo de «{nid}»")
        col, clase, verbo = tokens[0]
        if clase not in ("palabra", "cadena"):
            raise ErrorTexto(numero, col, f"«{nid}» necesita un verbo después del «=»")
        spec = vocab.get(verbo)
        if spec is None and not verbo.startswith("fn:"):
            cerca = difflib.get_close_matches(verbo, list(vocab), n=1)
            raise ErrorTexto(numero, col, f"verbo desconocido: «{verbo}»"
                                          + (f" — ¿quisiste decir «{cerca[0]}»?" if cerca else ""))
        params: dict[str, str] = {}
        flags = {"bypass": False, "debug": False}
        posicional_visto = False
        for col, clase, dato in tokens[1:]:
            if clase == "ref":
                pendientes.append((numero, col, *dato, nid, PIN_IN))
            elif clase == "bandera":
                if dato not in flags:
                    raise ErrorTexto(numero, col, f"bandera desconocida: «+{dato}» — hay +bypass y +debug")
                flags[dato] = True
            elif clase == "param":
                clave, (sub, crudo) = dato
                if sub == "ref":
                    pendientes.append((numero, col, *crudo, nid, clave))
                else:
                    tipo = spec["tipos"].get(clave, "str") if spec else "str"
                    params[clave] = _guardar(valor(tipo, crudo if sub != "tupla" else crudo))
            else:  # posicional
                posicional = spec["posicional"] if spec else None
                if posicional is None:
                    raise ErrorTexto(numero, col, f"«{dato}» suelto: `{verbo}` no recibe un valor "
                                                  "posicional — ¿quisiste escribir «clave=" f"{dato}»?")
                if posicional_visto:
                    raise ErrorTexto(numero, col, f"«{dato}» sobra: `{verbo}` recibe un solo valor "
                                                  "posicional")
                posicional_visto = True
                params[posicional] = _guardar(valor(spec["tipos"].get(posicional, "str"), dato))
        if spec and spec["valor"] and "name" not in params:
            params["name"] = nid
        g.nodes[nid] = {"verb": verbo, "params": params, "asset": None, "x": 0.0, "y": 0.0,
                        "debug": flags["debug"], "bypass": flags["bypass"]}
    for numero, col, origen, pin, destino, pin_destino in pendientes:
        if origen not in g.nodes:
            cerca = difflib.get_close_matches(origen, list(g.nodes), n=1)
            raise ErrorTexto(numero, col, f"«@{origen}» no es un nodo de este grafo"
                                          + (f" — ¿quisiste decir «{cerca[0]}»?" if cerca else ".")
                                          + " Los nombres son lo que está a la izquierda del «=».")
        g.edges.append((origen, pin, destino, pin_destino))
    return g


def lineas(texto: str) -> dict[str, int]:
    """nombre de nodo → línea donde se declara. Para ubicar un diagnóstico del Compile."""
    salida = {}
    for numero, linea in enumerate(texto.splitlines(), start=1):
        m = _CABECERA.match(linea)
        if m and m.group(1) not in salida:
            salida[m.group(1)] = numero
    return salida


def _tokens(linea: str, i: int, numero: int):
    """(columna, clase, dato): palabra/cadena/tupla, ref, param, bandera."""
    n = len(linea)
    while i < n:
        if linea[i].isspace():
            i += 1
            continue
        col = i + 1
        c = linea[i]
        if c == "#":
            raise ErrorTexto(numero, col, "no hay comentarios: el canvas no tiene dónde guardarlos. "
                                          "Si «#…» es un color, va entre comillas: \"#76502F\"")
        if c == "@":
            j, ref = _leer_ref(linea, i + 1, numero, col)
            yield col, "ref", ref
            i = j
        elif c == "+":
            m = re.compile(r"\+(\w+)").match(linea, i)
            if not m:
                raise ErrorTexto(numero, col, "«+» sin bandera — hay +bypass y +debug")
            yield col, "bandera", m.group(1)
            i = m.end()
        else:
            m = re.compile(r"(\w+)=(?!=)").match(linea, i)
            if m:
                clave = unicodedata.normalize("NFC", m.group(1))
                j = m.end()
                if j < n and linea[j] == "@":
                    j, ref = _leer_ref(linea, j + 1, numero, j + 1)
                    yield col, "param", (clave, ("ref", ref))
                else:
                    j, clase, dato = _leer_valor(linea, j, numero)
                    yield col, "param", (clave, (clase, dato))
                i = j
            else:
                j, clase, dato = _leer_valor(linea, i, numero)
                yield col, clase, dato
                i = j


def _leer_ref(linea: str, i: int, numero: int, col: int):
    m = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?:\.(\w+))?").match(linea, i)
    if not m:
        raise ErrorTexto(numero, col, "después de «@» va el nombre de un nodo: «@smooth» o «@deco.eje_z»")
    pin = unicodedata.normalize("NFC", m.group(2)) if m.group(2) else PIN_OUT
    return m.end(), (m.group(1), pin)


def _leer_valor(linea: str, i: int, numero: int):
    n = len(linea)
    if i >= n or linea[i].isspace():
        raise ErrorTexto(numero, i + 1, "falta el valor después del «=»")
    if linea[i] == '"':
        try:
            dato, fin = json.JSONDecoder().raw_decode(linea, i)
        except ValueError:
            raise ErrorTexto(numero, i + 1, "texto entre comillas sin cerrar") from None
        return fin, "cadena", dato
    if linea[i] == "(":
        fin = linea.find(")", i)
        if fin == -1:
            raise ErrorTexto(numero, i + 1, f"la tupla «{linea[i:].split()[0]}» no cierra — falta «)». "
                                            "Un vector es (x, y, z)")
        cuerpo = linea[i:fin + 1]
        if _tupla(cuerpo) is None:
            raise ErrorTexto(numero, i + 1, f"«{cuerpo}» no es una tupla de números")
        return fin + 1, "tupla", cuerpo
    j = i
    while j < n and not linea[j].isspace():
        j += 1
    return j, "palabra", linea[i:j]


def ayuda(verbo: str, vocab: dict | None = None) -> str:
    """La firma de un verbo escrita en la misma sintaxis: lo que un LLM necesita para usarlo."""
    vocab = vocabulario() if vocab is None else vocab
    spec = vocab.get(verbo)
    if spec is None:
        return f"{verbo}: verbo desconocido"
    from .registro import REGISTRO
    info = REGISTRO.get(verbo, {})
    entrada = f" @{info['in_name']}" if info.get("in_name") and not info.get("source") else ""
    if spec["variadico"]:
        entrada += "…"
    salida = info.get("out_name", "")
    pos = f" [{spec['posicional']}]" if spec["posicional"] else ""
    params = " ".join(f"{k}={escribir(valor(spec['tipos'].get(k, 'str'), d))}"
                      for k, d in spec["params"].items() if k != spec["posicional"])
    doc = info.get("doc", "")
    return f"{verbo}{pos}{entrada}{' → ' + salida if salida else ''} · {params}" + (f" — {doc}" if doc else "")


# ---------------------------------------------------------------- unión con el canvas

#: Paso horizontal entre un nodo y el que alimenta: el de los ejemplos de Resources/Examples.
PASO_X = 320.0
PASO_Y = 200.0


def es_documento(texto_: str) -> bool:
    """¿Es el texto de un grafo (alguna línea «nombre = …») y no un comando de consola?"""
    return any(_CABECERA.match(linea) for linea in texto_.splitlines() if linea.strip())


def aplicar(texto_: str, base_json: str = "", vocab: dict | None = None) -> dict:
    """El JSON del canvas que resulta de leer `texto_`, conservando el layout de `base_json`.

    Lo que el texto no dice lo pone el canvas: un nodo que sobrevive conserva `x`, `y` y `compact`
    por NOMBRE; uno nuevo va a la derecha de lo que lo alimenta, o donde lo ponga `layout.auto`. Los
    reroutes se guardan por índice de arista (SJamGraphEditor, `BuildJson`), así que se reindexan
    por identidad del cable. Los comentarios pasan tal cual. Levanta `ErrorTexto`.
    """
    vocab = vocabulario() if vocab is None else vocab
    g = leer(texto_, vocab)
    base = json.loads(base_json) if base_json and base_json.strip() else {}
    viejos = base.get("nodes", {}) or {}

    try:
        orden = g.topo_order()
    except ValueError:
        orden = list(g.nodes)
    fuentes: dict[str, list[str]] = {}
    for a, _ap, b, _bp in g.edges:
        fuentes.setdefault(b, []).append(a)
    pos: dict[str, tuple[float, float]] = {
        nid: (float(viejos[nid].get("x", 0.0)), float(viejos[nid].get("y", 0.0)))
        for nid in g.nodes if nid in viejos}
    if len(pos) < len(g.nodes):
        from .layout import auto
        auto_pos = auto([{"id": nid, "x": 0.0, "y": 0.0} for nid in g.nodes],
                        [(a, b) for a, _ap, b, _bp in g.edges])
        for nid in orden:
            if nid in pos:
                continue
            con_pos = [f for f in fuentes.get(nid, []) if f in pos]
            x, y = ((pos[con_pos[0]][0] + PASO_X, pos[con_pos[0]][1]) if con_pos
                    else auto_pos.get(nid, (0.0, 0.0)))
            # Nunca encima de otro: un nodo tapado es un nodo que el humano no ve aparecer.
            ocupados = set(pos.values())
            while (x, y) in ocupados:
                y += PASO_Y
            pos[nid] = (x, y)

    nodos = {}
    for nid, n in g.nodes.items():
        spec = vocab.get(n["verb"])
        params = ({k: _guardar(valor(spec["tipos"].get(k, "str"), d))
                   for k, d in spec["params"].items()} if spec else {})
        # El literal que un cable tapa no está en el texto (el cable manda), pero sigue siendo del
        # humano: si mañana desconecta, tiene que volver lo que había escrito y no el default.
        # Observación de Codex al contrastar el diseño (investigacion/codex.md).
        cableados = {bp for _a, _ap, b, bp in g.edges if b == nid and bp != PIN_IN}
        params.update({k: v for k, v in (viejos.get(nid, {}).get("params") or {}).items()
                       if k in cableados})
        params.update(n["params"])
        nodo = {"verb": n["verb"], "params": params, "asset": None,
                "x": pos[nid][0], "y": pos[nid][1]}
        for bandera in ("debug", "bypass"):
            if n.get(bandera):
                nodo[bandera] = True
        if viejos.get(nid, {}).get("compact"):
            nodo["compact"] = True
        nodos[nid] = nodo

    aristas = [list(e) for e in g.edges]
    salida = {"schema_version": 1, "nodes": nodos, "edges": aristas}
    viejas = [tuple(e) for e in base.get("edges", []) if len(e) == 4]
    reroutes = {}
    for indice, puntos in (base.get("reroutes") or {}).items():
        try:
            cable = viejas[int(indice)]
        except (ValueError, IndexError):
            continue
        if list(cable) in aristas:
            reroutes[str(aristas.index(list(cable)))] = puntos
    if reroutes:
        salida["reroutes"] = reroutes
    if base.get("comments"):
        salida["comments"] = base["comments"]
    return salida


def nombre_nuevo(verbo: str, usados) -> str:
    """El nombre con el que nace un nodo en el canvas: el verbo, y `_2`, `_3`… si ya existe.

    Es lo que el texto escribe a la izquierda del «=», así que tiene que ser un nombre escribible y
    no renombrar nunca a nadie: un nodo nuevo no mueve a los viejos. Una instancia `fn:…` se llama
    `funcion`, porque su verbo lleva un id opaco.
    """
    usados = set(usados)
    base = "funcion" if str(verbo).startswith("fn:") else re.sub(r"\W", "_", str(verbo), flags=re.A)
    if not base or not IDENT.match(base):
        base = "nodo_" + base.lstrip("_") if base else "nodo"
        base = re.sub(r"\W", "_", base, flags=re.A)
    if base not in usados:
        return base
    i = 2
    while f"{base}_{i}" in usados:
        i += 1
    return f"{base}_{i}"
