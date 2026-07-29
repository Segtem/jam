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


# Los nombres de entrada de cada tipo. Los 409 los DERIVA el motor —`shader_firmas` está generado por
# `tools/experiments/volcar_firmas.py`— y acá abajo quedan sólo los que Jam escribe a mano, como
# documentación de lo que el código de este archivo usa. Si los dos difieren gana el generado, y un
# test lo comprueba: la tabla escrita a mano existe para leerla, no para ser la verdad.
_ESCRITAS_A_MANO: dict[str, tuple[str, ...]] = {
    "Abs": ("None",),
    "Add": ("A", "B"),
    "AppendVector": ("A", "B"),
    "Arccosine": ("None",),
    "Ceil": ("None",),
    "Clamp": ("None", "Min", "Max"),
    "ComponentMask": ("None",),
    "Constant": (),
    "Constant2Vector": (),
    "Constant3Vector": (),
    "Constant4Vector": (),
    "Distance": ("A", "B"),
    "Divide": ("A", "B"),
    "DotProduct": ("A", "B"),
    "Floor": ("None",),
    "Fresnel": ("ExponentIn", "BaseReflectFractionIn", "Normal"),
    "If": ("A", "B", "A > B", "A == B", "A < B"),
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
    "PixelNormalWS": (),
    "Power": ("Base", "Exp"),
    "RotateAboutAxis": ("NormalizedRotationAxis", "RotationAngle", "PivotPoint", "Position"),
    "Saturate": ("None",),
    "ScalarParameter": (),
    "Sine": ("None",),
    "SmoothStep": ("Min", "Max", "Value"),
    "StaticSwitchParameter": ("True", "False"),
    "Step": ("Y", "X"),
    "Subtract": ("A", "B"),
    "TextureCoordinate": (),
    "TextureSample": ("UVs", "Tex", "Apply View MipBias"),
    "Time": (),
    "Transform": ("None",),
    "TransformPosition": ("None",),
    "VectorParameter": (),
    "VertexColor": (),
    "VertexNormalWS": (),
    "WorldPosition": (),
}

from .shader_firmas import ENTRADAS as _DEL_MOTOR  # noqa: E402

ENTRADAS: dict[str, tuple[str, ...]] = {**_ESCRITAS_A_MANO, **_DEL_MOTOR}

# Las salidas del material a las que se puede enchufar algo. El nombre es el de `MaterialProperty`.
SALIDAS = (
    "MP_BASE_COLOR", "MP_METALLIC", "MP_SPECULAR", "MP_ROUGHNESS", "MP_EMISSIVE_COLOR",
    "MP_OPACITY", "MP_OPACITY_MASK", "MP_NORMAL", "MP_WORLD_POSITION_OFFSET",
    "MP_AMBIENT_OCCLUSION", "MP_SUBSURFACE_COLOR",
    # La salida ÚNICA que reemplaza a todas las de arriba cuando el material trabaja por atributos.
    # Es la puerta al apilado de capas: un `BlendMaterialAttributes` mezcla dos materiales enteros
    # —color, rugosidad, normal, todo de una— en vez de mezclar canal por canal a mano.
    "MP_MATERIAL_ATTRIBUTES",
)

# Nodos que TERMINAN un grafo sin ser una salida de material, porque el grafo no es un material sino
# una FUNCIÓN. Es la única diferencia entre los dos: el mismo IR, otro nodo final y otro contenedor.
TERMINALES_DE_FUNCION = ("FunctionOutput", "MaterialLayerOutput")


@dataclass(frozen=True)
class Nodo:
    """Un nodo del grafo. `props` son propiedades de editor (`parameter_name`, `r`, `const`…)."""

    id: str
    tipo: str
    props: dict = field(default_factory=dict)
    x: int = 0
    y: int = 0
    # Las entradas de este nodo, cuando NO se pueden saber por su tipo. Es el caso de
    # `MaterialFunctionCall`: sus entradas son las de la función a la que apunta, así que se
    # descubren del asset y viajan con el nodo. Vacío = manda la tabla `ENTRADAS`.
    firma: tuple = ()


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
    blend_mode: str = ""        # vacío = el default (Opaque); "BLEND_MASKED" para recortar

    def nodo(self, id_: str) -> Nodo | None:
        for n in self.nodos:
            if n.id == id_:
                return n
        return None


