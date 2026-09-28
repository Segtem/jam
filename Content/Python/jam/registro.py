"""Registro NEUTRO de los verbos de Jam: qué es cada uno, no cómo se ejecuta. Cerebro puro, sin `unreal`.

Nombre, categoría, params con su default tipado, opciones, pines, tipos de entrada y salida,
superficies y documentación: todo lo que el Graph, el DSL, la Dash Bar y el oráculo necesitan para
DESCRIBIR y VALIDAR un verbo. La ejecución vive en un adaptador por motor —hoy `jam.tools`, el de
Unreal—, que al importarse le enchufa `"fn"` a cada verbo que implementa (`tools.IMPLEMENTA`).

Tarea `fuera-del-motor`, etapa 1: el núcleo (grafo, DSL, registro) tiene que poder importarse con
`sys.modules["unreal"] = None`. Antes esto vivía en `tools.py`, que importa `unreal` en su línea 10.
"""

from __future__ import annotations

# Las salidas del material salen del IR (puro) y no de una lista repetida acá: el desplegable del
# nodo `material_output` y lo que el verificador acepta son la MISMA lista, por construcción.
from .shader import SALIDAS as _SALIDAS_MATERIAL


#: Params que se MUDARON de verbo. Sin esto, un grafo guardado dice «parámetro desconocido» y hay
#: que adivinar; con esto dice adónde fue. `physics` vivía en `place` y era el mismo nodo haciendo
#: dos cosas distintas — ahora hacer caer es `drop`.
PARAMS_MUDADOS = {("place", "physics"): "drop"}


def necesita_instanciar(verbo: str) -> bool:
    """¿Este verbo describe DÓNDE y necesita que otro lo vuelva escena?

    Se decide por el TIPO de salida y no por una lista de nombres: el día que otro verbo pase a
    producir puntos, la Dash Bar lo compone sola en vez de dejar de colocar en silencio.
    """
    return REGISTRO.get(verbo, {}).get("out_name") == "P"


# ---- el registro: verbo → acción param-driven + defaults (fuente de verdad para DSL, help y panel) ----

# Anclas disponibles, para que los params que eligen una se dibujen como LISTA y no como campo de
# texto donde hay que acordarse el nombre (se lee del cerebro puro, una sola fuente de verdad).
def _anclas() -> list:
    from . import pivot
    return list(pivot.ANCLAS)


_ANCLAS = _anclas()

