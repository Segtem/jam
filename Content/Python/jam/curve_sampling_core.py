"""Construcción y remuestreo puros de polilíneas.

Este módulo no conoce Unreal ni los tipos ricos del adaptador de curvas. Recibe datos escalares y
tuplas XYZ, y devuelve tuplas verificables. ``curve.py`` conserva la responsabilidad fina de
envolverlas como ``CurvePath``/``CurveSet`` para que viajen por cables ``S``.
"""

from __future__ import annotations

import math

from .fields import ScalarSeries


def polyline_points(x, y, z, *, closed: bool = False) -> dict:
    """Combina tres series ``N[]`` del mismo tamaño en una polilínea XYZ.

    Con ``closed`` repite el primer punto al final, que es como el tutorial de Grasshopper convierte
    una polilínea en un POLÍGONO. Se repite el punto en vez de marcar una bandera porque todo lo que
    consume `S` recorre la lista de puntos: una bandera obligaría a que cada consumidor se acuerde
    de cerrar, y el que se olvide deja un polígono abierto por un lado sin que nada lo diga.
    """
    series = (x, y, z)
    if any(not isinstance(item, ScalarSeries) for item in series):
        return {"error": "polyline necesita tres series N[] conectadas en x, y, z."}
    counts = tuple(len(item.values) for item in series)
    if len(set(counts)) != 1:
        return {"error": "x, y, z de polyline deben tener la misma cantidad de muestras."}
    count = counts[0]
    if count < 2 or count > 4096:
        return {"error": "polyline necesita entre 2 y 4096 puntos."}

    points = tuple(zip(x.values, y.values, z.values))
    if any(not all(math.isfinite(float(value)) for value in point) for point in points):
        return {"error": "polyline recibió una coordenada no finita."}
    points = tuple(tuple(float(value) for value in point) for point in points)
    if any(math.dist(a, b) < 1e-6 for a, b in zip(points, points[1:])):
        return {"error": "polyline no admite puntos consecutivos coincidentes."}
    if closed:
        if math.dist(points[0], points[-1]) < 1e-6:
            return {"error": "polyline no puede cerrarse: el último punto ya coincide con el primero."}
        points = points + (points[0],)
    length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    return {"points": points, "length": length,
            "info": f"{len(points)} puntos · {length:.1f} cm" + (" · cerrada" if closed else "")}


def resample_points(points, *, count: int) -> dict:
    """Muestrea una polilínea a distancias uniformes, incluidos sus dos extremos."""
    try:
        count = int(count)
        source = tuple(tuple(float(value) for value in point) for point in points)
    except (TypeError, ValueError, OverflowError):
        return {"error": "curve_resample recibió puntos o count inválidos."}
    if count < 2 or count > 4096:
        return {"error": "count de curve_resample debe estar entre 2 y 4096."}
    if len(source) < 2 or any(len(point) != 3 for point in source):
        return {"error": "curve_resample necesita una polilínea XYZ de al menos dos puntos."}
    if any(not all(math.isfinite(value) for value in point) for point in source):
        return {"error": "curve_resample recibió una coordenada no finita."}

    # Los duplicados consecutivos no aportan longitud. Quitarlos vuelve robusta la lectura de un
    # SplineComponent real sin cambiar el recorrido ni inventar una dirección.
    clean = [source[0]]
    for point in source[1:]:
        if math.dist(clean[-1], point) >= 1e-6:
            clean.append(point)
    if len(clean) < 2:
        return {"error": "curve_resample recibió una curva de longitud cero."}

    lengths = tuple(math.dist(a, b) for a, b in zip(clean, clean[1:]))
    total = sum(lengths)
    if total < 1e-6:
        return {"error": "curve_resample recibió una curva de longitud cero."}

    result = []
    segment = 0
    walked = 0.0
    for index in range(count):
        target = total * index / (count - 1)
        while segment < len(lengths) - 1 and walked + lengths[segment] < target:
            walked += lengths[segment]
            segment += 1
        local = (target - walked) / lengths[segment]
        start, end = clean[segment], clean[segment + 1]
        result.append(tuple(
            start[axis] + (end[axis] - start[axis]) * local for axis in range(3)))

    # Evita que acumulación de coma flotante mueva los extremos que el autor escribió.
    result[0], result[-1] = clean[0], clean[-1]
    spacing = total / (count - 1)
    return {"points": tuple(result), "length": total, "spacing": spacing,
            "info": f"{len(clean)}→{count} puntos · paso {spacing:.1f} cm"}


