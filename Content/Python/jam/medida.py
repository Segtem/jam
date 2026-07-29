"""El núcleo declarativo del oráculo — PURO (0 `import unreal`).

Hoy cada oráculo está escrito a mano y devuelve su propio dialecto: `interpenetra` es una lista,
`bounds_ok` un booleano, `estado` un string, `al_ras` un booleano derivado de ese string. Siete
oráculos, siete interfaces. Pero los tres ingredientes son siempre los mismos:

  **medición** (un escalar del mundo) · **umbral** (una comparación) · **testigos** (quién ofende).

Acá esos tres se declaran una vez y de la declaración se deriva todo lo demás: el veredicto, el
reporte de texto, el JSON, el inventario de umbrales y la lista de puntos ciegos. Es el patrón que ya
funciona dos veces en Jam —`tools.REGISTRO` (146 verbos → DSL, Graph, panel, spec) y las 408 firmas
de shader derivadas del motor—; el oráculo era el subsistema que había quedado afuera.

De REST se toma la única restricción que sirve acá: **interfaz uniforme**. Todo se mide igual y todo
se lee igual. De FastAPI, declarar-para-derivar. Lo que NO se toma es confundir validación con
juicio: que la evidencia esté bien formada no dice nada sobre si el mundo está bien. Son dos capas y
no se tocan.

Dos decisiones contra Goodhart, y son el motivo de que esto exista:

  1. **`alcance` es obligatorio.** No se puede declarar una medida sin decir qué NO ve. Así un
     informe deja de poder decir «TODO VERDE» a secas: dice en qué fue verde y qué no miró.
  2. **El umbral es un dato con defensa** (`porque`), no una constante escondida en una firma. Hoy
     `1e-3`, `TOL_CM` y `cobertura_min` viven enterrados en parámetros por defecto: no se pueden
     listar, ni diffear, ni discutir. Un número que nadie puede discutir es Goodhart esperando.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Sequence

OPS: dict[str, Callable[[float, float], bool]] = {
    "<=": lambda x, u: x <= u,
    "<": lambda x, u: x < u,
    ">=": lambda x, u: x >= u,
    ">": lambda x, u: x > u,
    "==": lambda x, u: x == u,
}


class EvidenciaIncompleta(KeyError):
    """Faltan hechos para poder medir. Es distinto de «la medida dio mal»: acá no se puede opinar."""


class MedidaMalDeclarada(ValueError):
    """La declaración no cumple su propio contrato."""


@dataclass(frozen=True)
class Umbral:
    op: str
    valor: float
    porque: str = ""

    def __post_init__(self) -> None:
        if self.op not in OPS:
            raise MedidaMalDeclarada(f"operador «{self.op}» no está en {sorted(OPS)}")

    def cumple(self, x: float) -> bool:
        return OPS[self.op](x, self.valor)

    def __str__(self) -> str:
        return f"{self.op} {self.valor:g}"


@dataclass(frozen=True)
class Veredicto:
    """La MISMA forma para toda medida. Es la interfaz uniforme, y es lo que hoy no existe."""

    id: str
    valor: float
    unidad: str
    ok: bool
    umbral: str
    alcance: str
    testigos: tuple = ()

    def linea(self) -> str:
        marca = "✓" if self.ok else "✗"
        base = f"{marca} {self.id:<32} {self.valor:>10.3g} {self.unidad:<4} ({self.umbral})"
        if self.testigos and not self.ok:
            muestra = ", ".join(str(t) for t in self.testigos[:3])
            resto = f" +{len(self.testigos) - 3}" if len(self.testigos) > 3 else ""
            base += f"  → {muestra}{resto}"
        return base

    def a_dict(self) -> dict:
        return {"id": self.id, "valor": self.valor, "unidad": self.unidad, "ok": self.ok,
                "umbral": self.umbral, "alcance": self.alcance, "testigos": list(self.testigos)}


@dataclass(frozen=True)
class Medida:
    """Una pregunta del oráculo, declarada. `mide` devuelve SIEMPRE un número.

    Que devuelva un número y no un booleano no es capricho: obliga a que el umbral salga a la luz.
    `bounds_ok` escondía un `1e-3` adentro de la función; acá ese `1e-3` es un dato con nombre.
    """

    id: str
    requiere: tuple[str, ...]
    mide: Callable[[dict], float]
    unidad: str
    umbral: Umbral
    alcance: str
    testigos: Callable[[dict], Sequence] | None = None
    etiquetas: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.id or " " in self.id:
            raise MedidaMalDeclarada(f"id inválido: «{self.id}»")
        # La regla que da sentido a todo el módulo. Sin esto se vuelve un validador más.
        if not self.alcance.strip():
            raise MedidaMalDeclarada(
                f"{self.id}: falta `alcance` — una medida tiene que declarar qué NO ve")

    def evaluar(self, evidencia: dict) -> Veredicto:
        faltan = [k for k in self.requiere if k not in evidencia]
        if faltan:
            raise EvidenciaIncompleta(f"{self.id}: falta la evidencia {faltan}")
        valor = float(self.mide(evidencia))
        testigos = tuple(self.testigos(evidencia)) if self.testigos else ()
        return Veredicto(id=self.id, valor=valor, unidad=self.unidad,
                         ok=self.umbral.cumple(valor), umbral=str(self.umbral),
                         alcance=self.alcance, testigos=testigos)


@dataclass(frozen=True)
class Informe:
    veredictos: tuple[Veredicto, ...]

    @property
    def ok(self) -> bool:
        return all(v.ok for v in self.veredictos)

    def texto(self) -> str:
        """El reporte NUNCA dice «TODO VERDE» a secas: dice en qué fue verde, y qué no miró."""
        lineas = [v.linea() for v in self.veredictos]
        malas = [v for v in self.veredictos if not v.ok]
        if malas:
            lineas.append(f"\nVEREDICTO: {len(malas)} de {len(self.veredictos)} medidas en rojo")
        else:
            lineas.append(f"\nVEREDICTO: verde en {len(self.veredictos)} medidas. SIN MIRAR:")
            for v in self.veredictos:
                lineas.append(f"  · {v.id}: {v.alcance}")
        return "\n".join(lineas)

    def a_json(self) -> str:
        return json.dumps({"ok": self.ok, "medidas": [v.a_dict() for v in self.veredictos]},
                          ensure_ascii=True)


def evaluar(medidas: Sequence[Medida], evidencia: dict) -> Informe:
    """Corre las medidas que la evidencia alcanza a alimentar. Las que no, se SALTEAN y se dicen —
    callarlas sería el peor Goodhart posible: verde por no haber preguntado."""
    salida = []
    for m in medidas:
        if all(k in evidencia for k in m.requiere):
            salida.append(m.evaluar(evidencia))
    return Informe(tuple(salida))


def no_medibles(medidas: Sequence[Medida], evidencia: dict) -> list[str]:
    return [m.id for m in medidas if any(k not in evidencia for k in m.requiere)]


# ---- derivados de la declaración (lo que en FastAPI sería el OpenAPI) ----

def inventario(medidas: Sequence[Medida]) -> list[dict]:
    """Todos los umbrales del oráculo, en una tabla. Antes vivían escondidos en firmas."""
    return [{"id": m.id, "umbral": str(m.umbral), "unidad": m.unidad,
             "porque": m.umbral.porque, "requiere": list(m.requiere)} for m in medidas]


def puntos_ciegos(medidas: Sequence[Medida]) -> list[dict]:
    return [{"id": m.id, "alcance": m.alcance} for m in medidas]
