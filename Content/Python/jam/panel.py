"""Puente Jam ↔ UI: ejecución del DSL y del grafo, con preview → Confirmar/Descartar.

Lo llama la UI en C++ (`JamEditor`: Dash Bar y Graph) vía `ejecutar_dsl` / `ejecutar_grafo`. Ya NO
arma ningún widget UMG: el viejo EditorUtilityWidget (`WBP_JamPanel`) y su cableado quedaron
reemplazados por el módulo C++/Slate. Acá vive sólo la lógica compartida: parsear→correr→verificar,
spawnear como PREVIEW (tag `jam:preview`) y resolver con Confirmar (fija) o Descartar (borra).
"""

from __future__ import annotations

import unreal

from . import library

# Preview → Submit: las herramientas spawnean primero como PREVIEW (con veredicto); recién «Confirmar»
# las fija o «Descartar» las borra. `_PREVIEW` = actores del preview activo (uno a la vez).
_PREVIEW: list = []
_TAG_PREVIEW = "jam:preview"


def _asset_biblioteca():
    libro = library.buscar(limit=1)
    return libro[0]["ruta"] if libro else None


def _resolver_asset(nombre) -> str | None:
    """asset del comando (por nombre/ObjectPath) → si no se da, el ACTIVO de la sesión (lo que se
    eligió en Content) → y recién ahí el 1º de la biblioteca."""
    from . import session
    if nombre:
        if "/" in nombre or "." in nombre:   # ya es un ObjectPath
            return nombre
        hits = library.buscar(nombre, limit=1)
        return hits[0]["ruta"] if hits else None
    return session.asset() or _asset_biblioteca()


# ---- Preview → Submit ----

def _actor_sub():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _todos():
    return _actor_sub().get_all_level_actors()


def _tags_de(actor) -> list[str]:
    from . import ue
    return ue.tags(actor)


def _set_tags(actor, tags: list[str]) -> None:
    from . import ue
    ue.set_tags(actor, tags)


def _marcar_preview(actores) -> None:
    for a in actores:
        tags = _tags_de(a)
        if _TAG_PREVIEW not in tags:
            _set_tags(a, tags + [_TAG_PREVIEW])
    _PREVIEW.extend(actores)


def _descartar_preview() -> int:
    """Borra los actores del preview activo. Devuelve cuántos."""
    ed, n = _actor_sub(), 0
    for a in _PREVIEW:
        try:
            ed.destroy_actor(a)
            n += 1
        except Exception:  # noqa: BLE001
            pass
    _PREVIEW.clear()
    return n


def _limpiar_huerfanos() -> int:
    """Borra restos jam:preview de sesiones cerradas sin confirmar/descartar. Devuelve cuántos."""
    ed, n = _actor_sub(), 0
    for a in _todos():
        if _TAG_PREVIEW in _tags_de(a):
            try:
                ed.destroy_actor(a)
                n += 1
            except Exception:  # noqa: BLE001
                pass
    return n


def _preview(fn, widget=None) -> str:
    """Corre una herramienta como PREVIEW: descarta el preview anterior, spawnea, y captura por
    diff del nivel todo lo que la herramienta agregó (así Descartar limpia hasta los helpers)."""
    from . import ue
    _descartar_preview()
    antes = {a.get_path_name() for a in _todos()}
    texto = fn(widget)
    nuevos = [a for a in _todos() if a.get_path_name() not in antes]
    _marcar_preview(nuevos)
    # Dejarlas SELECCIONADAS en el editor: se ven resaltadas, aparecen en el Outliner y en Details,
    # y con F la cámara vuela hasta ellas. Es la diferencia entre "lo colocó" y "no veo nada".
    ue.seleccionar(nuevos)
    return (f"{texto}\n\nPREVIEW · {len(nuevos)} piezas en escena (seleccionadas) — "
            "«Confirmar» las fija · «Descartar» las borra.")


def hay_preview() -> bool:
    """¿Hay algo esperando que lo confirmen o descarten?"""
    return bool(_PREVIEW)


def _h_confirmar(widget=None) -> str:
    if not _PREVIEW:
        return "no hay preview activa para confirmar."
    n = len(_PREVIEW)
    for a in _PREVIEW:
        _set_tags(a, [t for t in _tags_de(a) if t != _TAG_PREVIEW])
    # decir QUÉ quedó y DÓNDE: sin esto, un confirm sobre algo fuera de cuadro no se distingue de
    # un confirm que no hizo nada.
    detalle = []
    for a in _PREVIEW[:4]:
        loc = a.get_actor_location()
        detalle.append(f"«{a.get_actor_label()}» ({loc.x:.0f}, {loc.y:.0f}, {loc.z:.0f})")
    if n > 4:
        detalle.append(f"…+{n - 4}")
    _PREVIEW.clear()
    return (f"CONFIRMADO ✓ — {n} piezas fijadas en el nivel: " + ", ".join(detalle)
            + "\n    siguen seleccionadas: F en el viewport vuela hasta ellas.")


def _h_descartar(widget=None) -> str:
    n = _descartar_preview()
    return f"descartado ✗ — {n} piezas borradas." if n else "no hay preview activa para descartar."


# ---- Ejecución del DSL y del grafo (lo que llama la UI C++) ----

