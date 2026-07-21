"""G2 — el TEXTO del DSL de grafo: parser + `conforms()` + GBNF (de los MISMOS fragmentos).

La sintaxis es la de la SPEC (vault: SPEC-JamSpace-Grafo-v1.0 §2): UNA declaracion por linea,
GBNF-friendly, para que el LLM escriba mapas enteros como grafos libres y el oraculo disponga.
REGLA ANTI-DRIFT (como shape_dsl): la GBNF se CONSTRUYE de los mismos fragmentos/regex del
parser — no hay dos fuentes de sintaxis que puedan divergir.

```
# comentario
@space hospital
@seed 7
node <id> [<type>] [start] [goal] [key <k>] [switch <f>] [hazard [<f>]]
          [dims <W>x<D>] [floor <n>] [tags <t1>,<t2>...]
          [power source|load] [drain <rec> <n>] [refill <rec> <n>]
          [task <tid> [dep <d1> dep <d2> ...]]
@resource <nombre> <start> [<lo> <hi>]
subgraph <id> {
  node <id> [<type>] [port] ...
  edge <a> <b> ...
}
node <id> [<type>] @expand <subgraph_id>
edge <a> <b> [open|stair|portal|shortcut|cable] [door <k>] [gate <f>|powered:<load_id>]
```

Reglas semanticas del parser (errores con NUMERO DE LINEA, como shape_dsl):
- ids `[a-z_][a-z0-9_]*`; nodo duplicado = error; `edge` solo entre nodos YA declarados
  (referencias hacia atras — mismo principio que el Shape DSL).
- `edge` duplicada (mismo par no ordenado) = error; self-loop = error.
- Tokens keyword-led en cualquier orden tras el tipo; `hazard` toma flag OPCIONAL (el token
  siguiente es flag salvo que sea una keyword). `dims` = floats `WxD`. `tags` = lista con comas
  sin espacios. El kind default de edge = `open`; `door`/`gate` son modificadores combinables
  con cualquier kind (un `shortcut gate f` es el atajo gateado de la SPEC).
- `subgraph <id> { ... }` declara nodos/aristas internas; `port` en nodes junta puertos en orden
  de declaracion. `@expand` solo vale top-level y refiere subgraphs ya declarados; si hay menos o
  mas puertos que aristas externas, el aplanador usa round-robin sobre los puertos.
- El `type` del nodo es ADVISORY contra el vocabulario (off-vocabulary = señal, no error —
  la disciplina de `validate_vocabulary`); el parser acepta cualquier identificador.
- `@space` opcional (programa de espacio); `@seed` opcional (default 0).
"""

from __future__ import annotations

import re

from src.mazes.spacegraph import GraphEdge, GraphNode, SpaceGraph, Subgraph

_ID_START_CHARS = "a-z_"
_ID_CONT_CHARS = "a-z0-9_"
_DIGIT_CHARS = "0-9"

_ID_TEXT = rf"[{_ID_START_CHARS}][{_ID_CONT_CHARS}]*"
_INT_TEXT = rf"-?[{_DIGIT_CHARS}]+"
_NUM_TEXT = rf"(?:[{_DIGIT_CHARS}]+(?:\.[{_DIGIT_CHARS}]+)?|\.[{_DIGIT_CHARS}]+)"
_DIMS_TEXT = rf"{_NUM_TEXT}x{_NUM_TEXT}"
_TAGS_TEXT = rf"{_ID_TEXT}(?:,{_ID_TEXT})*"

_ID_RE = re.compile(rf"^{_ID_TEXT}$")
_INT_RE = re.compile(rf"^{_INT_TEXT}$")
_DIMS_RE = re.compile(rf"^(?P<w>{_NUM_TEXT})x(?P<d>{_NUM_TEXT})$")
_TAGS_RE = re.compile(rf"^{_TAGS_TEXT}$")

_NODE_KEYWORDS = (
    "start", "goal", "key", "switch", "hazard", "dims", "floor", "tags",
    "power", "drain", "refill", "task", "port", "@expand",
)
_NODE_FLAG_KEYWORDS = ("start", "goal")
_NODE_SUBGRAPH_FLAG_KEYWORDS = ("port",)
_POWER_TOKENS = ("source", "load")
_EDGE_KIND_TOKENS = ("open", "stair", "portal", "shortcut", "cable")
_EDGE_MODIFIER_TOKENS = ("door", "gate")
_EDGE_KEYWORDS = _EDGE_KIND_TOKENS + _EDGE_MODIFIER_TOKENS


