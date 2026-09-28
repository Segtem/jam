"""La BASE COMÚN: verbos que se calculan en el núcleo y corren igual en Unreal, Godot y Unity.

Tarea `base-comun`. Cada entrada de `IMPLEMENTA` recibe lo que llega por el cable y los params del
verbo, y devuelve un dato del núcleo (una `malla_core.Malla`). Ningún motor recalcula: cada adaptador
sólo lo vuelve suyo con su primitiva «malla desde datos». Un verbo entra acá con el MISMO nombre que
tenía en Unreal (decisión de Brian, 2026-09-28): si un motor corriera otro código, la base no sería
común.

Cerebro puro: cero `import unreal`.
"""

from __future__ import annotations

from . import malla_core


def mesh_box(_entrada=None, *, size_x=100.0, size_y=100.0, size_z=100.0,
             steps_x=0, steps_y=0, steps_z=0) -> malla_core.Malla:
    return malla_core.caja(size_x=size_x, size_y=size_y, size_z=size_z,
                           steps_x=steps_x, steps_y=steps_y, steps_z=steps_z)


IMPLEMENTA = {"mesh_box": mesh_box}
