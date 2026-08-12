"""El *display flag*: ver SÓLO el nodo marcado, como Houdini y Substance Designer.

Cerebro puro, sin `unreal`. Jam ya tenía el flag por nodo y ya dibujaba su salida, pero lo hacía
**sumando**: el nodo marcado se dibujaba ADEMÁS de todo lo que el grafo hiciera igual —colocar
actores, hornear assets— y se podían marcar varios sin que eso cambiara nada. Ver una parte obligaba
a soportar el resto.

Acá vive la pieza que faltaba: **el recorte**. Marcar un nodo pasa a significar «esto es lo que
quiero ver», y el grafo corre solamente lo que hace falta para producirlo. Es la semántica de las
dos herramientas que Jam toma como norte:

  · **Houdini** — el display flag es del nodo, y la red cocina hasta ahí. Lo de aguas abajo no corre.
  · **Substance Designer** — el nodo elegido manda en el visor; el resto del grafo no se muestra.

Lo que se recorta es la EJECUCIÓN, no la validación: Compile sigue mirando el grafo entero, así que
un error aguas abajo se sigue viendo aunque ahora no corra. Esconder errores sería un precio muy
alto por ver una parte.
"""

from __future__ import annotations


def marcados(nodes: dict) -> list[str]:
    """Los nodos con el display flag prendido, en el orden del diagrama."""
    return [nid for nid, nodo in nodes.items() if isinstance(nodo, dict) and nodo.get("debug")]


def ancestros(nodes: dict, edges, nid: str) -> set[str]:
    """`nid` y TODO lo que lo alimenta, transitivamente.

    Es lo mínimo que hay que correr para poder mostrar `nid`. Se camina hacia atrás con una lista de
    pendientes y un conjunto de vistos: un grafo con ciclo no puede colgar esto. El ciclo lo rechaza
    Compile, pero esta función corre sobre lo que haya y no puede confiar en que la llamen bien.
    """
    if nid not in nodes:
        return set()
    entrantes: dict[str, list[str]] = {}
    for arista in edges:
        origen, destino = _puntas(arista)
        if origen is None:
            continue
        entrantes.setdefault(destino, []).append(origen)

    vistos = {nid}
    pendientes = [nid]
    while pendientes:
        actual = pendientes.pop()
        for previo in entrantes.get(actual, ()):
            if previo not in vistos and previo in nodes:
                vistos.add(previo)
                pendientes.append(previo)
    return vistos


def _puntas(arista):
    """(origen, destino) de una arista, en sus dos formas: por pin (4) o suelta (2)."""
    if len(arista) == 4:
        return arista[0], arista[2]
    if len(arista) == 2:
        return arista[0], arista[1]
    return None, None


def recorte(nodes: dict, edges) -> tuple[list[str], set[str]]:
    """(nodos marcados, nodos que TIENEN que correr).

    Sin ningún marcado devuelve todos: un grafo sin display flag se comporta exactamente como antes,
    y esa es la propiedad que hace que esto se pueda agregar sin romper nada de lo que ya andaba.

    Con varios marcados corre la UNIÓN de sus ancestros y se dibujan todos. Podría haberse elegido
    uno solo y descartado el resto, pero eso necesitaría un criterio de desempate arbitrario —¿el
    último?, ¿el de más abajo?— y rompería los diagramas guardados que ya tienen dos marcados. La
    unión no necesita desempate y hace lo evidente.
    """
    marcas = marcados(nodes)
    if not marcas:
        return [], set(nodes)
    permitidos: set[str] = set()
    for nid in marcas:
        permitidos |= ancestros(nodes, edges, nid)
    return marcas, permitidos


def omitidos(nodes: dict, permitidos: set[str]) -> list[str]:
    """Los que NO van a correr. Se nombran para poder decírselo al usuario: un nodo que dejó de
    correr sin aviso es indistinguible de un nodo roto."""
    return [nid for nid in nodes if nid not in permitidos]


def resumen(marcas: list[str], cuantos_omitidos: int) -> str:
    """La línea del reporte. Que el corte se ANUNCIE no es cosmético: alguien que marca un nodo y ve
    que su terminal dejó de colocar cosas tiene que poder leer por qué, en vez de creer que se rompió.
    """
    if not marcas:
        return ""
    quienes = ", ".join(marcas)
    if not cuantos_omitidos:
        return f"SOLO ▸ {quienes} — el grafo entero hace falta para mostrarlo"
    return (f"SOLO ▸ {quienes} — {cuantos_omitidos} nodo(s) aguas abajo no corrieron "
            f"(apagá el ◉ para correr todo)")