# `cat` = categoría estilo Dash (Content/Place/Scatter/Create/Edit) → agrupa los verbos en la
# Dash Bar. Es dato: mover una herramienta de categoría es cambiar este campo, sin tocar C++.
REGISTRO = {
    "asset":        {"cat": "Content", "params": {"name": ""},
                     "read_only": True,
                     "doc": "elige el asset activo (Content); las demás herramientas lo heredan"},
    "pick":         {"cat": "Content", "params": {},
                     "read_only": True,
                     "doc": "usa la malla SELECCIONADA en el Content Browser de Unreal como asset activo"},
    "pivot":        {"cat": "Edit",    "params": {"anchor": ""},
                     "opciones": {"anchor": [""] + list(_ANCLAS)},
                     "doc": "dónde está el pivote del asset y si sirve para repetir (o hay que anclarlo)"},
    "normalize":    {"cat": "Edit",  "params": {"anchor": "", "scene": True},
                     "opciones": {"anchor": [""] + list(_ANCLAS)},
                     "doc": "normaliza el pivote del asset (una vez): todas las tools lo agarran por ahí"},
    "pivot_set":    {"cat": "Edit",  "params": {"to": "base"},
                     "opciones": {"to": list(_ANCLAS)},
                     "doc": "mueve el pivote de los actores seleccionados al ancla elegida"},
    # `view` arranca en FALSE en el grafo y en TRUE como comando, y no es una inconsistencia: son
    # dos cosas distintas. Un COMANDO es «ponelo donde estoy mirando» —por eso `view` existe—; un
    # GRAFO es una descripción que tiene que dar el mismo resultado cada vez que corre. Con `view`
    # prendido, cada Run re-apuntaba a la cámara viva y el modelo aparecía en otro lado.
    #
    # Sale gratis: el grafo pasa TODOS los params (de acá), y el comando sólo los que se tipean, así
    # que el default de la FUNCIÓN (`view=True`) es el que manda desde la Dash Bar.
    "place":        {"cat": "Place",
                     "params": {"x": 0.0, "y": 0.0, "z": 0.0, "view": False, "surface": True,
                                "anchor": "base", "sink": 0.0, "align": False,
                                "yaw": 0.0, "scale": 1.0, "scale_min": 1.0, "scale_max": 1.0,
                                "points": ""},
                     "data_params": {"points": "P"},
                     "optional_data_params": ("points",),
                     # Además de un asset suelto acepta la COLECCIÓN de variantes, y reparte una
                     # por punto. El requisito de `points` viaja acá y no como regla aparte: sin
                     # puntos habría que elegir una variante, y eso no lo dijo nadie.
                     "in_accepts": {"A[]": ("points",)},
                     "opciones": {"anchor": list(_ANCLAS)},
                     "doc": "coloca en un PLANO: en sus coordenadas, o uno por punto si le cableás un "
                            "scatter a `points`. Lo que se cruzaría se descarta por huella. Para que "
                            "caigan y se apilen, usá `drop`. Verifica el entorno"},
    "scatter":      {"cat": "Scatter",
                     "params": {"count": 24, "area": 800.0, "x": 0.0, "y": 0.0,
                                "pattern": "poisson", "spacing": 0.0,
                                "rings": 3, "surface": True, "align": False, "slope_max": 90.0,
                                "height_min": 0.0, "height_max": 0.0, "noise": 0.0, "density": 1.0,
                                "scale_min": 1.0, "scale_max": 1.0, "spread": 1.0, "sink": 0.0,
                                "anchor": "", "view": False, "seed": 7},
                     "opciones": {"pattern": ["poisson", "grid", "radial", "hexagonal", "triangular"],
                                  "anchor": [""] + list(_ANCLAS)},
                     "doc": "calcula PUNTOS sobre la superficie real con máscaras (pendiente/altura/ruido/densidad). "
                            "Sin entrada reparte en un área; con PUNTOS reparte alrededor de cada uno "
                            "(multiplicador). No coloca: enchufalo al pin `points` de un `place`. Salida P"},
    # El hermano de `place`: mismo trabajo, distinta física. `place` reparte en un plano y descarta
    # lo que se cruzaría; `drop` deja caer y por eso las piezas se apilan. Tenerlo como una perilla
    # de `place` hacía que el mismo nodo significara dos cosas.
    "drop":         {"cat": "Place",
                     "label": "Soltar con física",
                     # Primera tool migrada al contrato nuevo: dice EN POSITIVO dónde se ve. Antes
                     # llegaba a la barra por no tener `graph_only`, o sea por omisión.
                     "superficies": ("dash", "graph"),
                     "params": {"x": 0.0, "y": 0.0, "height": 800.0, "view": False,
                                "anchor": "base", "sink": 0.0, "align": False,
                                "scale_min": 1.0, "scale_max": 1.0, "points": ""},
                     "data_params": {"points": "P"},
                     "optional_data_params": ("points",),
                     "in_accepts": {"A[]": ("points",)},
                     "opciones": {"anchor": list(_ANCLAS)},
                     "doc": "deja CAER: uno por punto si le cableás un scatter a `points`, y la tanda "
                            "se APILA (physics paint); sin puntos, uno solo a plomo desde `height`. "
                            "Verifica el apoyo"},
    "snap":         {"cat": "Place",   "params": {"grid": 100.0},
                     "doc": "snap a grilla y verifica alineación"},
    "replace":      {"cat": "Create",  "params": {"sx": 2.0, "sy": 2.0, "sz": 3.0},
                     "doc": "blockout → asset conservando footprint"},
    "spline":       {"cat": "Scatter",
                     "params": {"gap": 0.0, "axis": "x", "anchor": "base", "align": False,
                                "surface": False, "scale": 1.0, "jitter_yaw": 0.0, "seed": 7},
                     "opciones": {"axis": ["x", "y"], "anchor": list(_ANCLAS)},
                     "doc": "piezas modulares a su largo real a lo largo de un spline (verifica que tile sin solaparse)"},
    "create_spline": {"cat": "Create", "params": {},
                      "doc": "agrega un spline editable a la escena (primitiva de curva)"},
    "fracture":     {"cat": "Create",
                     "params": {"sites": 20, "seed": 123, "hollow": False, "thickness": 4.0,
                                "view": False},
                     "doc": "convierte un StaticMesh en destructible (Geometry Collection de Chaos). "
                            "hollow=vacía el volumen (barril/piñata). Conversor: place lo coloca "
                            "(editor-only, Dataflow)"},
    "nanite":       {"cat": "Create", "params": {},
                     "doc": "convierte un StaticMesh a Nanite sin tocar el original; "
                            "Run crea preview, Bake fija la copia y Discard la elimina"},
    "nanite_analyze": {"cat": "Create", "params": {"lod": 0},
                       "read_only": True,
                       "doc": "lee sin modificar: estado Nanite, triángulos, vértices, UV y LOD; "
                              "deja pasar el mismo asset A"},
    "nanite_validate": {"cat": "Create", "params": {"lod": 0},
                        "read_only": True,
                        "doc": "exige una representación Nanite habilitada y no vacía; "
                               "no juzga materiales ni calidad visual y deja pasar A"},
    # Mesh vive sólo en Graph: por sus cables fluye un DynamicMesh transitorio `M`. El tab no aparece
    # en Dash porque ejecutar una primitiva aislada allí no tiene un consumidor ni un asset que ver.
    "curve_bezier": {"cat": "Mesh", "graph_only": True,
                     "params": {"start_x": 0.0, "start_y": 0.0, "start_z": 0.0,
                                "end_x": 0.0, "end_y": 0.0, "end_z": 500.0,
                                "bend_x": 0.0, "bend_y": 0.0, "bend_z": 0.0,
                                "segments": 8},
                     "doc": "crea una curva Bézier transitoria S para sweep, pipes y ramas"},
    "curve_child": {"cat": "Mesh", "graph_only": True,
                    "params": {"at": 0.5, "length": 300.0, "angle": 55.0,
                               "azimuth": 0.0, "bend": 40.0, "radial_offset": 0.0,
                               "segments": 8, "samples": 32},
                    "doc": "crea una curva hija S anclada y orientada por el frame local de otra curva S"},
    "curve_noise": {"cat": "Mesh", "graph_only": True,
                    "params": {"amplitud": 10.0, "escala": 0.004, "octavas": 3,
                               "desde": 0.0, "seed": 0, "samples": 16},
                    "doc": "desvía una curva S perpendicular a su tangente con ruido; el tronco deja de ser un poste"},
    "curve_frames": {"cat": "Mesh", "graph_only": True,
                     "params": {"count": 12, "start": 0.0, "end": 1.0,
                                "radial_offset": 0.0, "turns": 0.0,
                                "angle_offset": 0.0, "radius_start": 0.0,
                                "radius_end": 0.0, "samples": 32, "seed": 7},
                     "doc": "samplea cada curva S como frames jerárquicos F con padre, índice, escala, radio, seed y pivote"},
    "distribute_frames": {"cat": "Mesh", "graph_only": True,
                          "params": {"count": 12, "start": 0.0, "end": 1.0,
                                     "rotate_per_index": 137.5, "angle_offset": 0.0,
                                     "angle_jitter": 0.0, "parameter_jitter": 0.0,
                                     "seed": 7},
                          "doc": "redistribuye cada padre F por cantidad y rango, con giro e irregularidad deterministas"},
    "transform_frames": {"cat": "Mesh", "graph_only": True,
                         "params": {"offset_x": 0.0, "offset_y": 0.0,
                                    "offset_z": 0.0, "pitch": 0.0, "yaw": 0.0,
                                    "roll": 0.0, "scale": 1.0,
                                    "offset_jitter_x": 0.0, "offset_jitter_y": 0.0,
                                    "offset_jitter_z": 0.0, "pitch_jitter": 0.0,
                                    "yaw_jitter": 0.0, "roll_jitter": 0.0,
                                    "scale_jitter": 0.0, "inherit_scale": True,
                                    "seed": 7},
                         "doc": "desplaza, rota y escala frames F en sus ejes locales, con variación determinista"},
    "branch_from_frames": {"cat": "Mesh", "graph_only": True,
                           "params": {"length_min": 200.0, "length_max": 400.0,
                                      "angle": 55.0, "angle_jitter": 0.0,
                                      "curl": 20.0, "curl_jitter": 0.0,
                                      "segments": 8, "inherit_scale": True,
                                      "relative_to_parent": False, "profile": "",
                                      "seed": 7},
                           "data_params": {"profile": "N[]"},
                           "optional_data_params": ("profile",),
                           "doc": "crea una curva hija S por cada frame F. «relative_to_parent» mide el largo como fracción del padre en vez de centímetros; el perfil N[] opcional lo modula según dónde nace sobre el padre (silueta cónica)"},
    # Condicional en dataflow: las dos ramas se evalúan igual, el select decide cuál sigue.
    # Un `select` por tipo y no uno genérico porque la regla es que las dos ramas y la salida sean
    # DEL MISMO TIPO — con un verbo por familia eso se cumple por construcción y el error de tipo
    # lo da el chequeo de cables de siempre, sin inventar inferencia.
    # Reroute con forma de nodo (estilo Blueprint): se selecciona, se mueve con el grupo y
    # sobrevive a copiar/pegar, que es lo que las vías sobre el cable no hacen.
    "reroute_mesh": {"cat": "Mesh", "graph_only": True, "params": {},
                        "doc": "punto de paso para ordenar cables: deja pasar Malla sin tocarla"},
    "reroute_asset": {"cat": "Mesh", "graph_only": True, "params": {},
                        "doc": "punto de paso para ordenar cables: deja pasar Asset sin tocarla"},
    "reroute_points": {"cat": "Mesh", "graph_only": True, "params": {},
                        "doc": "punto de paso para ordenar cables: deja pasar Puntos sin tocarla"},
    "reroute_curve": {"cat": "Mesh", "graph_only": True, "params": {},
                        "doc": "punto de paso para ordenar cables: deja pasar Curva sin tocarla"},
    "reroute_frames": {"cat": "Mesh", "graph_only": True, "params": {},
                        "doc": "punto de paso para ordenar cables: deja pasar Frames sin tocarla"},
    # El pincel del Physics Paint: marca DÓNDE, no reparte. Ver `brush_core`.
    "brush": {"cat": "Scatter",
              "label": "Pincel de reparto",
              # Estaba `graph_only`, así que el pincel vivía sólo en el canvas. Dash expone su
              # Physics Paint en la barra —es un gesto sobre la escena, no una cadena de nodos— y
              # acá pasa lo mismo: el pincel marca centros sobre lo que estás mirando.
              "superficies": ("dash", "graph"),
              "params": {"actor": "", "alto": 200.0},
              "etiquetas_params": {"actor": "actor", "alto": "alto (cm)"},
              "doc": "pincel: marca los centros de reparto. Con «actor» busca ese actor por nombre y el "
                     "grafo queda autocontenido; vacío, usa lo elegido en el nivel. «alto» los levanta "
                     "sobre el pivote, que es lo que hace falta para pintar con física: nacen arriba y "
                     "caen. Enchufalo a un scatter para repartir alrededor"},
    "select_mesh": {"cat": "Mesh", "graph_only": True,
                    "params": {"cond": "", "si": "", "no": ""},
                    "data_params": {"cond": "B", "si": "M", "no": "M"},
                    "etiquetas_params": {"cond": "condición (bool)", "si": "sí (Malla)",
                                         "no": "no (Malla)"},
                    "doc": "elige entre dos mallas M según un booleano; las dos ramas se calculan "
                           "igual (dataflow), el select sólo decide cuál sigue viaje"},
    "select_asset": {"cat": "Mesh", "graph_only": True,
                     "params": {"cond": "", "si": "", "no": ""},
                     "data_params": {"cond": "B", "si": "A", "no": "A"},
                     "etiquetas_params": {"cond": "condición (bool)", "si": "sí (Asset)",
                                          "no": "no (Asset)"},
                     "doc": "elige entre dos assets A según un booleano; las dos ramas se calculan "
                            "igual (dataflow), el select sólo decide cuál sigue viaje"},
    "asset_set": {"cat": "Mesh", "graph_only": True,
                  "params": {}, "require_main_inputs": True,
                  "doc": "combina dos o más assets A como una colección ordenada A[] de variantes"},
    "choose_asset": {"cat": "Mesh", "graph_only": True,
                     "params": {"assets": "", "mode": "random", "seed": 7},
                     "data_params": {"assets": "A[]"},
                     "opciones": {"mode": ["random", "cycle", "parent"]},
                     "doc": "elige una variante A[] determinista para cada frame F y produce AF"},
    "graph_curve": {"cat": "Mesh", "graph_only": True,
                    "params": {"start_value": 1.0, "end_value": 0.15,
                               "shape": "custom", "power": 2.0,
                               "midpoint": 0.55, "mid_value": 0.72, "samples": 16},
                    "opciones": {"shape": ["linear", "ease_in", "ease_out", "smooth", "custom"]},
                    "doc": "crea un falloff numérico N[] editable en dominio 0..1"},
    "series_range": {"label": "Rango", "cat": "Maths",
                     "graph_only": True,
                     "params": {"start": 0.0, "end": 1.0, "count": 11},
                     "etiquetas_params": {"start": "inicio", "end": "fin",
                                           "count": "cantidad"},
                     "doc": "crea una serie N[] equidistante con ambos extremos incluidos"},
    "series_remap": {"label": "Remapear serie", "cat": "Maths",
                     "graph_only": True,
                     "params": {"source_min": 0.0, "source_max": 1.0,
                                "target_min": 0.0, "target_max": 1.0, "clamp": True},
                     "etiquetas_params": {"source_min": "origen mínimo",
                                           "source_max": "origen máximo",
                                           "target_min": "destino mínimo",
                                           "target_max": "destino máximo",
                                           "clamp": "limitar al destino"},
                     "doc": "remapea cada valor de N[] entre dos dominios; puede limitar o extrapolar"},
    "curve_polyline": {"label": "Polilínea", "cat": "Mesh",
                       "graph_only": True,
                       "params": {"x": "", "y": "", "z": "", "closed": False},
                       "data_params": {"x": "N[]", "y": "N[]", "z": "N[]"},
                       "etiquetas_params": {"x": "coordenadas X", "y": "coordenadas Y",
                                             "z": "coordenadas Z", "closed": "cerrada"},
                       "doc": "combina tres series N[] del mismo largo como puntos XYZ de una polilínea S; "
                              "«cerrada» repite el primer punto al final y la vuelve un polígono"},
    "curve_interpolate": {"label": "Interpolar puntos", "cat": "Mesh",
                          "graph_only": True,
                          "params": {"x": "", "y": "", "z": "", "segments": 8},
                          "data_params": {"x": "N[]", "y": "N[]", "z": "N[]"},
                          "etiquetas_params": {"x": "coordenadas X", "y": "coordenadas Y",
                                               "z": "coordenadas Z",
                                               "segments": "tramos (Número)"},
                          "doc": "curva suave que PASA por los puntos, a diferencia de Bézier que "
                                 "los usa de control; parametrización centrípeta para que no se "
                                 "haga un rulo con puntos desparejos"},
    "curve_line": {"label": "Línea", "cat": "Mesh", "graph_only": True,
                   "params": {"desde": "0,0,0", "hasta": "0,0,300"},
                   "data_params": {"desde": "V", "hasta": "V"},
                   # Los dos extremos se pueden CABLEAR o escribir. Sin esto el Graph exigiría un
                   # cable para cada uno, y la línea más simple del tutorial —del origen hacia
                   # arriba— necesitaría dos nodos de vector para existir.
                   "optional_data_params": ("desde", "hasta"),
                   "etiquetas_params": {"desde": "desde (Vector)", "hasta": "hasta (Vector)"},
                   "doc": "el segmento entre dos posiciones, como curva S"},
    "curve_line_sdl": {"label": "Línea por dirección", "cat": "Mesh",
                       "graph_only": True,
                       "params": {"origen": "0,0,0", "direccion": "0,0,1", "largo": 300.0},
                       "data_params": {"origen": "V", "direccion": "V"},
                       "optional_data_params": ("origen", "direccion"),
                       "etiquetas_params": {"origen": "origen (Vector)",
                                            "direccion": "dirección (Vector)",
                                            "largo": "largo (Número)"},
                       "doc": "segmento desde un origen en una dirección; la dirección se normaliza, "
                              "así que el largo pedido es el largo que sale"},
    "curve_move": {"label": "Mover curva", "cat": "Mesh",
                   "graph_only": True,
                   "params": {"desplazamiento": "0,0,100"},
                   "data_params": {"desplazamiento": "V"},
                   "optional_data_params": ("desplazamiento",),
                   "etiquetas_params": {"desplazamiento": "mover (Vector)"},
                   "doc": "mueve una curva por un vector, conservando su metadata"},
    "curve_resample": {"label": "Remuestrear curva", "cat": "Mesh",
                       "graph_only": True,
                       "params": {"count": 24, "samples": 32},
                       "etiquetas_params": {"count": "cantidad", "samples": "muestras de spline"},
                       "doc": "remuestrea cada curva S a distancias uniformes y conserva su metadata"},
    "curve_smooth": {"label": "Suavizar curva", "cat": "Mesh",
                     "graph_only": True,
                     "params": {"iterations": 2, "strength": 0.5,
                                "preserve_ends": True, "samples": 32},
                     "etiquetas_params": {"iterations": "pasadas", "strength": "intensidad",
                                           "preserve_ends": "preservar extremos",
                                           "samples": "muestras de spline"},
                     "doc": "suaviza S sin cambiar su cantidad de puntos y conserva la metadata jerárquica"},
    "curve_fuse_collinear": {
                              "label": "Fusionar colineales", "cat": "Mesh",
                              "graph_only": True,
                              "params": {"angle_tolerance": 1.0,
                                         "distance_tolerance": 0.01, "samples": 32},
                              "etiquetas_params": {
                                  "angle_tolerance": "ángulo (°)",
                                  "distance_tolerance": "distancia (cm)",
                                  "samples": "muestras de spline"},
                              "doc": "quita puntos redundantes de S sin mover sus extremos"},
    "curve_subdivide": {"label": "Subdividir curva", "cat": "Mesh",
                         "graph_only": True,
                         "params": {"mode": "distance", "distance": 100.0,
                                    "count": 1, "samples": 32},
                         "opciones": {"mode": ["distance", "count"]},
                         "etiquetas_params": {"mode": "modo", "distance": "largo máximo (cm)",
                                               "count": "puntos por segmento",
                                               "samples": "muestras de spline"},
                         "doc": "inserta puntos por tramo sin perder los vértices originales de S"},
    "curve_offset": {"label": "Desplazar curva", "cat": "Mesh",
                     "graph_only": True,
                     "params": {"distance": 100.0, "side": "left", "plane": "xy",
                                "join": "miter", "miter_limit": 4.0, "samples": 32},
                     "opciones": {"side": ["left", "right"], "plane": ["xy", "xz", "yz"],
                                  "join": ["miter", "bevel"]},
                     "etiquetas_params": {"distance": "distancia (cm)", "side": "lado",
                                           "plane": "plano", "join": "unión",
                                           "miter_limit": "límite miter", "samples": "muestras"},
                     "doc": "desplaza S lateralmente con plano, lado y unión explícitos"},
    "curve_branches": {"cat": "Mesh", "graph_only": True,
                       "params": {"count": 12, "start": 0.2, "end": 0.92,
                                  "length_min": 200.0, "length_max": 400.0,
                                  "parent_scale_start": 1.0, "parent_scale_end": 1.0,
                                  "angle": 70.0, "angle_jitter": 8.0,
                                  "rotate_per_index": 137.0, "azimuth": 0.0,
                                  "azimuth_jitter": 5.0, "bend": 40.0,
                                  "bend_jitter": 20.0, "radial_offset": 0.0,
                                  "segments": 8, "samples": 32, "seed": 7},
                       "doc": "genera una lista S de ramas sobre cada curva padre, con rango, giro por índice y seed estilo TreeGen"},
    "mesh_triangle": {"cat": "Mesh", "graph_only": True,
                      "params": {"size": 100.0},
                      "doc": "crea un triángulo procedural; fuente M"},
    "mesh_quad":    {"cat": "Mesh", "graph_only": True,
                     "params": {"width": 100.0, "height": 100.0},
                     "doc": "crea un quad procedural con UV; fuente M"},
    "mesh_grid":    {"cat": "Mesh", "graph_only": True,
                     "params": {"width": 500.0, "height": 500.0, "columns": 6, "rows": 6},
                     "doc": "crea una grilla procedural subdividida; fuente M"},
    "mesh_cylinder": {"cat": "Mesh", "graph_only": True,
                      "params": {"radius": 50.0, "height": 200.0, "sides": 16,
                                 "height_steps": 1, "capped": True},
                      "doc": "crea un cilindro procedural parametrizado; fuente M"},
    "mesh_cone":    {"cat": "Mesh", "graph_only": True,
                     "params": {"base_radius": 60.0, "top_radius": 0.0, "height": 200.0,
                                "sides": 16, "height_steps": 4, "capped": True},
                     "doc": "crea cono o tronco variando sus radios; fuente M"},
    "mesh_sphere":  {"cat": "Mesh", "graph_only": True,
                     "params": {"radius": 100.0, "latitude_steps": 8, "longitude_steps": 12},
                     "doc": "crea una esfera procedural de baja o alta resolución; fuente M"},
    "mesh_from_asset": {"label": "Desde asset (compatibilidad)",
                        "cat": "Mesh", "graph_only": True,
                        "params": {},
                        "doc": "alias histórico de Copiar Static Mesh; conserva presets anteriores"},
    "mesh_copy_static": {
        "label": "Copiar Static Mesh", "cat": "Mesh",
        "graph_only": True,
        "params": {"lod_type": "max_available", "lod_index": 0,
                   "apply_build_settings": True, "request_tangents": True,
                   "use_build_scale": True},
        "opciones": {"lod_type": ["max_available", "hi_res", "source", "render"]},
        "etiquetas_params": {"lod_type": "tipo de LOD", "lod_index": "índice de LOD",
                              "apply_build_settings": "Build Settings",
                              "request_tangents": "copiar tangentes",
                              "use_build_scale": "aplicar Build Scale"},
        "doc": "copia un LOD de Static Mesh A a M y conserva Material IDs y materiales por section",
    },
    "mesh_copy_skeletal": {
        "label": "Copiar Skeletal Mesh", "cat": "Mesh",
        "graph_only": True,
        "params": {"lod_type": "max_available", "lod_index": 0,
                   "apply_build_settings": True, "request_tangents": True,
                   "use_build_scale": True},
        "opciones": {"lod_type": ["max_available", "source", "render"]},
        "etiquetas_params": {"lod_type": "tipo de LOD", "lod_index": "índice de LOD",
                              "apply_build_settings": "Build Settings",
                              "request_tangents": "copiar tangentes",
                              "use_build_scale": "aplicar Build Scale"},
        "doc": "copia geometría y materiales de un LOD de Skeletal Mesh A a M; los atributos internos dependen de la copia nativa",
    },
    "mesh_ribbon": {"label": "Cinta de curva", "cat": "Mesh",
                     "graph_only": True,
                     "params": {"width": 360.0, "plane": "xy", "join": "miter",
                                "miter_limit": 4.0, "uv_scale": 200.0,
                                "material_id": 0, "samples": 32},
                     "opciones": {"plane": ["xy", "xz", "yz"],
                                  "join": ["miter", "bevel"]},
                     "etiquetas_params": {"width": "ancho", "plane": "plano",
                                           "join": "unión", "miter_limit": "límite de miter",
                                           "uv_scale": "cm por UV", "material_id": "Material ID",
                                           "samples": "muestras"},
                     "doc": "convierte una curva abierta S en cinta M con UV0 longitudinal y Material ID"},
    "mesh_extrude": {"label": "Extruir superficie", "cat": "Mesh",
                     "graph_only": True,
                     "params": {"distance": 300.0, "direction_x": 0.0,
                                "direction_y": 0.0, "direction_z": 1.0,
                                "uv_scale": 100.0},
                     "etiquetas_params": {"distance": "distancia",
                                           "direction_x": "dirección X",
                                           "direction_y": "dirección Y",
                                           "direction_z": "dirección Z",
                                           "uv_scale": "cm por UV lateral"},
                     "doc": ("extruye una superficie M abierta en dirección fija, cose la "
                             "frontera y produce un sólido cerrado")},
    "mesh_pipe":    {"cat": "Mesh", "graph_only": True,
                     "params": {"radius_start": 30.0, "radius_end": 5.0,
                                "sides": 10, "samples": 16, "capped": True,
                                "profile_rotation": 0.0, "miter_limit": 4.0,
                                "radius_from_parent": 0.0, "pivot_uvs": False},
                     "doc": "barre un perfil circular sobre una curva S con taper lineal; salida M"},
    "mesh_pipe_profile": {"cat": "Mesh", "graph_only": True,
                          "params": {"profile": "", "radius": 30.0,
                                     "sides": 10, "samples": 16, "capped": True,
                                     "profile_rotation": 0.0, "miter_limit": 4.0,
                                     "pivot_uvs": False},
                          "data_params": {"profile": "N[]"},
                          "doc": "barre S usando un perfil de radio N[] no lineal; salida M"},
    "mesh_along_curve": {"cat": "Mesh", "graph_only": True,
                         "asset_argument": True,
                         "params": {"count": 12, "start": 0.1, "end": 0.95,
                                    "radial_offset": 30.0, "turns": 2.0,
                                    "angle_offset": 0.0, "scale_start": 0.45,
                                    "scale_end": 0.25, "scale_x": 1.0,
                                    "scale_y": 1.0, "scale_z": 1.0,
                                    "orientation": "outward", "rotation_jitter": 0.0,
                                    "scale_jitter": 0.0, "offset_jitter": 0.0, "seed": 7,
                                    "crossed": False, "double_sided": False, "samples": 32},
                         "opciones": {"orientation": ["outward", "world_up", "random"]},
                         "doc": "copia un StaticMesh A con escala, orientación y variación sobre una curva S"},
    "copy_mesh_to_frames": {"cat": "Mesh", "graph_only": True,
                            "asset_argument": True,
                            "params": {"asset_offset_x": 0.0, "asset_offset_y": 0.0,
                                       "asset_offset_z": 0.0, "asset_pitch": 0.0,
                                       "asset_yaw": 0.0, "asset_roll": 0.0,
                                       "asset_scale": 1.0, "scale_x": 1.0,
                                       "scale_y": 1.0, "scale_z": 1.0,
                                       "inherit_scale": True},
                            "doc": "copia una StaticMesh A sobre cada frame F usando su transform y escala"},
    "copy_asset_selection": {"cat": "Mesh", "graph_only": True,
                             "params": {"asset_offset_x": 0.0, "asset_offset_y": 0.0,
                                        "asset_offset_z": 0.0, "asset_pitch": 0.0,
                                        "asset_yaw": 0.0, "asset_roll": 0.0,
                                        "asset_scale": 1.0, "scale_x": 1.0,
                                        "scale_y": 1.0, "scale_z": 1.0,
                                        "inherit_scale": True},
                             "doc": "copia la selección AF usando una variante distinta por frame"},
    "hism_output": {"cat": "Mesh", "graph_only": True,
                    "params": {"name": "TreeGen_Foliage",
                               "asset_offset_x": 0.0, "asset_offset_y": 0.0,
                               "asset_offset_z": 0.0, "asset_pitch": 0.0,
                               "asset_yaw": 0.0, "asset_roll": 0.0,
                               "asset_scale": 1.0, "inherit_scale": True},
                    "doc": "crea un actor con un HISM por variante AF; participa de Preview/Bake/Discard"},
    "mass_probe": {"label": "Probar MassEntity", "cat": "Mass",
                   "graph_only": True, "read_only": True, "params": {},
                   "doc": "crea una entidad Mass real por frame F, comprueba arquetipo y transform, "
                          "las destruye y deja pasar el mismo F; prueba de núcleo, no población persistente"},
    "mass_config": {"label": "Configuración MassEntity", "cat": "Mass",
                    "graph_only": True, "read_only": True,
                    "params": {"path": "", "require_ism": False,
                               "require_lod_budget": False, "require_patrol": False,
                               "require_variation": False},
                    "doc": "valida un UMassEntityConfigAsset y produce una referencia durable MC"},
    "mass_spec": {"label": "Receta MassEntity", "cat": "Mass",
                  "graph_only": True, "read_only": True,
                  "params": {"config": "", "config_path": "", "seed": 7, "budget": 4096},
                  "data_params": {"config": "MC"},
                  "optional_data_params": ("config",),
                  "doc": "convierte frames F y una configuración MC opcional en una receta durable MS"},
    "mass_spawn": {"label": "Crear población", "cat": "Mass",
                   "graph_only": True, "params": {},
                   "doc": "crea una población MH efímera; Discard, cambio de mundo y cierre de PIE la liberan"},
    "mass_inspect": {"label": "Inspeccionar población", "cat": "Mass",
                     "graph_only": True, "read_only": True, "params": {},
                     "doc": "mide cantidad, mundo y transforms de una población MH sin modificarla"},
    "mass_clear": {"label": "Liberar población", "cat": "Mass",
                   "graph_only": True, "params": {},
                   "doc": "destruye de forma idempotente todas las entidades de una población MH"},
    "mesh_leaf": {"cat": "Mesh", "graph_only": True,
                  "asset_argument": True, "optional_asset_argument": True,
                  "params": {"count": 4, "start": 0.1, "end": 0.95,
                             "radial_offset": 20.0, "rotate_per_index": 137.0,
                             "angle_offset": 0.0, "leaves_per_cluster": 3,
                             "length": 90.0, "width": 45.0,
                             "asset_scale": 1.0, "asset_pitch": 0.0,
                             "asset_yaw": 0.0, "asset_roll": 0.0,
                             "size_start": 1.0, "size_end": 0.7,
                             "splay": 70.0, "lift": 18.0,
                             "rotation_jitter": 12.0, "scale_jitter": 0.2,
                             "offset_jitter": 4.0, "seed": 7,
                             "inherit_scale": False, "double_sided": True, "samples": 32},
                  "doc": "genera racimos de hojas sobre S; el pin A opcional usa una StaticMesh real y sin A conserva el follaje procedural portable"},
    "mesh_transform": {"cat": "Mesh", "graph_only": True,
                       "params": {"x": 0.0, "y": 0.0, "z": 0.0, "pitch": 0.0,
                                  "yaw": 0.0, "roll": 0.0, "scale_x": 1.0,
                                  "scale_y": 1.0, "scale_z": 1.0},
                       "doc": "mueve, rota y escala una malla M sin modificar la entrada"},
    "mesh_color": {"cat": "Mesh", "graph_only": True,
                   "params": {"color": "#808080"},
                   "doc": "asigna un Vertex Color #RRGGBB a una malla M sin modificar la entrada"},
    "material_wind": {"cat": "Shader", "graph_only": True,
                      "params": {"name": "M_JamArbolViento", "folder": "/Game/Jam/Materials",
                                 "fuerza": 0.25, "velocidad": 1.2, "concentracion": 2.0,
                                 "eje_x": 1.0, "eje_y": 0.3, "eje_z": 0.0},
                      "doc": "material de viento que gira cada rama sobre el pivote estampado en UV1/UV2; salida A"},
    "material_node": {"cat": "Shader", "graph_only": True,
                      "params": {"type": "Multiply", "id": "", "inputs": "", "props": "",
                                 "x": 0, "y": 0},
                      "doc": "agrega un nodo al grafo de material (cualquiera de los 409 tipos); "
                             "`inputs` cablea lo que ya existe (A=uv, B=escala); salida MT"},
    "material_connect": {"cat": "Shader", "graph_only": True,
                         "params": {"from_node": "", "to_node": "", "to_input": "",
                                    "from_output": ""},
                         "doc": "conecta dos nodos del grafo de material por nombre de entrada; salida MT"},
    "material_output": {"cat": "Shader", "graph_only": True,
                        "params": {"node": "", "target": "MP_BASE_COLOR", "from_output": ""},
                        "opciones": {"target": list(_SALIDAS_MATERIAL)},
                        "doc": "enchufa un nodo a una salida del material (BaseColor, Roughness, WPO...); salida MT"},
    "material_build": {"cat": "Shader", "graph_only": True,
                       "params": {"name": "M_JamMaterial", "folder": "/Game/Jam/Materials",
                                  "blend_mode": "", "shading_model": "", "two_sided": False,
                                  "use_attributes": False, "max_instructions": 0},
                       "opciones": {"blend_mode": ["", "BLEND_OPAQUE", "BLEND_MASKED",
                                                   "BLEND_TRANSLUCENT", "BLEND_ADDITIVE"],
                                    "shading_model": ["", "MSM_DEFAULT_LIT", "MSM_UNLIT",
                                                      "MSM_SUBSURFACE", "MSM_TWO_SIDED_FOLIAGE"]},
                       "doc": "hornea el grafo MT como material de verdad; verifica antes de crear nada "
                              "y MIDE el costo (max_instructions = presupuesto, 0 = sin límite); salida A"},
    "mesh_uv_box": {"cat": "Mesh", "graph_only": True,
                    "params": {"size_x": 0.0, "size_y": 0.0, "size_z": 0.0,
                               "yaw": 0.0, "pitch": 0.0, "roll": 0.0,
                               "channel": 0, "min_island_tris": 2},
                    "doc": "proyección CÚBICA de UVs (el UV cubic map): seis planos, cada triángulo al que mejor mira. size 0 = la caja se ajusta a la malla"},
    "mesh_uv_unwrap": {"cat": "Mesh", "graph_only": True,
                       "params": {"method": "conformal", "channel": 0, "align_to_axes": True},
                       "opciones": {"method": ["conformal", "spectral_conformal", "exp_map"]},
                       "doc": "despliega resolviendo el aplanado en vez de proyectar: menos estiramiento, más costuras"},
    "mesh_uv_pack": {"cat": "Mesh", "graph_only": True,
                     "params": {"resolution": 1024, "channel": 0, "optimize_rotation": True},
                     "doc": "empaqueta las islas en el atlas 0..1 (el uvlayout de Houdini) y dice cuánto quedó usado"},
    "material_function": {"cat": "Shader", "graph_only": True,
                          "params": {"name": "MF_JamFuncion", "folder": "/Game/Jam/Functions",
                                     "kind": "funcion", "description": ""},
                          "opciones": {"kind": ["funcion", "capa", "mezcla"]},
                          "doc": "hornea el grafo MT como FUNCIÓN reusable (o capa/mezcla de Material Layers); salida A"},
    "material_call": {"cat": "Shader", "graph_only": True,
                      "params": {"function": "", "id": "", "inputs": "", "x": 0, "y": 0},
                      "doc": "llama a una función de material dentro del grafo; sus entradas se DESCUBREN del asset; salida MT"},
    "material_instance": {"cat": "Shader", "graph_only": True,
                          "params": {"name": "MI_JamInstancia", "folder": "/Game/Jam/Materials",
                                     "parent": "", "scalars": "", "vectors": ""},
                          "doc": "instancia del material con parámetros fijados: variantes sin recompilar; salida A"},
    "mesh_vertex_gradient": {"cat": "Mesh", "graph_only": True,
                             "params": {"eje": "z", "desde": 0.0, "hasta": 1.0,
                                        "power": 1.0, "canal": "todos"},
                             "doc": "pinta un gradiente 0..1 en el color de vértice de M: la máscara que el shader de viento necesita"},
    "mesh_uv_scale": {"cat": "Mesh", "graph_only": True,
                      "params": {"u": 1.0, "v": 1.0, "channel": 0,
                                 "origin_u": 0.0, "origin_v": 0.0},
                      "doc": "escala un canal UV existente sobre toda la malla M"},
    "mesh_material": {"cat": "Mesh", "graph_only": True,
                      "params": {"material": "/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial",
                                 "material_asset": ""},
                      "data_params": {"material_asset": "A"},
                      "optional_data_params": ("material_asset",),
                      "doc": "asigna material y section a M; el pin A acepta la salida de material_build "
                             "(y manda sobre el campo); Mesh to Static conserva el slot"},
    "mesh_remap_materials": {
        "label": "Reasignar IDs de material",
        "cat": "Mesh", "graph_only": True,
        "params": {"from_id": 1, "to_id": 0},
        "etiquetas_params": {"from_id": "ID de origen", "to_id": "ID de destino"},
        "doc": "fusiona todos los triángulos de un Material ID en otro ID ya existente; conserva los slots y no modifica la entrada",
    },
    "mesh_clean_material_ids": {
        "label": "Limpiar IDs de material",
        "cat": "Mesh", "graph_only": True,
        "params": {"remove_duplicate_materials": True},
        "etiquetas_params": {"remove_duplicate_materials": "unir duplicados"},
        "doc": "elimina IDs y slots sin uso, compacta el rango a 0..N-1 y conserva alineada la lista de materiales de M",
    },
    "mesh_validate": {
        "label": "Validar malla", "cat": "Mesh", "graph_only": True,
        "params": {"require_closed": False, "max_components": 0,
                   "require_uv": False, "require_materials": False},
        "etiquetas_params": {"require_closed": "exigir cerrada",
                              "max_components": "máx. componentes",
                              "require_uv": "exigir UV", "require_materials": "exigir materiales"},
        "doc": "mide vacío, huecos de IDs, bordes ambiguos, cierre, componentes, UV y materiales; informa y "
                      "deja pasar M sin tocarla. «máx. componentes» en 0 = sin límite",
    },
    "mesh_loft": {"label": "Tender entre curvas", "cat": "Mesh",
                  "graph_only": True,
                  "params": {"samples": 16, "uv_scale": 200.0, "material_id": 0},
                  "etiquetas_params": {"samples": "muestras (Número)",
                                       "uv_scale": "escala UV (Número)",
                                       "material_id": "material (Número)"},
                  "doc": "tiende una superficie entre dos o más curvas cableadas al mismo pin; "
                         "con dos curvas es el reglado, con más es el loft. El ORDEN de los cables "
                         "decide de qué lado mira"},
    "mesh_merge":  {"cat": "Mesh", "graph_only": True, "params": {},
                     "doc": "combina dos o más mallas M en una salida"},
    "mesh_normals": {"cat": "Mesh", "graph_only": True,
                     "params": {"angle_weighted": True, "area_weighted": True},
                     "doc": "recalcula normales conservando los atributos de la malla M"},
    "mesh_weld": {
        "label": "Soldar bordes",
        "cat": "Mesh", "graph_only": True,
        "params": {"tolerance_cm": 0.01, "only_unique_pairs": True},
        "etiquetas_params": {"tolerance_cm": "tolerancia (cm)",
                              "only_unique_pairs": "sólo pares únicos"},
        "doc": "suelda bordes abiertos coincidentes de M para cerrar grietas entre piezas; "
               "no garantiza cerrar la malla del todo — piezas separadas por diseño quedan intactas",
    },
    "mesh_simplify_count": {
        "label": "Simplificar por triángulos",
        "cat": "Mesh", "graph_only": True,
        "params": {"target_triangles": 5000, "method": "attributes",
                   "preserve_seams": True, "regularize": 0.000001},
        "opciones": {"method": ["attributes", "normals", "volume", "standard"]},
        "etiquetas_params": {"target_triangles": "triángulos objetivo",
                              "method": "métrica", "preserve_seams": "preservar costuras",
                              "regularize": "regularizar"},
        "doc": "reduce M hasta una cantidad de triángulos; por defecto conserva atributos y costuras sin modificar la entrada",
    },
    "mesh_simplify_tolerance": {
        "label": "Simplificar por tolerancia",
        "cat": "Mesh", "graph_only": True,
        "params": {"tolerance_cm": 1.0, "method": "attributes",
                   "preserve_seams": True, "regularize": 0.000001},
        "opciones": {"method": ["attributes", "normals", "volume", "standard"]},
        "etiquetas_params": {"tolerance_cm": "desviación (cm)",
                              "method": "métrica", "preserve_seams": "preservar costuras",
                              "regularize": "regularizar"},
        "doc": "reduce M hasta que otro colapso superaría la desviación máxima en cm; conserva la entrada",
    },
    "mesh_simplify_edge_length": {
        "label": "Simplificar por arista",
        "cat": "Mesh", "graph_only": True,
        "params": {"edge_length_cm": 5.0, "method": "attributes",
                   "preserve_seams": True, "regularize": 0.000001},
        "opciones": {"method": ["attributes", "normals", "volume", "standard"]},
        "etiquetas_params": {"edge_length_cm": "largo objetivo (cm)",
                              "method": "métrica", "preserve_seams": "preservar costuras",
                              "regularize": "regularizar"},
        "doc": "reduce M por largo de arista con error geométrico; es un objetivo, no una remalla uniforme",
    },
    "debug": {"cat": "Debug", "graph_only": True,
              "params": {"tamano": 30.0, "grosor": 1.2, "escalar_con_dato": True,
                         "cada": 1, "solo_direccion": False},
              "doc": "AYUDANTE universal: conectale CUALQUIER cable y dibuja lo que corresponde. F→ejes por frame · P→cubo por punto (tamaño=peso) · S→recorrido de la curva · N[]→la serie como gráfico · M→caja + normales · AF→frames por variante. Sale por M: se mergea, hornea o coloca",
              },
    "points_to_frames": {"cat": "Mesh", "graph_only": True,
                         "params": {"orientacion": "normal", "escala": 1.0,
                                    "escala_desde_peso": True, "giro_al_azar": True, "seed": 7},
                         "opciones": {"orientacion": ["normal", "vertical"]},
                         "doc": "PUENTE P → F: convierte el stream de puntos de Flow en frames. El peso de la máscara pasa a ser la escala de cada pieza"},
    "mesh_box": {"cat": "Mesh", "graph_only": True,
                 "params": {"size_x": 100.0, "size_y": 100.0, "size_z": 100.0,
                            "steps_x": 0, "steps_y": 0, "steps_z": 0},
                 "doc": "caja con el pivote en la BASE (apoya sola, como pide un kit)"},
    "mesh_capsule": {"cat": "Mesh", "graph_only": True,
                     "params": {"radius": 30.0, "length": 150.0,
                                "hemisphere_steps": 5, "sides": 12},
                     "doc": "cápsula: la forma de blockout y colisión por excelencia"},
    "mesh_torus": {"cat": "Mesh", "graph_only": True,
                   "params": {"major_radius": 100.0, "minor_radius": 25.0,
                              "major_steps": 24, "minor_steps": 12},
                   "doc": "toro (dona); minor_radius tiene que ser menor que major_radius"},
    "mesh_disc": {"cat": "Mesh", "graph_only": True,
                  "params": {"radius": 100.0, "sides": 24, "start_angle": 0.0,
                             "end_angle": 360.0, "hole_radius": 0.0},
                  "doc": "disco plano; con hole_radius es un anillo y con los ángulos, una porción"},
    "mesh_round_rect": {"cat": "Mesh", "graph_only": True,
                        "params": {"size_x": 200.0, "size_y": 200.0,
                                   "corner_radius": 20.0, "steps_round": 6},
                        "doc": "rectángulo de esquinas redondeadas en el plano XY"},
    "mesh_stairs": {"cat": "Mesh", "graph_only": True,
                    "params": {"step_width": 150.0, "step_height": 18.0, "step_depth": 28.0,
                               "steps": 10, "floating": False},
                    "doc": "escalera recta; «floating» deja los escalones sueltos, sin faldón"},
    "mesh_stairs_curved": {"cat": "Mesh", "graph_only": True,
                           "params": {"step_width": 150.0, "step_height": 18.0,
                                      "inner_radius": 200.0, "curve_angle": 90.0,
                                      "steps": 12, "floating": False},
                           "doc": "escalera curva; curve_angle con signo elige el sentido del giro"},
    "mesh_sphere_box": {"cat": "Mesh", "graph_only": True,
                        "params": {"radius": 80.0, "steps": 6},
                        "doc": "esfera de topología cúbica: cuadrángulos parejos, sin los polos apretados de la lat/long"},
    "mesh_revolve": {"cat": "Mesh", "graph_only": True,
                     "params": {"steps": 24, "capped": True, "degrees": 360.0, "samples": 32},
                     "doc": "TORNO: revoluciona el perfil de una curva S alrededor del eje Z (x = distancia al eje, z = altura). Columnas, balaustres, vasijas"},
    "mesh_bark": {"cat": "Mesh", "graph_only": True,
                  "params": {"amplitud": 2.0, "escala": 0.06, "alargue": 0.25,
                             "octavas": 3, "surcos": 0.6, "seed": 7},
                  "doc": "relieve de corteza sobre M: ruido estirado a lo largo del eje (surcos verticales) desplazando cada vértice por su normal. «amplitud» debe ser menor que el radio más fino de la malla o la punta se invierte"},
    "mesh_noise": {"label": "Ruido Perlin", "cat": "Mesh",
                   "graph_only": True,
                   "params": {"amplitud": 100.0, "frecuencia": 0.003,
                              "seed": 7, "por_normal": True},
                   "etiquetas_params": {"amplitud": "amplitud (cm)",
                                         "frecuencia": "frecuencia (1/cm)",
                                         "por_normal": "desplazar por normal"},
                   "doc": "deforma M con Perlin 3D determinista; frecuencia en 1/cm y amplitud en cm"},
    "mesh_compare": {"cat": "Mesh", "graph_only": True,
                     "asset_argument": True,
                     "params": {"franjas": 8, "solo_forma": False,
                                "alto": 0.30, "ancho": 0.35, "esbeltez": 0.20,
                                "vertices": 0.50, "triangulos": 0.50,
                                "perfil": 0.15, "silueta": 0.18},
                     "doc": "ORÁCULO: compara la malla M contra un StaticMesh de referencia (tamaño, proporción, conteos, secciones, perfil de masa y silueta) y la deja pasar sin tocarla. «solo_forma» compara la FORMA sin exigir el mismo tamaño"},
    "mesh_preview": {"cat": "Mesh", "graph_only": True,
                     "label": "Ver sin hornear",
                     "params": {"name": "JamPreview"},
                     "doc": "muestra la malla en el nivel SIN escribir un asset: ~1 ms contra los "
                            "68-257 ms de hornear. Es el nodo para iterar — poné este al final "
                            "mientras ajustás, y cambialo por «Mesh to Static» cuando te guste"},
    "mesh_to_static": {"cat": "Mesh", "graph_only": True,
                       "params": {"name": "GeneratedMesh", "folder": "/Game/Jam/Meshes",
                                  "collision": True, "recompute_tangents": True,
                                  "show_vertex_colors": True},
                       "doc": "convierte M a StaticMesh A y muestra sus Vertex Colors; Preview/Bake/Discard"},
    "pcg":          {"cat": "Scatter",
                     "params": {"area": 1600.0, "count": 200, "density": 0.0, "view": False,
                                "name": "JamPCG", "preset": ""},
                     "doc": "realiza el scatter (o un preset) con el PCG nativo (HISM, regenerable)"},
    "gizmo":        {"cat": "Edit",    "params": {"on": True},
                     "doc": "marca en el viewport dónde está parado Jam + la huella del asset activo"},
    "ghost":        {"cat": "Edit",    "params": {"on": True},
                     "doc": "muestra la malla que se va a colocar siguiendo el punto de mira"},
}