def es_funcion(grafo: GrafoMaterial) -> bool:
    """¿Este grafo describe una FUNCIÓN de material en vez de un material?

    La diferencia es un nodo: una función termina en `FunctionOutput` (o `MaterialLayerOutput` si es
    una capa) y no enchufa nada a `MP_*`. Todo lo demás —el IR, el verificador, el evaluador, los
    verbos— es idéntico, y por eso una función se arma con los mismos nodos que un material.
    """
    return any(n.tipo in TERMINALES_DE_FUNCION for n in grafo.nodos)


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
        validas = destino.firma or ENTRADAS.get(destino.tipo, ())
        if validas and arista.entrada not in validas:
            problemas.append(
                f"arista {i}: «{destino.tipo}» no tiene la entrada «{arista.entrada}» "
                f"(tiene {list(validas)})")
        if (arista.hasta, arista.entrada) in alimentadas:
            problemas.append(f"arista {i}: «{arista.hasta}.{arista.entrada}» ya estaba conectada")
        alimentadas.add((arista.hasta, arista.entrada))

    if not any(a.es_salida_del_material for a in grafo.aristas) and not es_funcion(grafo):
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
# Armar un grafo a mano, nodo por nodo — lo que usan los verbos genéricos de material
# ---------------------------------------------------------------------------------------------
#
# Todo devuelve un grafo NUEVO en vez de modificar el que recibe. Es lo que hace que un nodo del
# canvas pueda alimentar a dos ramas distintas sin que una le pise el grafo a la otra: por el cable
# viaja un valor, no una referencia a algo mutable.

def vacio(nombre: str = "M_JamMaterial") -> GrafoMaterial:
    return GrafoMaterial(nombre=nombre, nodos=(), aristas=())


# El nombre con el que un nodo se conoce en el editor no siempre es el de su clase. Éstos no son
# typos: son cómo se llama el nodo en la paleta de UE, y buscarlos por parecido no los encuentra
# («Lerp» no es subcadena de «LinearInterpolate»).
ALIAS = {
    "Lerp": "LinearInterpolate",
    "CustomExpression": "Custom",
    "Dot": "DotProduct",
    "Cross": "CrossProduct",
    "Sqrt": "SquareRoot",
    "TexCoord": "TextureCoordinate",
}
# Un alias NO puede llamarse como un tipo que existe: `Mask` parece el ComponentMask y no lo es
# (el `Mask` de UE es un blend de MaterialX), así que aliasarlo daría en silencio otro nodo que el
# que dice el campo. `test_material_verbos` lo fija para los que vengan.


def normalizar_tipo(tipo: str) -> str:
    """El nombre de clase real de un tipo escrito como se lo llama en el editor."""
    return ALIAS.get(tipo.strip(), tipo.strip())


def entradas_de(tipo: str) -> tuple[str, ...]:
    """Los nombres de entrada de ese tipo de nodo, o `ValueError` si el tipo no existe.

    Ojo con el caso que confunde: un nodo de UNA sola entrada la llama ``"None"``. No es que no
    tenga entrada — es su nombre.
    """
    tipo = normalizar_tipo(tipo)
    if tipo not in ENTRADAS:
        agujas = tipo.lower()
        parecidos = sorted(t for t in ENTRADAS
                           if agujas in t.lower() or t.lower() in agujas)[:6]
        raise ValueError(f"«{tipo}» no es un MaterialExpression"
                         + (f" · ¿querías {parecidos}?" if parecidos else ""))
    return ENTRADAS[tipo]


def id_libre(grafo: GrafoMaterial, tipo: str) -> str:
    """Un id predecible para un nodo nuevo: `multiply1`, `multiply2`…

    Predecible importa: `material_connect` referencia los nodos POR ID, así que si el id lo eligiera
    un contador global habría que mirar el log para saber cómo se llamó el nodo que uno acaba de
    crear.
    """
    base = tipo[0].lower() + tipo[1:] if tipo else "nodo"
    usados = {n.id for n in grafo.nodos}
    i = 1
    while f"{base}{i}" in usados:
        i += 1
    return f"{base}{i}"


