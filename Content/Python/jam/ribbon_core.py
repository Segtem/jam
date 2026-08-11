"""Buffers puros para convertir una polilínea abierta en una cinta triangulada.

No importa ``unreal``: el adaptador fino de :mod:`jam.mesh` traduce estas tuplas a Geometry
Script. La costura longitudinal de UV necesita duplicar vértices en un recorrido cerrado; esa
política todavía no está implementada, por lo que el núcleo rechaza esos recorridos explícitamente.
"""

from __future__ import annotations

import math

from .curve_sampling_core import offset_points


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _sin_pliegues(left, right, margen: float = 0.98):
    """Angosta la cinta donde el recorrido dobla más cerrado que su propio ancho.

    Cuando el radio de curvatura es menor que la media anchura, el borde INTERIOR se cruza consigo
    mismo: su segmento apunta en contra del avance del eje y el cuadrilátero entre dos muestras se
    pliega, dejando caras dadas vuelta. Geométricamente no existe una cinta de ese ancho sobre esa
    curva, así que la única salida honesta es angostarla ahí.

    Lo encontró `malla.cara_visible` en su primer uso, 2026-08-10: 4 de 20 cintas sin ningún defecto
    inyectado ya salían con caras invertidas. Se degrada explícito y se informa, igual que
    `miter_limit` cae a bevel en vez de estirar la esquina en silencio.

    Devuelve `(left, right, tramos_angostados)`. Trabaja sobre el eje implícito —el punto medio de
    cada par— y aplica el MISMO factor a los dos bordes, para que la cinta se angoste sin descentrarse.

    LÍMITE MEDIDO, no supuesto: el punto medio deja de representar al eje cuando el miter de una
    esquina muy cerrada empuja un borde lejísimos, y ahí el ancho local ya no es `width`. Con giros
    de hasta 22° por muestra —el rango realista— esto deja 0 de 20 cintas plegadas, contra 4 de 20
    antes. Con giros de 140° y cintas más anchas que el paso, siguen quedando 11 de 20: ese caso
    es geométricamente degenerado y lo sigue marcando `malla.cara_visible`. NO se afinó el algoritmo
    contra la medida a propósito; corregirlo de verdad pide reescribir el offset con el eje real y su
    correspondencia de muestras, que es un corte aparte.
    """
    ejes = [tuple((l[eje] + r[eje]) / 2.0 for eje in range(3)) for l, r in zip(left, right)]
    medios = [tuple((l[eje] - r[eje]) / 2.0 for eje in range(3)) for l, r in zip(left, right)]
    escala = [1.0] * len(ejes)

    # Cada pasada corrige los tramos que siguen plegados; reducir un vértice puede plegar a su
    # vecino, así que se repite. El tope evita que un recorrido patológico gire para siempre.
    for _ in range(8):
        plegados = 0
        for i in range(len(ejes) - 1):
            d = tuple(ejes[i + 1][eje] - ejes[i][eje] for eje in range(3))
            largo_d = sum(componente * componente for componente in d)
            if largo_d < 1e-12:
                continue
            delta = tuple(medios[i + 1][eje] * escala[i + 1] - medios[i][eje] * escala[i]
                          for eje in range(3))
            proyeccion = sum(delta[eje] * d[eje] for eje in range(3))
            # El borde se da vuelta cuando el avance del eje no alcanza a compensar la diferencia
            # entre las medias anchuras. `-proyeccion > largo_d` es exactamente esa condición.
            if -proyeccion <= largo_d:
                continue
            plegados += 1
            factor = largo_d / (-proyeccion) * margen
            escala[i] *= factor
            escala[i + 1] *= factor
        if not plegados:
            break

    angostados = sum(1 for valor in escala if valor < 0.999)
    nuevo_left = [tuple(ejes[i][eje] + medios[i][eje] * escala[i] for eje in range(3))
                  for i in range(len(ejes))]
    nuevo_right = [tuple(ejes[i][eje] - medios[i][eje] * escala[i] for eje in range(3))
                   for i in range(len(ejes))]
    return nuevo_left, nuevo_right, angostados


def _normals(vertices, triangles):
    """Normal por vértice, promediando las caras que lo tocan.

    El cross va en orden `(c-a) × (b-a)` y no al revés porque los triángulos se emiten con el
    winding que Unreal considera frontal (ver `ribbon_buffers`). Con el orden matemático habitual
    estas normales saldrían del lado opuesto al de la cara que el motor dibuja, y la cinta se vería
    iluminada por detrás.
    """
    accumulated = [[0.0, 0.0, 0.0] for _ in vertices]
    for triangle in triangles:
        a, b, c = (vertices[index] for index in triangle)
        face = _cross(
            tuple(c[axis] - a[axis] for axis in range(3)),
            tuple(b[axis] - a[axis] for axis in range(3)),
        )
        if sum(component * component for component in face) < 1e-16:
            return None
        for index in triangle:
            for axis in range(3):
                accumulated[index][axis] += face[axis]
    result = []
    for normal in accumulated:
        length = math.sqrt(sum(component * component for component in normal))
        if length < 1e-8:
            return None
        result.append(tuple(component / length for component in normal))
    return tuple(result)


