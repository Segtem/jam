"""El LAYOUT del ribbon: qué subgrupo ocupa cada verbo y en qué orden salen.

Vive aparte del registro de verbos a propósito. Un verbo se registra por lo que HACE (`tools.REGISTRO`,
`flow.OPS`); dónde cae en la barra es una decisión de presentación que cambia sola cuando el tab
crece, y tenerla acá la vuelve una tabla que se lee de un vistazo en vez de un campo suelto repetido
en noventa y cinco entradas.

Los subgrupos son los «paneles» de Grasshopper: dentro de un tab, las fichas se apilan en varias
filas y se separan en bloques con etiqueta. Con 43 verbos en el tab Mesh, una sola fila obligaba a
scrollear horizontalmente para encontrar cualquier cosa.

El orden importa: es el que ve el usuario. Dentro de cada grupo van de lo más usado a lo más raro, y
los grupos van en el orden en que se usan al construir algo — primero se hace una forma, después se
la barre, al final se la hornea.
"""

from __future__ import annotations


# tab -> [(subgrupo, [verbos en orden])]
GRUPOS: dict[str, list[tuple[str, list[str]]]] = {
    "Mesh": [
        ("Primitivas", ["mesh_box", "mesh_sphere", "mesh_sphere_box", "mesh_cylinder",
                        "mesh_cone", "mesh_capsule", "mesh_torus", "mesh_disc",
                        "mesh_quad", "mesh_round_rect", "mesh_grid", "mesh_triangle",
                        "mesh_stairs", "mesh_stairs_curved"]),
        ("Curvas", ["curve_bezier", "curve_child", "curve_branches", "curve_noise",
                    "graph_curve"]),
        ("Frames", ["curve_frames", "distribute_frames", "transform_frames",
                    "branch_from_frames", "points_to_frames"]),
        ("Barrido", ["mesh_pipe", "mesh_pipe_profile", "mesh_revolve", "mesh_along_curve"]),
        ("Copias", ["copy_mesh_to_frames", "copy_asset_selection", "choose_asset",
                    "asset_set", "mesh_leaf"]),
        ("Acabado", ["mesh_bark", "mesh_normals", "mesh_uv_scale", "mesh_color",
                     "mesh_vertex_gradient", "mesh_material", "mesh_transform",
                     "mesh_merge"]),
        ("Hornear", ["mesh_from_asset", "mesh_to_static", "hism_output", "mesh_compare"]),
    ],
    "Content": [("Assets", ["asset", "pick"])],
    "Place": [("Colocar", ["place", "drop", "snap"])],
    "Scatter": [("Repartir", ["scatter", "spline", "pcg"])],
    "Create": [("Crear", ["create_spline", "replace", "fracture", "nanite"])],
    "Edit": [
        ("Pivote", ["pivot", "pivot_set", "normalize"]),
        ("Ayudas", ["ghost", "gizmo"]),
    ],
    "Vector": [("Generadores", ["pts_line", "pts_circle", "pts_arc", "pts_rect"])],
    "Mask": [("Máscaras", ["mask_slope", "mask_height", "mask_noise", "mask_density"])],
    "Weight": [
        ("Fuentes", ["weight_slope", "weight_height", "weight_noise", "weight_radial"]),
        ("Operadores", ["weight_invert", "weight_power", "weight_curve", "weight_combine"]),
        ("Aplicar", ["weight_cull"]),
    ],
    "Sets": [("Lista", ["cull_nth", "sub_list", "shift", "reverse", "relax"])],
    "Transform": [("Mover", ["move", "rotate_pts", "scale_pts", "jitter"])],
    "Combine": [("Unir", ["merge", "weave"])],
    "Display": [("Ver", ["info"])],
    "Params": [("Valores", ["number", "text"])],
    "Maths": [("Operar", ["math"])],
    "Source": [("Fuente", ["source_surface"])],
    "Output": [("Salida", ["instance", "weight_material"])],
    "Shader": [
        # La paleta: un nodo por ficha, agrupados como los agrupa UE. `material_node` queda al final
        # del grupo «Armar» como la puerta a los otros ~380 tipos que no están acá.
        ("Constantes", ["mat_const", "mat_color", "mat_scalar", "mat_vector"]),
        ("Matemática", ["mat_add", "mat_sub", "mat_mul", "mat_div", "mat_lerp", "mat_power",
                        "mat_clamp", "mat_oneminus", "mat_saturate"]),
        ("Textura", ["mat_texture", "mat_uv", "mat_panner", "mat_noise"]),
        ("Vectores", ["mat_append", "mat_mask", "mat_normalize", "mat_dot"]),
        ("Escena", ["mat_worldpos", "mat_vnormal", "mat_vcolor", "mat_time", "mat_fresnel"]),
        ("Armar", ["material_node", "material_connect", "material_output"]),
        ("Reusar", ["material_function", "material_call"]),
        ("Hornear", ["material_build", "material_instance"]),
        ("Recetas", ["material_wind"]),
    ],
    "Debug": [("Ver", ["debug"])],
}

# Cuántas filas apila el ribbon lo decide la UI (`SJamGraphEditor::RibbonRows`), que es la única que
# lo usa: duplicarlo acá sólo daría dos verdades que se desincronizan.


def grupo_de(cat: str, verbo: str) -> str:
    """El subgrupo del verbo, o cadena vacía si el tab no declara layout.

    Vacío es una respuesta válida, no un error: un tab nuevo se ve como un solo bloque sin etiqueta
    hasta que alguien decida cómo partirlo.
    """
    for nombre, verbos in GRUPOS.get(cat, ()):
        if verbo in verbos:
            return nombre
    return ""


def orden_de(cat: str, verbo: str) -> tuple[int, int]:
    """Clave de orden: (índice del grupo, índice dentro del grupo).

    Un verbo sin layout declarado va al final, en el orden en que lo devuelva el registro.
    """
    for i, (_, verbos) in enumerate(GRUPOS.get(cat, ())):
        if verbo in verbos:
            return (i, verbos.index(verbo))
    return (len(GRUPOS.get(cat, ())), 0)


def anotar(tools: list[dict]) -> list[dict]:
    """Agrega `grupo` a cada herramienta y las devuelve ordenadas para el ribbon.

    Ordena acá y no en C++ porque el orden es parte del layout, y el layout es esta tabla.
    """
    for herramienta in tools:
        herramienta["grupo"] = grupo_de(herramienta["cat"], herramienta["verbo"])
    return sorted(tools, key=lambda t: orden_de(t["cat"], t["verbo"]))