# Verbos que NO crean nada COLOCABLE: son selección, helpers o escritores de Content y por ahora no
# pasan por el Preview de actores. PCG ya no pertenece acá: su PCGVolume y su PCGGraph temporal
# participan juntos de Run/Bake/Discard.
SIN_SPAWN = {"asset", "pick", "gizmo", "ghost", "pivot", "pivot_set", "normalize", "fracture",
             "nanite_analyze", "nanite_validate"}

# Orden de las categorías en la barra (como Dash). Las vacías no se muestran.
# Las seis primeras son verbos de herramienta; las que siguen llegan de las ops de Flow que ahora
# también son verbos del Graph (ver `_registrar_ops_flow`). El orden agrupa por lo que hace cada
# familia: generar puntos → filtrarlos → pesarlos → reordenarlos → moverlos → juntarlos → mirarlos.
CATEGORIAS = ["Content", "Place", "Scatter", "Mass", "Create", "Mesh", "Edit",
              "Vector", "Mask", "Weight", "Sets", "Transform", "Combine", "Display", "Debug"]

# Contrato del Graph. Vive junto al REGISTRO para que Slate y el Preflight lean la misma verdad.
# `source` significa sin pin gordo `in`; una fuente todavía puede tener un pin de parámetro `asset`.
GRAPH_SOURCES = {"asset", "pick", "create_spline", "gizmo", "ghost", "pivot", "pivot_set",
                 "mass_config",
                 "curve_bezier", "curve_line", "curve_line_sdl", "curve_interpolate",
                 "mesh_triangle", "mesh_quad", "mesh_grid", "mesh_cylinder",
                 "mesh_cone", "mesh_sphere", "graph_curve", "series_range", "curve_polyline",
                 "mesh_box", "mesh_capsule", "mesh_torus", "mesh_disc",
                 "mesh_round_rect", "mesh_stairs", "mesh_stairs_curved", "mesh_sphere_box",
                 "brush",   # fuente: los centros salen de la selección, no de un cable
                 # Los `select_*` no tienen entrada principal: las dos ramas y la
                 # condición entran por pines de datos NOMBRADOS, porque «sí» y «no»
                 # tienen significado y no se pueden distinguir por orden de cable.
                 "select_mesh", "select_asset"}