def ejecutar_dsl(linea: str, widget=None) -> str:
    """Corre una línea de DSL. Los verbos de spawn pasan por preview (Confirmar/Descartar los
    resuelven). `widget` se ignora (compat con la firma que llama el C++)."""
    from . import dsl, menu, tools
    r = dsl.parsear(linea)
    verbo = r["verbo"]
    if not verbo:
        return "escribí un comando. «help» lista los verbos."
    # keywords en inglés (primario) + alias español por comodidad
    if verbo in ("help", "?", "ayuda"):
        return dsl.ayuda()
    if verbo in ("confirm", "confirmar", "ok"):
        return _h_confirmar()
    if verbo in ("discard", "descartar", "cancel"):
        return _h_descartar()
    if verbo in ("verify", "verificar", "oracle"):
        return menu.on_verificar_espacio()
    if verbo == "preset":
        from . import preset
        nombre = (linea.split(None, 1)[1].strip() if len(linea.split(None, 1)) > 1 else "").strip('"')
        if not nombre or nombre in ("list", "listar"):
            ps = preset.listar()
            if not ps:
                return "no hay presets. Guardá uno con «guardar preset» o poné JSON en <plugin>/presets/."
            return "presets:\n" + "\n".join(
                f"  · {p['nombre']}  [{p.get('kind','tool')}·{p['scope']}]  {p.get('descripcion','')}"
                for p in ps)
        # aplicar por nombre pasa por preview (confirm/discard lo resuelven)
        p = preset.cargar(nombre)
        if not p:
            return f"preset «{nombre}» no encontrado. «preset list» los muestra."
        return preset.aplicar(p)["texto"]
    if verbo in ("search", "list", "buscar", "listar"):
        hits = library.buscar(r["asset"] or "", limit=15)
        if not hits:
            return f"sin resultados para «{r['asset'] or ''}»."
        nombres = ", ".join(h["nombre"] for h in hits)
        return f"{len(hits)} assets: {nombres}"
    if verbo in tools.SIN_SPAWN:
        # selección/estado, no spawn: no pasan por preview (no agregan actores al nivel)
        kw, _desc = dsl.coaccionar(verbo, r["params"])
        if verbo == "pick":
            return tools.t_pick(None)   # lee la selección del Content Browser de Unreal
        # `name` como nombre de asset es SÓLO para el verbo `asset` (en pcg, `name` es el del volumen).
        pedido = r["asset"] or (r["params"].get("name") if verbo == "asset" else "") or ""
        asset = _resolver_asset(pedido)
        if pedido and asset is None:
            return f"asset «{pedido}» no encontrado en la biblioteca."
        return tools.REGISTRO[verbo]["fn"](asset, **kw)
    if verbo in tools.REGISTRO:
        asset = _resolver_asset(r["asset"])
        if r["asset"] and asset is None:
            return f"asset «{r['asset']}» no encontrado en la biblioteca."
        if not asset:
            return "biblioteca vacía (no hay assets que colocar)."
        kw, desconocidos = dsl.coaccionar(verbo, r["params"])
        fn = tools.REGISTRO[verbo]["fn"]
        cuerpo = _preview(lambda _w: fn(asset, **kw))
        if desconocidos:
            cuerpo += f"\n(ignoré params desconocidos: {', '.join(desconocidos)})"
        return cuerpo
    return f"verbo desconocido: «{verbo}». «help» lista los verbos."


def ejecutar_grafo(g_json: str, widget=None) -> str:
    """Corre un JamGraph (JSON) como UN preview: todos los actores del grafo se marcan juntos y
    Confirmar/Descartar resuelven el grafo entero. Es la ejecución del «Grasshopper» de Jam."""
    from . import graph
    g = graph.JamGraph.from_json(g_json)
    return _preview(lambda _w: graph.ejecutar(g))


def ejecutar_flow_json(g_json: str, widget=None) -> str:
    """Corre un FLOW (cadena estilo Houdini: source → máscaras → instance) como UN preview, y devuelve
    JSON {report, nodes:{id:{estado,texto}}} para que el canvas pinte cada nodo. El estado sale del
    stream que produjo: verde = pasó puntos, naranja = quedó vacío (el filtro comió todo)."""
    import json

    from . import flow, scatter

    f = flow.Flow.from_json(g_json)
    caja: dict = {}

    def correr(_w):
        try:
            salida = f.evaluar(ops=scatter.ops_flow())
        except ValueError as e:   # ciclo
            caja["_err"] = str(e)
            return f"[flow] {e}"
        lineas = []
        for nid, nodo in f.nodos.items():
            stream = salida.get(nid, [])
            kind = nodo["kind"]
            if kind == "instance":
                out = nodo["params"].get("_out", {})
                txt = (f"{out.get('colocados', 0)} instancias"
                       + (f" · {out['pisados']} evitadas por huella" if out.get("pisados") else "")
                       + ("" if out.get("assets") else " · SIN asset activo ✗"))
                estado = "ok" if out.get("colocados") else "warn"
            else:
                txt = f"{len(stream)} puntos"
                estado = "ok" if stream else "warn"
            caja[nid] = {"estado": estado, "texto": f"{kind}: {txt}"}
            lineas.append(f"[{nid}·{kind}] {txt}")
        return "\n".join(lineas)

    reporte = _preview(correr)
    if "_err" in caja:
        return json.dumps({"report": reporte, "nodes": {}}, ensure_ascii=True)
    return json.dumps({"report": reporte, "nodes": caja}, ensure_ascii=True)


def ejecutar_grafo_json(g_json: str, widget=None) -> str:
    """Igual que `ejecutar_grafo` pero devuelve JSON {report, nodes:{nid:{estado,texto}}}: el canvas
    pinta cada nodo con SU veredicto (verde/naranja/rojo, como los estados de Grasshopper)."""
    import json

    from . import graph
    g = graph.JamGraph.from_json(g_json)
    caja: dict = {}

    def correr(_w):
        texto, por_nodo = graph.ejecutar_detalle(g)
        caja.update(por_nodo)
        return texto

    reporte = _preview(correr)
    return json.dumps({"report": reporte, "nodes": caja}, ensure_ascii=True)
