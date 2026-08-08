"""Geometría pura de Jam — el CEREBRO sin Unreal.

AABBs como DATOS + la matemática del oráculo (penetración por regla del eje separador, escenografía
de fondo). **CERO `import unreal`**: corre en cualquier Python, testeable sin el editor, y sobrevive a
los cambios de motor (UE6/Scene Graph deprecan Actors). El adaptador `jam.ue` extrae estos datos del
motor; los oráculos razonan sobre estos datos. Esta es la línea de defensa anti-lock-in.
"""

from __future__ import annotations

from collections import namedtuple

Vec3 = namedtuple("Vec3", "x y z")
AABB = namedtuple("AABB", "origin extent")   # origin, extent: Vec3, en cm (extent = semi-extensión)
# Pieza = lo MÍNIMO que un oráculo necesita de un actor, como DATO puro. `jam.ue` la extrae del motor.
Pieza = namedtuple("Pieza", "nombre aabb location yaw")   # location: Vec3 (pivote), yaw: float (grados)

TOL_CM = 1.0                # menos que esto = tocándose, no interpenetrando
MAX_VECINO_CM = 50000.0     # semi-extensión > 500 m en un eje = escenografía de fondo (envuelve el mapa)


def penetracion(a: AABB, b: AABB, tol: float = TOL_CM) -> float:
    """Profundidad efectiva tras descontar la tolerancia; 0 si no supera el contacto permitido."""
    solapes = []
    for ca, ea, cb, eb in (
        (a.origin.x, a.extent.x, b.origin.x, b.extent.x),
        (a.origin.y, a.extent.y, b.origin.y, b.extent.y),
        (a.origin.z, a.extent.z, b.origin.z, b.extent.z),
    ):
        solape = (ea + eb) - abs(ca - cb)
        if solape <= tol:
            return 0.0
        solapes.append(solape)
    return min(solapes) - tol


def es_fondo(a: AABB, max_cm: float = MAX_VECINO_CM) -> bool:
    """True si el AABB es escenografía de fondo (descomunal: SkySphere, atmósfera). La
    interpenetración sólo tiene sentido entre piezas de escala comparable."""
    e = a.extent
    return max(e.x, e.y, e.z) > max_cm


def volumen(a: AABB) -> float:
    e = a.extent
    return e.x * e.y * e.z


def soporte_top(a: AABB, soportes, tol: float = TOL_CM, *, desde_arriba: bool = False):
    """Top del AABB del soporte más alto que solapa a `a` en XY.
    `soportes` = lista de Pieza (que NO debe incluir a la propia). Devuelve (z_top, nombre) o (None, None).

    Son DOS preguntas distintas y por eso hay una bandera:

    * Por defecto —«¿qué hay debajo de esto, donde está?»— un candidato que asoma por encima del
      CENTRO de `a` no cuenta: no está debajo, está al lado o alrededor. Sin esa regla, una pieza
      parada junto a una pared se teletransportaría al techo de la pared.
    * `desde_arriba` —«esto viene CAYENDO; ¿dónde aterriza?»— cualquier cosa que solape en XY es
      piso, por alta que sea. Es la única forma de que una tanda soltada a la MISMA cota se apile:
      con la regla del centro, cada pieza asoma sobre el centro de su vecina, las dos se descartan
      mutuamente, ninguna sube y quedan las dos cruzadas. Medido con barriles de 65×65×80 a 30 cm:
      24 piezas, caída 0.0 cm y 99 pares interpenetrados.

    ⚠ Con `desde_arriba` el llamador DEBE filtrar la escenografía de fondo (`es_fondo`): la
    SkySphere solapa en XY con todo y su top está a 16 km. La regla del centro la descartaba de
    casualidad; sin ella, sin filtro, todo aterrizaría en el cielo.
    """
    mejor = None
    for s in soportes:
        os_, es = s.aabb.origin, s.aabb.extent
        if desde_arriba:
            # El CENTRO DE MASA tiene que quedar sobre el soporte. Rozarlo no alcanza: en el mundo
            # una pieza apoyada de refilón se voltea y sigue cayendo.
            #
            # Con «cualquier solape» alcanzaba, y el resultado era una CHIMENEA: medido con 24
            # piezas poisson a 30 cm, 23 se apilaban en una torre de 6,5 m y sólo una tocaba el
            # piso. Con el centro, 18 quedan en el piso y 6 encima — un montón, que es lo que uno
            # pinta.
            if abs(os_.x - a.origin.x) > es.x + tol or abs(os_.y - a.origin.y) > es.y + tol:
                continue
        else:
            if abs(os_.x - a.origin.x) > (es.x + a.extent.x) \
                    or abs(os_.y - a.origin.y) > (es.y + a.extent.y):
                continue  # no solapa en XY → no es soporte
        s_top = os_.z + es.z
        if not desde_arriba and s_top > a.origin.z + tol:
            continue  # el soporte asoma por encima del centro → no está "debajo"
        if mejor is None or s_top > mejor[0]:
            mejor = (s_top, s.nombre)
    return mejor if mejor else (None, None)
