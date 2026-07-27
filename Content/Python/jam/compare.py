"""Oráculo de forma: mide una malla y la compara contra una referencia.

Nace de una pregunta concreta de Brian: «funciona, pero no genera el árbol que está en TreeGen; ¿cómo
verificamos dónde está el error?». TreeGen distribuye sus árboles YA horneados como StaticMesh
(`/TreeGen/Examples/Pine`, `Birch`…), así que existe una verdad de referencia contra la cual medir en
vez de mirar y opinar.

El módulo es PURO: recibe posiciones de vértices y conteos, no toca Unreal. El adaptador vive en
`mesh.py`, que sabe leer tanto una `DynamicMesh` del grafo como una `StaticMesh` de Content.

Lo que más discrimina no es el conteo de vértices sino el **perfil vertical**: qué fracción de la masa
vive en cada franja de altura. Dos árboles con el mismo total de vértices pero uno sin follaje arriba
tienen perfiles muy distintos, y el perfil dice *dónde* está la diferencia.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


FRANJAS = 8


@dataclass(frozen=True)
class Medida:
    """Firma de forma de una malla. Comparable entre una DynamicMesh y una StaticMesh."""

    vertices: int
    triangulos: int
    secciones: int
    alto: float
    ancho: float
    base_z: float
    perfil: tuple[float, ...]

    def como_dict(self) -> dict:
        return {
            "vertices": self.vertices, "triangulos": self.triangulos,
            "secciones": self.secciones, "alto": self.alto, "ancho": self.ancho,
            "base_z": self.base_z, "perfil": list(self.perfil),
        }


def medir(posiciones, *, triangulos: int, secciones: int, franjas: int = FRANJAS) -> Medida:
    """Convierte una nube de vértices en una firma comparable.

    `posiciones` es cualquier iterable de (x, y, z). El perfil se normaliza por altura relativa, así
    que dos árboles de tamaños distintos siguen siendo comparables en FORMA.
    """
    puntos = [(float(p[0]), float(p[1]), float(p[2])) for p in posiciones]
    if not puntos:
        raise ValueError("medir necesita al menos un vértice.")
    if franjas < 1:
        raise ValueError("franjas debe ser al menos 1.")
    if not all(math.isfinite(c) for p in puntos for c in p):
        raise ValueError("la malla contiene una coordenada no finita.")

    zs = [p[2] for p in puntos]
    z_min, z_max = min(zs), max(zs)
    alto = z_max - z_min
    ancho = max(
        max(p[0] for p in puntos) - min(p[0] for p in puntos),
        max(p[1] for p in puntos) - min(p[1] for p in puntos),
    )

    conteo = [0] * franjas
    for _x, _y, z in puntos:
        if alto <= 1e-6:
            conteo[0] += 1
            continue
        indice = int((z - z_min) / alto * franjas)
        conteo[min(indice, franjas - 1)] += 1
    total = float(len(puntos))
    perfil = tuple(c / total for c in conteo)

    return Medida(
        vertices=len(puntos), triangulos=int(triangulos), secciones=int(secciones),
        alto=alto, ancho=ancho, base_z=z_min, perfil=perfil,
    )


def _razon(generada: float, referencia: float) -> float:
    """gen/ref, acotado. 1.0 = idéntico. 0 y 0 se consideran iguales."""
    if abs(referencia) < 1e-9:
        return 1.0 if abs(generada) < 1e-9 else float("inf")
    return generada / referencia


def distancia_perfil(a, b) -> float:
    """Distancia de variación total entre dos perfiles: 0 = misma silueta, 1 = disjuntos."""
    if len(a) != len(b):
        raise ValueError("los perfiles deben tener la misma cantidad de franjas.")
    return sum(abs(x - y) for x, y in zip(a, b)) / 2.0


# Cuánto se puede desviar cada métrica antes de considerarla un problema. Son razones gen/ref:
# 0.30 significa «hasta un 30% arriba o abajo». Las mallas procedurales nunca coinciden exacto; lo
# que importa es el ORDEN de magnitud y la silueta.
TOLERANCIAS = {"alto": 0.30, "ancho": 0.35, "vertices": 0.50, "triangulos": 0.50}
TOLERANCIA_PERFIL = 0.15


def comparar(generada: Medida, referencia: Medida, *, tolerancias: dict | None = None,
             tolerancia_perfil: float = TOLERANCIA_PERFIL) -> dict:
    """Diff métrica a métrica, ordenado por gravedad.

    Devuelve {ok, filas, peor, texto}. `filas` trae, por métrica, el valor de cada lado, la razón y
    si pasa. Se ordena por desvío para que lo primero que se lee sea lo que más separa a las dos
    mallas.
    """
    limites = dict(TOLERANCIAS)
    limites.update(tolerancias or {})
    filas = []

    for nombre in ("alto", "ancho", "vertices", "triangulos"):
        g = float(getattr(generada, nombre))
        r = float(getattr(referencia, nombre))
        razon = _razon(g, r)
        desvio = abs(razon - 1.0) if math.isfinite(razon) else float("inf")
        filas.append({
            "metrica": nombre, "generada": g, "referencia": r, "razon": razon,
            "desvio": desvio, "limite": limites[nombre], "ok": desvio <= limites[nombre],
        })

    # Las secciones son estructurales: 1 sección donde la referencia tiene 2 significa que falta un
    # material entero (en un árbol, típicamente el follaje). No admite tolerancia.
    filas.append({
        "metrica": "secciones", "generada": float(generada.secciones),
        "referencia": float(referencia.secciones),
        "razon": _razon(generada.secciones, referencia.secciones),
        "desvio": 0.0 if generada.secciones == referencia.secciones else 1.0,
        "limite": 0.0, "ok": generada.secciones == referencia.secciones,
    })

    distancia = distancia_perfil(generada.perfil, referencia.perfil)
    filas.append({
        "metrica": "perfil", "generada": distancia, "referencia": 0.0, "razon": distancia,
        "desvio": distancia, "limite": tolerancia_perfil, "ok": distancia <= tolerancia_perfil,
    })

    filas.sort(key=lambda f: (f["ok"], -f["desvio"]))
    fallan = [f for f in filas if not f["ok"]]
    peor = fallan[0]["metrica"] if fallan else None
    return {"ok": not fallan, "filas": filas, "peor": peor,
            "texto": reporte(filas, generada, referencia)}


def _fmt(nombre: str, valor: float) -> str:
    if nombre in ("vertices", "triangulos", "secciones"):
        return f"{int(valor)}"
    if nombre == "perfil":
        return f"{valor:.3f}"
    return f"{valor:.0f}"


def reporte(filas, generada: Medida, referencia: Medida) -> str:
    lineas = []
    for f in filas:
        marca = "✓" if f["ok"] else "✗"
        nombre = f["metrica"]
        if nombre == "perfil":
            lineas.append(
                f"  {marca} perfil        distancia {f['generada']:.3f} "
                f"(límite {f['limite']:.2f})")
            continue
        razon = f["razon"]
        r = "∞" if not math.isfinite(razon) else f"{razon:.2f}×"
        lineas.append(
            f"  {marca} {nombre:<12} {_fmt(nombre, f['generada']):>8} vs "
            f"{_fmt(nombre, f['referencia']):>8}  ({r})")

    franjas = len(generada.perfil)
    lineas.append(f"  masa por franja de altura (de base a copa, {franjas} franjas):")
    lineas.append("    generada    " + " ".join(f"{v * 100:4.0f}%" for v in generada.perfil))
    lineas.append("    referencia  " + " ".join(f"{v * 100:4.0f}%" for v in referencia.perfil))
    return "\n".join(lineas)
