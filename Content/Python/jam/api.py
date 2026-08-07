"""jam.api — el ÚNICO contrato entre Jam y CUALQUIER interfaz.

Una interfaz (la Dash Bar en C++, una CLI externa, una web…) sólo necesita estas funciones. Así la UI
es un cliente FINO y reemplazable: hoy la llama el módulo C++/Slate vía ExecPythonCommandEx; mañana
puede llamarla un proceso Python FUERA de Unreal (por la ejecución remota del editor) sin tocar el
cerebro. Todo entra/sale como str o JSON — nunca objetos de UE. Ante UE6/Verse, la UI se reescribe
contra ESTE contrato; el cerebro no se toca.

Contrato:
    spec()                → JSON {categorias, tools} para armar la UI
    assets(q, limit, dir) → JSON {total, shown, folders, assets} del proyecto (Content browser)
    select_asset(path)    → fija el asset activo de la sesión (lo heredan las herramientas)
    run(command)          → corre una línea de DSL, devuelve el veredicto (texto)
    compile_graph(json)   → valida Graph/Flow sin ejecutar ni modificar la escena
    run_graph(json)       → corre un JamGraph (JSON), devuelve el reporte (texto)
    confirm() / discard() → fija o descarta el preview activo
"""

from __future__ import annotations


def spec() -> str:
    """Lo que muestra la DASH: la biblioteca de herramientas publicadas, no el catálogo de verbos.

    La Dash es el estante donde están las herramientas que uno construyó; el Graph es el taller
    donde se construyen. Antes mostraba 19 verbos sueltos (place, scatter, snap…) — siguen todos
    disponibles **en el Graph**, que es donde se combinan; lo que cambió es que la barra ya no es un
    catálogo fijo sino algo que se puebla publicando desde el Graph.

    Arranca vacía a propósito. Una barra vacía que dice cómo llenarse enseña el modelo; una llena de
    primitivas invita a usarlas sueltas y esconde que se pueden componer.
    """
    import json

    from . import funcion

    herramientas = []
    for definicion in funcion.listar_definiciones():
        if not definicion.get("publicada", True):
            continue
        ficha = funcion.herramienta(
            definicion["funcion_id"], definicion["nombre"], definicion["cuerpo"])
        # En la Dash no son «Funciones» (eso es su forma en el Graph): son LAS herramientas.
        ficha["cat"] = "Herramientas"
        ficha["seccion"] = "Herramientas"
        herramientas.append(ficha)
    # Sin herramientas no hay categorías: el ribbon no dibuja tabs vacíos y la barra queda limpia.
    categorias = ["Herramientas"] if herramientas else []
    return json.dumps({"categorias": categorias, "tools": herramientas}, ensure_ascii=True)


def assets(query: str = "", limit: int = 200, folder: str = "") -> str:
    """JSON {total, shown, all, folders, assets} — `total` vs `shown` le dice a la UI cuántos quedan
    fuera del tope (que era el "no veo todos los mesh")."""
    from . import library
    return library.buscar_json(query, limit=limit, carpeta=folder)


def select_asset(path: str) -> str:
    """Fija el asset activo de la sesión (lo que hereda cualquier herramienta sin asset explícito).
    Es el mismo verbo `asset` del DSL/grafo: Content escribe UN estado, no una variable de la UI."""
    from . import tools
    return tools.t_asset(path)


def run(command: str) -> str:
    from . import panel
    return panel.ejecutar_dsl(command, None)


def run_graph(graph_json: str) -> str:
    from . import panel
    return panel.ejecutar_grafo(graph_json, None)


def _expandir_funciones(graph_json: str) -> tuple[str, str]:
    """(json ya sin funciones, error). Expandir es lo PRIMERO que pasa en el borde: de ahí para
    adentro nadie sabe que existen las funciones, y el oráculo sigue midiendo el grafo entero."""
    from . import funcion
    try:
        return funcion.expandir_json(graph_json), ""
    except funcion.FuncionError as e:
        return graph_json, str(e)