def con_nodo(grafo: GrafoMaterial, tipo: str, *, id: str = "", props: dict | None = None,
             entradas: dict | None = None, x: int = 0, y: int = 0,
             firma: tuple = ()) -> tuple[GrafoMaterial, str]:
    """Agrega un nodo (y de paso sus cables de entrada). Devuelve `(grafo_nuevo, id_del_nodo)`.

    `firma` pisa la tabla de tipos para los nodos cuyas entradas dependen de a qué apunten —hoy
    `MaterialFunctionCall`—, y viaja con el nodo para que el verificador puro las siga conociendo.
    """
    validas = firma or entradas_de(tipo)
    tipo = normalizar_tipo(tipo)     # el IR guarda el nombre de CLASE: es lo que el emisor busca
    nuevo_id = id.strip() or id_libre(grafo, tipo)
    if grafo.nodo(nuevo_id) is not None:
        raise ValueError(f"ya hay un nodo «{nuevo_id}» en el grafo")

    cables = []
    for pin, origen in (entradas or {}).items():
        if pin not in validas:
            raise ValueError(f"«{tipo}» no tiene la entrada «{pin}» (tiene {list(validas) or 'ninguna'})")
        salida = ""
        if "." in str(origen):
            origen, salida = str(origen).split(".", 1)
        if grafo.nodo(origen) is None:
            raise ValueError(f"«{origen}» no es un nodo de este grafo "
                             f"(hay {[n.id for n in grafo.nodos] or 'ninguno'})")
        cables.append(Arista(desde=origen, hasta=nuevo_id, entrada=pin, salida=salida))

    nodo = Nodo(id=nuevo_id, tipo=tipo, props=dict(props or {}), x=int(x), y=int(y),
                firma=tuple(firma))
    return GrafoMaterial(nombre=grafo.nombre, nodos=grafo.nodos + (nodo,),
                         aristas=grafo.aristas + tuple(cables), two_sided=grafo.two_sided,
                         shading_model=grafo.shading_model, blend_mode=grafo.blend_mode), nuevo_id


def con_cable(grafo: GrafoMaterial, desde: str, hasta: str, entrada: str = "",
              salida: str = "") -> GrafoMaterial:
    """Conecta `desde` → `hasta.entrada`. Sin `entrada`, usa la única que tenga el destino."""
    if grafo.nodo(desde) is None:
        raise ValueError(f"«{desde}» no es un nodo de este grafo")
    destino = grafo.nodo(hasta)
    if destino is None:
        raise ValueError(f"«{hasta}» no es un nodo de este grafo")
    validas = destino.firma or entradas_de(destino.tipo)
    if not entrada:
        if len(validas) != 1:
            raise ValueError(f"«{hasta}» ({destino.tipo}) tiene {len(validas)} entradas "
                             f"{list(validas)}: hay que decir cuál")
        entrada = validas[0]
    elif entrada not in validas:
        raise ValueError(f"«{destino.tipo}» no tiene la entrada «{entrada}» (tiene {list(validas)})")
    return GrafoMaterial(nombre=grafo.nombre, nodos=grafo.nodos,
                         aristas=grafo.aristas + (Arista(desde, hasta, entrada, salida),),
                         two_sided=grafo.two_sided, shading_model=grafo.shading_model,
                         blend_mode=grafo.blend_mode)


def con_salida(grafo: GrafoMaterial, desde: str, propiedad: str,
               salida: str = "") -> GrafoMaterial:
    """Enchufa un nodo a una salida del material (`MP_BASE_COLOR`, `MP_ROUGHNESS`…)."""
    if grafo.nodo(desde) is None:
        raise ValueError(f"«{desde}» no es un nodo de este grafo")
    if propiedad not in SALIDAS:
        raise ValueError(f"«{propiedad}» no es una salida de material (hay {list(SALIDAS)})")
    return GrafoMaterial(nombre=grafo.nombre, nodos=grafo.nodos,
                         aristas=grafo.aristas + (Arista(desde, propiedad, "", salida),),
                         two_sided=grafo.two_sided, shading_model=grafo.shading_model,
                         blend_mode=grafo.blend_mode)