def parse_space_graph(text: str) -> SpaceGraph:
    """Texto del DSL → `SpaceGraph`.

    Lanza `ValueError` con numero de linea ante sintaxis malformada, duplicados, referencias
    adelantadas/rotas, self-loops, dims/floor malformados o start/goal repetidos.
    """
    graph = SpaceGraph()
    seen_edges: set[tuple[tuple[str, str], str]] = set()
    start_node: str | None = None
    goal_node: str | None = None
    saw_space = False
    saw_seed = False
    expand_lines: dict[str, int] = {}

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line_no = i + 1
        raw_line = lines[i]
        i += 1
        line = _strip_comment(raw_line).strip()
        if not line:
            continue

        tokens = line.split()
        head = tokens[0]
        if head == "subgraph":
            subgraph, i = _parse_subgraph_block(lines, i, line_no, tokens)
            if subgraph.id in graph.subgraphs:
                _raise_line(line_no, f"subgraph duplicado: {subgraph.id!r}")
            graph.subgraphs[subgraph.id] = subgraph
            continue
        if head == "@space":
            if saw_space:
                _raise_line(line_no, "directiva @space repetida")
            graph.space = _parse_space(tokens, line_no)
            saw_space = True
            continue
        if head == "@seed":
            if saw_seed:
                _raise_line(line_no, "directiva @seed repetida")
            graph.seed = _parse_seed(tokens, line_no)
            saw_seed = True
            continue
        if head == "@resource":
            name, budget = _parse_resource(tokens, line_no)
            if name in graph.resources:
                _raise_line(line_no, f"resource repetido: {name!r}")
            graph.resources[name] = budget
            continue
        if head.startswith("@"):
            _raise_line(line_no, f"directiva desconocida: {head!r}")
        if head == "node":
            node, is_port = _parse_node_line(
                tokens,
                line_no,
                allow_expand=True,
                known_subgraphs=graph.subgraphs,
            )
            if is_port:
                _raise_line(line_no, "port solo es valido dentro de subgraph")
            if node.id in graph.nodes:
                _raise_line(line_no, f"nodo duplicado: {node.id!r}")
            if node.start:
                if start_node is not None:
                    _raise_line(line_no, f"start en mas de un nodo: {start_node!r} y {node.id!r}")
                start_node = node.id
            if node.goal:
                if goal_node is not None:
                    _raise_line(line_no, f"goal en mas de un nodo: {goal_node!r} y {node.id!r}")
                goal_node = node.id
            graph.nodes[node.id] = node
            if node.expand is not None:
                expand_lines[node.id] = line_no
            continue
        if head == "edge":
            edge = _parse_edge_line(tokens, line_no, graph.nodes)
            edge_key = _edge_key(edge)
            if edge_key in seen_edges:
                pair = edge_key[0]
                _raise_line(line_no, f"edge duplicada: {pair[0]}-{pair[1]}")
            seen_edges.add(edge_key)
            graph.edges.append(edge)
            continue

        _raise_line(line_no, f"declaracion desconocida: {head!r}")

    _validate_expansions(graph, expand_lines)
    return graph


