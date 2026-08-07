"""Oráculo de SCATTER — Dash esparce; Jam verifica que el reparto sea sano.

Cuatro preguntas deterministas sobre un conjunto de instancias esparcidas:
  1. ¿Cantidad?  — ¿se colocaron las que se pidieron? (una región saturada deja faltantes).
  2. ¿Contención? — ¿el centro de cada instancia cae dentro de la región objetivo?
  3. ¿Sin interpenetrar? — ¿ningún par de instancias está clavado? (reusa el AABB de colocación).
  4. ¿Cobertura? — ¿el reparto cubre la región o quedó amontonado?
     (fracción de celdas de una grilla NxN sobre la región que contienen ≥1 instancia).

Reusa `jam.oracle_placement` para el AABB y la profundidad de interpenetración — una sola fuente
de verdad para "dos piezas clavadas".
"""

from __future__ import annotations

from . import geometry


def _centro_xy(pieza) -> tuple[float, float]:
    o = pieza.aabb.origin
    return o.x, o.y


def verificar(
    piezas: list,
    centro: tuple[float, float],
    semi: tuple[float, float],
    cantidad_pedida: int,
    *,
    grilla: int = 3,
    cobertura_min: float = 0.6,
    tol: float = geometry.TOL_CM,
) -> dict:
    """Veredicto del scatter sobre `piezas` (lista de geometry.Pieza): cantidad, instancias fuera de
    región, pares que interpenetran, cobertura."""
    n = len(piezas)
    cx, cy = centro
    sx, sy = semi

    fuera = []
    for p in piezas:
        x, y = _centro_xy(p)
        if abs(x - cx) > sx + tol or abs(y - cy) > sy + tol:
            fuera.append(p.nombre)

    choques = []
    for i in range(len(piezas)):
        for j in range(i + 1, len(piezas)):
            d = geometry.penetracion(piezas[i].aabb, piezas[j].aabb, tol)
            if d > 0.0:
                choques.append((piezas[i].nombre, piezas[j].nombre, round(d, 1)))

    celdas = set()
    if sx > 0 and sy > 0:
        for p in piezas:
            x, y = _centro_xy(p)
            gx = min(grilla - 1, max(0, int((x - (cx - sx)) / (2 * sx) * grilla)))
            gy = min(grilla - 1, max(0, int((y - (cy - sy)) / (2 * sy) * grilla)))
            celdas.add((gx, gy))
    cobertura = len(celdas) / (grilla * grilla) if grilla else 0.0

    return {
        "cantidad": n,
        "cantidad_ok": n == cantidad_pedida,
        "fuera": fuera,
        "interpenetra": choques,
        "cobertura": round(cobertura, 3),
        "cobertura_ok": cobertura >= cobertura_min,
    }


def contra_la_escena(piezas: list, existentes: list, *, tol: float = geometry.TOL_CM) -> dict:
    """Segundo chequeo: cuántas de las piezas nuevas pisan algo que YA ESTABA en la escena.

    El de arriba mide la TANDA contra sí misma, y eso deja pasar el caso peor: dos scatter seguidos
    con los mismos parámetros caen exactamente uno encima del otro y el oráculo informa «0 clavados»
    —porque dentro de cada tanda, efectivamente, nadie se pisa—. Medir la propia tanda y llamarlo
    veredicto es el oráculo haciéndose trampa al solitario.

    No es un error: colocar encima de algo puede ser lo que uno quiere. Por eso sale como AVISO
    (amarillo) y no como ✗.
    """
    # La escenografía de fondo NO cuenta: la SkySphere envuelve el mapa entero, así que TODA pieza
    # colocada está «adentro» de ella. Sin este filtro el aviso saltaba las 24 de 24 veces con
    # penetraciones de 16 km, y un aviso que salta siempre no lo lee nadie. Es el mismo filtro que
    # `oracle_placement.verificar` ya aplicaba — faltaba acá, no es una regla nueva.
    reales = [v for v in existentes if not geometry.es_fondo(v.aabb)]
    pisadas = []
    for nueva in piezas:
        for vieja in reales:
            d = geometry.penetracion(nueva.aabb, vieja.aabb, tol)
            if d > 0.0:
                pisadas.append((nueva.nombre, vieja.nombre, round(d, 1)))
                break     # con una alcanza: lo que importa es CUÁNTAS piezas nuevas pisan algo
    return {
        "existentes": len(reales),
        "pisadas": pisadas,
        "limpias": len(piezas) - len(pisadas),
    }


def texto_contra_la_escena(r: dict, colocadas: int) -> str:
    """El renglón del segundo chequeo. Vacío si no había nada con qué chocar."""
    if not r["existentes"]:
        return ""
    if not r["pisadas"]:
        return (f"  \u2713 ninguna de las {colocadas} pisa algo de lo que ya estaba "
                f"({r['existentes']} pieza(s) en la zona)")
    muestra = "; ".join(f"{a}\u00d7{b} ({d}cm)" for a, b, d in r["pisadas"][:3])
    extra = "" if len(r["pisadas"]) <= 3 else f" (+{len(r['pisadas']) - 3} m\u00e1s)"
    return (f"  \u26a0 {colocadas} colocados \u00b7 {len(r['pisadas'])} pisados contra lo que ya "
            f"estaba: {muestra}{extra}")


def es_ok(r: dict) -> bool:
    return r["cantidad_ok"] and not r["fuera"] and not r["interpenetra"] and r["cobertura_ok"]


def verificar_texto(
    piezas: list,
    centro: tuple[float, float],
    semi: tuple[float, float],
    cantidad_pedida: int,
    *,
    existentes: list | None = None,
    **kw,
) -> str:
    """Veredicto en DOS pasos: la tanda contra sí misma, y después contra la escena.

    Los dos hacen falta y miden cosas distintas. El primero dice si el reparto está bien hecho; el
    segundo, si además convive con lo que ya había. Un scatter puede ser impecable y estar
    íntegramente encima de otro.
    """
    r = verificar(piezas, centro, semi, cantidad_pedida, **kw)
    lineas = [f"SCATTER · {r['cantidad']}/{cantidad_pedida} instancias · cobertura {int(r['cobertura'] * 100)}%"]
    if not r["cantidad_ok"]:
        lineas.append(f"  ✗ cantidad: faltan {cantidad_pedida - r['cantidad']} (región saturada)")
    if r["fuera"]:
        lineas.append(f"  ✗ fuera de región: {', '.join(r['fuera'])}")
    if r["interpenetra"]:
        muestra = "; ".join(f"{a}×{b} ({d}cm)" for a, b, d in r["interpenetra"][:4])
        extra = "" if len(r["interpenetra"]) <= 4 else f" (+{len(r['interpenetra']) - 4} más)"
        lineas.append(f"  ✗ interpenetran {len(r['interpenetra'])} pares: {muestra}{extra}")
    if not r["cobertura_ok"]:
        lineas.append(f"  ✗ cobertura {int(r['cobertura'] * 100)}% < mínimo — reparto amontonado")
    if es_ok(r):
        lineas.append("  ✓ REPARTO SANO — cantidad, contenido, sin clavarse, bien cubierto")
    if existentes:
        renglon = texto_contra_la_escena(contra_la_escena(piezas, existentes), len(piezas))
        if renglon:
            lineas.append(renglon)
    return "\n".join(lineas)