def smooth_points(points, *, iterations: int = 2, strength: float = 0.5,
                  preserve_ends: bool = True) -> dict:
    """Suavizado Laplaciano simultáneo sobre una polilínea abierta.

    Cada pasada mueve un punto hacia el promedio de sus vecinos. No inserta muestras —ésa es la
    responsabilidad de ``resample_points``— y nunca muta la entrada.
    """
    try:
        iterations, strength = int(iterations), float(strength)
        source = tuple(tuple(float(value) for value in point) for point in points)
    except (TypeError, ValueError, OverflowError):
        return {"error": "curve_smooth recibió puntos, iterations o strength inválidos."}
    if iterations < 1 or iterations > 64:
        return {"error": "iterations de curve_smooth debe estar entre 1 y 64."}
    if not math.isfinite(strength) or strength <= 0.0 or strength > 1.0:
        return {"error": "strength de curve_smooth debe cumplir 0 < strength ≤ 1."}
    if len(source) < 2 or any(len(point) != 3 for point in source):
        return {"error": "curve_smooth necesita una polilínea XYZ de al menos dos puntos."}
    if any(not all(math.isfinite(value) for value in point) for point in source):
        return {"error": "curve_smooth recibió una coordenada no finita."}
    if any(math.dist(a, b) < 1e-6 for a, b in zip(source, source[1:])):
        return {"error": "curve_smooth no admite puntos consecutivos coincidentes."}

    output = source
    if len(source) >= 3:
        for _ in range(iterations):
            previous = output
            current = []
            for index, point in enumerate(previous):
                if index == 0:
                    target = point if preserve_ends else tuple(
                        (point[axis] + previous[1][axis]) * 0.5 for axis in range(3))
                elif index == len(previous) - 1:
                    target = point if preserve_ends else tuple(
                        (previous[-2][axis] + point[axis]) * 0.5 for axis in range(3))
                else:
                    target = tuple(
                        (previous[index - 1][axis] + previous[index + 1][axis]) * 0.5
                        for axis in range(3))
                current.append(tuple(
                    point[axis] + (target[axis] - point[axis]) * strength
                    for axis in range(3)))
            output = tuple(current)

    length = sum(math.dist(a, b) for a, b in zip(output, output[1:]))
    return {"points": output, "length": length,
            "info": (f"{len(output)} puntos · {iterations} pasadas × {strength:g} · "
                     f"extremos {'fijos' if preserve_ends else 'libres'}")}


def fuse_collinear_points(points, *, angle_tolerance: float = 1.0,
                          distance_tolerance: float = 0.01) -> dict:
    """Quita puntos co-localizados o colineales sin mover los extremos del recorrido."""
    try:
        angle_tolerance = float(angle_tolerance)
        distance_tolerance = float(distance_tolerance)
        source = tuple(tuple(float(value) for value in point) for point in points)
    except (TypeError, ValueError, OverflowError):
        return {"error": "curve_fuse_collinear recibió puntos o tolerancias inválidos."}
    if not math.isfinite(angle_tolerance) or not 0.0 <= angle_tolerance <= 90.0:
        return {"error": "angle_tolerance debe estar entre 0 y 90 grados."}
    if not math.isfinite(distance_tolerance) or not 0.0 <= distance_tolerance <= 100.0:
        return {"error": "distance_tolerance debe estar entre 0 y 100 cm."}
    if len(source) < 2 or any(len(point) != 3 for point in source):
        return {"error": "curve_fuse_collinear necesita una polilínea XYZ de al menos dos puntos."}
    if any(not all(math.isfinite(value) for value in point) for point in source):
        return {"error": "curve_fuse_collinear recibió una coordenada no finita."}
    source_length = sum(math.dist(a, b) for a, b in zip(source, source[1:]))
    if source_length < 1e-6:
        return {"error": "curve_fuse_collinear recibió una curva de longitud cero."}

    # Los extremos escritos por el autor son identidad. Sólo se descartan puntos interiores que
    # caen dentro de la tolerancia de su vecino; si el último está cerca, reemplaza al interior.
    spatial = [source[0]]
    for point in source[1:-1]:
        if math.dist(spatial[-1], point) > distance_tolerance:
            spatial.append(point)
    while len(spatial) > 1 and math.dist(spatial[-1], source[-1]) <= distance_tolerance:
        spatial.pop()
    spatial.append(source[-1])

    # Stack incremental: al quitar un punto vuelve a medir el nuevo triplete, por lo que una recta
    # de cualquier cantidad de muestras colapsa a sus dos extremos en una sola pasada determinista.
    fused = []
    for point in spatial:
        while len(fused) >= 2:
            start, middle = fused[-2], fused[-1]
            incoming = tuple(middle[axis] - start[axis] for axis in range(3))
            outgoing = tuple(point[axis] - middle[axis] for axis in range(3))
            len_in, len_out = math.dist(start, middle), math.dist(middle, point)
            if len_in < 1e-9 or len_out < 1e-9:
                fused.pop()
                continue
            cosine = sum(incoming[axis] * outgoing[axis] for axis in range(3)) / (len_in * len_out)
            angle = math.degrees(math.acos(min(1.0, max(-1.0, cosine))))
            if angle > angle_tolerance:
                break
            fused.pop()
        fused.append(point)

    output = tuple(fused)
    removed = len(source) - len(output)
    length = sum(math.dist(a, b) for a, b in zip(output, output[1:]))
    if len(output) < 2 or length < 1e-6:
        return {"error": "curve_fuse_collinear colapsó la curva a longitud cero."}
    return {"points": output, "length": length, "removed": removed,
            "info": (f"{len(source)}→{len(output)} puntos · quitó {removed} · "
                     f"ángulo ≤ {angle_tolerance:g}°")}