def _parse_subgraph_block(lines: list[str], index: int, line_no: int,
                          tokens: list[str]) -> tuple[Subgraph, int]:
    if len(tokens) != 3 or tokens[2] != "{":
        _raise_line(line_no, "subgraph malformado: esperado 'subgraph <id> {'")
    subgraph_id = _parse_identifier(tokens[1], line_no, "subgraph")
    subgraph = Subgraph(id=subgraph_id)
    seen_edges: set[tuple[tuple[str, str], str]] = set()

    i = index
    while i < len(lines):
        inner_line_no = i + 1
        raw_line = lines[i]
        i += 1
        line = _strip_comment(raw_line).strip()
        if not line:
            continue
        inner_tokens = line.split()
        head = inner_tokens[0]
        if head == "}":
            if len(inner_tokens) != 1:
                _raise_line(inner_line_no, "cierre de subgraph malformado")
            return subgraph, i
        if head == "subgraph":
            _raise_line(inner_line_no, "subgraph anidado no soportado en V1")
        if head.startswith("@"):
            _raise_line(inner_line_no, f"directiva no valida dentro de subgraph: {head!r}")
        if head == "node":
            node, is_port = _parse_node_line(inner_tokens, inner_line_no, allow_port=True)
            if node.start or node.goal:
                _raise_line(inner_line_no, "subgraph no puede declarar start/goal")
            if node.id in subgraph.nodes:
                _raise_line(inner_line_no, f"nodo duplicado en subgraph {subgraph_id!r}: {node.id!r}")
            subgraph.nodes[node.id] = node
            if is_port:
                subgraph.ports.append(node.id)
            continue
        if head == "edge":
            edge = _parse_edge_line(inner_tokens, inner_line_no, subgraph.nodes)
            edge_key = _edge_key(edge)
            if edge_key in seen_edges:
                pair = edge_key[0]
                _raise_line(inner_line_no, f"edge duplicada: {pair[0]}-{pair[1]}")
            seen_edges.add(edge_key)
            subgraph.edges.append(edge)
            continue
        _raise_line(inner_line_no, f"declaracion desconocida dentro de subgraph: {head!r}")

    _raise_line(line_no, f"subgraph {subgraph_id!r} sin cierre '}}'")


def _edge_key(edge: GraphEdge) -> tuple[tuple[str, str], str]:
    pair = tuple(sorted((edge.a, edge.b)))
    aspect = "cable" if edge.kind == "cable" else "physical"
    return pair, aspect


def _validate_expansions(graph: SpaceGraph, expand_lines: dict[str, int]) -> None:
    if not expand_lines:
        return
    degree = {node_id: 0 for node_id in graph.nodes}
    for edge in graph.edges:
        if edge.a in degree:
            degree[edge.a] += 1
        if edge.b in degree:
            degree[edge.b] += 1
    for node_id, line_no in expand_lines.items():
        expand = graph.nodes[node_id].expand
        if expand is None:
            continue
        subgraph = graph.subgraphs.get(expand)
        if subgraph is None:
            _raise_line(line_no, f"@expand refiere subgraph no declarado: {expand!r}")
        # Si hay menos/más puertos que aristas externas, flatten_hierarchy aplica round-robin.
        if degree[node_id] > 0 and not subgraph.ports:
            _raise_line(line_no, f"@expand {expand!r} no tiene ports para {degree[node_id]} aristas")


def conforms(text: str) -> bool:
    """¿El texto es un grafo valido? Reusa el parser como unica autoridad anti-drift."""
    try:
        parse_space_graph(text)
    except ValueError:
        return False
    return True


