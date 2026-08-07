"""Asentar una TANDA de piezas — el núcleo del *physics paint*, sin Unreal.

`jam.physics.soltar` asienta UNA pieza contra lo que ya estaba en el nivel. Pintar es otra cosa: se
sueltan N piezas a la vez y **cada una es piso de la siguiente**. Sin eso, veinte rocas soltadas
sobre el mismo pozo terminan las veinte en el fondo, atravesadas entre sí; con eso, se apilan.

El orden importa y por eso no es el de la lista: se asienta **de abajo hacia arriba** (base más baja
primero). Es la única regla que hace que el resultado no dependa de en qué orden vinieron los
puntos — y un grafo tiene que dar lo mismo cada vez que corre. Con desempate por nombre, dos
corridas con los mismos puntos dan exactamente la misma pila.

Reusa `geometry.soporte_top` — la MISMA pregunta «¿qué hay debajo?» que ya contestan `physics.soltar`
y `oracle_physics.verificar`. Una segunda copia de esa regla se separaría en silencio.
"""

from __future__ import annotations

from . import geometry


def base_de(a: geometry.AABB) -> float:
    """Z de la cara inferior del AABB."""
    return a.origin.z - a.extent.z


def bajar(p: geometry.Pieza, caida: float) -> geometry.Pieza:
    """La misma pieza `caida` cm más abajo (negativo = sube). Devuelve una pieza NUEVA: son
    `namedtuple`, y mutar una que otro ya guardó como soporte sería un fantasma imposible de seguir."""
    a = p.aabb
    origen = geometry.Vec3(a.origin.x, a.origin.y, a.origin.z - caida)
    loc = geometry.Vec3(p.location.x, p.location.y, p.location.z - caida)
    return geometry.Pieza(p.nombre, geometry.AABB(origen, a.extent), loc, p.yaw)


def orden_de_caida(piezas) -> list[int]:
    """Índices de `piezas` ordenados como caerían: la de base más baja primero.

    Depende sólo del contenido, nunca del orden de entrada — de eso vive la reproducibilidad.
    """
    return sorted(range(len(piezas)),
                  key=lambda i: (base_de(piezas[i].aabb), piezas[i].nombre, i))


def asentar_tanda(piezas, soportes, *, tol: float = geometry.TOL_CM) -> list[dict]:
    """Asienta `piezas` sobre `soportes` **y sobre sí mismas**. Devuelve un dict por pieza, en el
    orden de ENTRADA: `{"caida", "soporte", "apoyada", "pieza"}`.

    `caida` > 0 = flotaba y bajó; < 0 = estaba clavada y subió; `apoyada` False = no había nada
    debajo (queda donde estaba, y el oráculo de aguas abajo lo dirá — acá no se inventa un piso).
    """
    apilables = list(soportes)
    salida = [{"caida": 0.0, "soporte": None, "apoyada": False, "pieza": p} for p in piezas]

    for i in orden_de_caida(piezas):
        p = piezas[i]
        z_top, etiqueta = geometry.soporte_top(p.aabb, apilables, tol)
        if z_top is None:
            # Sin piso no se mueve, pero SÍ sigue siendo soporte: algo que caiga encima tiene que
            # apoyarse en ella igual. Descartarla haría que la de arriba la atraviese.
            apilables.append(p)
            continue
        caida = base_de(p.aabb) - z_top
        movida = bajar(p, caida)
        salida[i] = {"caida": round(caida, 1), "soporte": etiqueta, "apoyada": True,
                     "pieza": movida}
        apilables.append(movida)

    return salida


def resumen(resultados) -> str:
    """Renglón para el veredicto: cuántas se asentaron, cuánto cayeron, cuántas quedaron sin piso."""
    if not resultados:
        return "ASENTAR — nada que soltar"
    apoyadas = [r for r in resultados if r["apoyada"]]
    sin_piso = len(resultados) - len(apoyadas)
    caidas = [r["caida"] for r in apoyadas]
    if not apoyadas:
        return f"ASENTAR ✗ — ninguna de {len(resultados)} encontró piso debajo"
    media = sum(caidas) / len(caidas)
    cola = f" · {sin_piso} sin piso" if sin_piso else ""
    return (f"ASENTAR ✓ — {len(apoyadas)}/{len(resultados)} asentadas · "
            f"caída media {media:.1f}cm, máx {max(caidas):.1f}cm{cola}")