def _compile_cuerpo_funcion(graph_json: str) -> str | None:
    """Envelope de Compile si el canvas contiene una definición; `None` si es un grafo normal."""
    import json

    from . import funcion
    from .graph import JamGraph

    cuerpo = JamGraph.from_json(graph_json)
    if not funcion.es_cuerpo(cuerpo):
        return None
    contrato, diagnosticos = funcion.validar_cuerpo(cuerpo)
    globales = diagnosticos.get("_graph", [])
    estados = {}
    lineas = []
    for nid, nodo in cuerpo.nodes.items():
        mensajes = diagnosticos.get(nid, []) or globales
        if mensajes:
            texto = " · ".join(mensajes)
            estados[nid] = {"estado": "error", "texto": texto}
            lineas.append(f"[{nid}·{nodo.get('verb', '?')}] {texto}")
        else:
            estados[nid] = {"estado": "ok", "texto": "Compile ✓"}
    if diagnosticos:
        reporte = "COMPILE ✗ — función inválida\n" + "\n".join(lineas)
    else:
        def pines(items):
            return ", ".join(
                f"{p['name']}: {funcion.ETIQUETAS_TIPOS_PIN[p['tipo']]}" for p in items
            ) or "ninguno"
        reporte = (f"COMPILE ✓ — firma de función · {pines(contrato['entradas'])} → "
                   f"{pines(contrato['salidas'])} · {len(cuerpo.nodes)} nodos")
    return json.dumps({"ok": not diagnosticos, "preview": False,
                       "report": reporte, "nodes": estados}, ensure_ascii=True)


def run_graph_json(graph_json: str) -> str:
    """JSON {report, nodes:{nid:{estado,texto}}} para pintar el canvas. Detecta SOLO: si el grafo son
    ops de flow (source/mask/instance) lo corre como cadena Houdini; si son verbos, como grafo de
    verbos. Así el mismo botón Run del canvas hace lo correcto sin que la UI sepa la diferencia."""
    import json

    from . import flow, funcion, graph, panel
    cuerpo = graph.JamGraph.from_json(graph_json)
    if funcion.es_cuerpo(cuerpo):
        compilado = json.loads(_compile_cuerpo_funcion(graph_json) or "{}")
        if not compilado.get("ok"):
            return json.dumps(compilado, ensure_ascii=True)
        return json.dumps({
            "ok": False, "preview": False,
            "report": ("RUN — una definición no se ejecuta sola. "
                       "Usá «Guardar y volver al grafo», insertá su ficha de Biblioteca y "
                       "ejecutá la instancia con valores conectados."),
            "nodes": {nid: {"estado": "info", "texto": "parte de la definición"}
                      for nid in cuerpo.nodes},
        }, ensure_ascii=True)
    graph_json, error = _expandir_funciones(graph_json)
    if error:
        return json.dumps({"ok": False, "report": f"RUN ✗ — {error}", "nodes": {}},
                          ensure_ascii=True)
    if flow.Flow.from_json(graph_json).solo_flow():
        return panel.ejecutar_flow_json(graph_json, None)
    return panel.ejecutar_grafo_json(graph_json, None)


def compile_graph_json(graph_json: str) -> str:
    """Compile/Preflight sin efectos para el canvas. Devuelve el mismo envelope por nodo que Run.

    Resuelve tipos, aridad, ciclos, expresiones y assets, pero no abre Preview ni llama ninguna tool.
    """
    import json

    from . import flow, graph

    cuerpo = _compile_cuerpo_funcion(graph_json)
    if cuerpo is not None:
        return cuerpo

    graph_json, error = _expandir_funciones(graph_json)
    if error:
        return json.dumps({"ok": False, "report": f"COMPILE ✗ — {error}", "nodes": {}},
                          ensure_ascii=True)

    f = flow.Flow.from_json(graph_json)
    if f.solo_flow():
        from . import scatter
        diagnosticos = f.validar(ops=scatter.ops_flow())
        nodos = f.nodos
    else:
        g = graph.JamGraph.from_json(graph_json)
        diagnosticos = graph.validar(g)
        nodos = {nid: {"kind": nodo.get("verb", "")} for nid, nodo in g.nodes.items()}

    estados = {}
    lineas = []
    errores_globales = diagnosticos.get("_graph", [])
    for nid, nodo in nodos.items():
        mensajes = diagnosticos.get(nid, []) or errores_globales
        if mensajes:
            texto = " · ".join(mensajes)
            estados[nid] = {"estado": "error", "texto": texto}
            lineas.append(f"[{nid}·{nodo.get('kind', '?')}] {texto}")
        else:
            estados[nid] = {"estado": "ok", "texto": "Compile ✓"}
    for mensaje in diagnosticos.get("_graph", []):
        lineas.append(f"[grafo] {mensaje}")

    if diagnosticos:
        reporte = "COMPILE ✗ — corregí los errores antes de Run\n" + "\n".join(lineas)
    else:
        reporte = f"COMPILE ✓ — {len(nodos)} nodo(s), sin efectos en la escena"
    return json.dumps({"ok": not diagnosticos, "report": reporte, "nodes": estados}, ensure_ascii=True)