def parsear_pares(texto: str) -> dict[str, str]:
    """``"A=uv, B=escala"`` → ``{"A": "uv", "B": "escala"}``.

    Es el formato de los campos `inputs` y `props` de los verbos. Se corta por la PRIMERA `=` para
    que un valor pueda tener signos igual, y se ignoran los pares vacíos: un campo que termina en
    coma no es un error, es alguien escribiendo.
    """
    salida: dict[str, str] = {}
    for parte in str(texto or "").split(","):
        if not parte.strip():
            continue
        if "=" not in parte:
            raise ValueError(f"«{parte.strip()}» no tiene forma `clave=valor`")
        clave, valor = parte.split("=", 1)
        if not clave.strip():
            raise ValueError(f"«{parte.strip()}» no nombra ninguna clave")
        salida[clave.strip()] = valor.strip()
    return salida


def parsear_props(texto: str) -> dict:
    """Igual que `parsear_pares`, pero adivinando el tipo de los literales obvios.

    Los números y los booleanos se convierten acá porque el IR es puro y tiene que poder evaluarse
    sin Unreal. Lo demás queda en texto a propósito: el adaptador lo convierte preguntándole a la
    propiedad qué tipo tiene, que es cómo un `noise_function` o un color en hex llegan bien sin que
    este lado sepa nada de enums.
    """
    import re

    salida = {}
    for clave, crudo in parsear_pares(texto).items():
        bajo = crudo.lower()
        if bajo in ("true", "false"):
            salida[clave] = bajo == "true"
            continue
        # Un color en hex es un VALOR, no un nombre: se convierte acá para que el IR guarde números.
        # Dejándolo como texto, el adaptador igual lo resolvía —conoce el tipo de la propiedad— pero
        # `evaluar` no, y previsualizar un material con un color explotaba con
        # «could not convert string to float: '#B0764A'». El IR tiene que poder leerse sin Unreal.
        if re.fullmatch(r"#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?", crudo):
            salida[clave] = color_de_hex(crudo)
            continue
        try:
            salida[clave] = int(crudo) if crudo.lstrip("+-").isdigit() else float(crudo)
        except ValueError:
            salida[clave] = crudo
    return salida


# ---------------------------------------------------------------------------------------------
# Evaluar el IR en CPU — el oráculo que compara el shader con lo que quería decir
# ---------------------------------------------------------------------------------------------
#
# `verificar` mira la FORMA del grafo; esto mira lo que CALCULA. Sirve para lo que un test de
# topología no puede: comprobar que el material compilado desde el tab Weight da el mismo número que
# la máscara de CPU en el mismo punto. Una entrada cruzada (Min por Max), grados donde iban radianes
# o un `1 - x` de más pasan cualquier verificación estructural y los caza esto en un renglón.
#
# No pretende ser un compilador de HLSL: cubre los tipos que Jam emite. Un tipo que no conoce levanta
# `ValueError` en vez de devolver un número inventado, que es lo que haría inútil al oráculo.

_CANALES = {"R": 0, "G": 1, "B": 2, "A": 3}


def color_de_hex(texto: str) -> tuple[float, float, float, float]:
    """``#RRGGBB``/``#RRGGBBAA`` sRGB → RGBA lineal, que es en lo que piensan los materiales.

    La UI escribe colores en hex porque es lo que un artista sabe leer; el IR los guarda en lineal
    porque es lo que UE guarda. Saltear la conversión da un material notoriamente más claro que el
    color elegido, y como «se ve parecido» el error sobrevive.
    """
    import re

    limpio = str(texto or "").strip().lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}(?:[0-9A-Fa-f]{2})?", limpio):
        raise ValueError("color debe usar formato #RRGGBB o #RRGGBBAA.")
    canales = [int(limpio[i:i + 2], 16) / 255.0 for i in range(0, len(limpio), 2)]
    if len(canales) == 3:
        canales.append(1.0)
    r, g, b, a = canales
    lineal = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return (lineal[0], lineal[1], lineal[2], a)


