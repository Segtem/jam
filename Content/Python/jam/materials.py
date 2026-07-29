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
# Oráculo de costo: cuánto sale de verdad el material que se acaba de crear
# ---------------------------------------------------------------------------------------------
#
# El verificador estructural dice que el grafo está bien armado y `shader.profundidad` aproxima la
# cadena de dependencias, pero ninguno de los dos sabe cuánto CUESTA. Eso sólo lo sabe el compilador
# de shaders, y por eso el número se mide en vez de estimarse.
#
# **Headless funciona, pero hace falta `-AllowCommandletRendering`.** Sin ese flag,
# `GetStatistics` devuelve todo en cero: `GMaxRHIShaderPlatform` no tiene un `FMaterialResource`
# válido y la función sale por el default. Con el flag, las instrucciones se mueven con la
# complejidad (medido: 406 → 742 → 1638 para 1, 4 y 12 capas de ruido encadenadas).

# El costo FIJO de un material opaco que no hace nada, medido en UE 5.7.4 / Vulkan sobre un
# `Constant3Vector` enchufado al BaseColor. Sirve para que el número signifique algo: lo que agrega
# el grafo es la diferencia contra esto, no el total. `MP_WORLD_POSITION_OFFSET` mueve el de vértice
# (medido: 196 → 250 con un WPO constante).
PISO = {"ps": 287, "vs": 196}


def medir(material) -> dict:
    """Las estadísticas de shader del material. `medido=False` cuando no se pudieron obtener.

    Distinguir «midió cero» de «no pudo medir» no es un detalle: un material siempre cuesta algo,
    así que un cero informado como número haría creer que el shader es gratis. Cuando no hay
    rendering disponible se dice, y quien llame decide si eso invalida su veredicto.
    """
    lib = unreal.MaterialEditingLibrary
    lib.recompile_material(material)
    st = lib.get_statistics(material)
    ps = int(st.num_pixel_shader_instructions)
    vs = int(st.num_vertex_shader_instructions)
    return {
        "ps": ps,
        "vs": vs,
        "sobre_piso_ps": ps - PISO["ps"],
        "sobre_piso_vs": vs - PISO["vs"],
        "samplers": int(st.num_samplers),
        "texturas_ps": int(st.num_pixel_texture_samples),
        "interpoladores": int(st.num_interpolator_scalars),
        # Un material con algo enchufado nunca compila a cero instrucciones: si las dos vienen en
        # cero, lo que falló fue la medición.
        "medido": ps > 0 or vs > 0,
    }


def veredicto_de_presupuesto(costo: dict, tope: int, ruta: str) -> str | None:
    """El mensaje de error si el material no entra en el presupuesto, o `None` si entra.

    Es la decisión sola, sin tocar Unreal, para que se pueda probar sin un editor. Y contesta lo que
    a alguien le va a importar cuando falle: cuánto se pasó, cuánto de eso es el piso inevitable y
    dónde quedó el asset para poder abrirlo.
    """
    if tope <= 0:
        return None
    if not costo.get("medido"):
        return (f"hay un presupuesto de {tope} instrucciones y el costo NO se pudo medir: "
                f"headless hace falta -AllowCommandletRendering. El material quedó en {ruta}.")
    if costo["ps"] <= tope:
        return None
    return (f"PRESUPUESTO ✗ — {costo['ps']} instrucciones de píxel > {tope}. El piso de un "
            f"material opaco es {PISO['ps']}, o sea que el grafo agrega "
            f"{costo['sobre_piso_ps']}. Quedó en {ruta} para poder mirarlo.")


def resumen_de_costo(medida: dict) -> str:
    if not medida.get("medido"):
        return ("costo NO medido (falta -AllowCommandletRendering headless, "
                "o no hay RHI disponible)")
    extra_ps = medida["sobre_piso_ps"]
    extra_vs = medida["sobre_piso_vs"]
    return (f"PS {medida['ps']} ({extra_ps:+d} sobre el piso) · "
            f"VS {medida['vs']} ({extra_vs:+d}) · "
            f"{medida['samplers']} sampler(s) · {medida['interpoladores']} interp.")


# ---------------------------------------------------------------------------------------------
# Emisor: de un `shader.GrafoMaterial` puro a un material de verdad
# ---------------------------------------------------------------------------------------------