def inspect_json(node_id: str = "", filtro: str = "", filas: int = 200,
                 orden: str = "", descendente: bool = False) -> str:
    """Inspector de datos del último Run — el Geometry Spreadsheet de Jam.

    Sin `node_id` devuelve la LISTA de nodos inspeccionables (id + tipo + cantidad) para que el panel
    arme su selector. Con `node_id` devuelve las columnas y las filas de ese nodo.

    `filtro` es texto libre; `orden` es el NOMBRE de una columna y `descendente` invierte. Los tres
    los resuelve `debug.tabla_datos` sobre TODAS las filas antes de recortar, así que la UI no
    reimplementa ninguna regla: pide y muestra.
    """
    import json

    from . import debug, graph

    corrida = graph.ultima_corrida()
    if not corrida:
        return json.dumps({"ok": False, "error": "todavía no corriste el grafo.",
                           "nodos": [], "columnas": [], "filas": []}, ensure_ascii=True)

    from . import mesh

    def resumen(valor):
        datos = mesh.inspeccionar(valor, filas=1)
        return {"tipo": mesh._describir(valor), "cantidad": mesh.contar(valor),
                "inspeccionable": bool(datos["columnas"])}

    nodos = [{"id": nid, **resumen(valor)} for nid, valor in corrida.items()]
    if not node_id:
        return json.dumps({"ok": True, "nodos": nodos, "columnas": [], "filas": []},
                          ensure_ascii=True)

    if node_id not in corrida:
        return json.dumps({"ok": False, "error": f"«{node_id}» no está en el último Run.",
                           "nodos": nodos, "columnas": [], "filas": []}, ensure_ascii=True)

    datos = mesh.inspeccionar(corrida[node_id], filas=max(1, int(filas)), filtro=filtro,
                              orden=orden, descendente=bool(descendente))
    # Las celdas viajan ya FORMATEADAS: el formato depende del tipo de columna, que sólo se conoce
    # acá. La UI muestra lo que recibe en vez de reimplementar el redondeo.
    tipos = [c["tipo"] for c in datos["columnas"]]
    datos["filas"] = [[debug._texto_celda(v, tipo) for v, tipo in zip(fila, tipos)]
                      for fila in datos["filas"]]
    return json.dumps({"ok": True, "nodos": nodos, "node": node_id, **datos}, ensure_ascii=True)


def presets(kind: str = "", scope: str = "") -> str:
    """JSON de los presets disponibles (nombre/kind/categoria/descripcion/tags/scope) para la UI."""
    from . import preset
    return preset.listar_json(kind=(kind or None), scope=(scope or None))


def preset_apply(nombre: str) -> str:
    """Aplica un preset por nombre (recrea como preview + oráculo). Confirmar/Descartar lo resuelven."""
    from . import preset
    r = preset.aplicar(nombre)
    return r["texto"]


def preset_save_command(nombre: str, command: str, categoria: str = "", scope: str = "local") -> str:
    """Guarda la línea de comando actual como preset de tool."""
    from . import preset
    p = preset.desde_comando(nombre, command, categoria=categoria, scope=scope)
    ruta = preset.guardar(p)
    return f"PRESET guardado ✓ — «{nombre}» ({scope})  {ruta}"


def preset_save_graph(nombre: str, graph_json: str, categoria: str = "", scope: str = "local") -> str:
    """Guarda el canvas como preset compound. El `kind` sale del grafo: `flow` si son sólo ops de
    flow, `graph` si contiene verbos (Place, Mesh, TreeGen…). Aplicarlo usa ese mismo runner."""
    from . import preset
    p = preset.desde_grafo(nombre, graph_json, categoria=categoria, scope=scope)
    ruta = preset.guardar(p)
    return f"PRESET ({p['kind']}) guardado ✓ — «{nombre}» ({scope})  {ruta}"


def flow_spec() -> str:
    """JSON de las ops de flow (source/mask/combine/output) para el canvas estilo Houdini."""
    from . import flow
    return flow.spec_json()


def spec_all() -> str:
    """Spec COMBINADO: verbos de herramienta + ops de flow, para que el canvas ofrezca ambos. Cada
    entrada trae su `cat`; las de flow además `source`/`aridad`."""
    import json

    from . import flow, funcion, tools
    # El canvas incorpora también herramientas graph-only, como el tab Mesh cuyos cables transportan
    # DynamicMesh `M`. La Dash Bar conserva sólo verbos útiles como acción aislada.
    verbos = json.loads(tools.spec_json(include_graph_only=True))
    ops = json.loads(flow.spec_json())
    # Las ops puras de Flow ahora TAMBIÉN son verbos del Graph (`tools.OPS_FLOW_EN_GRAPH`), así que
    # llegan por los dos lados. Gana la entrada del registro de verbos: es la que trae el contrato de
    # tipos (`in_name`/`out_name` = P) que usan el Preflight y el canvas.
    ya_estan = {item["verbo"] for item in verbos["tools"]}
    solo_flow = [item for item in ops["tools"] if item["verbo"] not in ya_estan]
    funciones = funcion.herramientas()
    cats_flow = [item["cat"] for item in solo_flow]
    cats = verbos["categorias"] + [c for c in ops["categorias"]
                                   if c not in verbos["categorias"] and c in cats_flow]
    if funciones and "Funciones" not in cats:
        cats.append("Funciones")
    from . import ribbon
    todas = ribbon.anotar(verbos["tools"] + solo_flow) + funciones
    return json.dumps({"categorias": cats, "tools": todas}, ensure_ascii=True)


