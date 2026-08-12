"""Ver SÓLO el nodo marcado, por el camino REAL del Graph.

Los tests puros fijan el recorte y las siete mutaciones confirman que discriminan, pero lo que hay
que demostrar es de escena: que marcar un nodo del medio **de verdad impida** que el terminal
coloque cosas. Eso no se puede afirmar sin correr el Graph adentro del editor y después contar lo
que quedó en el nivel.

Se corre la misma cadena tres veces —sin marcar, marcando el del medio, marcando el terminal— y se
mira el nivel, no el reporte.
"""
import json

import unreal

from jam import api, panel

def log(m):
    unreal.log(f"[SOLO] {m}")

FALLAS = []

def exigir(condicion, descripcion):
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def cadena(marcado=None):
    """`curve_bezier → mesh_ribbon → Ver sin hornear`. El terminal COLOCA un actor: es lo que se
    quiere ver desaparecer cuando alguien marca un nodo de más arriba."""
    nodos = {
        "eje": {"verb": "curve_bezier", "params": {
            "start_x": "0.0", "start_y": "0.0", "start_z": "0.0",
            "end_x": "900.0", "end_y": "0.0", "end_z": "80.0",
            "bend_x": "0.0", "bend_y": "320.0", "bend_z": "-40.0", "segments": "12"},
            "asset": None, "x": 0, "y": 0},
        "cinta": {"verb": "mesh_ribbon", "params": {"width": "360.0"}, "asset": None,
                  "x": 300, "y": 0},
        "fin": {"verb": "mesh_preview", "params": {"name": "JamPreviewSolo"}, "asset": None,
                "x": 600, "y": 0},
    }
    for nid in nodos:
        nodos[nid]["debug"] = (nid == marcado)
    return json.dumps({"schema_version": 1, "nodes": nodos,
                       "edges": [["eje", "out", "cinta", "in"], ["cinta", "out", "fin", "in"]]})


def etiquetas_del_preview():
    """Las ETIQUETAS y no la cuenta.

    Contar actores no discrimina y por poco pasa por verde: marcando el nodo del medio queda 1 actor
    igual que sin marcar, pero es OTRO —el dibujo del display flag (`JamDebug_viz`) en vez del que
    coloca el terminal (`JamPreviewSolo`)—. La pregunta es cuál está, no cuántos.
    """
    return sorted(str(a.get_actor_label()) for a in panel._actores_preview("graph"))


def puso_el_terminal(etiquetas):
    return any("JamPreviewSolo" in e for e in etiquetas)


def dibujo_del_flag(etiquetas):
    return any("JamDebug" in e for e in etiquetas)


def correr(marcado):
    panel._descartar_preview("graph")
    salida = api.run_graph(cadena(marcado))
    return salida, etiquetas_del_preview()


log("=" * 78)
log("La misma cadena, cambiando SÓLO dónde está el display flag:")
log("-" * 78)

salida_libre, libre = correr(None)
log(f"  sin marcar nada:        {libre}")

salida_medio, medio = correr("cinta")
log(f"  marcando «cinta»:       {medio}")

salida_fin, fin = correr("fin")
log(f"  marcando el terminal:   {fin}")

log("-" * 78)
exigir(puso_el_terminal(libre), f"sin marcar, el terminal coloca lo suyo ({libre})")
exigir(not dibujo_del_flag(libre), "sin marcar, no hay dibujo de display flag")
exigir("SOLO ▸" not in salida_libre, "sin marcar, el reporte no habla de recorte")

exigir("SOLO ▸ cinta" in salida_medio,
       "marcando el del medio, el reporte anuncia el recorte")
exigir("no corrieron" in salida_medio, "y dice cuántos quedaron afuera")
# La prueba de fuego, por IDENTIDAD y no por cuenta: el actor del terminal no tiene que existir.
exigir(not puso_el_terminal(medio),
       f"marcando el del medio, el terminal YA NO coloca lo suyo ({medio})")
exigir(dibujo_del_flag(medio),
       f"y en su lugar queda el dibujo del nodo marcado ({medio})")

exigir("SOLO ▸ fin" in salida_fin,
       "marcando el terminal, también se anuncia (aunque no recorte nada)")
exigir(puso_el_terminal(fin),
       f"marcando el terminal, la cadena entera corre y coloca lo suyo ({fin})")

log("-" * 78)
log("Reporte con «cinta» marcada (últimas líneas):")
for linea in salida_medio.splitlines()[-4:]:
    log(f"    {linea[:110]}")

panel._descartar_preview("graph")
log("JAM_SOLO_58 TODO VERDE" if not FALLAS else f"JAM_SOLO_58 ROJO — {len(FALLAS)}")