# Tools que realmente pueden ejecutarse sin un asset. `asset` y `pick` lo PRODUCEN; `create_spline` y
# `pivot_set` trabajan sobre la escena/selección. Gizmo y Ghost sí necesitan uno para mostrar huella.
GRAPH_NO_ASSET = {"mesh_preview", "asset", "pick", "create_spline", "pivot_set", "instance", "brush",
                  # Un reroute no CONSUME un asset: lo deja pasar.
                  "reroute_mesh", "reroute_asset", "reroute_points", "reroute_curve", "reroute_frames",
                  "select_mesh", "select_asset",
                  # `scatter` genera PUNTOS: no toca ningún asset. Lo usaba sólo para
                  # medir huellas, y eso ahora pasa al colocar.
                  "scatter",
                  "curve_bezier", "curve_line", "curve_line_sdl", "curve_interpolate",
                  "mesh_triangle", "mesh_quad", "mesh_grid", "mesh_cylinder",
                  "mesh_cone", "mesh_sphere", "mesh_ribbon", "mesh_pipe", "mesh_pipe_profile",
                  "mesh_box", "mesh_capsule", "mesh_torus", "mesh_disc",
                  "mesh_round_rect", "mesh_stairs", "mesh_stairs_curved",
                  "mesh_sphere_box", "mesh_revolve", "curve_polyline", "curve_move",
                  "curve_resample",
                  "curve_smooth", "curve_fuse_collinear", "curve_subdivide", "curve_offset",
                  "mesh_transform", "mesh_extrude", "mesh_merge", "mesh_loft", "graph_curve", "series_range", "series_remap",
                  "curve_child", "curve_frames", "distribute_frames", "transform_frames",
                  "branch_from_frames",
                  "asset_set", "choose_asset", "curve_branches", "mesh_leaf",
                  "copy_asset_selection", "hism_output", "mass_probe", "mass_config", "mass_spec",
                  "mass_spawn", "mass_inspect", "mass_clear",
                  "mesh_color", "mesh_uv_scale", "mesh_material", "mesh_bark", "mesh_noise", "points_to_frames", "debug",
                  "mesh_remap_materials", "mesh_clean_material_ids",
                  "mesh_validate",
                  "mesh_normals", "mesh_weld", "mesh_simplify_count", "mesh_simplify_tolerance",
                  "mesh_simplify_edge_length", "mesh_to_static",
                  # UVs procedurales y todo el frente de shader: ninguno necesita un asset de
                  # entrada — trabajan sobre la malla que les llega o sobre el grafo de material.
                  # Sin estar acá, `validar` los rechaza con «requiere asset explícito» y NO se
                  # pueden correr desde el canvas, aunque llamar a su función directamente funcione.
                  "mesh_uv_box", "mesh_uv_unwrap", "mesh_uv_pack",
                  "material_node", "material_connect", "material_output", "material_build",
                  "material_function", "material_call", "material_instance", "material_wind",
                  # Dos que estaban rotos desde que se agregaron y nadie podía correr en el canvas:
                  # transforman el dato que les llega y no tocan ningún asset.
                  "curve_noise", "mesh_vertex_gradient"}
