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


def asentar_tanda(piezas, soportes, *, suelos=None, tol: float = geometry.TOL_CM) -> list[dict]:
    """Asienta `piezas` sobre `soportes`, sobre el SUELO y sobre sí mismas. Devuelve un dict por
    pieza, en el orden de ENTRADA: `{"caida", "soporte", "apoyada", "sobre_hermana", "pieza"}`.

    `suelos[i]` = `(z, nombre)` del suelo bajo la pieza `i`, o None. Va aparte de `soportes` porque
    un AABB **no puede describir un terreno**: medido en un landscape de 121 m con lomas, su caja
    dice `top = 3 m` y las tres piezas soltadas quedaron las tres a esa cota, flotando sobre el
    suelo real. La altura del terreno bajo CADA pieza sólo la sabe un raycast, y eso lo hace el
    adaptador — acá entra ya medida, como un dato.

    `caida` > 0 = flotaba y bajó; < 0 = estaba clavada o se apiló y subió; `apoyada` False = no
    había nada debajo (queda donde estaba, y el oráculo de aguas abajo lo dirá — acá no se inventa
    un piso).
    """
    # La escenografía de fondo NO es piso. Soltando desde arriba, la SkySphere solapa en XY con
    # todo y su top está a 16 km: sin este filtro la tanda entera aterrizaría en el cielo. La regla
    # del centro la descartaba de casualidad; acá hay que decirlo.
    apilables = [s for s in soportes if not geometry.es_fondo(s.aabb)]
    # Para poder decir después cuántas quedaron ENCIMA DE OTRA PIEZA de la tanda, que es la
    # diferencia visible entre una pila y una capa.
    nombres_tanda = {p.nombre for p in piezas}
    salida = [{"caida": 0.0, "soporte": None, "apoyada": False, "sobre_hermana": False,
               "pieza": p} for p in piezas]

    for i in orden_de_caida(piezas):
        p = piezas[i]
        # `desde_arriba`: la tanda se SUELTA, no se evalúa donde está. Es lo que hace que dos
        # piezas nacidas a la misma cota se apilen en vez de descartarse mutuamente y quedar
        # cruzadas — el caso normal del pincel, donde el scatter las deja todas sobre el piso.
        z_top, etiqueta = geometry.soporte_top(p.aabb, apilables, tol, desde_arriba=True)
        # El suelo medido gana si está MÁS ALTO que cualquier hermana: una loma que sube por debajo
        # sostiene antes que una pieza que quedó en el valle.
        suelo = None if suelos is None else suelos[i]
        if suelo is not None and (z_top is None or suelo[0] > z_top):
            z_top, etiqueta = suelo[0], suelo[1]
        if z_top is None:
            # Sin piso no se mueve, pero SÍ sigue siendo soporte: algo que caiga encima tiene que
            # apoyarse en ella igual. Descartarla haría que la de arriba la atraviese.
            apilables.append(p)
            continue
        caida = base_de(p.aabb) - z_top
        movida = bajar(p, caida)
        salida[i] = {"caida": round(caida, 1), "soporte": etiqueta, "apoyada": True,
                     "sobre_hermana": etiqueta in nombres_tanda, "pieza": movida}
        apilables.append(movida)

    return salida


def resumen(resultados) -> str:
    """Renglón para el veredicto.

    NO habla de «caída media»: soltando una tanda, la mitad de los movimientos son hacia ARRIBA
    —una pieza que se apila sobre otra sube—, y promediar subidas con bajadas daba «caída media
    -60cm», que no significa nada. Lo que se quiere saber es otra cosa: **cuántas quedaron encima
    de otra pieza**, que es la diferencia visible entre una pila y una capa.
    """
    if not resultados:
        return "ASENTAR \u2014 nada que soltar"
    apoyadas = [r for r in resultados if r["apoyada"]]
    sin_piso = len(resultados) - len(apoyadas)
    if not apoyadas:
        return f"ASENTAR \u2717 \u2014 ninguna de {len(resultados)} encontr\u00f3 piso debajo"
    apiladas = sum(1 for r in apoyadas if r.get("sobre_hermana"))
    corrimiento = max(abs(r["caida"]) for r in apoyadas)
    cola = f" \u00b7 {sin_piso} sin piso" if sin_piso else ""
    marca = "\u2717" if sin_piso else "\u2713"
    return (f"ASENTAR {marca} \u2014 {len(apoyadas)}/{len(resultados)} asentadas \u00b7 "
            f"{apiladas} apiladas sobre otra pieza \u00b7 "
            f"corrimiento m\u00e1x {corrimiento:.1f}cm{cola}")
