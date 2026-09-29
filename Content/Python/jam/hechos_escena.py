"""Los hechos L0 de una escena después de colocar: lo que `oracle juzgar` lee. Cerebro puro.

Tarea `sonda-escena-l0` (plan: `commander/docs/AURA-PROPIO-CORTE-1.md`). Entra la TANDA —lo que se
acaba de colocar— y el resto de la escena, como `geometry.Pieza`; sale el JSON con las bolsas que
ya leen las medidas de Jam:

- `pieza`: cada una de la tanda (`colocacion.interpenetracion`, `colocacion.bounds`).
- `vecina`: el resto de la escena, SIN la tanda. Si una pieza fuera también vecina, se mediría
  contra sí misma y la interpenetración daría rojo siempre.
- `asentada`: la tanda otra vez, con su soporte: los pares DENTRO de la tanda los juzga
  `physics.tanda_sin_interpenetracion` (una vez por par) y el soporte `physics.tanda_completa`.
- `asentamiento`: cada pieza contra lo que tiene debajo, escena u otra pieza de la tanda
  (`physics.tiene_suelo`, `physics.apoyado`).

No decide nada: aplana. El juez es Oracle.
"""

from __future__ import annotations

from . import oracle_physics_facts
from .oracle_shadow import _plano


def hechos(tanda, escena) -> dict:
    tanda, escena = list(tanda), list(escena)
    asentamiento, asentada = [], []
    for p in tanda:
        otras = escena + [q for q in tanda if q is not p]
        a = oracle_physics_facts.hechos(p, otras)["asentamiento"][0]
        asentamiento.append(a)
        asentada.append(_plano(p) | {
            "apoyada": a["tiene_suelo"], "apoyada_medible": True,
            "soporte": a["soporte"], "soporte_medible": a["soporte_medible"],
            "sobre_hermana": a["soporte"] in {q.nombre for q in tanda}})
    return {"pieza": [_plano(p) for p in tanda], "vecina": [_plano(q) for q in escena],
            "asentada": asentada, "asentamiento": asentamiento}