def _vec(x) -> list[float]:
    if isinstance(x, (list, tuple)):
        return [float(v) for v in x]
    if isinstance(x, str):
        # Que el mensaje diga QUÉ pasó: un `float('#B0764A')` a secas manda a leer un stack de
        # cuatro niveles para descubrir que una propiedad quedó guardada como texto.
        raise ValueError(f"el IR guarda «{x}» como texto donde va un número: "
                         "los colores se parsean con `parsear_props`, que los convierte")
    return [float(x)]


def _porcomponente(fn, a: list[float], b: list[float]) -> list[float]:
    """Aplica `fn` componente a componente, difundiendo el escalar como hace HLSL."""
    n = max(len(a), len(b))
    ancho_a = a if len(a) > 1 else a * n
    ancho_b = b if len(b) > 1 else b * n
    return [fn(ancho_a[i], ancho_b[i]) for i in range(n)]


def _sat1(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def _smoothstep1(lo: float, hi: float, x: float) -> float:
    if lo == hi:
        return 0.0 if x < lo else 1.0
    t = _sat1((x - lo) / (hi - lo))
    return t * t * (3.0 - 2.0 * t)


def evaluar(grafo: GrafoMaterial, entorno: dict, *, ruido=None) -> dict[str, list[float]]:
    """Evalúa el grafo en UN punto y devuelve el valor de cada nodo.

    `entorno` da lo que en el shader viene del vértice o del mundo: ``posicion``, ``normal``,
    ``color``, ``tiempo``. `ruido` es la función que reemplaza al nodo `Noise` —se pasa aparte porque
    el ruido de la GPU y el de Jam **no son la misma función**: UE hashea distinto, así que el patrón
    difiere aunque la escala, el rango y el contraste coincidan. Pasando el ruido de Jam se verifica
    todo lo demás; el ruido en sí se compara por estadística, no punto a punto.
    """
    entorno = dict(entorno or {})
    valores: dict[str, list[float]] = {}

    entrantes: dict[str, dict[str, tuple[str, str]]] = {n.id: {} for n in grafo.nodos}
    for arista in grafo.aristas:
        if not arista.es_salida_del_material and arista.hasta in entrantes:
            entrantes[arista.hasta][arista.entrada] = (arista.desde, arista.salida)

    def leer(id_: str, entrada: str, defecto=None) -> list[float]:
        cable = entrantes[id_].get(entrada)
        if cable is None:
            if defecto is None:
                raise ValueError(f"«{id_}» no tiene nada conectado en «{entrada}»")
            return _vec(defecto)
        valor = calcular(cable[0])
        canal = _CANALES.get(cable[1])
        return [valor[canal]] if canal is not None and canal < len(valor) else valor

    def calcular(id_: str) -> list[float]:
        if id_ in valores:
            return valores[id_]
        nodo = grafo.nodo(id_)
        if nodo is None:
            raise ValueError(f"no existe el nodo «{id_}»")
        valores[id_] = _calcular_nodo(nodo, leer, entorno, ruido)
        return valores[id_]

    for nodo in grafo.nodos:
        calcular(nodo.id)
    return valores


def _calcular_nodo(nodo: Nodo, leer, entorno: dict, ruido) -> list[float]:
    import math

    t, p, id_ = nodo.tipo, nodo.props, nodo.id

    if t == "Constant":
        return [float(p.get("r", 0.0))]
    if t == "Constant2Vector":
        return [float(p.get("r", 0.0)), float(p.get("g", 0.0))]
    if t in ("Constant3Vector", "Constant4Vector"):
        # Medido: el valor NO va en r/g/b sueltas como en `Constant2Vector`, va entero en `constant`.
        # Escribirlo en `r` lanza, y el nodo se queda en negro con el grafo entero bien cableado.
        return _vec(p.get("constant", (0.0, 0.0, 0.0, 1.0)))[:3 if t == "Constant3Vector" else 4]
    if t == "ScalarParameter":
        return [float(p.get("default_value", 0.0))]
    if t == "VectorParameter":
        return _vec(p.get("default_value", (0.0, 0.0, 0.0, 1.0)))
    if t == "WorldPosition":
        return _vec(entorno.get("posicion", (0.0, 0.0, 0.0)))
    if t in ("VertexNormalWS", "PixelNormalWS"):
        return _vec(entorno.get("normal", (0.0, 0.0, 1.0)))
    if t == "VertexColor":
        return _vec(entorno.get("color", (1.0, 1.0, 1.0, 1.0)))
    if t == "Time":
        return [float(entorno.get("tiempo", 0.0))]

    if t == "ComponentMask":
        origen = leer(id_, "None")
        return [origen[i] for i, canal in enumerate("rgba")
                if p.get(canal, False) and i < len(origen)]

    if t == "AppendVector":
        return leer(id_, "A") + leer(id_, "B")

    unarias = {
        "Abs": abs,
        "Arccosine": lambda v: math.acos(max(-1.0, min(1.0, v))),
        "Ceil": math.ceil,
        "Floor": math.floor,
        "OneMinus": lambda v: 1.0 - v,
        "Saturate": _sat1,
        "Sine": math.sin,
    }
    if t in unarias:
        return [float(unarias[t](v)) for v in leer(id_, "None")]

    binarias = {
        "Add": lambda a, b: a + b,
        "Subtract": lambda a, b: a - b,
        "Multiply": lambda a, b: a * b,
        "Divide": lambda a, b: a / b if b else 0.0,
        "Min": min,
        "Max": max,
        # `step(Y, X)` de HLSL: 1 cuando X ≥ Y. El orden de las entradas es al revés de lo que
        # sugiere el nombre, y es exactamente el tipo de error que este evaluador existe para cazar.
        "Step": lambda y, x: 1.0 if x >= y else 0.0,
    }
    if t in binarias:
        if t == "Step":
            return _porcomponente(binarias[t], leer(id_, "Y"), leer(id_, "X"))
        return _porcomponente(binarias[t], leer(id_, "A"), leer(id_, "B"))

    if t == "Power":
        base, exponente = leer(id_, "Base"), leer(id_, "Exp")
        return _porcomponente(lambda b, e: max(0.0, b) ** e, base, exponente)
    if t == "Clamp":
        valor, lo, hi = leer(id_, "None"), leer(id_, "Min", 0.0), leer(id_, "Max", 1.0)
        return [max(lo[0], min(hi[0], v)) for v in valor]
    if t == "SmoothStep":
        lo, hi, valor = leer(id_, "Min", 0.0), leer(id_, "Max", 1.0), leer(id_, "Value")
        return [_smoothstep1(lo[0], hi[0], v) for v in valor]
    if t == "LinearInterpolate":
        a, b, alfa = leer(id_, "A"), leer(id_, "B"), leer(id_, "Alpha")
        diferencia = _porcomponente(lambda x, y: y - x, a, b)
        base = a if len(a) > 1 else a * len(diferencia)
        peso = alfa if len(alfa) > 1 else alfa * len(diferencia)
        return [base[i] + diferencia[i] * peso[i] for i in range(len(diferencia))]
    if t == "Length":
        v = leer(id_, "None")
        return [math.sqrt(sum(c * c for c in v))]
    if t == "Distance":
        a, b = leer(id_, "A"), leer(id_, "B")
        d = _porcomponente(lambda x, y: x - y, a, b)
        return [math.sqrt(sum(c * c for c in d))]
    if t == "DotProduct":
        a, b = leer(id_, "A"), leer(id_, "B")
        return [sum(x * y for x, y in zip(a, b))]
    if t == "Normalize":
        v = leer(id_, "VectorInput")
        largo = math.sqrt(sum(c * c for c in v)) or 1.0
        return [c / largo for c in v]

    if t == "Noise":
        if ruido is None:
            raise ValueError("hay un nodo Noise y no se pasó `ruido=`: el resultado sería inventado")
        posicion = leer(id_, "World Position")
        while len(posicion) < 3:
            posicion.append(0.0)
        lo = float(p.get("output_min", -1.0))
        hi = float(p.get("output_max", 1.0))
        crudo = float(ruido(posicion[0], posicion[1], posicion[2]))   # se espera en 0..1
        return [lo + (hi - lo) * crudo]

    raise ValueError(f"«{id_}»: el evaluador no sabe calcular un «{t}»")


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
