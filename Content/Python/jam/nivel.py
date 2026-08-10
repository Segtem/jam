"""Leer el grafo de espacio del NIVEL REAL (Fase A) — el oráculo de winnability sobre lo que construís.

Los actores del nivel se etiquetan con TAGS de Unreal que Jam interpreta, y de ahí se arma el
`SpaceGraph` que `solve_graph` ya sabe verificar. Así "Verificar espacio" deja de correr sobre un
mapa inventado en código y pasa a verificar el mapa que realmente pusiste en la escena.

Convención de tags (strings en `actor.tags`, prefijo `jam:`):
  jam:node                     → marca al actor como NODO del grafo (una sala / un punto)
  jam:id=<id>                  → id del nodo (si falta, se usa el label del actor)
  jam:type=<tipo>              → tipo semántico (spawn/clue/boss/extract/room…)
  jam:key=<llave>              → pickup que se obtiene al ENTRAR a ese nodo
  jam:start / jam:goal         → nodo de entrada / de extracción
  jam:link=<destino>           → arista a otro nodo (no dirigida)
  jam:link=<destino>:<llave>   → esa arista es una PUERTA que exige tener <llave>

`marcar_nodo()` escribe estos tags desde Jam; `grafo_del_nivel()` los lee.
"""

from __future__ import annotations

import unreal

from . import bridge, ue

bridge.ensure_oraculo_on_path()

from oraculo.mazes.spacegraph import GraphEdge, GraphNode, SpaceGraph  # noqa: E402

_PREFIJO = "jam:"


def _tags(actor) -> list[str]:
    try:
        return [str(t) for t in actor.get_editor_property("tags")]
    except Exception:  # noqa: BLE001
        return [str(t) for t in (getattr(actor, "tags", None) or [])]


def _parse(tags: list[str]) -> dict:
    """Config jam de un actor a partir de sus tags."""
    d = {"node": False, "id": None, "type": "room", "key": None,
         "start": False, "goal": False, "links": []}
    for t in tags:
        if not t.startswith(_PREFIJO):
            continue
        cuerpo = t[len(_PREFIJO):]
        if cuerpo == "node":
            d["node"] = True
        elif cuerpo == "start":
            d["start"] = True
        elif cuerpo == "goal":
            d["goal"] = True
        elif "=" in cuerpo:
            k, v = cuerpo.split("=", 1)
            if k == "id":
                d["id"] = v
            elif k == "type":
                d["type"] = v
            elif k == "key":
                d["key"] = v
            elif k == "link":
                if ":" in v:
                    tgt, door = v.split(":", 1)
                    d["links"].append((tgt, door))
                else:
                    d["links"].append((v, None))
    return d


def marcar_nodo(actor, id: str | None = None, *, tipo: str = "room", key: str | None = None,
                start: bool = False, goal: bool = False, enlaces=None):
    """Etiqueta a `actor` como nodo del grafo. `enlaces` = lista de destino (str) o (destino, llave)."""
    tags = [t for t in _tags(actor) if not t.startswith(_PREFIJO)]  # limpia jam: previos
    tags.append(_PREFIJO + "node")
    if id:
        tags.append(f"{_PREFIJO}id={id}")
    if tipo and tipo != "room":
        tags.append(f"{_PREFIJO}type={tipo}")
    if key:
        tags.append(f"{_PREFIJO}key={key}")
    if start:
        tags.append(_PREFIJO + "start")
    if goal:
        tags.append(_PREFIJO + "goal")
    for e in (enlaces or []):
        if isinstance(e, (tuple, list)):
            tgt = e[0]
            door = e[1] if len(e) > 1 else None
            tags.append(f"{_PREFIJO}link={tgt}:{door}" if door else f"{_PREFIJO}link={tgt}")
        else:
            tags.append(f"{_PREFIJO}link={e}")
    actor.set_editor_property("tags", [unreal.Name(t) for t in tags])
    return actor


def grafo_del_nivel(actores=None) -> SpaceGraph:
    """Arma el SpaceGraph a partir de los actores etiquetados. `actores` None = todo el nivel."""
    if actores is None:
        actores = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    nodes: dict[str, GraphNode] = {}
    metas = []  # (id, links, actor)
    for a in actores:
        cfg = _parse(_tags(a))
        if not cfg["node"]:
            continue
        nid = cfg["id"] or a.get_actor_label()
        nodes[nid] = GraphNode(id=nid, type=cfg["type"], key=cfg["key"],
                               start=cfg["start"], goal=cfg["goal"])
        metas.append((nid, cfg["links"]))

    # aristas no dirigidas, deduplicadas; si algún sentido declara puerta, la arista queda con puerta
    pares: dict[tuple, str | None] = {}
    faltantes = []
    for nid, links in metas:
        for tgt, door in links:
            if tgt not in nodes:
                faltantes.append((nid, tgt))
                continue
            clave = tuple(sorted((nid, tgt)))
            if clave not in pares or (door and not pares[clave]):
                pares[clave] = door
    edges = [GraphEdge(a=k[0], b=k[1], kind="door", door_id=d) for k, d in pares.items()]
    g = SpaceGraph(nodes=nodes, edges=edges, space="extraction")
    g.jam_faltantes = faltantes  # enlaces a nodos inexistentes (diagnóstico)
    return g


def veredicto_nivel(actores=None):
    """Corre el oráculo sobre el grafo del nivel. Devuelve (dict_solve|None, grafo). None si no hay nodos."""
    g = grafo_del_nivel(actores)
    if not g.nodes:
        return None, g
    return ue.espacio(g), g


def veredicto_texto_nivel(actores=None) -> str:
    r, g = veredicto_nivel(actores)
    if r is None:
        return ("Nivel sin nodos de Jam: etiquetá actores con tags jam:node / jam:start / jam:goal / "
                "jam:key= / jam:link= para que el oráculo pueda verificar la winnability.")
    n_nodos, n_aristas = len(g.nodes), len(g.edges)
    falt = getattr(g, "jam_faltantes", [])
    aviso = f"\n   ⚠ enlaces a nodos inexistentes: {falt}" if falt else ""
    if r["solvable"]:
        camino = " → ".join(r["path"])
        return (f"[nivel real] GANABLE ✓  ({n_nodos} nodos, {n_aristas} aristas, "
                f"{r['optimal_steps']} tramos)\n   ruta óptima: {camino}{aviso}")
    razon = r.get("reason", "sin ruta que complete la extracción")
    return f"[nivel real] NO GANABLE ✗  — {razon}  ({n_nodos} nodos, {n_aristas} aristas){aviso}"