def build_gbnf() -> str:
    """Construye la gramatica GBNF desde los mismos fragmentos y menus que usa el parser."""
    edge_kind = _gbnf_choice(_EDGE_KIND_TOKENS)
    node_flag = _gbnf_choice(_NODE_FLAG_KEYWORDS)
    subgraph_node_flag = _gbnf_choice(_NODE_SUBGRAPH_FLAG_KEYWORDS)
    power_kind = _gbnf_choice(_POWER_TOKENS)
    return f"""# SpaceGraph DSL -- gramatica GBNF de G2.
# Sintaxis local solamente: referencias hacia atras, duplicados y start/goal unicos se validan
# en parse_space_graph/conforms.

root        ::= line*
line        ::= blank | comment | space_decl | seed_decl | resource_decl | subgraph_block | node_line | edge_line
space_decl  ::= "@space" sp identifier eol
seed_decl   ::= "@seed" sp integer eol
resource_decl ::= "@resource" sp identifier sp integer (sp integer sp integer)? eol
subgraph_block ::= "subgraph" sp identifier sp "{{" eol subgraph_line* "}}" eol
subgraph_line ::= blank | comment | subgraph_node_line | subgraph_edge_line

node_line   ::= "node" sp identifier node_type? node_token* eol
subgraph_node_line ::= "node" sp identifier node_type? subgraph_node_token* eol
node_type   ::= sp identifier
node_token  ::= sp node_flag | sp key_decl | sp switch_decl | sp hazard_decl | sp dims_decl | sp floor_decl | sp tags_decl | sp power_decl | sp drain_decl | sp refill_decl | sp task_decl | sp expand_decl
subgraph_node_token ::= sp subgraph_node_flag | sp key_decl | sp switch_decl | sp hazard_decl | sp dims_decl | sp floor_decl | sp tags_decl | sp power_decl | sp drain_decl | sp refill_decl | sp task_decl
node_flag   ::= {node_flag}
subgraph_node_flag ::= {subgraph_node_flag}
key_decl    ::= "key" sp identifier
switch_decl ::= "switch" sp identifier
hazard_decl ::= "hazard" (sp identifier)?
dims_decl   ::= "dims" sp dims
floor_decl  ::= "floor" sp integer
tags_decl   ::= "tags" sp tags_value
power_decl  ::= "power" sp power_kind
power_kind  ::= {power_kind}
drain_decl  ::= "drain" sp identifier sp integer
refill_decl ::= "refill" sp identifier sp integer
task_decl   ::= "task" sp identifier task_dep*
task_dep    ::= sp "dep" sp identifier
expand_decl ::= "@expand" sp identifier

edge_line   ::= "edge" sp identifier sp identifier edge_token* eol
subgraph_edge_line ::= edge_line
edge_token  ::= sp edge_kind | sp door_decl | sp gate_decl
edge_kind   ::= {edge_kind}
door_decl   ::= "door" sp identifier
gate_decl   ::= "gate" sp gate_value
gate_value  ::= identifier | powered_gate
powered_gate ::= "powered:" identifier

dims        ::= number "x" number
tags_value  ::= identifier ("," identifier)*
identifier  ::= [{_ID_START_CHARS}] [{_ID_CONT_CHARS}]*
integer     ::= "-"? [{_DIGIT_CHARS}]+
number      ::= [{_DIGIT_CHARS}]+ ("." [{_DIGIT_CHARS}]+)? | "." [{_DIGIT_CHARS}]+
sp          ::= [ \\t]+
eol         ::= [ \\t]* ("#" [^\\n]*)? nl
blank       ::= [ \\t]* nl
comment     ::= [ \\t]* "#" [^\\n]* nl
nl          ::= "\\n"
"""


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0].rstrip()


def _parse_space(tokens: list[str], line_no: int) -> str:
    if len(tokens) != 2:
        _raise_line(line_no, "directiva @space malformada")
    return _parse_identifier(tokens[1], line_no, "@space")


def _parse_seed(tokens: list[str], line_no: int) -> int:
    if len(tokens) != 2:
        _raise_line(line_no, "directiva @seed malformada")
    return _parse_int(tokens[1], line_no, "@seed")


def _parse_resource(tokens: list[str], line_no: int) -> tuple[str, tuple[int, int, int]]:
    if len(tokens) not in (3, 5):
        _raise_line(line_no, "directiva @resource malformada")
    name = _parse_identifier(tokens[1], line_no, "@resource")
    start = _parse_int(tokens[2], line_no, "@resource start")
    lo = _parse_int(tokens[3], line_no, "@resource lo") if len(tokens) == 5 else 0
    hi = _parse_int(tokens[4], line_no, "@resource hi") if len(tokens) == 5 else start
    if hi < lo:
        _raise_line(line_no, f"resource {name!r} malformado: hi < lo")
    return name, (start, lo, hi)


