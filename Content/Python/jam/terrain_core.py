"""Juicio puro sobre una definición de Mesh Terrain (``UMeshPartitionDefinition``).

El adaptador del motor obtiene el material y las prioridades de modificadores; este módulo decide
qué significan. No modifica assets y no conoce ``unreal``, por lo que el mismo contrato sirve para
Graph, tests y futuros sensores de Oracle — el mismo trato que ``nanite_core``.

Primera integración deliberadamente angosta: sólo lee ``Material`` y ``ModifierTypePriorities``,
los dos únicos campos de ``UMeshPartitionDefinition`` que son ``UPROPERTY`` simples (un objeto y un
array de nombres). ``ChannelMap`` y ``CompiledSectionBuildVariants`` son structs C++ propios del
plugin y su exposición a Python no está verificada todavía — se agregan cuando una sonda en UE
5.8.1 confirme qué forma toman del lado de Python, no antes.
"""

from __future__ import annotations


def medida(*, asset: str, material: str | None, modifier_priorities: list[str]) -> dict:
    """Normaliza la lectura del motor y rechaza respuestas imposibles.

    Sin material es un estado observable y válido de reportar (una definición recién creada no
    tiene uno todavía). Una prioridad de modificador repetida, en cambio, no puede salir de una
    lista bien formada: indica que el adaptador leyó algo corrupto.
    """
    prioridades = [str(p) for p in modifier_priorities]
    repetidas = sorted({p for p in prioridades if prioridades.count(p) > 1})
    if repetidas:
        raise ValueError(f"prioridades de modificador repetidas: {', '.join(repetidas)}")
    return {
        "asset": str(asset),
        "material": str(material) if material else None,
        "modifier_priorities": prioridades,
    }


def diagnosticar(datos: dict) -> list[str]:
    """Defectos estructurales que esta medición puede defender.

    Deliberadamente no juzga blending de canales, resolución de textura, calidad de las secciones
    horneadas ni el aspecto en el mundo: esos hechos necesitan sensores propios sobre
    ``ACompiledSection`` y el ``ChannelMap``, que todavía no están verificados.
    """
    defectos: list[str] = []
    if not datos["material"]:
        defectos.append("la definición no tiene material asignado")
    return defectos


def es_valido(datos: dict) -> bool:
    return not diagnosticar(datos)


def _nombre(asset: str) -> str:
    return str(asset).rsplit("/", 1)[-1].split(".", 1)[0] or str(asset)


def texto_analisis(datos: dict) -> str:
    material = _nombre(datos["material"]) if datos["material"] else "sin material"
    n = len(datos["modifier_priorities"])
    return (
        f"TERRAIN ANÁLISIS ✓ — «{_nombre(datos['asset'])}» · {material} · "
        f"{n} prioridad(es) de modificador"
    )


def texto_validacion(datos: dict) -> str:
    defectos = diagnosticar(datos)
    if defectos:
        return "TERRAIN ✗ — " + "; ".join(defectos)
    return f"TERRAIN ✓ — material «{_nombre(datos['material'])}» asignado"
