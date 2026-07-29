"""UVs procedurales en el editor real: la cadena de Houdini, con veredicto.

La referencia es un grafo de Houdini —malla → proyección → `uvlayout`— sobre un casco facetado. Acá
se corre lo equivalente con los verbos de Jam y, sobre todo, se comprueba que el ORÁCULO diga cosas
verdaderas, porque un desplegado se juzga por números y no mirando el checker:

    · empaquetar tiene que SUBIR el aprovechamiento del atlas;
    · una malla sin desplegar tiene que delatarse (triángulos sin UV, o densidad absurda);
    · proyección cúbica y desplegado conforme tienen que dar resultados DISTINTOS y medibles,
      porque si midieran igual el número no estaría midiendo nada.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \\
        -script=<plugin>/tools/experiments/verifica_uv_procedural.py \\
        -RenderOffScreen -unattended -nosplash -stdout
"""

from __future__ import annotations

import unreal

from jam import mesh, tools


FALLAS = []


def log(mensaje: str) -> None:
    unreal.log(f"[UVPROC] {mensaje}")


def exigir(condicion: bool, descripcion: str) -> None:
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def correr(verbo, entrada=None, **params):
    info = tools.REGISTRO[verbo]
    completos = dict(info["params"])
    completos.update(params)
    texto = info["fn"](entrada, **completos)
    return texto, tools.dato_producido_runtime(verbo)


def main() -> None:
    log("=" * 70)

    # Una forma dura y facetada, que es donde la proyección cúbica es la respuesta correcta.
    _, base = correr("mesh_stairs", None)
    log(f"malla de prueba: {mesh._info(base)}")

    # --- 1. proyección cúbica, como el «UV cubic map» de la referencia ---
    texto, proyectada = correr("mesh_uv_box", base, channel=0)
    log(f"box:    {texto}")
    medida_box = mesh._medir_uv(proyectada, 0)
    exigir(medida_box["valido"], "la proyección cúbica dejó UV0 válido")
    exigir(not medida_box["sin_uv"], "no quedó ningún triángulo sin UV")
    exigir(medida_box["area_uv"] > 0.0, f"el área UV es real: {medida_box['area_uv']:.4f}")

    # --- 2. empaquetar: el `uvlayout` ---
    texto, empaquetada = correr("mesh_uv_pack", proyectada, resolution=1024)
    log(f"pack:   {texto}")
    medida_pack = mesh._medir_uv(empaquetada, 0)
    exigir(medida_box["cobertura"] > 1.02,
           f"la proyección cúbica deja las islas ENCIMADAS ({medida_box['cobertura']:.1f}×), "
           "que es lo que el empaquetado existe para resolver")
    exigir(medida_pack["cobertura"] <= 1.02,
           f"y empaquetar las separa: {medida_box['cobertura']:.1f}× → "
           f"{medida_pack['cobertura']:.2f}×")
    exigir(medida_pack["dentro_01"], "el resultado vive dentro del cuadrado 0..1")
    exigir(medida_pack["cobertura"] > 0.3,
           f"sin desperdiciar el atlas: {medida_pack['cobertura'] * 100:.0f}% aprovechado")

    # --- 3. desplegado conforme, para comparar técnicas ---
    texto, desplegada = correr("mesh_uv_unwrap", base, method="conformal")
    log(f"unwrap: {texto}")
    medida_unwrap = mesh._medir_uv(desplegada, 0)
    exigir(medida_unwrap["valido"] and not medida_unwrap["sin_uv"],
           "el desplegado conforme cubre toda la malla")
    exigir(abs(medida_unwrap["densidad"] - medida_box["densidad"]) > 1e-6,
           f"cúbica y conforme MIDEN distinto (cúbica {medida_box['densidad']:.4f} vs "
           f"conforme {medida_unwrap['densidad']:.4f}): si midieran igual, el número no mediría nada")

    # --- 4. el oráculo delata lo que está mal ---
    vacio = unreal.DynamicMeshPool().request_mesh()
    unreal.GeometryScript_Primitives.append_box(
        vacio, unreal.GeometryScriptPrimitiveOptions(), unreal.Transform(), 100.0, 100.0, 100.0)
    unreal.GeometryScript_UVs.set_num_uv_sets(vacio, 4)
    medida_sin = mesh._medir_uv(vacio, 3)
    exigir(medida_sin["sin_uv"] or medida_sin["area_uv"] == 0.0,
           f"un canal recién creado se delata como vacío: {mesh._veredicto_uv(medida_sin, 3)}")

    medida_inexistente = mesh._medir_uv(vacio, 7)
    exigir(not medida_inexistente["valido"] or medida_inexistente["area_uv"] == 0.0,
           f"un canal que no existe se reporta como tal: {mesh._veredicto_uv(medida_inexistente, 7)}")

    # --- 5. la cadena entera por el camino del ejecutor, encadenada ---
    _, m = correr("mesh_cylinder", None)
    _, m = correr("mesh_uv_box", m, channel=0)
    texto, m = correr("mesh_uv_pack", m, resolution=512)
    log(f"cadena cilindro → box → pack: {texto}")
    final = mesh._medir_uv(m, 0)
    exigir(final["valido"] and not final["sin_uv"] and final["cobertura"] > 0.2
           and final["dentro_01"],
           f"la cadena completa deja un desplegado usable: {mesh._veredicto_uv(final, 0)}")

    log("=" * 70)
    log("VEREDICTO: " + ("TODO VERDE" if not FALLAS else f"{len(FALLAS)} FALLA(S): {FALLAS}"))


main()