def _parse_node_line(tokens: list[str], line_no: int, *, allow_port: bool = False,
                     allow_expand: bool = False,
                     known_subgraphs: dict[str, Subgraph] | None = None) -> tuple[GraphNode, bool]:
    if len(tokens) < 2:
        _raise_line(line_no, "node malformado: falta id")
    node_id = _parse_identifier(tokens[1], line_no, "id de nodo")

    node_type: str | None = None
    offset = 2
    if offset < len(tokens) and tokens[offset] not in _NODE_KEYWORDS:
        node_type = _parse_identifier(tokens[offset], line_no, "type")
        offset += 1

    start = False
    goal = False
    key: str | None = None
    switch: str | None = None
    hazard: str | None = None
    dims: tuple[float, float] | None = None
    floor = 0
    tags: tuple[str, ...] = ()
    power: str | None = None
    drain: tuple[str, int] | None = None
    refill: tuple[str, int] | None = None
    task: tuple[str, tuple[str, ...]] | None = None
    expand: str | None = None
    is_port = False
    seen_keywords: set[str] = set()

    i = offset
    while i < len(tokens):
        token = tokens[i]
        if token == "port":
            if not allow_port:
                _raise_line(line_no, "port solo es valido dentro de subgraph")
            _mark_keyword(seen_keywords, token, line_no)
            is_port = True
            i += 1
            continue
        if token == "@expand":
            if not allow_expand:
                _raise_line(line_no, "@expand solo es valido en el grafo top-level")
            _mark_keyword(seen_keywords, token, line_no)
            expand = _parse_identifier(
                _require_value(tokens, i + 1, line_no, token),
                line_no,
                "@expand",
            )
            if known_subgraphs is not None and expand not in known_subgraphs:
                _raise_line(line_no, f"@expand refiere subgraph no declarado: {expand!r}")
            i += 2
            continue
        if token == "start":
            _mark_keyword(seen_keywords, token, line_no)
            start = True
            i += 1
            continue
        if token == "goal":
            _mark_keyword(seen_keywords, token, line_no)
            goal = True
            i += 1
            continue
        if token == "key":
            _mark_keyword(seen_keywords, token, line_no)
            key = _parse_identifier(_require_value(tokens, i + 1, line_no, token), line_no, "key")
            i += 2
            continue
        if token == "switch":
            _mark_keyword(seen_keywords, token, line_no)
            switch = _parse_identifier(_require_value(tokens, i + 1, line_no, token), line_no, "switch")
            i += 2
            continue
        if token == "hazard":
            _mark_keyword(seen_keywords, token, line_no)
            if i + 1 < len(tokens) and tokens[i + 1] not in _NODE_KEYWORDS:
                hazard = _parse_identifier(tokens[i + 1], line_no, "hazard")
                i += 2
            else:
                hazard = ""
                i += 1
            continue
        if token == "dims":
            _mark_keyword(seen_keywords, token, line_no)
            dims = _parse_dims(_require_value(tokens, i + 1, line_no, token), line_no)
            i += 2
            continue
        if token == "floor":
            _mark_keyword(seen_keywords, token, line_no)
            floor = _parse_int(_require_value(tokens, i + 1, line_no, token), line_no, "floor")
            i += 2
            continue
        if token == "tags":
            _mark_keyword(seen_keywords, token, line_no)
            tags = _parse_tags(_require_value(tokens, i + 1, line_no, token), line_no)
            i += 2
            continue
        if token == "power":
            _mark_keyword(seen_keywords, token, line_no)
            power = _parse_power(_require_value(tokens, i + 1, line_no, token), line_no)
            i += 2
            continue
        if token == "drain":
            _mark_keyword(seen_keywords, token, line_no)
            drain = _parse_resource_delta(tokens, i + 1, line_no, token)
            i += 3
            continue
        if token == "refill":
            _mark_keyword(seen_keywords, token, line_no)
            refill = _parse_resource_delta(tokens, i + 1, line_no, token)
            i += 3
            continue
        if token == "task":
            _mark_keyword(seen_keywords, token, line_no)
            task_id = _parse_identifier(_require_value(tokens, i + 1, line_no, token), line_no, "task")
            deps: list[str] = []
            i += 2
            while i < len(tokens) and tokens[i] == "dep":
                deps.append(_parse_identifier(_require_value(tokens, i + 1, line_no, "dep"),
                                              line_no, "dep"))
                i += 2
            task = (task_id, tuple(deps))
            continue
        if token == "dep":
            _raise_line(line_no, "dep solo es valido inmediatamente despues de task")

        expected = ", ".join(_NODE_KEYWORDS)
        _raise_line(line_no, f"token de node desconocido {token!r}; esperados: {expected}")

    return GraphNode(
        id=node_id,
        type=node_type,
        dims=dims,
        key=key,
        switch=switch,
        hazard=hazard,
        start=start,
        goal=goal,
        floor=floor,
        tags=tags,
        power=power,
        drain=drain,
        refill=refill,
        task=task,
        expand=expand,
    ), is_port


