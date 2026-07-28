"""Material de los ayudantes visuales de Jam (fantasmas), con color y opacidad por parámetro.

Se fabrica UNA vez en `/Jam/Materials/M_JamGhost` (unlit + translúcido, con parámetros `Color` y
`Opacity`) y después cada fantasma usa una instancia dinámica con su propio color. Si por lo que sea
no se puede crear, se cae a los materiales translúcidos que ya trae el motor: el fantasma se ve
igual, sólo que sin control de color.
"""

from __future__ import annotations

import unreal

RUTA = "/Jam/Materials/M_JamGhost"

# Plan B: translúcidos del editor de físicas del motor (no tienen parámetro de color).
_FALLBACK = (
    "/Engine/EditorMaterials/PhAT_ElemSelectedMaterial",
    "/Engine/EditorMaterials/PhAT_ElemUnselectedMaterial",
)

_CACHE: dict = {"base": None, "intentado": False}


def _crear() -> unreal.Material | None:
    """Fabrica el material: unlit translúcido, Emissive=Color, Opacity=Opacity."""
    try:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        mat = tools.create_asset("M_JamGhost", "/Jam/Materials", unreal.Material,
                                 unreal.MaterialFactoryNew())
        if mat is None:
            return None
        mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
        mat.set_editor_property("two_sided", True)

        lib = unreal.MaterialEditingLibrary
        color = lib.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -400, 0)
        color.set_editor_property("parameter_name", "Color")
        color.set_editor_property("default_value", unreal.LinearColor(0.1, 0.5, 1.0, 1.0))
        opac = lib.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -400, 220)
        opac.set_editor_property("parameter_name", "Opacity")
        opac.set_editor_property("default_value", 0.35)

        lib.connect_material_property(color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        lib.connect_material_property(opac, "", unreal.MaterialProperty.MP_OPACITY)
        lib.recompile_material(mat)
        unreal.EditorAssetLibrary.save_asset(RUTA, only_if_is_dirty=False)
        return mat
    except Exception as e:  # noqa: BLE001
        unreal.log_warning(f"[Jam] no pude fabricar {RUTA} ({e}); uso los translúcidos del motor.")
        return None


def base() -> unreal.MaterialInterface | None:
    """El material base de los fantasmas (cacheado). None si no hay ninguno usable."""
    if _CACHE["base"] is not None:
        return _CACHE["base"]
    try:
        if unreal.EditorAssetLibrary.does_asset_exist(RUTA):
            _CACHE["base"] = unreal.load_asset(RUTA)
    except Exception:  # noqa: BLE001
        pass
    if _CACHE["base"] is None and not _CACHE["intentado"]:
        _CACHE["intentado"] = True
        _CACHE["base"] = _crear()
    if _CACHE["base"] is None:
        for r in _FALLBACK:
            try:
                m = unreal.load_asset(r)
                if isinstance(m, unreal.MaterialInterface):
                    _CACHE["base"] = m
                    break
            except Exception:  # noqa: BLE001
                continue
    return _CACHE["base"]


def instancia(color: unreal.LinearColor, opacidad: float = 0.35, dueno=None):
    """Instancia dinámica del material base con ese color. None si no hay material."""
    b = base()
    if b is None:
        return None
    try:
        # `unreal.MaterialInstanceDynamic` NO expone `create` desde Python: la fábrica vive en
        # MaterialLibrary. Como el except devolvía el material base, el fantasma venía saliendo
        # opaco y sin color en silencio.
        mid = unreal.MaterialLibrary.create_dynamic_material_instance(dueno, b)
        if mid is None:
            return b
        mid.set_vector_parameter_value("Color", color)
        mid.set_scalar_parameter_value("Opacity", opacidad)
        return mid
    except Exception:  # noqa: BLE001
        return b   # sin parámetros (fallback del motor): al menos translúcido


# ---------------------------------------------------------------------------------------------
# Emisor: de un `shader.GrafoMaterial` puro a un material de verdad
# ---------------------------------------------------------------------------------------------

def emitir(grafo, carpeta: str = "/Game/Jam/Materials", *, sobrescribir: bool = True) -> dict:
    """Crea el material que describe `grafo`. Devuelve `{"material":…, "info":…}` o `{"error":…}`.

    El grafo se verifica ANTES de tocar Unreal: un grafo mal armado no llega a crear un asset roto,
    y los mensajes salen de Python en vez de un log de compilación de shaders.

    Gotchas medidos en el editor, no supuestos:

    * `create_asset` sólo crea **en memoria** — sin `save_loaded_asset` el material se pierde al
      cerrar. Un probe que creaba en una sesión y leía en otra recibió `None`.
    * las propiedades de editor se aplican por nombre y **fallan en silencio** si el nombre no
      existe, así que se cuentan y se reportan: un `parameter_name` que no se aplicó deja un
      parámetro anónimo que ninguna instancia puede tocar.
    """
    from . import shader

    problemas = shader.verificar(grafo)
    if problemas:
        return {"error": "el grafo no es válido: " + " · ".join(problemas)}

    lib = unreal.MaterialEditingLibrary
    ruta = f"{carpeta}/{grafo.nombre}"
    reusado = False
    if unreal.EditorAssetLibrary.does_asset_exist(ruta):
        if not sobrescribir:
            return {"error": f"{ruta} ya existe (pasá sobrescribir=True para reemplazarlo)"}
        # Se REUSA el asset en vez de borrarlo y volver a crearlo. Borrar no lo saca de memoria, así
        # que el `create_asset` siguiente choca con el nombre y devuelve None — que es exactamente
        # lo que pasa al reemitir tras retocar un parámetro, o sea el caso más común. Reusar además
        # conserva las referencias: una malla que ya tenía este material asignado la sigue teniendo.
        material = unreal.EditorAssetLibrary.load_asset(ruta)
        if material is None:
            return {"error": f"{ruta} existe pero no se pudo cargar para reemplazarlo"}
        if not _vaciar(material):
            return {"error": f"{ruta}: no se pudo vaciar el grafo anterior "
                             f"(quedan {lib.get_num_material_expressions(material)} nodos)"}
        reusado = True
    else:
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        material = tools.create_asset(grafo.nombre, carpeta, unreal.Material,
                                      unreal.MaterialFactoryNew())
    if material is None:
        return {"error": f"no se pudo crear el material en {ruta}"}
    if grafo.two_sided:
        material.set_editor_property("two_sided", True)

    creados: dict[str, object] = {}
    props_fallidas: list[str] = []
    for nodo in grafo.nodos:
        clase = getattr(unreal, f"MaterialExpression{nodo.tipo}", None)
        if clase is None:
            return {"error": f"{nodo.id}: unreal no expone MaterialExpression{nodo.tipo}"}
        expresion = lib.create_material_expression(material, clase, nodo.x, nodo.y)
        if expresion is None:
            return {"error": f"{nodo.id}: no se pudo crear el nodo {nodo.tipo}"}
        for nombre, valor in nodo.props.items():
            try:
                expresion.set_editor_property(nombre, _valor_de_propiedad(nombre, valor))
            except Exception:  # noqa: BLE001 — se reporta, no se decide acá
                props_fallidas.append(f"{nodo.id}.{nombre}")
        creados[nodo.id] = expresion

    cables, fallidos = 0, []
    for arista in grafo.aristas:
        origen = creados[arista.desde]
        if arista.es_salida_del_material:
            propiedad = getattr(unreal.MaterialProperty, arista.hasta)
            ok = lib.connect_material_property(origen, arista.salida, propiedad)
        else:
            ok = lib.connect_material_expressions(
                origen, arista.salida, creados[arista.hasta], arista.entrada)
        if ok:
            cables += 1
        else:
            fallidos.append(f"{arista.desde}→{arista.hasta}.{arista.entrada}")

    lib.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_loaded_asset(material):
        return {"error": f"{ruta} se creó pero no se pudo guardar"}

    detalle = ""
    if fallidos:
        detalle += f" · {len(fallidos)} cables NO conectados: {fallidos[:4]}"
    if props_fallidas:
        detalle += f" · {len(props_fallidas)} propiedades ignoradas: {props_fallidas[:4]}"
    # La clave `error` sólo va si HAY error: el resto de Jam pregunta `if "error" in result`, así
    # que dejarla en None haría fallar todos los caminos felices.
    if fallidos:
        return {"error": f"{ruta}: {len(fallidos)} conexiones no se pudieron hacer{detalle}"}
    return {
        "material": material,
        "info": (f"{ruta} · {len(grafo.nodos)} nodos · {cables}/{len(grafo.aristas)} cables"
                 f"{' · reusado' if reusado else ' · nuevo'}{detalle}"),
    }


def _vaciar(material, pasadas: int = 8) -> bool:
    """Deja el material sin ninguna expresión. Devuelve False si no lo logró.

    `delete_all_material_expressions` **no borra todo en una pasada** — medido: de 8 nodos deja 3,
    después 1, y recién en la tercera llega a 0. Reemitir sin esto va acumulando basura: el asset
    terminaba con 44 nodos cuando el grafo describía 30, con la topología correcta y catorce nodos
    huérfanos colgados. Y no se pueden enumerar desde Python para borrarlos uno por uno
    (`expressions` y `expression_collection` no son accesibles), así que se repite hasta que la
    cuenta deja de bajar.
    """
    lib = unreal.MaterialEditingLibrary
    previo = lib.get_num_material_expressions(material)
    for _ in range(pasadas):
        if previo == 0:
            return True
        lib.delete_all_material_expressions(material)
        actual = lib.get_num_material_expressions(material)
        if actual == previo:      # dejó de bajar: no va a mejorar repitiendo
            return actual == 0
        previo = actual
    return previo == 0


def _valor_de_propiedad(nombre: str, valor):
    """Traduce el valor puro del IR al tipo que espera la propiedad de editor.

    El IR no puede nombrar tipos de Unreal sin importarlo, así que escribe enums como texto
    (`"TRANSFORMSOURCE_LOCAL"`) y colores como tuplas; la traducción vive acá, que es el único lado
    que conoce el motor. Los miembros de enum en Python van en MAYÚSCULA: `TRANSFORMPOSSOURCE_World`
    no existe, `TRANSFORMPOSSOURCE_WORLD` sí, y equivocarse ahí no lanza — deja la propiedad en su
    valor por defecto.
    """
    if isinstance(valor, (tuple, list)) and len(valor) in (3, 4):
        componentes = [float(c) for c in valor]
        if len(componentes) == 3:
            componentes.append(1.0)
        return unreal.LinearColor(*componentes)
    if not isinstance(valor, str):
        return valor
    for enum in (getattr(unreal, "MaterialPositionTransformSource", None),
                 getattr(unreal, "MaterialVectorCoordTransformSource", None),
                 getattr(unreal, "MaterialVectorCoordTransform", None)):
        if enum is not None and hasattr(enum, valor):
            return getattr(enum, valor)
    return valor
