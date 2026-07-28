"""Grafos de material como DATO puro: nodos y aristas, sin tocar Unreal.

Un material es un artefacto de UE, pero su *descripción* no tiene por qué serlo. Separarlos da lo
mismo que en el resto de Jam (ver el desacople cerebro/adaptador): el grafo se arma, se compara y se
verifica en Python puro, y un adaptador de veinte líneas lo emite dentro de un `UMaterial`.

Eso además es lo que hace que las tres fases compartan una sola pieza:

    · el material de viento del árbol lo describe `viento_de_arbol()`;
    · el tab Weight —que ya es un grafo de shader evaluado en CPU— compilará al MISMO IR;
    · los verbos genéricos de material irán agregando nodos a un IR de estos.

Los nombres de tipo son los de UE **sin** el prefijo `MaterialExpression`, y los nombres de entrada
son los que devuelve `get_material_expression_input_names` en el editor: se midieron, no se
adivinaron. Dos detalles que se adivinan mal y fallan EN SILENCIO:

* los nodos de una sola entrada la llaman ``"None"``;
* los valores de enum van en MAYÚSCULA_CON_GUIONES (``"TRANSFORMPOSSOURCE_WORLD"``, no
  ``"TRANSFORMPOSSOURCE_World"``), y el color de un `VectorParameter` va en ``default_value`` como
  tupla RGBA, no en propiedades ``r``/``g``/``b`` sueltas.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Los nombres de entrada de cada tipo, medidos contra UE 5.7.4. Sirven para dos cosas: verificar que
# una arista apunte a una entrada que existe, y no tener que recordarlos al escribir un grafo.
# No pretende ser exhaustivo (hay 417 tipos); es el subconjunto que Jam usa hoy.
ENTRADAS: dict[str, tuple[str, ...]] = {
    "Abs": ("None",),
    "Add": ("A", "B"),
    "AppendVector": ("A", "B"),
    "Clamp": ("None", "Min", "Max"),
    "ComponentMask": ("None",),
    "Constant": (),
    "Constant3Vector": (),
    "Distance": ("A", "B"),
    "Divide": ("A", "B"),
    "Fresnel": ("ExponentIn", "BaseReflectFractionIn", "Normal"),
    "Length": ("None",),
    "LinearInterpolate": ("A", "B", "Alpha"),
    "Max": ("A", "B"),
    "Min": ("A", "B"),
    "Multiply": ("A", "B"),
    "Noise": ("World Position", "FilterWidth"),
    "Normalize": ("VectorInput",),
    "ObjectPositionWS": (),
    "OneMinus": ("None",),
    "Panner": ("Coordinate", "Time", "Speed"),
    "Power": ("Base", "Exp"),
    "RotateAboutAxis": ("NormalizedRotationAxis", "RotationAngle", "PivotPoint", "Position"),
    "Saturate": ("None",),
    "ScalarParameter": (),
    "Sine": ("None",),
    "StaticSwitchParameter": ("True", "False"),
    "Subtract": ("A", "B"),
    "TextureCoordinate": (),
    "TextureSample": ("UVs", "Tex", "Apply View MipBias"),
    "Time": (),
    "Transform": ("None",),
    "TransformPosition": ("None",),
    "VectorParameter": (),
    "VertexColor": (),
    "WorldPosition": (),
}

# Las salidas del material a las que se puede enchufar algo. El nombre es el de `MaterialProperty`.
SALIDAS = (
    "MP_BASE_COLOR", "MP_METALLIC", "MP_SPECULAR", "MP_ROUGHNESS", "MP_EMISSIVE_COLOR",
    "MP_OPACITY", "MP_OPACITY_MASK", "MP_NORMAL", "MP_WORLD_POSITION_OFFSET",
    "MP_AMBIENT_OCCLUSION", "MP_SUBSURFACE_COLOR",
)


@dataclass(frozen=True)
class Nodo:
    """Un nodo del grafo. `props` son propiedades de editor (`parameter_name`, `r`, `const`…)."""

    id: str
    tipo: str
    props: dict = field(default_factory=dict)
    x: int = 0
    y: int = 0


@dataclass(frozen=True)
class Arista:
    """`desde.salida → hasta.entrada`. Si `hasta` empieza con `MP_`, es una salida del material."""

    desde: str
    hasta: str
    entrada: str = ""
    salida: str = ""

    @property
    def es_salida_del_material(self) -> bool:
        return self.hasta.startswith("MP_")


@dataclass(frozen=True)
class GrafoMaterial:
    nombre: str
    nodos: tuple[Nodo, ...]
    aristas: tuple[Arista, ...]
    two_sided: bool = False
    shading_model: str = ""     # vacío = el default (DefaultLit)

    def nodo(self, id_: str) -> Nodo | None:
        for n in self.nodos:
            if n.id == id_:
                return n
        return None


def verificar(grafo: GrafoMaterial) -> list[str]:
    """Los problemas del grafo, en una lista vacía si está bien.

    Es el oráculo estructural: se corre ANTES de tocar Unreal, así que un grafo mal armado no llega
    a crear un asset roto. Lo que no puede ver desde acá es el costo en instrucciones — eso lo mide
    `MaterialStatistics`, que necesita que los shaders compilen de verdad.
    """
    problemas = []
    ids = [n.id for n in grafo.nodos]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    if repetidos:
        problemas.append(f"ids repetidos: {repetidos}")

    for nodo in grafo.nodos:
        if nodo.tipo not in ENTRADAS:
            problemas.append(f"{nodo.id}: tipo desconocido «{nodo.tipo}»")

    conocidos = set(ids)
    alimentadas = set()
    for i, arista in enumerate(grafo.aristas):
        if arista.desde not in conocidos:
            problemas.append(f"arista {i}: sale de «{arista.desde}», que no existe")
            continue
        if arista.es_salida_del_material:
            if arista.hasta not in SALIDAS:
                problemas.append(f"arista {i}: «{arista.hasta}» no es una salida de material")
            continue
        if arista.hasta not in conocidos:
            problemas.append(f"arista {i}: entra a «{arista.hasta}», que no existe")
            continue
        destino = grafo.nodo(arista.hasta)
        validas = ENTRADAS.get(destino.tipo, ())
        if validas and arista.entrada not in validas:
            problemas.append(
                f"arista {i}: «{destino.tipo}» no tiene la entrada «{arista.entrada}» "
                f"(tiene {list(validas)})")
        if (arista.hasta, arista.entrada) in alimentadas:
            problemas.append(f"arista {i}: «{arista.hasta}.{arista.entrada}» ya estaba conectada")
        alimentadas.add((arista.hasta, arista.entrada))

    if not any(a.es_salida_del_material for a in grafo.aristas):
        problemas.append("el grafo no alimenta ninguna salida del material: no haría nada")

    ciclo = _buscar_ciclo(grafo)
    if ciclo:
        problemas.append(f"hay un ciclo: {' → '.join(ciclo)}")
    return problemas


def _buscar_ciclo(grafo: GrafoMaterial) -> list[str]:
    """Un ciclo cuelga el compilador de materiales, así que conviene verlo desde Python."""
    salientes: dict[str, list[str]] = {n.id: [] for n in grafo.nodos}
    for arista in grafo.aristas:
        if not arista.es_salida_del_material and arista.desde in salientes:
            salientes[arista.desde].append(arista.hasta)

    estado: dict[str, int] = {}

    def visitar(id_: str, camino: list[str]) -> list[str]:
        estado[id_] = 1
        for siguiente in salientes.get(id_, ()):
            if estado.get(siguiente) == 1:
                return camino + [id_, siguiente]
            if estado.get(siguiente, 0) == 0:
                encontrado = visitar(siguiente, camino + [id_])
                if encontrado:
                    return encontrado
        estado[id_] = 2
        return []

    for nodo in grafo.nodos:
        if estado.get(nodo.id, 0) == 0:
            encontrado = visitar(nodo.id, [])
            if encontrado:
                return encontrado
    return []


def firma(grafo: GrafoMaterial) -> dict:
    """Resumen determinista del grafo, para comparar dos materiales.

    Es a un material lo que `compare.medir` es a una malla: números que no dependen de en qué orden
    se armó el grafo ni de cómo se llamen los nodos, sólo de lo que el material ES.
    """
    tipos: dict[str, int] = {}
    for nodo in grafo.nodos:
        tipos[nodo.tipo] = tipos.get(nodo.tipo, 0) + 1
    return {
        "nodos": len(grafo.nodos),
        "aristas": len(grafo.aristas),
        "tipos": dict(sorted(tipos.items())),
        "salidas": sorted({a.hasta for a in grafo.aristas if a.es_salida_del_material}),
        "parametros": sorted(
            n.props.get("parameter_name", "")
            for n in grafo.nodos if n.tipo.endswith("Parameter")),
        "profundidad": profundidad(grafo),
    }


def profundidad(grafo: GrafoMaterial) -> int:
    """Cuántos nodos encadenados hay entre la fuente más lejana y una salida del material.

    Es lo más cerca del costo que se puede medir sin compilar: un grafo más profundo es una cadena
    de dependencias más larga. No reemplaza a `MaterialStatistics`, lo aproxima.
    """
    entrantes: dict[str, list[str]] = {n.id: [] for n in grafo.nodos}
    for arista in grafo.aristas:
        if not arista.es_salida_del_material and arista.hasta in entrantes:
            entrantes[arista.hasta].append(arista.desde)

    memoria: dict[str, int] = {}

    def alto(id_: str, visitando: frozenset) -> int:
        if id_ in memoria:
            return memoria[id_]
        if id_ in visitando:      # con ciclo no hay profundidad; `verificar` ya lo reporta
            return 0
        fuentes = entrantes.get(id_, ())
        valor = 1 + max((alto(f, visitando | {id_}) for f in fuentes), default=0)
        memoria[id_] = valor
        return valor

    finales = [a.desde for a in grafo.aristas if a.es_salida_del_material]
    return max((alto(f, frozenset()) for f in finales), default=0)


# ---------------------------------------------------------------------------------------------
# El material de viento del árbol
# ---------------------------------------------------------------------------------------------

def viento_de_arbol(*, nombre: str = "M_JamArbolViento", fuerza: float = 0.25,
                    velocidad: float = 1.2, concentracion: float = 2.0,
                    eje=(1.0, 0.3, 0.0)) -> GrafoMaterial:
    """El material que hace que cada rama se mueva sobre SU pivote.

    Consume lo que `mesh_pipe(pivot_uvs=True)` dejó estampado en la malla:

        UV1 = (pivote.x, pivote.y)      UV2 = (pivote.z, largo de la rama)

    y con eso reconstruye el pivote en espacio local. La rotación va por World Position Offset
    alrededor de ese punto, así que la rama gira sobre su nacimiento en vez de deslizarse.

    Tres decisiones que son las que separan esto de un árbol que se dobla como un bloque:

    * **el giro crece con la distancia al pivote**, normalizada por el largo de la rama. La base no
      se mueve y la punta se mueve todo; es lo que hace que parezca que la rama flexiona en vez de
      trasladarse.
    * **la fase la desplaza el propio pivote**. Sin eso todas las ramas oscilan al unísono y el
      árbol late como un corazón. `Length(pivote)` da una constante por rama, distinta para cada
      una y estable en el tiempo.
    * **el color de vértice multiplica el resultado**, así que la máscara de
      `mesh_vertex_gradient` decide qué partes pueden moverse. Un tronco pintado en cero queda
      quieto aunque tenga pivote.

    `fuerza` está en radianes: 0.25 es un movimiento de brisa, 1.0 ya es tormenta.
    """
    n = []
    a = []

    def nodo(id_, tipo, x, y, **props):
        n.append(Nodo(id=id_, tipo=tipo, props=props, x=x, y=y))
        return id_

    def cable(desde, hasta, entrada="", salida=""):
        a.append(Arista(desde=desde, hasta=hasta, entrada=entrada, salida=salida))

    # --- el pivote, reconstruido de los UVs que estampó el pipeline ---
    nodo("uv_xy", "TextureCoordinate", -1500, -200, coordinate_index=1)
    nodo("uv_zl", "TextureCoordinate", -1500, -40, coordinate_index=2)
    # ComponentMask lleva la máscara en sus props (r/g/b/a), no en una entrada.
    nodo("pivote_z", "ComponentMask", -1300, -40, r=True, g=False, b=False, a=False)
    nodo("largo", "ComponentMask", -1300, 90, r=False, g=True, b=False, a=False)
    cable("uv_zl", "pivote_z", "None")
    cable("uv_zl", "largo", "None")
    # AppendVector(float2, float) → float3: el pivote entero.
    nodo("pivote", "AppendVector", -1100, -120)
    cable("uv_xy", "pivote", "A")
    cable("pivote_z", "pivote", "B")

    # --- dónde está este vértice respecto de su pivote ---
    nodo("pos_mundo", "WorldPosition", -1500, 220)
    nodo("pos_local", "TransformPosition", -1300, 220,
         transform_source_type="TRANSFORMPOSSOURCE_WORLD",
         transform_type="TRANSFORMPOSSOURCE_LOCAL")
    cable("pos_mundo", "pos_local", "None")
    nodo("delta", "Subtract", -1100, 220)
    cable("pos_local", "delta", "A")
    cable("pivote", "delta", "B")
    nodo("dist", "Length", -900, 220)
    cable("delta", "dist", "None")

    # --- cuánto le toca moverse: 0 en la base, 1 en la punta ---
    nodo("avance", "Divide", -700, 220)
    cable("dist", "avance", "A")
    cable("largo", "avance", "B")
    nodo("avance_sat", "Saturate", -540, 220)
    cable("avance", "avance_sat", "None")
    nodo("concentracion", "ScalarParameter", -700, 380,
         parameter_name="Concentracion", default_value=float(concentracion))
    nodo("flexion", "Power", -380, 220)
    cable("avance_sat", "flexion", "Base")
    cable("concentracion", "flexion", "Exp")

    # --- la oscilación, desfasada por rama ---
    nodo("tiempo", "Time", -1500, 520)
    nodo("velocidad", "ScalarParameter", -1500, 640,
         parameter_name="Velocidad", default_value=float(velocidad))
    nodo("reloj", "Multiply", -1300, 520)
    cable("tiempo", "reloj", "A")
    cable("velocidad", "reloj", "B")
    nodo("desfase", "Length", -1300, 660)      # constante por rama: decorrelaciona el vaivén
    cable("pivote", "desfase", "None")
    nodo("fase", "Add", -1100, 520)
    cable("reloj", "fase", "A")
    cable("desfase", "fase", "B")
    nodo("vaiven", "Sine", -900, 520)
    cable("fase", "vaiven", "None")

    # --- el ángulo final ---
    nodo("fuerza", "ScalarParameter", -900, 660,
         parameter_name="Fuerza", default_value=float(fuerza))
    nodo("amplitud", "Multiply", -700, 520)
    cable("vaiven", "amplitud", "A")
    cable("fuerza", "amplitud", "B")
    nodo("mascara", "VertexColor", -700, 660)
    nodo("permitido", "Multiply", -520, 520)
    cable("amplitud", "permitido", "A")
    cable("mascara", "permitido", "B", salida="R")
    nodo("angulo", "Multiply", -300, 400)
    cable("permitido", "angulo", "A")
    cable("flexion", "angulo", "B")

    # --- girar sobre el pivote y devolverlo a mundo ---
    nodo("eje", "VectorParameter", -520, 800, parameter_name="EjeViento",
         default_value=(float(eje[0]), float(eje[1]), float(eje[2]), 1.0))
    nodo("eje_norm", "Normalize", -340, 800)
    cable("eje", "eje_norm", "VectorInput")
    nodo("giro", "RotateAboutAxis", -120, 400)
    cable("eje_norm", "giro", "NormalizedRotationAxis")
    cable("angulo", "giro", "RotationAngle")
    cable("pivote", "giro", "PivotPoint")
    cable("pos_local", "giro", "Position")
    nodo("a_mundo", "Transform", 80, 400,
         transform_source_type="TRANSFORMSOURCE_LOCAL", transform_type="TRANSFORM_WORLD")
    cable("giro", "a_mundo", "None")
    cable("a_mundo", "MP_WORLD_POSITION_OFFSET")

    # --- un color mínimo para que el material se vea sin depender de texturas ---
    nodo("color_corteza", "VectorParameter", -300, 900, parameter_name="Corteza",
         default_value=(0.22, 0.16, 0.11, 1.0))
    nodo("rugosidad", "ScalarParameter", -300, 1020,
         parameter_name="Rugosidad", default_value=0.85)
    cable("color_corteza", "MP_BASE_COLOR")
    cable("rugosidad", "MP_ROUGHNESS")

    return GrafoMaterial(nombre=nombre, nodos=tuple(n), aristas=tuple(a))