def _parse_edge_line(tokens: list[str], line_no: int, nodes: dict[str, GraphNode]) -> GraphEdge:
    if len(tokens) < 3:
        _raise_line(line_no, "edge malformada: faltan endpoints")
    a = _parse_identifier(tokens[1], line_no, "id de edge")
    b = _parse_identifier(tokens[2], line_no, "id de edge")
    if a == b:
        _raise_line(line_no, f"self-loop: {a}")
    for endpoint in (a, b):
        if endpoint not in nodes:
            _raise_line(line_no, f"edge con nodo no declarado antes: {endpoint!r}")

    kind = "open"
    door_id: str | None = None
    gate_flag: str | None = None
    seen_keywords: set[str] = set()
    saw_kind = False

    i = 3
    while i < len(tokens):
        token = tokens[i]
        if token in _EDGE_KIND_TOKENS:
            if saw_kind:
                _raise_line(line_no, f"kind de edge repetido: {token}")
            kind = token
            saw_kind = True
            i += 1
            continue
        if token == "door":
            _mark_keyword(seen_keywords, token, line_no)
            door_id = _parse_identifier(_require_value(tokens, i + 1, line_no, token), line_no, "door")
            i += 2
            continue
        if token == "gate":
            _mark_keyword(seen_keywords, token, line_no)
            gate_flag = _parse_gate_value(_require_value(tokens, i + 1, line_no, token), line_no)
            i += 2
            continue

        expected = ", ".join(_EDGE_KEYWORDS)
        _raise_line(line_no, f"token de edge desconocido {token!r}; esperados: {expected}")

    return GraphEdge(a=a, b=b, kind=kind, door_id=door_id, gate_flag=gate_flag)


def _parse_identifier(text: str, line_no: int, label: str) -> str:
    if not _ID_RE.match(text):
        _raise_line(line_no, f"{label} malformado: {text!r}")
    return text


def _parse_int(text: str, line_no: int, label: str) -> int:
    if not _INT_RE.match(text):
        _raise_line(line_no, f"{label} malformado: {text!r}")
    return int(text)


def _parse_power(text: str, line_no: int) -> str:
    if text not in _POWER_TOKENS:
        _raise_line(line_no, f"power malformado: {text!r}")
    return text


def _parse_resource_delta(tokens: list[str], index: int, line_no: int,
                          keyword: str) -> tuple[str, int]:
    name = _parse_identifier(_require_value(tokens, index, line_no, keyword), line_no, keyword)
    amount = _parse_int(_require_value(tokens, index + 1, line_no, keyword), line_no, keyword)
    if amount < 0:
        _raise_line(line_no, f"{keyword} malformado: monto negativo")
    return name, amount


def _parse_gate_value(text: str, line_no: int) -> str:
    if text.startswith("powered:"):
        load_id = text.removeprefix("powered:")
        _parse_identifier(load_id, line_no, "gate powered")
        return text
    return _parse_identifier(text, line_no, "gate")


def _parse_dims(text: str, line_no: int) -> tuple[float, float]:
    match = _DIMS_RE.match(text)
    if not match:
        _raise_line(line_no, f"dims malformadas: {text!r}")
    return float(match["w"]), float(match["d"])


def _parse_tags(text: str, line_no: int) -> tuple[str, ...]:
    if not _TAGS_RE.match(text):
        _raise_line(line_no, f"tags malformados: {text!r}")
    return tuple(text.split(","))


def _mark_keyword(seen: set[str], keyword: str, line_no: int) -> None:
    if keyword in seen:
        _raise_line(line_no, f"keyword repetida: {keyword}")
    seen.add(keyword)


def _require_value(tokens: list[str], index: int, line_no: int, keyword: str) -> str:
    if index >= len(tokens):
        _raise_line(line_no, f"falta valor para {keyword!r}")
    return tokens[index]


def _gbnf_choice(values: tuple[str, ...]) -> str:
    return " | ".join(f'"{value}"' for value in values)


def _raise_line(line_no: int, message: str) -> None:
    raise ValueError(f"línea {line_no}: {message}")


SPACEGRAPH_GBNF = build_gbnf()