def collapse_function(nombre: str, graph_json: str, selected_json: str,
                      scope: str = "local") -> str:
    """Colapsa la selección, guarda el cuerpo y devuelve el grafo padre + spec de la instancia."""
    import json

    from . import funcion, preset
    from .graph import JamGraph
    try:
        seleccion = set(json.loads(selected_json))
        funcion_id = funcion.nuevo_id()
        padre, cuerpo = funcion.colapsar(
            JamGraph.from_json(graph_json), seleccion, funcion_id)
        p = preset.desde_grafo(
            nombre, cuerpo.to_json(), scope=scope, funcion_id=funcion_id)
        ruta = preset.guardar(p)
        tool = funcion.herramienta(funcion_id, nombre, cuerpo)
        return json.dumps({"ok": True, "graph": json.loads(padre.to_json()), "tool": tool,
                           "report": f"FUNCIÓN guardada ✓ — «{nombre}» ({scope})  {ruta}"},
                          ensure_ascii=True)
    except (ValueError, TypeError, OSError) as e:
        return json.dumps({"ok": False, "report": f"FUNCIÓN ✗ — {e}"}, ensure_ascii=True)


def tool_export(funcion_id: str, ruta: str) -> str:
    """Escribe una herramienta como archivo portable `.jamtool`: `{ok, ruta, nombre}`.

    Es JSON, legible y editable — a propósito. La analogía con `.sbsar` de Substance tienta a
    compilar, pero una herramienta de Jam es **transparente por obligación**: se expande inline
    antes de compilar, y si fuera opaca el oráculo dejaría de ver lo que mide. Se empaqueta; no se
    cierra.
    """
    import json

    from . import funcion, preset

    try:
        d = funcion.obtener_definicion(funcion_id)
        paquete = {
            "jamtool": 1,                       # versión del formato, para poder migrarlo después
            "funcion_id": d["funcion_id"],
            "nombre": d["nombre"],
            "descripcion": d.get("descripcion", ""),
            "publicada": bool(d.get("publicada", True)),
            "graph": json.loads(d["cuerpo"].to_json()),
        }
        destino = str(ruta).strip()
        if not destino:
            raise ValueError("falta la ruta de destino")
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(paquete, f, ensure_ascii=True, indent=1)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True)
    return json.dumps({"ok": True, "ruta": destino, "nombre": paquete["nombre"],
                       "report": f"HERRAMIENTA exportada ✓ — «{paquete['nombre']}» → {destino}"},
                      ensure_ascii=True)


def tool_import(ruta: str) -> str:
    """Trae una herramienta `.jamtool` a la biblioteca LOCAL: `{ok, verbo, nombre}`.

    Conserva la identidad (`funcion_id`) del archivo: si esa herramienta ya estaba, la reemplaza en
    vez de dejar dos con el mismo nombre y distinto id. Y valida el cuerpo antes de guardar — un
    archivo de otra versión de Jam podría traer un verbo que acá no existe, y es mejor decirlo al
    importar que dejar una ficha que revienta al usarla.
    """
    import json

    from . import funcion, preset
    from .graph import JamGraph

    try:
        with open(str(ruta), "r", encoding="utf-8") as f:
            paquete = json.load(f)
        if not isinstance(paquete, dict) or "graph" not in paquete:
            raise ValueError("el archivo no es una herramienta de Jam (falta «graph»)")
        cuerpo = JamGraph.from_json(json.dumps(paquete["graph"]))
        _firma, diagnosticos = funcion.validar_cuerpo(cuerpo)
        if diagnosticos:
            detalle = " · ".join(m for ms in diagnosticos.values() for m in ms)
            raise ValueError(f"la herramienta no es válida en este Jam: {detalle}")
        nombre = str(paquete.get("nombre") or "Herramienta importada")
        identidad = str(paquete.get("funcion_id") or funcion.nuevo_id())
        p = preset.desde_grafo(nombre, cuerpo.to_json(),
                               descripcion=str(paquete.get("descripcion", "")),
                               scope="local", funcion_id=identidad,
                               publicada=bool(paquete.get("publicada", True)))
        preset.guardar(p)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True)
    return json.dumps({"ok": True, "verbo": funcion.PREFIJO + identidad, "nombre": nombre,
                       "report": f"HERRAMIENTA importada ✓ — «{nombre}»"}, ensure_ascii=True)


