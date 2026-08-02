"""JamGraph — el sustrato tipo Grasshopper: un grafo de nodos donde CADA NODO es un comando de Jam
(un verbo de `jam.tools.REGISTRO`) y las aristas dan el orden de ejecución (dataflow).

Es la MISMA sustancia que el CLI/Dash Bar (verbos + params + oráculo), en otra vista: en vez de
escribir `scatter count=8` tenés un nodo «scatter» con un pin `count=8`. Correr el grafo = orden
topológico → ejecutar cada nodo con su tool → el oráculo verifica cada uno. El editor visual (Slate)
es una cara de esto; este archivo es la lógica, testeable headless.

Formato JSON (lo que intercambia con el editor en C++):
    {"nodes": {"n1": {"verb":"create_spline","params":{},"asset":null,"x":40,"y":60}, ...},
     "edges": [["n1","n2"]]}
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .math_core import DEFAULTS as _VALUE_DEFAULTS
from .math_core import VALOR_KINDS


#: pin de entrada «gordo» (orden de ejecución + el asset que viaja por el cable). Cualquier OTRO pin
#: de entrada es un PARÁMETRO del verbo (x, anchor, count…) o el pin especial `asset`.
PIN_IN = "in"
PIN_OUT = "out"
PIN_ASSET = "asset"

#: nodos de VALOR (de `jam.flow`): no ejecutan un verbo, aportan un valor con nombre que se puede
#: cablear a cualquier pin de parámetro. number/math = número · text = texto (anclas, nombres…).
# Tipo de pin que acepta cualquier salida (el ayudante de Debug).
COMODIN = "*"

#: Salida de cada nodo del ÚLTIMO Run, para que el inspector pueda mirarla después sin recalcular.
#: Es el equivalente del Geometry Spreadsheet de Houdini: se selecciona un nodo y se ven sus datos.
#: Se vacía al empezar cada Run, así que nunca muestra algo de una corrida anterior.
_ULTIMA_CORRIDA: dict[str, object] = {}


def ultima_corrida() -> dict[str, object]:
    """Salidas del último Run, por node id. Vacío si todavía no se corrió nada."""
    return dict(_ULTIMA_CORRIDA)


class JamGraph:
    def __init__(self):
        self.nodes: dict[str, dict] = {}          # id → {verb, params, asset, x, y}
        # (origen, origen_pin, destino, destino_pin)
        self.edges: list[tuple[str, str, str, str]] = []

    # ---- construcción ----

    def add(self, verb: str, params: dict | None = None, asset: str | None = None,
            nid: str | None = None, x: float = 0.0, y: float = 0.0) -> str:
        nid = nid or f"n{len(self.nodes) + 1}"
        self.nodes[nid] = {"verb": verb, "params": dict(params or {}), "asset": asset,
                           "x": float(x), "y": float(y)}
        return nid

    def connect(self, origen: str, destino: str, destino_pin: str = PIN_IN,
                origen_pin: str = PIN_OUT) -> None:
        """Conecta `origen.origen_pin` → `destino.destino_pin`. Por defecto out→in (el cable «gordo»,
        por el que viaja el asset). Pasá `destino_pin="x"` (o `"asset"`, `"anchor"`…) para cablear un
        PARÁMETRO: el valor del nodo de origen maneja ese parámetro, como en Grasshopper."""
        if origen in self.nodes and destino in self.nodes:
            self.edges.append((origen, origen_pin, destino, destino_pin))

    # ---- orden topológico (Kahn); detecta ciclos ----

    def topo_order(self) -> list[str]:
        indeg = {n: 0 for n in self.nodes}
        adj: dict[str, list[str]] = {n: [] for n in self.nodes}
        for a, _ap, b, _bp in self.edges:
            if a in self.nodes and b in self.nodes:
                adj[a].append(b)
                indeg[b] += 1
        # cola estable: respeta el orden de inserción entre nodos sin dependencia
        cola = [n for n in self.nodes if indeg[n] == 0]
        orden: list[str] = []
        while cola:
            n = cola.pop(0)
            orden.append(n)
            for m in adj[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    cola.append(m)
        if len(orden) != len(self.nodes):
            raise ValueError("el grafo tiene un ciclo (no se puede ordenar)")
        return orden

    # ---- serialización ----

    def to_json(self) -> str:
        return json.dumps({"nodes": self.nodes, "edges": [list(e) for e in self.edges]},
                          ensure_ascii=True)

    # ---- valores: los nodos number/math/text aportan una tabla de variables ----

    def valores(self) -> dict:
        """{ nombre: valor } resuelto por el registro común de Graph y Flow."""
        from .flow import _eval_expr
        from .math_core import resolver
        tabla, _por_nodo, _errores = resolver(
            self.nodes, self.edges, campo_verbo="verb", eval_expr=_eval_expr)
        return tabla

    @classmethod
    def from_json(cls, s: str) -> "JamGraph":
        d = json.loads(s) if s else {}
        g = cls()
        # Un nodo de Flow nombra su operación en `kind`. Se lee como fallback SÓLO para que el
        # diagnóstico diga cuál es la op intrusa en vez de «verbo desconocido: «»» en un grafo mixto.
        g.nodes = {k: {"verb": v.get("verb") or v.get("kind", ""),
                       "params": dict(v.get("params", {})),
                       "asset": v.get("asset"), "x": float(v.get("x", 0.0)), "y": float(v.get("y", 0.0)),
                       # Flag de debug POR NODO, como el display flag de Houdini o la tecla D de
                       # PCG: se prende el nodo que ya está, sin agregar ni cablear nada.
                       "debug": bool(v.get("debug", False))}
                   for k, v in d.get("nodes", {}).items()}
        # aristas: [from, from_pin, to, to_pin] (por pin) o [from, to] (compat: out→in)
        for e in d.get("edges", []):
            if len(e) == 4:
                g.edges.append((e[0], e[1], e[2], e[3]))
            elif len(e) == 2:
                g.edges.append((e[0], PIN_OUT, e[1], PIN_IN))
        return g


# ---- Compile / Preflight puro ----

class GraphValidationError(ValueError):
    """El Graph no cumple su contrato y no debe entrar a Preview ni ejecutar tools."""

    def __init__(self, diagnostics: dict[str, list[str]]):
        self.diagnostics = diagnostics
        detalle = "; ".join(
            f"{nid}: {', '.join(mensajes)}" for nid, mensajes in diagnostics.items()
        )
        super().__init__(detalle or "grafo inválido")


@dataclass
class GraphPlan:
    """Plan inmutable en intención: todo lo que el runner necesita ya fue validado y resuelto."""

    order: list[str]
    params: dict[str, dict]
    input_assets: dict[str, str | None]
    output_assets: dict[str, str | None]
    values: dict[str, object]
    values_by_node: dict[str, object]


def _tipo_default(pin: str, default) -> str:
    if "spline" in pin.lower():
        return "S"
    if isinstance(default, bool):
        return "B"
    if isinstance(default, (int, float)):
        return "N"
    return "T"


def _tipo_salida(verb: str, registro: dict) -> str | None:
    if verb in VALOR_KINDS:
        from .math_core import tipo_salida
        return tipo_salida(verb)
    info = registro.get(verb)
    return info.get("out_name", "A") if info else None


def _tipo_entrada(verb: str, pin: str, registro: dict) -> str | None:
    if verb in VALOR_KINDS:
        if pin == PIN_IN:
            return None
        from .math_core import tipo_param
        return tipo_param(verb, pin)
    info = registro.get(verb)
    if not info:
        return None
    if pin == PIN_IN:
        return info.get("in_name") if not info.get("source") and info.get("aridad", 1) != 0 else None
    if pin == PIN_ASSET:
        # `asset_row`, no `asset_pin`: el primero es «tiene su propio pin en el canvas» y el
        # segundo «consume un asset». `place` consume uno pero lo recibe por su entrada principal,
        # así que un cable a `place.asset` no apunta a ningún pin que exista.
        return "A" if info.get("asset_row") else None
    data_type = info.get("data_params", {}).get(pin)
    if data_type:
        return data_type
    defaults = info.get("params", {})
    return _tipo_default(pin, defaults[pin]) if pin in defaults else None


def _resolver_parametro(valor, default, tabla: dict):
    """Resuelve expresión + tipo sin defaults silenciosos. Devuelve `(valor, error_o_None)`."""
    from .flow import _es_numero, _eval_expr

    resuelto = valor
    if isinstance(valor, str):
        texto = valor.strip()
        if texto.startswith("="):
            resuelto = _eval_expr(texto[1:], tabla)
            if resuelto is None:
                return None, f"expresión sin resolver: «{texto}»"
        elif isinstance(default, (int, float)) and not isinstance(default, bool) \
                and texto and not _es_numero(texto):
            resuelto = _eval_expr(texto, tabla)
            if resuelto is None:
                return None, f"expresión sin resolver: «{texto}»"
    try:
        if isinstance(default, bool):
            if isinstance(resuelto, bool):
                return resuelto, None
            normal = str(resuelto).strip().lower()
            if normal in ("1", "true", "si", "sí", "yes", "on"):
                return True, None
            if normal in ("0", "false", "no", "off"):
                return False, None
            return None, f"booleano inválido: «{resuelto}»"
        if isinstance(default, int):
            return int(float(resuelto)), None
        if isinstance(default, float):
            return float(resuelto), None
        return str(resuelto), None
    except (TypeError, ValueError):
        return None, f"valor inválido: «{resuelto}»"


def _resolver_asset_runtime(nombre: str) -> str | None:
    """Nombre/ObjectPath explícito → ruta canónica existente. Nunca consulta session ni el 1º asset."""
    from . import library

    pedido = str(nombre or "").strip()
    if not pedido:
        return None
    if "/" in pedido or "." in pedido:
        obj = library.cargar_placeable(pedido)
        return obj.get_path_name() if obj is not None else None
    hits = library.buscar(pedido, limit=0)
    exactos = [hit for hit in hits if hit["nombre"].lower() == pedido.lower()]
    return exactos[0]["ruta"] if len(exactos) == 1 else None


def _resolver_pick_runtime() -> str | None:
    from . import library

    seleccion = library.seleccion_ue()
    return seleccion[0]["ruta"] if seleccion else None


def compilar(g: JamGraph, *, registro: dict | None = None, resolver_asset=None,
             resolver_pick=None, transformar_asset=None) -> GraphPlan:
    """Compila el DAG completo sin ejecutar tools ni modificar Unreal.

    Valida nodos, endpoints, pines, tipos, cardinalidad, ciclos, variables, expresiones, params y la
    presencia de assets explícitos. En runtime también comprueba que nombres/rutas y Pick resuelvan.
    """
    if registro is None:
        from . import tools
        registro = tools.REGISTRO
        resolver_asset = resolver_asset or _resolver_asset_runtime
        resolver_pick = resolver_pick or _resolver_pick_runtime
        transformar_asset = transformar_asset or tools.asset_producido
    else:
        resolver_asset = resolver_asset or (lambda nombre: str(nombre).strip() or None)
        resolver_pick = resolver_pick or (lambda: None)
        transformar_asset = transformar_asset or (lambda _verbo, _asset, _params: None)

    diagnosticos: dict[str, list[str]] = {}

    def error(nid: str, mensaje: str) -> None:
        mensajes = diagnosticos.setdefault(nid, [])
        if mensaje not in mensajes:
            mensajes.append(mensaje)

    if not g.nodes:
        error("_graph", "grafo vacío — agregá nodos")

    for nid, nodo in g.nodes.items():
        verb = nodo.get("verb", "")
        if verb not in VALOR_KINDS and verb not in registro:
            error(nid, f"verbo desconocido: «{verb}»")

    valid_edges: list[tuple[str, str, str, str]] = []
    vistos: set[tuple[str, str, str, str]] = set()
    entradas: dict[tuple[str, str], int] = {}
    for origen, origen_pin, destino, destino_pin in g.edges:
        enlace = (origen, origen_pin, destino, destino_pin)
        if enlace in vistos:
            error(destino if destino in g.nodes else "_graph", "conexión duplicada")
            continue
        vistos.add(enlace)
        if origen not in g.nodes:
            error(destino if destino in g.nodes else "_graph", f"origen inexistente: «{origen}»")
            continue
        if destino not in g.nodes:
            error(origen, f"destino inexistente: «{destino}»")
            continue
        if origen == destino:
            error(origen, "un nodo no puede conectarse a sí mismo")
        if origen_pin != PIN_OUT:
            error(origen, f"pin de salida desconocido: «{origen_pin}»")
            continue
        tipo_out = _tipo_salida(g.nodes[origen].get("verb", ""), registro)
        tipo_in = _tipo_entrada(g.nodes[destino].get("verb", ""), destino_pin, registro)
        if tipo_out is None:
            error(origen, "la salida no declara un tipo válido")
            continue
        if tipo_in is None:
            error(destino, f"pin de entrada desconocido o no permitido: «{destino_pin}»")
            continue
        # «*» es un pin COMODÍN: lo usa el ayudante de Debug, que dibuja cualquier cosa que llegue.
        # Sin esto haría falta un nodo de debug por tipo, y había que saber de antemano cuál usar.
        if tipo_in != COMODIN and tipo_out != tipo_in:
            error(origen, f"salida {tipo_out} incompatible con {destino}.{destino_pin} ({tipo_in})")
            error(destino, f"{destino_pin} esperaba {tipo_in}, recibió {tipo_out}")
            continue
        entradas[(destino, destino_pin)] = entradas.get((destino, destino_pin), 0) + 1
        valid_edges.append(enlace)

    for (nid, pin), cantidad in entradas.items():
        info = registro.get(g.nodes[nid].get("verb", ""), {})
        variadico = pin == PIN_IN and info.get("aridad") == -1
        if not variadico and cantidad > 1:
            error(nid, f"el pin «{pin}» admite un solo cable; recibió {cantidad}")

    try:
        orden = g.topo_order()
    except ValueError as exc:
        orden = []
        error("_graph", str(exc))

    # Variables: soportan cables hacia sus params y referencias por nombre en expresiones.
    nombres: dict[str, str] = {}
    for nid, nodo in g.nodes.items():
        if nodo.get("verb") not in VALOR_KINDS:
            continue
        nombre = str(nodo.get("params", {}).get("name") or nid)
        if nombre in nombres:
            error(nombres[nombre], f"nombre de variable duplicado: «{nombre}»")
            error(nid, f"nombre de variable duplicado: «{nombre}»")
        else:
            nombres[nombre] = nid

    param_sources = {(b, bp): a for a, _ap, b, bp in valid_edges if bp != PIN_IN}
    from .flow import _eval_expr
    from .math_core import resolver as resolver_valores
    tabla, valores_por_nodo, errores_valor = resolver_valores(
        g.nodes, valid_edges, campo_verbo="verb", eval_expr=_eval_expr)
    for nid, mensajes in errores_valor.items():
        for mensaje in mensajes:
            error(nid, mensaje)

    params_plan: dict[str, dict] = {}
    for nid, nodo in g.nodes.items():
        verb = nodo.get("verb", "")
        if verb in VALOR_KINDS or verb not in registro:
            continue
        defaults = registro[verb].get("params", {})
        crudos = {k: v for k, v in nodo.get("params", {}).items() if k != PIN_ASSET}
        for desconocido in sorted(set(crudos) - set(defaults)):
            error(nid, f"parámetro desconocido: «{desconocido}»")
        efectivos: dict = {}
        data_params = registro[verb].get("data_params", {})
        # Un pin de datos puede ser OPCIONAL: sin cable, el verbo corre sin ese dato. Es el caso del
        # perfil de `branch_from_frames`, donde no conectar nada significa «sin modulación».
        opcionales = set(registro[verb].get("optional_data_params", ()))
        for pin, default in defaults.items():
            origen = param_sources.get((nid, pin))
            if pin in data_params:
                if origen is None and pin not in opcionales:
                    error(nid, f"requiere conexión {data_params[pin]} en «{pin}»")
                # El objeto rico se inyecta durante Run; Compile sólo valida existencia y tipo.
                continue
            if origen is not None:
                if origen not in valores_por_nodo:
                    error(nid, f"el cable de «{pin}» no produjo un valor")
                    continue
                valor = valores_por_nodo[origen]
                fallo = None
            else:
                valor, fallo = _resolver_parametro(crudos.get(pin, default), default, tabla)
            if fallo:
                error(nid, f"{pin}: {fallo}")
            else:
                efectivos[pin] = valor
        params_plan[nid] = efectivos

    # Si la estructura ya impide un orden confiable, no se intenta propagar assets.
    input_assets: dict[str, str | None] = {}
    output_assets: dict[str, str | None] = {}
    if orden:
        main_sources: dict[str, list[str]] = {}
        asset_sources: dict[str, str] = {}
        for origen, _ap, destino, destino_pin in valid_edges:
            if destino_pin == PIN_IN:
                main_sources.setdefault(destino, []).append(origen)
            elif destino_pin == PIN_ASSET:
                asset_sources[destino] = origen

        for nid in orden:
            nodo = g.nodes[nid]
            verb = nodo.get("verb", "")
            if verb in VALOR_KINDS or verb not in registro:
                input_assets[nid] = None
                output_assets[nid] = None
                continue
            info = registro[verb]
            entradas_principales = main_sources.get(nid, [])
            if not info.get("source") and info.get("aridad", 1) != 0 \
                    and (info.get("in_name") != "A" or info.get("require_main_inputs")):
                minimo = int(info.get("min_inputs", 1))
                if len(entradas_principales) < minimo:
                    tipo_entrada = info.get("in_name") or "dato"
                    error(nid, f"requiere al menos {minimo} conexión(es) {tipo_entrada} en «in»")
            asset: str | None = None
            necesita_resolver = False
            if verb == "asset":
                asset = params_plan.get(nid, {}).get("name")
                necesita_resolver = True
                if not str(asset or "").strip():
                    error(nid, "Asset requiere un nombre/ObjectPath o un cable Text → name")
            elif verb == "pick":
                try:
                    asset = resolver_pick()
                except Exception as exc:  # noqa: BLE001
                    asset = None
                    error(nid, f"Pick no pudo leer la selección: {type(exc).__name__}: {exc}")
                if not asset:
                    error(nid, "Pick requiere una StaticMesh seleccionada en Content Browser")
            elif info.get("asset_pin", False):
                origen_asset = asset_sources.get(nid)
                if origen_asset is not None:
                    asset = output_assets.get(origen_asset)
                if not asset:
                    local = nodo.get("asset") or nodo.get("params", {}).get(PIN_ASSET)
                    if str(local or "").strip():
                        asset = str(local).strip()
                        necesita_resolver = True
                if not asset:
                    for origen in main_sources.get(nid, []):
                        if output_assets.get(origen):
                            asset = output_assets[origen]
                            break
                if not asset and info.get("asset_required", False):
                    error(nid, "requiere asset explícito: cable Asset/Pick, campo asset o entrada A")

            if asset and necesita_resolver:
                pedido = str(asset)
                try:
                    asset = resolver_asset(pedido)
                except Exception as exc:  # noqa: BLE001
                    asset = None
                    error(nid, f"no pude resolver asset: {type(exc).__name__}: {exc}")
                if not asset:
                    error(nid, f"asset no encontrado o no colocable: «{pedido}»")

            input_assets[nid] = asset
            # Un productor A puede nacer desde otro tipo de dato (mesh_to_static: M → A), de modo que
            # su ruta prevista depende de params aunque no tenga un asset A de entrada.
            producido = transformar_asset(verb, asset, params_plan.get(nid, {})) \
                if info.get("out_name") == "A" else None
            output_assets[nid] = producido or asset

    if diagnosticos:
        raise GraphValidationError(diagnosticos)
    return GraphPlan(orden, params_plan, input_assets, output_assets, tabla, valores_por_nodo)


def validar(g: JamGraph, **kwargs) -> dict[str, list[str]]:
    """Versión cómoda del Preflight que devuelve diagnósticos en vez de lanzar excepción."""
    try:
        compilar(g, **kwargs)
    except GraphValidationError as exc:
        return exc.diagnostics
    return {}


# ---- ejecución (reusa las tools y el oráculo; sólo acepta un GraphPlan válido) ----


# El símbolo con el que un veredicto pide AMARILLO. Lo pone el oráculo, no el ejecutor: quien sabe
# si algo es «indeseado pero aceptable» es quien midió.
AVISO = "\u26a0"


def _estado(texto: str) -> str:
    """Convención de Grasshopper llevada al oráculo: cada nodo se pinta por su VEREDICTO.

    Cuatro escalones, y el del medio es el que faltaba:

    * **rojo** (`error`) — reventó, no hay resultado.
    * **naranja** (`warn`) — el oráculo dice REVISAR ✗: el resultado NO sirve.
    * **amarillo** (`aviso`) — ⚠ pasó algo indeseado pero aceptable. El nodo corrió y su resultado
      sirve; lo que cambia es que no salió gratis («12 pisados contra lo que ya estaba»). Sin este
      escalón, eso se pintaba de VERDE y era exactamente lo que hacía falta ver.
    * **verde** (`ok`) — ✓.

    El orden importa: un texto puede traer ✓ y ⚠ a la vez —el verbo hizo lo suyo y algo hay que
    mirar— y en ese caso gana el amarillo.
    """
    if texto.startswith("[error]"):
        return "error"
    if "✗" in texto:
        return "warn"
    if AVISO in texto:
        return "aviso"
    return "ok" if "✓" in texto else "info"


def ejecutar(g: JamGraph, plan: GraphPlan | None = None) -> str:
    """Reporte de texto de correr el grafo (ver `ejecutar_detalle`)."""
    return ejecutar_detalle(g, plan)[0]


def ejecutar_detalle(g: JamGraph, plan: GraphPlan | None = None) -> tuple[str, dict]:
    """Corre el grafo en orden topológico: cada nodo dispara su tool y su oráculo. Devuelve
    (reporte, {nid: {'estado','texto'}}) — el estado es lo que pinta cada nodo en el canvas.
    Los actores quedan en el nivel (quien llama decide preview/confirm)."""
    from . import dsl, tools
    try:
        plan = plan or compilar(g)
    except GraphValidationError as exc:
        por_nodo = {
            nid: {"estado": "error", "texto": " · ".join(mensajes)}
            for nid, mensajes in exc.diagnostics.items() if nid in g.nodes
        }
        reporte = "\n".join(
            f"[{nid}] {' · '.join(mensajes)}" for nid, mensajes in exc.diagnostics.items()
        )
        return reporte, por_nodo

    por_nodo: dict[str, dict] = {}
    lineas = []
    runtime_outputs: dict[str, object] = {}
    marcados: list[tuple[str, object]] = []
    _ULTIMA_CORRIDA.clear()
    main_sources: dict[str, list[str]] = {}
    asset_sources: dict[str, str] = {}
    data_sources: dict[tuple[str, str], str] = {}
    for origen, _origen_pin, destino, destino_pin in g.edges:
        if destino_pin == PIN_ASSET:
            asset_sources[destino] = origen
        elif destino_pin == PIN_IN:
            main_sources.setdefault(destino, []).append(origen)
        else:
            data_sources[(destino, destino_pin)] = origen

    for nid in plan.order:
        n = g.nodes[nid]
        verb = n["verb"]

        # nodos de VALOR: no ejecutan verbo; aportan su valor (y lo muestran en el nodo).
        if verb in VALOR_KINDS:
            nombre = str(n.get("params", {}).get("name") or nid)
            v = plan.values_by_node.get(nid)
            txt = f"{nombre} = {v}" if v is not None else f"{nombre} = (sin resolver)"
            lineas.append(f"[{nid}·{verb}] {txt}")
            por_nodo[nid] = {"estado": "ok" if v is not None else "warn", "texto": txt}
            if v is not None:
                runtime_outputs[nid] = v
                _ULTIMA_CORRIDA[nid] = v
            continue

        info = tools.REGISTRO[verb]  # el Compile ya garantizó que existe
        asset = plan.input_assets.get(nid)
        # Compile propaga la ruta FINAL prevista. Durante Run, transformadores como Fracture crean
        # una variante temporal única; los consumidores deben recibir esa salida real, no la ruta
        # determinista que podría pertenecer a un Bake anterior.
        origen_asset = asset_sources.get(nid)
        entrada = asset
        asset_argument = None
        if info.get("asset_argument"):
            asset_argument = runtime_outputs.get(origen_asset) if origen_asset is not None else asset
            valores_main = [runtime_outputs[origen] for origen in main_sources.get(nid, [])
                            if runtime_outputs.get(origen) is not None]
            if info.get("aridad") == -1:
                entrada = valores_main
            elif valores_main:
                entrada = valores_main[0]
        elif origen_asset is not None and runtime_outputs.get(origen_asset) is not None:
            entrada = runtime_outputs[origen_asset]
        elif origen_asset is None:
            valores_main = [runtime_outputs[origen] for origen in main_sources.get(nid, [])
                            if runtime_outputs.get(origen) is not None]
            if info.get("aridad") == -1:
                entrada = valores_main
            elif valores_main:
                entrada = valores_main[0]
        # Los params ya están resueltos y tipados por Compile. `dsl.coaccionar` se conserva como última
        # frontera de compatibilidad con la firma histórica de las tools.
        kw, _desc = dsl.coaccionar(verb, {k: str(v) for k, v in plan.params.get(nid, {}).items()})
        if info.get("asset_argument"):
            kw["asset"] = asset_argument
        for pin in info.get("data_params", {}):
            origen_dato = data_sources.get((nid, pin))
            kw[pin] = runtime_outputs.get(origen_dato) if origen_dato is not None else None
        tools.limpiar_asset_producido_runtime(verb)
        try:
            txt = str(info["fn"](entrada, **kw))
        except Exception as e:  # noqa: BLE001
            txt = f"[error] {type(e).__name__}: {e}"
        lineas.append(f"[{nid}·{verb}] {txt}")
        estado = _estado(txt)
        por_nodo[nid] = {"estado": estado, "texto": txt}
        producido = tools.dato_producido_runtime(verb, entrada)
        salida = (producido if producido is not None else entrada) if estado != "error" else None
        runtime_outputs[nid] = salida
        if salida is not None:
            _ULTIMA_CORRIDA[nid] = salida

        # ---- flag de debug del nodo ----
        # El estado del arte no es un nodo de debug aparte: Houdini usa el display flag, PCG la
        # tecla D, Grasshopper el preview toggle. Se marca el nodo que YA está y se ve su salida.
        # Acá se hace lo mismo: la tabla va al reporte y la geometría se junta para dibujarla.
        if n.get("debug") and salida is not None:
            lineas.extend(_tabla_de(salida))
            marcados.append((nid, salida))

    if marcados:
        lineas.append(_dibujar_marcados(marcados))
    return "\n".join(lineas), por_nodo


def _tabla_de(salida) -> list[str]:
    """Tabla de texto del dato para el reporte. Una malla necesita el motor para leerse, así que se
    intenta por el adaptador y se cae al núcleo puro si no hay Unreal (suite headless)."""
    from . import debug as viz
    try:
        from . import mesh
        datos = mesh.inspeccionar(salida, filas=viz.FILAS_TABLA)
    except Exception:  # noqa: BLE001
        return viz.tabla(salida)
    return viz.texto_de_tabla(datos)


def _dibujar_marcados(marcados) -> str:
    """Junta la salida de los nodos marcados en UNA malla y la deja en la escena.

    Cae dentro del `_preview` que envuelve al Run, así que Discard se la lleva junto con el resto:
    el debug no ensucia el nivel ni obliga a limpiar a mano.
    """
    # Un flag de debug NUNCA debe tumbar el Run: si el dibujo falla —o si no hay motor, como en la
    # suite headless— se informa y el grafo sigue. La tabla del reporte no depende de esto.
    try:
        from . import mesh
        partes, fallos = [], []
        for nid, salida in marcados:
            dibujo = mesh.debug_de_cualquier_cosa(salida)
            if "error" in dibujo:
                fallos.append(f"{nid}: {dibujo['error']}")
            else:
                partes.append(dibujo["mesh"])
    except Exception as exc:  # noqa: BLE001
        return f"DEBUG ✗ — no se pudo dibujar: {type(exc).__name__}: {exc}"
    try:
        if not partes:
            return "DEBUG ✗ — nada dibujable" + (f" ({'; '.join(fallos)})" if fallos else "")
        combinada = partes[0] if len(partes) == 1 else mesh.merge(partes).get("mesh")
        if combinada is None:
            return "DEBUG ✗ — no pude combinar los dibujos"
        puesto = mesh.colocar_visualizacion(combinada)
    except Exception as exc:  # noqa: BLE001
        return f"DEBUG ✗ — no se pudo dibujar: {type(exc).__name__}: {exc}"
    extra = f" · {len(fallos)} sin dibujo" if fallos else ""
    return (f"DEBUG ✓ — {len(partes)} nodo(s) marcado(s) en escena{extra} "
            f"— «Descartar» lo borra{'' if 'error' not in puesto else ': ' + puesto['error']}")