def ribbon_buffers(points, *, width: float = 360.0, plane: str = "xy",
                   join: str = "miter", miter_limit: float = 4.0,
                   uv_scale: float = 200.0) -> dict:
    """Construye vértices, triángulos, normales y UV0 de una cinta abierta.

    ``U`` acumula la distancia media recorrida por ambos bordes y la divide por ``uv_scale``;
    ``V`` cruza de izquierda (0) a derecha (1). Así un bevel conserva continuidad y una textura
    mantiene escala aun cuando los dos bordes no recorren exactamente la misma longitud.
    """
    try:
        source = tuple(tuple(float(value) for value in point) for point in points)
        width, uv_scale = float(width), float(uv_scale)
        plane, join = (str(value or "").strip().lower() for value in (plane, join))
        miter_limit = float(miter_limit)
    except (TypeError, ValueError, OverflowError):
        return {"error": "mesh_ribbon recibió puntos o parámetros inválidos."}
    if len(source) < 2 or any(len(point) != 3 for point in source):
        return {"error": "mesh_ribbon necesita una polilínea XYZ de al menos dos puntos."}
    if any(not all(math.isfinite(value) for value in point) for point in source):
        return {"error": "mesh_ribbon recibió una coordenada no finita."}
    if math.dist(source[0], source[-1]) < 1e-6:
        return {"error": "mesh_ribbon todavía no admite recorridos cerrados con costura UV."}
    if not math.isfinite(width) or not 0.01 <= width <= 1_000_000.0:
        return {"error": "width de mesh_ribbon debe estar entre 0.01 y 1000000 cm."}
    if not math.isfinite(uv_scale) or not 0.01 <= uv_scale <= 1_000_000.0:
        return {"error": "uv_scale de mesh_ribbon debe estar entre 0.01 y 1000000 cm."}

    common = {"distance": width * 0.5, "plane": plane, "join": join,
              "miter_limit": miter_limit}
    left = offset_points(source, side="left", **common)
    right = offset_points(source, side="right", **common)
    if "error" in left:
        return {"error": left["error"].replace("curve_offset", "mesh_ribbon")}
    if "error" in right:
        return {"error": right["error"].replace("curve_offset", "mesh_ribbon")}
    if len(left["points"]) != len(right["points"]):
        return {"error": "mesh_ribbon produjo bordes con distinta cantidad de muestras."}
    if len(left["points"]) * 2 > 4096:
        return {"error": "mesh_ribbon no puede producir más de 4096 vértices por recorrido."}

    puntos_left, puntos_right, angostados = _sin_pliegues(left["points"], right["points"])
    vertices = tuple(
        point
        for pair in zip(puntos_left, puntos_right)
        for point in pair
    )
    # El orden de estos índices decide qué lado de la cinta DIBUJA Unreal: el backface culling mira
    # el winding, no las normales que se envían aparte. Medido el 2026-08-10 con
    # `tools/experiments/investiga_winding_ribbon_58.py`: con el orden opuesto al de acá, el motor
    # reportaba los 48 triángulos del tutorial «Borde de camino» con la cara hacia -Z y la calzada
    # era invisible desde arriba, mientras un `mesh_box` nativo daba su tapa hacia +Z. El muro de
    # «Muro sobre spline» heredaba la misma vuelta porque se extruye sobre esta superficie.
    triangles = tuple(
        triangle
        for index in range(len(left["points"]) - 1)
        for triangle in (
            (index * 2, index * 2 + 2, index * 2 + 1),
            (index * 2 + 1, index * 2 + 2, index * 2 + 3),
        )
    )
    normals = _normals(vertices, triangles)
    if normals is None:
        return {"error": "mesh_ribbon produjo un triángulo degenerado; revise ancho y curva."}

    u_values = [0.0]
    for index in range(1, len(puntos_left)):
        step = (math.dist(puntos_left[index - 1], puntos_left[index])
                + math.dist(puntos_right[index - 1], puntos_right[index])) * 0.5
        u_values.append(u_values[-1] + step / uv_scale)
    uv0 = tuple(uv for u in u_values for uv in ((u, 0.0), (u, 1.0)))
    return {
        "vertices": vertices,
        "triangles": triangles,
        "normals": normals,
        "uv0": uv0,
        "width": width,
        "length_u": u_values[-1] * uv_scale,
        "bevels": left["bevels"],
        "angostados": angostados,
        "info": (f"{len(vertices)} vértices · {len(triangles)} triángulos · "
                 f"ancho {width:g} cm · UV0 {u_values[-1]:.2f} U"
                 + (f" · {angostados} muestras angostadas por curva cerrada" if angostados else "")),
    }
