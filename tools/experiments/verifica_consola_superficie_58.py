"""La consola contesta la verdad sobre un verbo de grafo, por el camino REAL.

Los 15 tests puros fijan el criterio, pero el corte vive en `panel.ejecutar_dsl` y ninguno de ellos
lo atraviesa: el mensaje que lee el usuario sale de ahí. Probar el criterio y dar por probada la
consola es el atajo que ya dio cuatro bugs en verde en una sola sesión.

Acá se escribe la línea como la escribiría Brian —`api.run`, la misma entrada que usa el C++— y se
mira lo que vuelve.

Lo que contestaba ANTES, medido con el corte desactivado en esta misma sonda:

    mesh_extrude distance=20  →  «biblioteca vacía (no hay assets que colocar).»

Un mensaje que manda a mirar la biblioteca por un problema que no está ahí: el verbo necesita una
malla que sólo llega por un cable, y no hay asset que pueda arreglarlo.
"""
import unreal

from jam import api

def log(m):
    unreal.log(f"[CONSOLA] {m}")

FALLAS = []

def exigir(condicion, descripcion):
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


log("=" * 78)
log("Verbos de grafo escritos como comando:")
log("-" * 78)

for verbo, tipo in (("mesh_extrude distance=20", "M"), ("mesh_ribbon width=300", "S")):
    salida = api.run(verbo)
    log(f"  «{verbo}» → {salida.splitlines()[0][:96]}")
    exigir("verbo de grafo" in salida, f"«{verbo}» se declara verbo de grafo")
    exigir(f"entrada {tipo}" in salida, f"y nombra el tipo que le falta ({tipo})")
    exigir("Graph" in salida, "y dice dónde sí funciona")
    # El síntoma viejo, nombrado para que se note si vuelve.
    exigir("biblioteca" not in salida.lower(),
           "y NO manda a mirar la biblioteca, que no tiene nada que ver")

log("-" * 78)
log("Verbos que sí son comandos (tienen que pasar el corte):")
log("-" * 78)

for linea in ("drop", "scatter count=3", "pick"):
    salida = api.run(linea)
    log(f"  «{linea}» → {salida.splitlines()[0][:96]}")
    # No se exige que COLOQUEN: en commandlet el spawn no ocurre (trampa conocida). Lo que se
    # exige es que el corte no los haya atajado — que es lo único que esta sonda cambió.
    exigir("verbo de grafo" not in salida, f"«{linea}» pasa el corte y llega a ejecutarse")

log("-" * 78)
log("Y el bug que esta sonda destapó de paso — `scatter` era el ejemplo del docstring del DSL:")
salida = api.run("scatter count=5")
log(f"  «scatter count=5» → {salida.splitlines()[0][:96]}")
exigir("AttributeError" not in salida,
       "`scatter` ya no explota iterando la ruta del asset letra por letra "
       "(«'str' object has no attribute 'pos'»)")
exigir("SCATTER" in salida, "y llega a repartir puntos de verdad")

log("-" * 78)
ayuda = api.run("help")
exigir("mesh_extrude" not in ayuda, "la ayuda ya no ofrece un verbo que no puede correr")
exigir("drop" in ayuda, "la ayuda sigue ofreciendo los que sí")
exigir("viven sólo en el Graph" in ayuda,
       "y dice que los otros existen y dónde (esconderlos sin decirlo sería otra mentira)")
log(f"  ayuda: {len(ayuda.splitlines())} líneas")
for linea in ayuda.splitlines():
    if "viven sólo en el Graph" in linea:
        log(f"  {linea.strip()}")

log("=" * 78)
log("JAM_CONSOLA_58 TODO VERDE" if not FALLAS else f"JAM_CONSOLA_58 ROJO — {len(FALLAS)}")
