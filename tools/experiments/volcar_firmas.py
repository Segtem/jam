"""Vuelca las firmas de TODOS los `MaterialExpression` del motor a un módulo Python.

`jam.shader.ENTRADAS` empezó siendo una tabla escrita a mano con los cuarenta y pico de tipos que
Jam usaba. Eso alcanza mientras los grafos los escriba Jam; no alcanza para un verbo `material_node`
que acepte cualquiera de los 417, porque el verificador rechazaría como «tipo desconocido» todo lo
que no estuviera en la lista, y no hay forma de mantener 417 firmas a mano sin que se desactualicen.

Los nombres de entrada son DESCUBRIBLES (`get_material_expression_input_names`), así que la tabla se
deriva: este script la genera, queda commiteada, y `verifica_material_verbos.py` comprueba contra el
motor que siga siendo cierta. El mismo patrón con el que el registro de verbos deriva sus params.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \\
        -script=<plugin>/tools/experiments/volcar_firmas.py \\
        -RenderOffScreen -unattended -nosplash -stdout

Escribe `Content/Python/jam/shader_firmas.py`. Salida del log en Saved/Logs/<proyecto>.log.
"""

from __future__ import annotations

import os

import unreal


PREFIJO = "MaterialExpression"
DESTINO = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "Content", "Python", "jam", "shader_firmas.py")

CABECERA = '''"""Firmas de los `MaterialExpression` de Unreal. GENERADO — no editar a mano.

Lo produce `tools/experiments/volcar_firmas.py` corriendo dentro del editor, que es el único lado
que puede preguntarle al motor cómo se llaman las entradas de cada nodo. Se commitea para que el
verificador de `jam.shader` funcione en Python pelado, sin Unreal, y `verifica_material_verbos.py`
comprueba que no se haya quedado vieja.

Dos cosas que se leen mal si uno no las espera:

* los nodos de UNA sola entrada la llaman ``"None"`` — no es que no tengan entrada;
* hay tipos sin ninguna entrada (constantes, parámetros, coordenadas): tupla vacía.

Motor: {motor}  ·  {cantidad} tipos.
"""

from __future__ import annotations

ENTRADAS: dict[str, tuple[str, ...]] = {{
'''


def log(m: str) -> None:
    unreal.log(f"[FIRMAS] {m}")


def main() -> None:
    log("=" * 68)
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_SondaFirmas", "/Game/Jam/_Sonda", unreal.Material, unreal.MaterialFactoryNew())
    if material is None:
        log("no se pudo crear el material de sonda")
        return

    lib = unreal.MaterialEditingLibrary
    # `MaterialExpression` a secas es la clase BASE: sacarle el prefijo deja el nombre vacío y mete
    # una entrada `'': ()` en la tabla que no corresponde a ningún nodo.
    tipos = sorted(n[len(PREFIJO):] for n in dir(unreal)
                   if n.startswith(PREFIJO) and n != PREFIJO
                   and isinstance(getattr(unreal, n), type))

    firmas: dict[str, tuple] = {}
    sin_crear: list[str] = []
    for nombre in tipos:
        clase = getattr(unreal, PREFIJO + nombre)
        try:
            nodo = lib.create_material_expression(material, clase, 0, 0)
        except Exception:  # noqa: BLE001 — hay clases abstractas que no se instancian
            sin_crear.append(nombre)
            continue
        if nodo is None:
            sin_crear.append(nombre)
            continue
        firmas[nombre] = tuple(str(x) for x in lib.get_material_expression_input_names(nodo))

    log(f"{len(firmas)} tipos con firma · {len(sin_crear)} no instanciables")
    if sin_crear:
        log(f"no instanciables (los primeros): {sin_crear[:12]}")

    lineas = [f"    {nombre!r}: {firma!r}," for nombre, firma in sorted(firmas.items())]
    texto = CABECERA.format(motor=unreal.SystemLibrary.get_engine_version().split("-")[0],
                            cantidad=len(firmas)) + "\n".join(lineas) + "\n}\n"
    with open(DESTINO, "w", encoding="utf-8") as f:
        f.write(texto)
    log(f"escrito {DESTINO} ({len(texto)} bytes)")

    unreal.EditorAssetLibrary.delete_asset("/Game/Jam/_Sonda/M_SondaFirmas")
    log("=" * 68)


main()