def function_manage(action: str, funcion_id: str = "", payload: str = "",
                    scope: str = "local") -> str:
    """ABM de definiciones para Slate. `payload` es nombre en create/rename y grafo en update."""
    import json

    from . import funcion, preset
    from .graph import JamGraph

    try:
        action = str(action or "").strip().lower()
        identidad = funcion.nombre_de_instancia(funcion_id) \
            if funcion.es_instancia(funcion_id) else funcion_id

        if action == "create":
            nombre = str(payload or "").strip()
            if not nombre:
                raise funcion.FuncionError("la función necesita un nombre")
            if any(d["nombre"].casefold() == nombre.casefold()
                   for d in funcion.listar_definiciones()):
                raise funcion.FuncionError(f"ya existe una función llamada «{nombre}»")
            identidad = funcion.nuevo_id()
            cuerpo = JamGraph()
            cuerpo.add("input", {"name": "entrada", "type": "*"}, nid="entrada", x=40, y=80)
            cuerpo.add("output", {"name": "salida", "type": "*"}, nid="salida", x=380, y=80)
            cuerpo.connect("entrada", "salida")
            p = preset.desde_grafo(
                nombre, cuerpo.to_json(), scope=scope, funcion_id=identidad)
            ruta = preset.guardar(p)
            tool = funcion.herramienta(identidad, nombre, cuerpo)
            return json.dumps({"ok": True, "graph": json.loads(cuerpo.to_json()), "tool": tool,
                               "report": f"FUNCIÓN creada ✓ — «{nombre}»  {ruta}"},
                              ensure_ascii=True)

        d = funcion.obtener_definicion(identidad)
        if action == "get":
            return json.dumps({"ok": True, "graph": json.loads(d["cuerpo"].to_json()),
                               "tool": funcion.herramienta(
                                   d["funcion_id"], d["nombre"], d["cuerpo"]),
                               "report": f"Editando función — «{d['nombre']}»"},
                              ensure_ascii=True)

        if action == "rename":
            nombre = str(payload or "").strip()
            if not nombre:
                raise funcion.FuncionError("la función necesita un nombre")
            if any(x["funcion_id"] != identidad and x["nombre"].casefold() == nombre.casefold()
                   for x in funcion.listar_definiciones()):
                raise funcion.FuncionError(f"ya existe una función llamada «{nombre}»")
            cuerpo = d["cuerpo"]
        elif action == "update":
            cuerpo = JamGraph.from_json(payload)
            _firma, diagnosticos = funcion.validar_cuerpo(cuerpo)
            if diagnosticos:
                detalle = " · ".join(
                    mensaje for mensajes in diagnosticos.values() for mensaje in mensajes)
                raise funcion.FuncionError(detalle)
            nombre = d["nombre"]
        elif action == "publish":
            # Publicar/despublicar: sólo cambia si la herramienta aparece en la Dash. El cuerpo no
            # se toca, así que los grafos que ya la usan siguen andando igual.
            quiere = str(payload or "").strip().lower() not in ("false", "0", "no", "")
            cuerpo = d["cuerpo"]
            nombre = d["nombre"]
            p = preset.desde_grafo(nombre, cuerpo.to_json(), descripcion=d["descripcion"],
                                   scope=d["scope"], funcion_id=identidad, publicada=quiere)
            preset.guardar(p)
            estado = "publicada" if quiere else "despublicada"
            return json.dumps(
                {"ok": True, "publicada": quiere, "verbo": funcion.PREFIJO + identidad,
                 "report": f"FUNCIÓN {estado} ✓ — «{nombre}»"}, ensure_ascii=True)

        elif action == "delete":
            if not preset.borrar_funcion(identidad):
                raise funcion.FuncionError(f"no pude borrar la función «{d['nombre']}»")
            return json.dumps({"ok": True, "verbo": funcion.PREFIJO + identidad,
                               "report": f"FUNCIÓN eliminada ✓ — «{d['nombre']}»"},
                              ensure_ascii=True)
        else:
            raise funcion.FuncionError(f"acción ABM desconocida: {action or '?'}")

        # Una definición legada adopta su identidad anterior explícitamente al primer cambio. El
        # verbo no cambia, por lo que sus instancias existentes siguen funcionando.
        p = preset.desde_grafo(nombre, cuerpo.to_json(), descripcion=d["descripcion"],
                               scope=d["scope"], funcion_id=identidad)
        ruta = preset.guardar(p)
        tool = funcion.herramienta(identidad, nombre, cuerpo)
        return json.dumps({"ok": True, "graph": json.loads(cuerpo.to_json()), "tool": tool,
                           "report": f"FUNCIÓN actualizada ✓ — «{nombre}»  {ruta}"},
                          ensure_ascii=True)
    except (ValueError, TypeError, OSError) as e:
        return json.dumps({"ok": False, "report": f"FUNCIÓN ✗ — {e}"}, ensure_ascii=True)


