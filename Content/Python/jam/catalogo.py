"""Catálogo de medidas — los oráculos escritos a mano, re-expresados como declaraciones.

Esto es la prueba de que el patrón sirve: **las mismas preguntas, el mismo veredicto**, pero
declaradas en vez de programadas. `tests/test_medida.py` lo verifica por diferencia contra
`oracle_placement` y `oracle_snap` sobre cientos de casos generados.

Lo que se ganó al traducir, y no es poco:

  · **Aparecieron dos umbrales escondidos.** `bounds_ok` era `volumen(aabb) > 1e-3` con el `1e-3`
    enterrado en el cuerpo de la función. Ahora es un dato con defensa escrita.
  · **`en_grilla` mezclaba dos preguntas.** El oráculo de snap devolvía un solo booleano para
    «posición en la grilla» Y «yaw en su paso». Acá son dos medidas, así que el informe dice CUÁL de
    las dos falló en vez de un «no» sin causa.
  · **Los puntos ciegos quedaron escritos.** Los AABB no ven la malla real ni la oclusión visual, y
    eso no estaba dicho en ningún lado — se sabía, que es distinto de estar declarado.

Falta traducir: pared (continuidad y cobertura), scatter, physics, reemplazo, espacio. Se hacen
cuando el módulo se mude al paquete `oraculo` aparte, que es su lugar definitivo.
"""

from __future__ import annotations

from . import geometry
from .medida import Medida, Umbral

# ---- colocación ----------------------------------------------------------------

def _volumen(ev) -> float:
    return geometry.volumen(ev["pieza"].aabb)


def _vecinas(ev):
    """Las otras piezas que cuentan: la escenografía de fondo se ignora (una SkySphere «contiene» a
    todo y haría que cualquier cosa interpenetre)."""
    return [o for o in ev["otras"] if not geometry.es_fondo(o.aabb)]


def _penetracion_maxima(ev) -> float:
    a = ev["pieza"].aabb
    tol = ev.get("tol", geometry.TOL_CM)
    return max((geometry.penetracion(a, o.aabb, tol) for o in _vecinas(ev)), default=0.0)


def _piezas_clavadas(ev):
    a = ev["pieza"].aabb
    tol = ev.get("tol", geometry.TOL_CM)
    salida = []
    for o in _vecinas(ev):
        d = geometry.penetracion(a, o.aabb, tol)
        if d > 0.0:
            salida.append(f"{o.nombre}:{d:.1f}cm")
    return salida


BOUNDS = Medida(
    id="colocacion.bounds",
    requiere=("pieza",),
    mide=_volumen,
    unidad="cm3",
    umbral=Umbral(">", 1e-3, porque="una malla vacía o degenerada da volumen ~0 y la colocación "
                                   "es inútil aunque no choque con nada"),
    alcance="volumen del AABB. NO ve si la malla está partida, invertida, ni si tiene "
            "geometría adentro del bounding box",
    etiquetas=("colocacion", "sanidad"),
)

INTERPENETRACION = Medida(
    id="colocacion.interpenetracion",
    requiere=("pieza", "otras"),
    mide=_penetracion_maxima,
    unidad="cm",
    umbral=Umbral("<=", 0.0, porque="`penetracion()` ya descuenta la tolerancia de contacto "
                                    "(TOL_CM), así que tocarse da 0 y clavarse da >0"),
    testigos=_piezas_clavadas,
    alcance="solape de AABB entre piezas de escala comparable. NO ve: solape de la MALLA real "
            "(dos AABB pueden solapar sin que los triángulos se toquen, y al revés en mallas "
            "cóncavas), oclusión visual, ni si la pieza quedó flotando",
    etiquetas=("colocacion", "kitbash"),
)

# ---- snap ----------------------------------------------------------------------

def _desvio_de(v: float, paso: float) -> float:
    return abs(v - round(v / paso) * paso)


def _desvio_grilla(ev) -> float:
    loc = ev["pieza"].location
    grilla = ev.get("grilla", 100.0)
    return max(_desvio_de(getattr(loc, e), grilla) for e in ("x", "y", "z"))


def _ejes_fuera(ev):
    loc = ev["pieza"].location
    grilla = ev.get("grilla", 100.0)
    tol = ev.get("tol", geometry.TOL_CM)
    return [f"{e}={_desvio_de(getattr(loc, e), grilla):.1f}"
            for e in ("x", "y", "z") if _desvio_de(getattr(loc, e), grilla) > tol]


GRILLA = Medida(
    id="snap.grilla",
    requiere=("pieza",),
    mide=_desvio_grilla,
    unidad="cm",
    umbral=Umbral("<=", geometry.TOL_CM, porque="por debajo de 1 cm el desvío no se ve y no "
                                                "produce juntas visibles"),
    testigos=_ejes_fuera,
    alcance="desvío del PIVOTE respecto de la grilla. NO ve si el pivote está donde debería estar "
            "dentro de la malla — un pivote mal puesto puede estar perfecto en la grilla y la "
            "pieza igual quedar corrida",
    etiquetas=("snap",),
)

YAW = Medida(
    id="snap.yaw",
    requiere=("pieza",),
    mide=lambda ev: _desvio_de(ev["pieza"].yaw, ev.get("paso_yaw", 90.0)),
    unidad="grados",
    umbral=Umbral("<=", 0.5, porque="medio grado en una pieza de 4 m da ~3 cm en la punta: el "
                                    "límite donde una junta empieza a abrirse a la vista"),
    alcance="sólo el YAW contra su paso. NO ve pitch ni roll, ni si la pieza está orientada "
            "hacia el lado correcto (0° y 180° son igual de válidos para esta medida)",
    etiquetas=("snap",),
)


COLOCACION = (BOUNDS, INTERPENETRACION)
SNAP = (GRILLA, YAW)
TODAS = COLOCACION + SNAP