GRAPH_IN_NAMES = {"reroute_mesh": "M", "reroute_asset": "A", "reroute_points": "P", "reroute_curve": "S", "reroute_frames": "F",
                  "mass_probe": "F",
                  "mass_spec": "F", "mass_spawn": "MS", "mass_inspect": "MH", "mass_clear": "MH",
                  "points_to_frames": "P", "debug": "*", "curve_child": "S", "curve_noise": "S", "curve_frames": "S", "distribute_frames": "F",
                  "series_remap": "N[]",
                  "curve_move": "S", "curve_resample": "S", "curve_smooth": "S",
                  "curve_fuse_collinear": "S", "curve_subdivide": "S",
                  "curve_offset": "S",
                  "transform_frames": "F", "branch_from_frames": "F", "curve_branches": "S",
                  "asset_set": "A", "choose_asset": "F",
                  "mesh_from_asset": "A", "mesh_copy_static": "A",
                  "mesh_copy_skeletal": "A", "mesh_ribbon": "S", "mesh_pipe": "S", "mesh_pipe_profile": "S",
                  "mesh_revolve": "S",
                  "mesh_along_curve": "S", "copy_mesh_to_frames": "F", "mesh_leaf": "S",
                  "mesh_loft": "S",
                  "copy_asset_selection": "AF",
                  "hism_output": "AF", "mesh_transform": "M", "mesh_extrude": "M", "mesh_color": "M",
                  "mesh_uv_scale": "M", "mesh_material": "M", "mesh_bark": "M", "mesh_noise": "M",
                  "mesh_remap_materials": "M", "mesh_clean_material_ids": "M",
                  "mesh_validate": "M",
                  "mesh_vertex_gradient": "M", "mesh_merge": "M", "mesh_normals": "M",
                  "mesh_weld": "M",
                  "mesh_simplify_count": "M", "mesh_simplify_tolerance": "M",
                  "mesh_simplify_edge_length": "M",
                  "mesh_uv_box": "M", "mesh_uv_unwrap": "M", "mesh_uv_pack": "M",
                  # Entrada OPCIONAL: sin cable reparte en un área; con puntos, alrededor de cada uno.
                  "scatter": "P",
                  "mesh_compare": "M", "mesh_to_static": "M", "mesh_preview": "M",
                  "material_node": "MT", "material_connect": "MT", "material_output": "MT",
                  "material_build": "MT", "material_function": "MT", "material_call": "MT",
                  "material_instance": "A", "instance": "P"}