def confirm(owner: str = "") -> str:
    """Fija un Preview. `owner='graph'/'dash'` aísla la interfaz; vacío confirma todos."""
    from . import panel
    return panel._h_confirmar(owner=owner or None)


def commit(command: str = "") -> str:
    """«Poné esto»: si hay una preview activa la FIJA; si no hay ninguna, corre `command` y la fija
    en el acto. Así el botón Confirmar hace lo que uno espera cuando está apuntando con el gizmo —
    apretar y que el objeto aparezca ahí — sin dejar de servir para el flujo previsualizar→confirmar."""
    from . import panel
    if panel.hay_preview("dash"):
        return panel.ejecutar_dsl("confirm", None)
    if not command.strip():
        return "no hay preview activa ni comando para colocar."
    salida = panel.ejecutar_dsl(command, None)
    if not panel.hay_preview("dash"):
        return salida          # el comando no creó nada (error o verbo de selección): no hay qué fijar
    return f"{salida}\n{panel.ejecutar_dsl('confirm', None)}"


def ghost_target(x: float, y: float, z: float, view: bool = True, anchor: str = "base") -> str:
    """Le dice al fantasma GRIS dónde va a caer la pieza (los valores de los campos de la
    herramienta). Es plomería de la UI: cada vez que cambian x/y/z, el gris se mueve."""
    from . import ghost
    return ghost.objetivo(x, y, z, view, anchor)


def aim() -> str:
    """JSON {hit, x, y, z} del punto de mira del viewport — dónde está parado Jam."""
    import json

    from . import ue
    m = ue.punto_de_mira()
    if m is None or m["punto"] is None:
        return json.dumps({"hit": False, "x": 0.0, "y": 0.0, "z": 0.0})
    p = m["punto"]
    return json.dumps({"hit": bool(m["hit"]), "x": p.x, "y": p.y, "z": p.z})


def discard(owner: str = "") -> str:
    """Descarta un Preview. `owner='graph'/'dash'` aísla la interfaz; vacío descarta todos."""
    from . import panel
    return panel._h_descartar(owner=owner or None)