def subdivide_points(points, *, mode: str = "distance", distance: float = 100.0,
                     count: int = 1) -> dict:
    """Inserta muestras en cada segmento conservando exactamente todos los vértices originales."""
    try:
        mode = str(mode or "").strip().lower()
        distance, count = float(distance), int(count)
        source = tuple(tuple(float(value) for value in point) for point in points)
    except (TypeError, ValueError, OverflowError):
        return {"error": "curve_subdivide recibió puntos o parámetros inválidos."}
    if mode not in {"distance", "count"}:
        return {"error": "mode de curve_subdivide debe ser distance o count."}
    if not math.isfinite(distance) or not 0.01 <= distance <= 1_000_000.0:
        return {"error": "distance de curve_subdivide debe estar entre 0.01 y 1000000 cm."}
    if count < 1 or count > 64:
        return {"error": "count de curve_subdivide debe estar entre 1 y 64."}
    if len(source) < 2 or any(len(point) != 3 for point in source):
        return {"error": "curve_subdivide necesita una polilínea XYZ de al menos dos puntos."}
    if any(not all(math.isfinite(value) for value in point) for point in source):
        return {"error": "curve_subdivide recibió una coordenada no finita."}
    lengths = tuple(math.dist(a, b) for a, b in zip(source, source[1:]))
    if any(length < 1e-6 for length in lengths):
        return {"error": "curve_subdivide no admite puntos consecutivos coincidentes."}

    divisions = tuple(
        count + 1 if mode == "count" else max(1, int(math.ceil(length / distance)))
        for length in lengths)
    output_count = 1 + sum(divisions)
    if output_count > 4096:
        return {"error": "curve_subdivide no puede producir más de 4096 puntos por recorrido."}

    output = [source[0]]
    for start, end, segment_divisions in zip(source, source[1:], divisions):
        for index in range(1, segment_divisions + 1):
            if index == segment_divisions:
                output.append(end)
            else:
                alpha = index / segment_divisions
                output.append(tuple(
                    start[axis] + (end[axis] - start[axis]) * alpha for axis in range(3)))
    result = tuple(output)
    inserted = len(result) - len(source)
    max_segment = max(math.dist(a, b) for a, b in zip(result, result[1:]))
    return {"points": result, "length": sum(lengths), "inserted": inserted,
            "max_segment": max_segment,
            "info": (f"{len(source)}→{len(result)} puntos · insertó {inserted} · "
                     + (f"máx. {max_segment:.1f} cm" if mode == "distance"
                        else f"{count} por segmento"))}