GRAPH_OUT_NAMES = {"brush": "P", "mesh_preview": "", "reroute_mesh": "M", "reroute_asset": "A", "reroute_points": "P", "reroute_curve": "S", "reroute_frames": "F",
                   "mass_probe": "F", "mass_config": "MC",
                   "mass_spec": "MS", "mass_spawn": "MH", "mass_inspect": "MH", "mass_clear": "MH",
                   "select_mesh": "M", "select_asset": "A",
                   "points_to_frames": "F", "debug": "M", "asset": "A", "pick": "A", "create_spline": "S",
                   # `scatter` describe DÓNDE (puntos) y `instance` decide cuándo eso se vuelve
                   # escena. Es lo que le da un significado obvio a encadenar nodos de colocación.
                   "scatter": "P", "instance": "A",
                   "material_wind": "A", "material_build": "A",
                   "material_node": "MT", "material_connect": "MT", "material_output": "MT",
                   "material_call": "MT", "material_function": "A", "material_instance": "A",
                   "curve_bezier": "S", "curve_line": "S", "curve_line_sdl": "S",
                   "curve_interpolate": "S",
                   "curve_child": "S", "curve_noise": "S", "curve_frames": "F",
                   "curve_polyline": "S", "curve_move": "S", "curve_resample": "S", "curve_smooth": "S",
                   "curve_fuse_collinear": "S", "curve_subdivide": "S",
                   "curve_offset": "S",
                   "distribute_frames": "F", "transform_frames": "F",
                   "branch_from_frames": "S", "curve_branches": "S",
                   "asset_set": "A[]", "choose_asset": "AF", "graph_curve": "N[]",
                   "series_range": "N[]", "series_remap": "N[]",
                   "mesh_triangle": "M", "mesh_quad": "M", "mesh_grid": "M",
                   "mesh_cylinder": "M", "mesh_cone": "M", "mesh_sphere": "M",
                   "mesh_box": "M", "mesh_capsule": "M", "mesh_torus": "M",
                   "mesh_disc": "M", "mesh_round_rect": "M", "mesh_stairs": "M",
                   "mesh_stairs_curved": "M", "mesh_sphere_box": "M", "mesh_revolve": "M",
                   "mesh_from_asset": "M", "mesh_copy_static": "M",
                   "mesh_copy_skeletal": "M", "mesh_ribbon": "M", "mesh_pipe": "M", "mesh_pipe_profile": "M",
                   "mesh_along_curve": "M", "mesh_loft": "M",
                   "copy_mesh_to_frames": "M", "mesh_leaf": "M",
                   "copy_asset_selection": "M",
                   "hism_output": "H", "mesh_transform": "M", "mesh_extrude": "M", "mesh_color": "M",
                   "mesh_uv_scale": "M", "mesh_material": "M", "mesh_bark": "M", "mesh_noise": "M",
                   "mesh_remap_materials": "M", "mesh_clean_material_ids": "M",
                   "mesh_validate": "M",
                   "mesh_vertex_gradient": "M", "mesh_merge": "M", "mesh_normals": "M",
                  "mesh_weld": "M",
                   "mesh_simplify_count": "M", "mesh_simplify_tolerance": "M",
                   "mesh_simplify_edge_length": "M",
                  "mesh_uv_box": "M", "mesh_uv_unwrap": "M", "mesh_uv_pack": "M",
                  # Entrada OPCIONAL: sin cable reparte en un área; con puntos, alrededor de cada uno.
                  "scatter": "P",
                   "mesh_compare": "M", "mesh_to_static": "A"}