def preview_2d(node_id: str = "", ancho: int = 320, alto: int = 320, canal: int = 0,
               sufijo: str = "") -> str:
    """Dibuja el dato del nodo como PNG y devuelve `{ok, ruta, tipo, ayuda}`.

    Es el visor 2D del panel. Sólo dibuja lo que NO se puede ver en el viewport —el desplegado de
    UVs de una malla y la máscara que calcula un grafo de material—; para todo lo demás contesta por
    qué no hay nada que dibujar, que es información y no un panel en blanco.

    El PNG se escribe en `Saved/JamPreview2D/` con el id del nodo en el nombre. Va a disco en vez de
    a una textura transitoria porque así lo abre cualquier cosa: el panel, el explorador de archivos
    o Brian arrastrándolo a otro lado.
    """
    import json
    import os

    import unreal

    from . import graph, mesh, preview2d, shader

    corrida = graph.ultima_corrida()
    if not corrida:
        return json.dumps({"ok": False, "error": "todavía no corriste el grafo."},
                          ensure_ascii=True)
    if node_id not in corrida:
        return json.dumps({"ok": False,
                           "error": f"«{node_id}» no dejó datos en la última corrida.",
                           "nodos": sorted(corrida)}, ensure_ascii=True)

    dato = corrida[node_id]
    carpeta = os.path.join(unreal.Paths.project_saved_dir(), "JamPreview2D")
    os.makedirs(carpeta, exist_ok=True)
    # `sufijo` separa la MINIATURA del nodo (64 px) del dibujo grande del panel (320 px). Sin eso
    # los dos escribirían el mismo archivo y, peor, compartirían el nombre con que Slate cachea la
    # textura: el panel mostraría la miniatura pixelada o al revés.
    ruta = os.path.join(carpeta, f"{node_id}{sufijo}.png")

    if isinstance(dato, shader.GrafoMaterial):
        salidas = [a.desde for a in dato.aristas if a.es_salida_del_material]
        nodo = salidas[-1] if salidas else (dato.nodos[-1].id if dato.nodos else "")
        if not nodo:
            return json.dumps({"ok": False, "error": "el grafo de material está vacío."},
                              ensure_ascii=True)
        from . import scatter_core as sc

        def evaluar(g, entorno):
            # El ruido de UE tiene otro dibujo que el de Jam; para PREVISUALIZAR se usa el de Jam,
            # que es el que además comparte el scatter. La diferencia está anotada en
            # `weight_material`: misma escala y misma estadística, otras manchas.
            return shader.evaluar(g, entorno, ruido=lambda x, y, _z: sc.value_noise(x, y, 1.0, 0))

        pixeles = preview2d.mascara_de_grafo(dato, nodo, evaluar, ancho=int(ancho), alto=int(alto))
        tipo, detalle = "MT", f"máscara del nodo «{nodo}» · {len(dato.nodos)} nodos de material"
    elif isinstance(dato, unreal.DynamicMesh):
        triangulos = mesh.uv_triangulos(dato, int(canal))
        if not triangulos:
            return json.dumps(
                {"ok": False,
                 "error": f"la malla no tiene UVs en el canal {canal}: proyectá o desplegá primero "
                          "(mesh_uv_box / mesh_uv_unwrap)."}, ensure_ascii=True)
        pixeles = preview2d.islas_uv(triangulos, int(ancho), int(alto))
        medida = mesh._medir_uv(dato, int(canal))
        tipo = "M"
        detalle = f"UV{canal} · {len(triangulos)} triángulos · {mesh._veredicto_uv(medida, canal)}"
    else:
        nombre = type(dato).__name__
        return json.dumps({"ok": False, "tipo": nombre,
                           "error": preview2d.texto_de_ayuda(nombre)}, ensure_ascii=True)

    with open(ruta, "wb") as f:
        f.write(preview2d.png(int(ancho), int(alto), pixeles))
    return json.dumps({"ok": True, "ruta": ruta, "tipo": tipo, "detalle": detalle},
                      ensure_ascii=True)


def preview_2d_todos(lado: int = 64, canal: int = 0) -> str:
    """Miniatura de CADA nodo dibujable de la última corrida: `{ok, thumbs: {node_id: ruta}}`.

    Es lo que alimenta las miniaturas en el canvas, al estilo de Substance Designer: el nodo deja de
    mostrar un icono genérico y muestra lo que produjo.

    Existe como UNA función y no como N llamadas a `preview_2d` desde el C++ porque cada viaje a
    Python desde Slate cuesta un `ExecPythonCapture`; con un grafo de 30 nodos serían 30 procesos de
    ida y vuelta por cada Run. Acá el bucle corre adentro de Python y el C++ paga un solo viaje.

    Los nodos que no se pueden dibujar se saltean en silencio: no tener miniatura es el estado
    normal de la mayoría de los nodos (un asset, un número), no un error que haya que reportar.
    """
    import json

    from . import graph

    corrida = graph.ultima_corrida()
    if not corrida:
        return json.dumps({"ok": False, "error": "todavía no corriste el grafo."}, ensure_ascii=True)

    thumbs = {}
    for nid in corrida:
        try:
            res = json.loads(preview_2d(nid, int(lado), int(lado), int(canal), sufijo="_thumb"))
        except Exception:  # noqa: BLE001
            continue   # una miniatura que falla no puede tumbar a las demás
        if res.get("ok") and res.get("ruta"):
            thumbs[nid] = res["ruta"]
    return json.dumps({"ok": True, "thumbs": thumbs}, ensure_ascii=True)


def variables(graph_json: str = "") -> str:
    """Nombres de variable usables en una expresión: `{ok, variables: [...]}`.

    Alimenta el desplegable del nodo `math`. Sale de `JamGraph.valores()`, o sea del MISMO código
    que después resuelve la expresión: así el desplegable no puede ofrecer un nombre que el
    evaluador vaya a rechazar. Una lista construida aparte se desincronizaría el día que cambie
    qué cuenta como variable.

    Sólo las NUMÉRICAS, por la misma razón que el mensaje de error no las sugiere: un booleano no
    es usable en una expresión (`math` los excluye de su tabla), así que ofrecerlo mandaría a quien
    lo elige directo a un error.
    """
    import json

    from .graph import JamGraph

    try:
        tabla = JamGraph.from_json(graph_json).valores()
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True)
    nombres = sorted(k for k, v in tabla.items()
                     if isinstance(v, (int, float)) and not isinstance(v, bool))
    return json.dumps({"ok": True, "variables": nombres}, ensure_ascii=True)