def offset_points(points, *, distance: float = 100.0, side: str = "left",
                  plane: str = "xy", join: str = "miter",
                  miter_limit: float = 4.0) -> dict:
    """Desplaza una polilínea en uno de los planos principales.

    ``miter`` conserva un punto por esquina mientras su extensión no supere ``miter_limit`` veces
    la distancia. Al superar el límite cae a bevel: el presupuesto nunca queda implícito.
    """
    try:
        distance, miter_limit = float(distance), float(miter_limit)
        source = tuple(tuple(float(value) for value in point) for point in points)
        side, plane, join = (str(value or "").strip().lower() for value in (side, plane, join))
    except (TypeError, ValueError, OverflowError):
        return {"error": "curve_offset recibió puntos o parámetros inválidos."}
    if not math.isfinite(distance) or not 0.01 <= distance <= 1_000_000.0:
        return {"error": "distance de curve_offset debe estar entre 0.01 y 1000000 cm."}
    if side not in {"left", "right"}:
        return {"error": "side de curve_offset debe ser left o right."}
    if plane not in {"xy", "xz", "yz"}:
        return {"error": "plane de curve_offset debe ser xy, xz o yz."}
    if join not in {"miter", "bevel"}:
        return {"error": "join de curve_offset debe ser miter o bevel."}
    if not math.isfinite(miter_limit) or not 1.0 <= miter_limit <= 100.0:
        return {"error": "miter_limit de curve_offset debe estar entre 1 y 100."}
    if len(source) < 2 or any(len(point) != 3 for point in source):
        return {"error": "curve_offset necesita una polilínea XYZ de al menos dos puntos."}
    if any(not all(math.isfinite(value) for value in point) for point in source):
        return {"error": "curve_offset recibió una coordenada no finita."}

    axes = {"xy": (0, 1, 2), "xz": (0, 2, 1), "yz": (1, 2, 0)}[plane]
    axis_u, axis_v, axis_other = axes
    closed = len(source) >= 4 and math.dist(source[0], source[-1]) < 1e-6
    vertices = source[:-1] if closed else source
    if len(vertices) < (3 if closed else 2):
        return {"error": "curve_offset recibió un recorrido cerrado degenerado."}

    projected = tuple((point[axis_u], point[axis_v]) for point in vertices)
    pairs = ((index, (index + 1) % len(vertices)) for index in range(len(vertices))) if closed \
        else ((index, index + 1) for index in range(len(vertices) - 1))
    directions = []
    for start_index, end_index in pairs:
        start, end = projected[start_index], projected[end_index]
        delta = (end[0] - start[0], end[1] - start[1])
        length = math.hypot(*delta)
        if length < 1e-6:
            return {"error": f"curve_offset tiene un segmento de longitud cero en el plano {plane}."}
        directions.append((delta[0] / length, delta[1] / length))

    signed_distance = distance if side == "left" else -distance

    def normal(direction):
        return (-direction[1], direction[0])

    def lifted(index, planar):
        result = [0.0, 0.0, 0.0]
        result[axis_u], result[axis_v] = planar
        result[axis_other] = vertices[index][axis_other]
        return tuple(result)

    output = []
    # De qué vértice del eje nació cada punto emitido. `mesh_ribbon` lo necesita para conocer el eje
    # REAL de cada muestra: el punto medio entre bordes deja de servir cuando un miter empuja uno de
    # los dos muy lejos. Un bevel emite dos puntos con el mismo origen, a propósito.
    origins = []
    bevels = 0
    for index, point in enumerate(projected):
        if not closed and index == 0:
            n = normal(directions[0])
            output.append(lifted(index, (
                point[0] + n[0] * signed_distance,
                point[1] + n[1] * signed_distance)))
            origins.append(index)
            continue
        if not closed and index == len(projected) - 1:
            n = normal(directions[-1])
            output.append(lifted(index, (
                point[0] + n[0] * signed_distance,
                point[1] + n[1] * signed_distance)))
            origins.append(index)
            continue

        previous_direction = directions[index - 1]
        next_direction = directions[index % len(directions)]
        previous_normal, next_normal = normal(previous_direction), normal(next_direction)
        summed = (previous_normal[0] + next_normal[0], previous_normal[1] + next_normal[1])
        summed_length = math.hypot(*summed)
        denominator = 0.0
        if summed_length >= 1e-9:
            bisector = (summed[0] / summed_length, summed[1] / summed_length)
            denominator = bisector[0] * previous_normal[0] + bisector[1] * previous_normal[1]
        ratio = math.inf if abs(denominator) < 1e-9 else abs(1.0 / denominator)
        use_miter = join == "miter" and ratio <= miter_limit
        if use_miter:
            scale = signed_distance / denominator
            output.append(lifted(index, (
                point[0] + bisector[0] * scale,
                point[1] + bisector[1] * scale)))
            origins.append(index)
        else:
            bevels += 1
            for n in (previous_normal, next_normal):
                output.append(lifted(index, (
                    point[0] + n[0] * signed_distance,
                    point[1] + n[1] * signed_distance)))
                origins.append(index)
        if len(output) > 4096:
            return {"error": "curve_offset no puede producir más de 4096 puntos por recorrido."}

    if closed:
        output.append(output[0])
        origins.append(origins[0])
    result = tuple(output)
    length = sum(math.dist(a, b) for a, b in zip(result, result[1:]))
    return {"points": result, "length": length, "closed": closed, "bevels": bevels,
            "origins": tuple(origins),
            "info": (f"{len(source)}→{len(result)} puntos · {distance:g} cm {side} · "
                     f"{plane.upper()} · {join} · {bevels} bevel")}