# ---- las ops de Flow como verbos del Graph ----
# Hasta acá Jam tenía dos vocabularios que no se tocaban: 29 ops de Flow que producen un stream de
# puntos `P`, y 50 verbos de herramienta de los que NINGUNO consumía `P`. Un canvas mixto caía entero
# al runner de verbos, donde cada op de Flow era desconocida.
# El ejecutor del Graph es genérico —`info["fn"](entrada, **params)` más `dato_producido_runtime`—,
# así que envolver una op es mecánico. Con esto las máscaras, los weights y los generadores de puntos
# alimentan el tab Mesh, y `points_to_frames` cierra el puente `P → F`.
# `instance` y `source_surface` quedan afuera: sus funciones viven en el adaptador de Unreal.
# `number`, `math` y `text` también: el Graph ya los maneja como nodos de VALOR.

# ---- los nodos de material, uno por ficha ----
# `material_node` puede crear cualquiera de los 408 tipos escribiendo su nombre, pero eso es una
# línea de comando disfrazada de nodo: para usarlo hay que SABER que `Lerp` se llama
# `LinearInterpolate`. El resto de Jam funciona al revés —una ficha por verbo, con su icono y su
# firma en el tooltip— y no hay razón para que el tab de shader sea la excepción.
#
# Éstos son los que se usan todo el tiempo. Los otros 390 siguen a un `material_node` de distancia,
# que queda como la puerta a lo que no está en la paleta.
NODOS_MATERIAL: dict[str, tuple[str, str]] = {
    # Constantes y parámetros: de dónde salen los números
    "mat_const":     ("Constant", "un número fijo"),
    "mat_color":     ("Constant3Vector", "un color/vector fijo (prop `constant=#RRGGBB`)"),
    "mat_scalar":    ("ScalarParameter", "número con NOMBRE: se retoca en una instancia sin recompilar"),
    "mat_vector":    ("VectorParameter", "color con NOMBRE: se retoca en una instancia"),
    # Matemática
    "mat_add":       ("Add", "A + B"),
    "mat_sub":       ("Subtract", "A − B"),
    "mat_mul":       ("Multiply", "A × B"),
    "mat_div":       ("Divide", "A ÷ B"),
    "mat_lerp":      ("LinearInterpolate", "mezcla A y B según Alpha (el Lerp de UE)"),
    "mat_power":     ("Power", "Base elevado a Exp: endurece o suaviza un gradiente"),
    "mat_clamp":     ("Clamp", "recorta entre Min y Max"),
    "mat_oneminus":  ("OneMinus", "1 − x: invierte una máscara"),
    "mat_saturate":  ("Saturate", "recorta a 0..1"),
    # Texturas y coordenadas
    "mat_texture":   ("TextureSample", "muestrea una textura (prop `texture=/Game/...`)"),
    "mat_uv":        ("TextureCoordinate", "las UVs de la malla (prop `coordinate_index`)"),
    "mat_panner":    ("Panner", "desplaza unas UVs con el tiempo: texturas que se mueven"),
    "mat_noise":     ("Noise", "ruido procedural, sin textura"),
    # Vectores
    "mat_append":    ("AppendVector", "junta A y B en un vector más ancho"),
    "mat_mask":      ("ComponentMask", "toma canales sueltos (props r/g/b/a)"),
    "mat_normalize": ("Normalize", "vector a largo 1"),
    "mat_dot":       ("DotProduct", "producto punto: cuánto se parecen dos direcciones"),
    # Lo que aporta la geometría y la escena
    "mat_worldpos":  ("WorldPosition", "la posición del píxel en el mundo"),
    "mat_vnormal":   ("VertexNormalWS", "la normal del vértice"),
    "mat_vcolor":    ("VertexColor", "el color de vértice pintado en la malla"),
    "mat_time":      ("Time", "el reloj: lo que hace que algo se mueva"),
    "mat_fresnel":   ("Fresnel", "más fuerte en los bordes vistos de canto"),
}


def _registrar_nodos_material() -> list[str]:
    from . import shader

    registrados = []
    for verbo, (tipo, doc) in NODOS_MATERIAL.items():
        entradas = shader.ENTRADAS.get(tipo, ())
        # La firma va en el DOC porque es lo que se necesita para cablearlo, y va derivada del motor
        # para que no pueda mentir: si UE renombra un pin, el tooltip cambia solo.
        firma = f" · entradas: {', '.join(entradas)}" if entradas else " · sin entradas"
        REGISTRO[verbo] = {
            "cat": "Shader", "graph_only": True,
            "params": {"id": "", "inputs": "", "props": "", "x": 0, "y": 0},
            "doc": f"{tipo}: {doc}{firma}", "_nodo_material": tipo,
        }
        GRAPH_IN_NAMES[verbo] = "MT"
        GRAPH_OUT_NAMES[verbo] = "MT"
        GRAPH_MIN_INPUTS[verbo] = 0      # cualquiera puede arrancar un grafo de material
        GRAPH_NO_ASSET.add(verbo)
        registrados.append(verbo)
    return registrados


def _registrar_ops_flow() -> list[str]:
    from . import flow
    registradas = []
    for kind, meta in flow.OPS_META.items():
        if kind in REGISTRO or kind not in flow.OPS or kind in flow.VALOR_KINDS:
            continue
        aridad = flow.OPS[kind][1]
        REGISTRO[kind] = {
            "cat": meta.get("cat", "Flow"),
            "graph_only": True, "params": dict(meta.get("params", {})),
            "opciones": dict(meta.get("opciones", {})),
            "doc": meta.get("doc", ""), "_flow_op": True,
        }
        GRAPH_IN_NAMES[kind] = "" if aridad == 0 else "P"
        GRAPH_OUT_NAMES[kind] = "P"
        if aridad == 0:
            GRAPH_SOURCES.add(kind)
        else:
            GRAPH_ARITY[kind] = aridad
            if aridad == -1:
                GRAPH_MIN_INPUTS[kind] = 2
        GRAPH_NO_ASSET.add(kind)
        registradas.append(kind)
    return registradas


GRAPH_ARITY = {"mesh_merge": -1, "asset_set": -1, "mesh_loft": -1}
# `material_node` tiene pin de entrada MT pero el PRIMER nodo de una cadena no tiene de dónde
# venir: con el mínimo en 1 haría falta un verbo `material_new` de puro trámite en el canvas.
GRAPH_MIN_INPUTS = {"mesh_merge": 2, "asset_set": 2, "mesh_loft": 2, "material_node": 0, "scatter": 0,
                    "material_call": 0, "material_instance": 0}
OPS_FLOW_EN_GRAPH = _registrar_ops_flow()
NODOS_MATERIAL_EN_GRAPH = _registrar_nodos_material()

#: Verbos que ningún otro motor va a tener, y por qué. Lo que no está acá y no es puro NO es «sólo de
#: Unreal»: es «todavía no tiene implementación» en el motor que falte, y lo dice así.
_SOLO_UNREAL = {"nanite": "Nanite existe sólo en Unreal", "nanite_analyze": "Nanite existe sólo en Unreal",
                "nanite_validate": "Nanite existe sólo en Unreal",
                "fracture": "la fractura es Chaos Destruction, de Unreal",
                "pcg": "usa el framework PCG de Unreal"}