def cable_bajo_punto(payload_json: str) -> str:
    """Qué cable hay bajo un punto: `{cable, x, y, t, distancia}` o `{}` si no hay ninguno.

    Alimenta el reroute: el `.cpp` manda `{x, y, cables:[{id, ax, ay, bx, by}]}` en coordenadas de
    MODELO y recibe el tramo tocado más el punto SOBRE la curva donde insertar la vía.

    Las cuentas viven en `jam.layout` —que reproduce la misma curva que se dibuja— y no en Slate,
    por lo mismo que alinear y distribuir: así se pueden verificar sin abrir el editor.
    """
    import json

    from . import layout

    try:
        d = json.loads(payload_json) or {}
        m = layout.cable_mas_cercano(
            float(d.get("x", 0.0)), float(d.get("y", 0.0)), d.get("cables") or [])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return "{}"
    # Un objeto vacío y no un error: «no había cable ahí» es el caso normal de un doble clic en el
    # fondo, y el editor lo usa para decidir que abre el buscador.
    return json.dumps(m or {}, ensure_ascii=True)


def acomodar(nodos_json: str, accion: str) -> str:
    """Alinear/distribuir la selección del canvas. JSON `{ok, pos: {id: [x, y]}}`.

    `nodos_json` es `[{"id","x","y","w","h"}]` en coordenadas de MODELO. `accion` es uno de
    `izquierda/derecha/arriba/abajo/centro-x/centro-y` (alinear), `dist-x`/`dist-y` (distribuir)
    `auto` (acomodar el grafo por capas) o `snap` (ajustar a la grilla).

    `auto` es el único que necesita saber CÓMO están cableados los nodos, no sólo dónde están, así
    que para él `nodos_json` toma la forma `{"nodos": [...], "edges": [[origen, destino], ...]}`.
    Se acepta cualquiera de las dos formas en vez de agregar una función aparte: es el mismo gesto
    para el usuario —«acomodame esto»— y el mismo camino de vuelta, aplicar posiciones.

    Las cuentas viven en `jam.layout`, puro y testeado, y no en Slate: son las mismas con cualquier
    pan, zoom y DPI, y así se pueden verificar sin abrir el editor.
    """
    import json

    from . import layout

    try:
        crudo = json.loads(nodos_json)
        if isinstance(crudo, dict):
            nodos = crudo.get("nodos") or []
            aristas = [(e[0], e[1]) for e in (crudo.get("edges") or []) if len(e) >= 2]
        else:
            nodos, aristas = (crudo or []), []
        if str(accion) == "auto":
            pos = layout.auto(nodos, aristas)
        elif str(accion) == "snap":
            pos = layout.ajustar_a_grilla(nodos)
        elif str(accion) in ("dist-x", "dist-y"):
            pos = layout.distribuir(nodos, str(accion)[-1])
        else:
            pos = layout.alinear(nodos, str(accion))
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=True)
    return json.dumps({"ok": True, "pos": {k: [v[0], v[1]] for k, v in pos.items()}},
                      ensure_ascii=True)


def params_de_nodo_nuevo(verbo: str) -> str:
    """Los params con los que nace un nodo en el canvas. JSON `{param: valor}`.

    Existe por una tensión real entre dos cosas que las dos hacen falta:

    * un grafo tiene que ser REPRODUCIBLE — dos Run del mismo grafo, el mismo resultado. Eso
      prohíbe leer la cámara viva en cada corrida;
    * lo que uno coloca tiene que aparecer DONDE ESTÁ MIRANDO, no en el origen del mundo a
      kilómetros de la cámara, o se siente como que la herramienta no hizo nada.

    Se resuelven capturando el punto de mira UNA VEZ, cuando el nodo se crea, y escribiéndolo en sus
    params. Desde ahí el nodo tiene coordenadas propias, editables, y corre igual mil veces — que es
    exactamente lo que hace Houdini cuando soltás un nodo.
    """
    import json

    from . import tools, ue

    info = tools.REGISTRO.get(str(verbo))
    if info is None:
        return json.dumps({}, ensure_ascii=True)
    params = dict(info.get("params", {}))

    campos = tools.CAPTURA_LA_MIRA.get(str(verbo))
    if campos:
        mira = ue.punto_de_mira()
        if mira is not None and mira["punto"] is not None:
            punto = mira["punto"]
            for campo, valor in zip(campos, (punto.x, punto.y, punto.z)):
                if campo in params:
                    params[campo] = round(float(valor), 1)
    return json.dumps(params, ensure_ascii=True)