def emitir(grafo, carpeta: str = "/Game/Jam/Materials", *, sobrescribir: bool = True,
           medir_costo: bool = True, usar_atributos: bool = False) -> dict:
    """Crea el material que describe `grafo`. Devuelve `{"material":…, "costo":…, "info":…}`
    o `{"error":…}`.

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
    # Estas van ANTES que los nodos: sin `BLEND_MASKED` la salida de opacidad no se compila y el
    # cable a MP_OPACITY_MASK se pierde sin que nadie proteste.
    #
    # `shading_model` estuvo declarado en el IR y sin aplicar: un `MSM_UNLIT` no cambiaba nada y
    # sólo se notó midiendo el costo, porque un unlit tenía que salir MUCHO más barato y salía
    # idéntico. Un campo que se puede escribir y no hace nada es peor que no tenerlo.
    # Con atributos, el material tiene UNA sola entrada (`MP_MATERIAL_ATTRIBUTES`) en vez de una por
    # canal. Es lo que habilita apilar: un `BlendMaterialAttributes` mezcla dos materiales enteros de
    # una. Sin este flag el cable a esa salida se conecta igual y NO hace nada.
    if usar_atributos:
        material.set_editor_property("use_material_attributes", True)
    for propiedad, valor in (("blend_mode", grafo.blend_mode),
                             ("shading_model", grafo.shading_model)):
        if not valor:
            continue
        try:
            material.set_editor_property(
                propiedad, _valor_de_propiedad(material, propiedad, valor))
        except Exception:  # noqa: BLE001
            return {"error": f"{ruta}: no se pudo poner {propiedad}={valor}"}

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
                expresion.set_editor_property(nombre, _valor_de_propiedad(expresion, nombre, valor))
            except Exception as exc:  # noqa: BLE001 — se reporta, no se decide acá
                props_fallidas.append(f"{nodo.id}.{nombre} ({type(exc).__name__})")
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

    # El oráculo de costo va acá y no en cada verbo: así los tres caminos que emiten materiales
    # (viento, máscara de Weight, y el armado a mano) reportan el mismo número sin repetirlo.
    # `get_statistics` BLOQUEA hasta que los shaders compilen, que es justamente lo que lo vuelve
    # una medición y no una estimación; `medir=False` lo saltea cuando eso no se puede pagar.
    costo = medir(material) if medir_costo else {"medido": False}
    return {
        "material": material,
        "costo": costo,
        "info": (f"{ruta} · {len(grafo.nodos)} nodos · {cables}/{len(grafo.aristas)} cables"
                 f"{' · reusado' if reusado else ' · nuevo'}{detalle}"
                 + (f" · {resumen_de_costo(costo)}" if medir_costo else "")),
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


def _valor_de_propiedad(dueno, nombre: str, valor):
    """Traduce el valor puro del IR al tipo que espera esa propiedad de editor.

    El IR no puede nombrar tipos de Unreal sin importarlo, así que escribe enums como texto
    (`"TRANSFORMSOURCE_LOCAL"`) y colores como tuplas. La traducción vive acá, que es el único lado
    que conoce el motor.

    La conversión la decide **el valor que la propiedad ya tiene**, no una lista de enums conocidos.
    Con una lista fija, cada tipo de nodo nuevo que usara un enum distinto fallaba —y `set` de un
    texto donde va un enum lanza `TypeError`, o peor: en algunos casos lo acepta y deja el default—,
    así que un verbo genérico que acepta cualquiera de los 409 tipos no podía funcionar. Preguntando
    el tipo actual funciona para todos sin enumerar ninguno.
    """
    if isinstance(valor, (tuple, list)) and len(valor) in (3, 4):
        componentes = [float(c) for c in valor]
        if len(componentes) == 3:
            componentes.append(1.0)
        return unreal.LinearColor(*componentes)
    if not isinstance(valor, str):
        return valor

    # Una RUTA de asset se carga. El IR es puro y no puede guardar un `UObject`, así que una
    # referencia a otro asset —la función de `MaterialFunctionCall`, una textura— viaja como texto.
    # Sin esto, `set_editor_property` recibe un str donde espera el objeto y lanza `TypeError`: la
    # propiedad queda sin aplicar, el nodo sin firma, y los cables que dependían de ella tampoco se
    # conectan. Ni los enums ni los colores en hex empiezan con «/», así que no hay ambigüedad.
    if valor.startswith("/"):
        cargado = unreal.EditorAssetLibrary.load_asset(valor)
        if cargado is not None:
            return cargado

    actual = None
    if dueno is not None:
        try:
            actual = dueno.get_editor_property(nombre)
        except Exception:  # noqa: BLE001 — la propiedad no existe; el `set` de arriba lo reportará
            return valor
    if isinstance(actual, unreal.EnumBase):
        # Por NOMBRE y con `getattr`: los enums de UE derivan de `EnumBase`, no de `enum.Enum`, y
        # **no son subscriptables** — `NoiseFunction["NOISEFUNCTION_VALUE_ALU"]` lanza `TypeError`.
        # El nombre va en MAYÚSCULA: `TRANSFORMPOSSOURCE_World` no existe, `..._WORLD` sí.
        return getattr(type(actual), valor)
    if isinstance(actual, unreal.LinearColor):
        return unreal.LinearColor(*shader_color(valor))
    if isinstance(actual, bool):
        return valor.strip().lower() in ("1", "true", "sí", "si", "yes")
    if isinstance(actual, int) and not isinstance(actual, bool):
        return int(float(valor))
    if isinstance(actual, float):
        return float(valor)
    return valor


def shader_color(texto: str):
    from . import shader

    return shader.color_de_hex(texto)


def op_weight_material(entradas, p):
    """Terminal del flow: compila la cadena de Weight que llega hasta acá y la hornea como material.

    Es el gemelo de `instance`. Donde `instance` pone una malla en cada punto que sobrevivió, esto
    toma la MISMA cadena de máscaras y la deja como shader: lo que decidía dónde caen las rocas ahora
    decide dónde se pinta la roca. El stream pasa de largo sin tocarse, así que el nodo se puede
    colgar en el medio de un grafo que además instancia.

    Necesita ver el GRAFO, no el stream — lo lee de `_flow`/`_nid`, que `Flow.evaluar` deja en los
    params justamente para esto.
    """
    from . import shader, weight_material

    flujo, nid = p.get("_flow"), p.get("_nid")
    stream = entradas[0] if entradas else []
    if flujo is None or nid is None:
        p["_out"] = {"error": "este nodo necesita el contexto del grafo y no lo recibió"}
        return stream

    try:
        colores = {clave: shader.color_de_hex(p.get(clave, defecto))
                   for clave, defecto in (("color_a", "#4D4A45"), ("color_b", "#AE9466"))}
    except ValueError as exc:
        p["_out"] = {"error": str(exc)}
        return stream

    compilado = weight_material.desde_flow(
        flujo, nid, nombre=str(p.get("name", "M_JamMascara")),
        color_a=colores["color_a"], color_b=colores["color_b"],
        rugosidad=float(p.get("rugosidad", 0.9)))
    if "error" in compilado:
        p["_out"] = {"error": compilado["error"]}
        return stream

    resultado = emitir(compilado["grafo"], str(p.get("folder", "/Game/Jam/Materials")))
    if "error" in resultado:
        p["_out"] = {"error": resultado["error"]}
        return stream

    p["_out"] = {"material": resultado["info"], "ops": compilado["ops"],
                 "notas": compilado["notas"],
                 "resumen": f"{len(compilado['ops'])} op(s) de Weight → "
                            f"{len(compilado['grafo'].nodos)} nodos de material"}
    return stream


# ---------------------------------------------------------------------------------------------
# Funciones de material: el mismo IR, otro contenedor
# ---------------------------------------------------------------------------------------------
#
# Una función de material es un grafo reusable con entradas y salidas con nombre. Para Jam es la
# pieza que lo deja ACUMULAR vocabulario propio en vez de sólo usar el del motor: lo que hoy es un
# grafo que se copia y pega, mañana es un nodo con nombre que se llama desde cualquier material.
#
# Y encaja sin fricción porque `MaterialFunctionCall` **descubre sus entradas por nombre** —medido—,
# que es el mismo patrón con el que Jam deriva las 408 firmas de las expresiones del motor.

# Qué clase de función emitir. Las tres se editan igual; cambian el contenedor y el nodo terminal.
CONTENEDORES = {
    "funcion": ("MaterialFunction", "MaterialFunctionFactoryNew", "FunctionOutput"),
    "capa": ("MaterialFunctionMaterialLayer", "MaterialFunctionMaterialLayerFactory",
             "MaterialLayerOutput"),
    "mezcla": ("MaterialFunctionMaterialLayerBlend",
               "MaterialFunctionMaterialLayerBlendFactory", "MaterialLayerOutput"),
}


def emitir_funcion(grafo, carpeta: str = "/Game/Jam/Functions", *, clase: str = "funcion",
                   descripcion: str = "", sobrescribir: bool = True) -> dict:
    """Crea la función de material que describe `grafo`. Mismo contrato que `emitir`.

    El grafo tiene que terminar en el nodo terminal que corresponda (`FunctionOutput` para una
    función común, `MaterialLayerOutput` para una capa o una mezcla) — `shader.verificar` lo acepta
    como final válido, y sin él la función no expone nada y no sirve para nada.
    """
    from . import shader

    if clase not in CONTENEDORES:
        return {"error": f"clase «{clase}» desconocida (hay {list(CONTENEDORES)})"}
    nombre_clase, nombre_factory, terminal = CONTENEDORES[clase]

    problemas = shader.verificar(grafo)
    if problemas:
        return {"error": "el grafo no es válido: " + " · ".join(problemas)}
    if not any(n.tipo == terminal for n in grafo.nodos):
        return {"error": f"una «{clase}» tiene que terminar en un nodo {terminal} "
                         f"(hay {sorted({n.tipo for n in grafo.nodos})})"}

    lib = unreal.MaterialEditingLibrary
    ruta = f"{carpeta}/{grafo.nombre}"
    reusada = False
    if unreal.EditorAssetLibrary.does_asset_exist(ruta):
        if not sobrescribir:
            return {"error": f"{ruta} ya existe (pasá sobrescribir=True para reemplazarla)"}
        funcion = unreal.EditorAssetLibrary.load_asset(ruta)
        if funcion is None:
            return {"error": f"{ruta} existe pero no se pudo cargar"}
        # Igual que en los materiales: reusar en vez de borrar y recrear. `delete_asset` no lo saca
        # de memoria y el `create_asset` siguiente chocaría con el nombre.
        for _ in range(8):
            if lib.get_num_material_expressions_in_function(funcion) == 0:
                break
            lib.delete_all_material_expressions_in_function(funcion)
        reusada = True
    else:
        fabrica = getattr(unreal, nombre_factory, None)
        contenedor = getattr(unreal, nombre_clase, None)
        if fabrica is None or contenedor is None:
            return {"error": f"unreal no expone {nombre_clase}/{nombre_factory}"}
        funcion = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            grafo.nombre, carpeta, contenedor, fabrica())
    if funcion is None:
        return {"error": f"no se pudo crear la función en {ruta}"}
    if descripcion:
        try:
            funcion.set_editor_property("description", str(descripcion))
        except Exception:  # noqa: BLE001 — la descripción es cosmética, no aborta
            pass

    creados: dict[str, object] = {}
    props_fallidas: list[str] = []
    for nodo in grafo.nodos:
        tipo = getattr(unreal, f"MaterialExpression{nodo.tipo}", None)
        if tipo is None:
            return {"error": f"{nodo.id}: unreal no expone MaterialExpression{nodo.tipo}"}
        expresion = lib.create_material_expression_in_function(funcion, tipo, nodo.x, nodo.y)
        if expresion is None:
            return {"error": f"{nodo.id}: no se pudo crear el nodo {nodo.tipo} en la función"}
        for clave, valor in nodo.props.items():
            try:
                expresion.set_editor_property(clave, _valor_de_propiedad(expresion, clave, valor))
            except Exception as exc:  # noqa: BLE001
                props_fallidas.append(f"{nodo.id}.{clave} ({type(exc).__name__})")
        creados[nodo.id] = expresion

    cables, fallidos = 0, []
    for arista in grafo.aristas:
        if arista.es_salida_del_material:
            # Una función no tiene salidas de material: su salida es un nodo del propio grafo.
            fallidos.append(f"{arista.desde}→{arista.hasta} (una función no tiene salidas MP_*)")
            continue
        if lib.connect_material_expressions(creados[arista.desde], arista.salida,
                                            creados[arista.hasta], arista.entrada):
            cables += 1
        else:
            fallidos.append(f"{arista.desde}→{arista.hasta}.{arista.entrada}")

    lib.update_material_function(funcion)
    if not unreal.EditorAssetLibrary.save_loaded_asset(funcion):
        return {"error": f"{ruta} se creó pero no se pudo guardar"}

    detalle = ""
    if props_fallidas:
        detalle += f" · {len(props_fallidas)} propiedades ignoradas: {props_fallidas[:4]}"
    if fallidos:
        return {"error": f"{ruta}: {len(fallidos)} conexiones no se pudieron hacer "
                         f"{fallidos[:4]}{detalle}"}
    entradas = sorted(n.props.get("input_name", "") for n in grafo.nodos
                      if n.tipo == "FunctionInput")
    return {
        "funcion": funcion,
        "entradas": [e for e in entradas if e],
        "info": (f"{ruta} · {clase} · {len(grafo.nodos)} nodos · {cables} cables"
                 f"{' · reusada' if reusada else ' · nueva'}"
                 + (f" · entradas {[e for e in entradas if e]}" if any(entradas) else "")
                 + detalle),
    }


def entradas_de_funcion(ruta: str) -> list[str] | None:
    """Los nombres de entrada de una función de material, PREGUNTÁNDOLE al asset.

    Es el mismo trato que Jam le da a las 408 expresiones del motor: la firma no se declara, se
    descubre. Por eso una función escrita por Jam se usa igual que un nodo nativo. Devuelve `None`
    si el asset no se pudo cargar (que es distinto de una función sin entradas, que da `[]`).
    """
    funcion = unreal.EditorAssetLibrary.load_asset(str(ruta))
    if funcion is None:
        return None
    # La firma se lee de un `MaterialFunctionCall` apuntado a ella, y no de los nodos de la función:
    # es exactamente lo que va a ver el material que la llame, incluido el ORDEN de los pines. (Los
    # nodos de una función tampoco se pueden enumerar desde Python: hay `get_num_..._in_function`,
    # que devuelve una cuenta, y nada para listarlos.)
    #
    # El material de sonda es TRANSITORIO a propósito. La primera versión creaba un asset y lo
    # borraba en un `finally`, y a la segunda llamada explotaba con «the asset already exists»:
    # `delete_asset` no lo saca de memoria —el mismo gotcha que obligó a reusar en `emitir`—, así
    # que borrar y recrear es justamente el patrón que no funciona. Sin asset no hay problema.
    sonda = unreal.Material()
    if sonda is None:
        return None
    try:
        llamada = unreal.MaterialEditingLibrary.create_material_expression(
            sonda, unreal.MaterialExpressionMaterialFunctionCall, 0, 0)
        llamada.set_editor_property("material_function", funcion)
        return [str(x) for x in
                unreal.MaterialEditingLibrary.get_material_expression_input_names(llamada)]
    except Exception:  # noqa: BLE001
        return None


def instanciar(padre: str, nombre: str, carpeta: str = "/Game/Jam/Materials", *,
               escalares: dict | None = None, vectores: dict | None = None) -> dict:
    """Crea (o reusa) una `MaterialInstanceConstant` del material `padre` y le fija parámetros.

    Los parámetros que NO existen en el padre se reportan en vez de aplicarse en silencio: el
    `set_material_instance_*` de UE no protesta por un nombre inventado, así que sin esta
    comprobación una instancia queda idéntica al padre y nadie sabe por qué.
    """
    material = unreal.EditorAssetLibrary.load_asset(str(padre))
    if material is None:
        return {"error": f"no pude cargar el material padre «{padre}»"}

    ruta = f"{carpeta}/{nombre}"
    reusada = unreal.EditorAssetLibrary.does_asset_exist(ruta)
    if reusada:
        instancia_ = unreal.EditorAssetLibrary.load_asset(ruta)
    else:
        instancia_ = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            str(nombre), str(carpeta), unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew())
    if instancia_ is None:
        return {"error": f"no se pudo crear la instancia en {ruta}"}

    lib = unreal.MaterialEditingLibrary
    lib.set_material_instance_parent(instancia_, material)
    disponibles = {"escalar": {str(n) for n in lib.get_scalar_parameter_names(material)},
                   "vector": {str(n) for n in lib.get_vector_parameter_names(material)}}

    aplicados, inexistentes = [], []
    for nombre_param, valor in (escalares or {}).items():
        if nombre_param not in disponibles["escalar"]:
            inexistentes.append(nombre_param)
            continue
        lib.set_material_instance_scalar_parameter_value(instancia_, nombre_param, float(valor))
        aplicados.append(nombre_param)
    for nombre_param, valor in (vectores or {}).items():
        if nombre_param not in disponibles["vector"]:
            inexistentes.append(nombre_param)
            continue
        lib.set_material_instance_vector_parameter_value(
            instancia_, nombre_param, unreal.LinearColor(*valor))
        aplicados.append(nombre_param)

    lib.update_material_instance(instancia_)
    if not unreal.EditorAssetLibrary.save_loaded_asset(instancia_):
        return {"error": f"{ruta} se creó pero no se pudo guardar"}
    if inexistentes:
        return {"error": f"{ruta}: el padre no tiene el/los parámetro(s) {sorted(inexistentes)} "
                         f"(tiene escalares {sorted(disponibles['escalar'])} y "
                         f"vectores {sorted(disponibles['vector'])})"}
    return {
        "instancia": instancia_,
        "info": (f"{ruta} ← {padre}{' · reusada' if reusada else ' · nueva'}"
                 + (f" · {len(aplicados)} parámetro(s): {aplicados}" if aplicados
                    else " · sin parámetros fijados (queda igual al padre)")),
    }
