"""El pincel como FUENTE DE PUNTOS. Cerebro puro (cero `import unreal`).

La idea que lo hace barato: un grafo de Jam es declarativo —se configura y se corre— y pintar es
interactivo. En vez de volver interactivo al grafo, se parten las responsabilidades:

  · el **grafo** decide QUÉ se coloca y CÓMO (assets, física, escala);
  · el **pincel** decide DÓNDE, y para eso alcanza con que produzca puntos.

Así el pincel es *otra fuente de P*, exactamente como `scatter`, y el grafo no cambia de naturaleza.
Y como `scatter` ya reparte ALREDEDOR de los puntos que entran, el pincel no reparte nada: sólo
marca los centros. `brush → scatter → place` sale de composición, sin duplicar el repartidor.

Qué es un «pincel» en el nivel: un actor cualquiera que se mueve con el gizmo de transformación de
Unreal. No hace falta un tipo nuevo — se selecciona, se mueve, se corre.
"""

from __future__ import annotations


def centros(posiciones, *, alto: float = 0.0) -> list[tuple[float, float, float]]:
    """Centros del pincel a partir de las posiciones de los actores elegidos.

    `alto` LEVANTA el punto sobre el pivote del actor. No es un detalle: para pintar con física uno
    quiere que las cosas nazcan ARRIBA y caigan. Con `alto=0` nacen dentro del piso y la simulación
    las expulsa hacia cualquier lado.

    Devuelve tuplas planas `(x, y, z)` y no objetos del motor a propósito: así esto se testea sin
    Unreal y el adaptador se queda con la única línea que necesita el motor.
    """
    salida = []
    for p in posiciones:
        x, y, z = (float(p[0]), float(p[1]), float(p[2]))
        salida.append((x, y, z + float(alto)))
    return salida


def semilla_por_centro(base: int, x: float, y: float) -> int:
    """Semilla estable para un centro: dos corridas del mismo pincel dan lo mismo.

    Sin esto, mover el pincel y volver atrás daría un reparto distinto — y el oráculo de Jam exige
    que dos Run del mismo grafo den el mismo resultado.
    """
    return (int(base) * 73856093 ^ int(x) * 19349663 ^ int(y) * 83492791) & 0x7FFFFFFF