_SOLO_UNREAL_POR_CATEGORIA = {"Mass": "MassEntity es de Unreal",
                              "Shader": "arma el grafo de materiales de Unreal"}

#: La base común (tarea `base-comun`): se calculan en el núcleo (`jam.comun`) y cada motor sólo los
#: vuelve suyos con su primitiva «malla desde datos». Un test ata esta lista a `comun.IMPLEMENTA`.
COMUNES = frozenset({"mesh_box", "graph_curve", "series_range", "series_remap", "curve_bezier",
                     "curve_polyline", "curve_interpolate", "curve_line", "curve_line_sdl",
                     "curve_move", "curve_resample", "curve_smooth"})
#: Las PRIMITIVAS del contrato que cada motor implementa con lo suyo (no se calculan en el núcleo):
#: mostrar una malla sin hornearla. También corren en cualquier motor: todo adaptador las trae.
PRIMITIVAS = frozenset({"mesh_preview"})

for _nombre, _info in REGISTRO.items():
    _source = _nombre in GRAPH_SOURCES
    # En qué motores corre (tarea `fuera-del-motor`, criterio 11 de `dsl-grafos`). Se DERIVA: una op
    # de Flow o un verbo de la base común es cálculo del núcleo y corre en cualquiera («*»); el resto
    # vive en el adaptador de Unreal.
    _info["motores"] = (("*",) if (_info.get("_flow_op") or _nombre in COMUNES
                                   or _nombre in PRIMITIVAS) else ("unreal",))
    _porque = _SOLO_UNREAL.get(_nombre) or _SOLO_UNREAL_POR_CATEGORIA.get(_info.get("cat", ""))
    if _porque:
        _info["porque"] = _porque
    _info["source"] = _source
    _info["aridad"] = GRAPH_ARITY.get(_nombre, 0 if _source else 1)
    _info["min_inputs"] = GRAPH_MIN_INPUTS.get(_nombre, 0 if _source else 1)
    _info["in_name"] = "" if _source else GRAPH_IN_NAMES.get(_nombre, "A")
    _info["asset_required"] = _nombre not in GRAPH_NO_ASSET
    # `asset_pin` = este verbo CONSUME un asset (y hay que resolvérselo). No confundir con dibujar
    # una fila: son dos preguntas distintas y mezclarlas rompe la resolución.
    _info["asset_pin"] = bool(
        _info["asset_required"] or _info.get("optional_asset_argument", False))
    # `asset_row` = tiene una fila `asset` en el canvas: pin con NOMBRE y campo de texto, que se
    # grisea solo cuando le entra un cable (como cualquier otro param cableado).
    #
    # La tiene todo el que consume un asset. Cuando además su entrada principal es de tipo A, esa
    # fila ES la entrada principal y el nub anónimo del header se oculta — el duplicado no eran la
    # fila y el nub, era tener los DOS. Se queda el que dice qué es.
    _info["asset_row"] = bool(_info["asset_pin"])
    _info["out_name"] = GRAPH_OUT_NAMES.get(_nombre, "A")


#: Los parámetros que son un ÁNGULO EN GRADOS, y por eso la ficha les dibuja una perilla.
#:
#: Se DECLARA en vez de derivarse del nombre porque derivarlo da falsos positivos que
#: importan: `optimize_rotation` y `angle_weighted` son booleanos, `target_triangles` y
#: `triangulos` sólo comparten letras —«tri-ANGLE-s», «tri-ANGUL-os»—, y esos dos se
#: colaron igual en la primera curación: los sacó el test, no la lectura. Un control que
#: aparece donde no va enseña una
#: mentira sobre el parámetro.
#:
#: Los de `math_sin/cos/tan` quedan afuera a propósito: miden en RADIANES, y convertirlos
#: para la aguja agregaría un camino de ida y vuelta cuyo único consumidor son tres
#: verbos. Para pasar de grados a radianes ya está `math_radians`, que es un nodo visible.
PARAMS_ANGULARES = {
    "branch_from_frames": ("angle", "angle_jitter",),
    "copy_asset_selection": ("asset_pitch", "asset_roll", "asset_yaw",),
    "copy_mesh_to_frames": ("asset_pitch", "asset_roll", "asset_yaw",),
    "curve_branches": ("angle", "angle_jitter", "rotate_per_index",),
    "curve_child": ("angle",),
    "curve_frames": ("angle_offset",),
    "curve_fuse_collinear": ("angle_tolerance",),
    "distribute_frames": ("angle_jitter", "angle_offset", "rotate_per_index",),
    "hism_output": ("asset_pitch", "asset_roll", "asset_yaw",),
    "math_radians": ("grados",),
    "mesh_along_curve": ("angle_offset", "rotation_jitter",),
    "mesh_disc": ("end_angle", "start_angle",),
    "mesh_leaf": ("angle_offset", "asset_pitch", "asset_roll", "asset_yaw", "rotate_per_index", "rotation_jitter",),
    "mesh_pipe": ("profile_rotation",),
    "mesh_pipe_profile": ("profile_rotation",),
    "mesh_revolve": ("degrees",),
    "mesh_stairs_curved": ("curve_angle",),
    "mesh_transform": ("pitch", "roll", "yaw",),
    "mesh_uv_box": ("pitch", "roll", "yaw",),
    "place": ("yaw",),
    "spline": ("jitter_yaw",),
    "transform_frames": ("pitch", "pitch_jitter", "roll", "roll_jitter", "yaw", "yaw_jitter",),
}


def unidad_de(verbo: str, pin: str) -> str:
    """`"grados"` si ese parámetro es un ángulo; `""` si es una cantidad cualquiera."""
    return "grados" if pin in PARAMS_ANGULARES.get(verbo, ()) else ""

def disponible(verbo: str, motor: str = "unreal", implementados=None) -> tuple[bool, str]:
    """¿Este verbo corre en `motor`? `(sí, porqué_no)`.

    Si el adaptador conectado anunció lo que implementa (`implementados`), manda eso: es la verdad del
    motor que está del otro lado. Si no, lo declarado en `motores`. Un verbo fuera del registro (una
    instancia `fn:`, un nodo de valor) no se juzga acá.
    """
    info = REGISTRO.get(verbo)
    if info is None:
        return True, ""
    si = (verbo in implementados) if implementados is not None else (
        "*" in info.get("motores", ()) or motor in info.get("motores", ()))
    if si:
        return True, ""
    return False, info.get("porque") or f"todavía no tiene implementación en {motor}"


def spec_json(*, include_graph_only: bool = False, motor: str = "unreal", implementados=None) -> str:
    """El registro como JSON (categoría/verbo/doc/params) para que la Dash Bar en C++ se arme sola.
    Agregar una herramienta a REGISTRO la hace aparecer en su sección sin tocar C++."""
    import json

    from .letras import letras_de_pines

    def tipo(v) -> str:
        # el TIPO viaja en el spec para que la UI use el control expresivo que corresponde
        # (checkbox para bool, spinner para números) en vez de un campo de texto para todo.
        if isinstance(v, bool):
            return "bool"
        if isinstance(v, int):
            return "int"
        if isinstance(v, float):
            return "float"
        return "str"

    salida = []
    from .registro_core import superficies_de

    for nombre, info in REGISTRO.items():
        # La superficie decide quién ve la tool. `include_graph_only` sigue siendo el pedido del
        # canvas —«dame todo»—; sin él se sirve la Dash Bar, que es una superficie declarada y ya no
        # «lo que nadie marcó».
        if not include_graph_only and "dash" not in superficies_de(info):
            continue
        opciones = info.get("opciones", {})
        # Letra de cada pin para el modo compacto. Va en el spec —y no la calcula el C++— para que
        # la regla viva UNA vez, en `jam.letras`, donde está testeada contra los 140 verbos.
        letras = letras_de_pines(list(info["params"]))
        # Deshabilitado, no escondido (Brian, 2026-09-28): un grafo de otro motor se sigue leyendo
        # entero, y se ve qué falta y por qué.
        esta, porque = disponible(nombre, motor, implementados)
        salida.append({
            "disponible": esta,
            "porque": porque,
            "motores": list(info.get("motores", ())),
            "verbo": nombre,
            "label": info.get("label", nombre),
            "cat": info.get("cat", "Place"),
            "doc": info["doc"],
            "source": info["source"],
            "aridad": info["aridad"],
            # Tipo del pin gordo de entrada: en el grafo de verbos viaja el asset/actor activo.
            "in_name": info["in_name"],
            # Tipos EXTRA que admite el pin gordo además del suyo. Viaja en el spec para que la
            # regla de compatibilidad del C++ no tenga que conocer verbos por nombre.
            "in_accepts": sorted(info.get("in_accepts", {})),
            "asset_pin": info["asset_pin"],
            "asset_row": info["asset_row"],
            "out_name": info["out_name"],
            # Salidas ADEMÁS de la principal, para que la ficha dibuje un nub por cada una. Casi
            # siempre vacío, y ahí el C++ hace exactamente lo de siempre: un solo nub «out». La
            # rebanada no viaja —es un invocable y vive en el cerebro—; Slate sólo necesita saber
            # qué pines existen, de qué tipo son y cómo se llaman.
            "outs": [{"name": pin, "tipo": tipo_pin, "label": etiqueta}
                     for pin, tipo_pin, etiqueta, _corte in info.get("outs", ())],
            # `opciones` → la UI dibuja una LISTA en vez de un campo de texto (anclas, modos…)
            "params": [{"nombre": k,
                        "label": info.get("etiquetas_params", {}).get(k, k),
                        "default": str(v), "tipo": tipo(v),
                        "data_type": info.get("data_params", {}).get(k, ""),
                        "letra": letras.get(k, "?"),
                        "opciones": opciones.get(k, []),
                        # `unidad` = «grados» ⇒ la ficha suma una PERILLA al lado del número. Un
                        # ángulo es una dirección, no una cantidad: la aguja dice hacia dónde
                        # apunta de un vistazo y «137.5» hay que imaginárselo.
                        "unidad": unidad_de(nombre, k)}
                       for k, v in info["params"].items()],
        })
    return json.dumps({"categorias": CATEGORIAS, "tools": salida}, ensure_ascii=True)
