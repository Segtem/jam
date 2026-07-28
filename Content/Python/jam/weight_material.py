"""Compila la cadena de máscaras del tab Weight a un material. CEREBRO PURO (0 `import unreal`).

El tab Weight ya **es** un grafo de shader: cada op escribe un campo escalar 0..1 y lo multiplica en
el `weight` del punto, igual que se multiplican máscaras en un material. La única diferencia es dónde
corre. Este módulo saca esa diferencia del medio: la misma cadena que decide DÓNDE se dispersan las
rocas compila a un `GrafoMaterial` que decide DÓNDE se pintan.

    source_surface → weight_slope → weight_noise → weight_power → instance
                                                                └→ weight_material

Lo que el material recibe no es una aproximación a ojo: donde la máscara de CPU vale 0.7, el material
vale 0.7. Eso se puede afirmar porque `shader.evaluar` corre el IR en Python y se compara contra
`flow` punto por punto — está en `tests/test_weight_material.py`.

**Las tres cosas que NO son iguales**, y conviene tenerlas escritas antes que descubrirlas mirando:

1. **El ruido tiene otro dibujo.** `Noise` de UE hashea distinto que `scatter_core.value_noise`. La
   escala, el rango (0..1) y el contraste son los mismos, así que la máscara tiene la misma
   estadística y el mismo «grano»; las manchas caen en otro lado. Un `seed` distinto se traduce a un
   desplazamiento del espacio de ruido: separa semillas, no reproduce la de CPU.
2. **`weight_cull` por densidad no existe en GPU.** Con `soft ≥ 0.5` la op de CPU tira una moneda
   determinista por punto; un shader no tiene «puntos». El material recorta con umbral duro y lo
   avisa en las notas.
3. **Los bordes duros son duros por 1e-4.** `smoothstep(a, a, x)` es una división por cero en HLSL,
   así que el compilador separa el techo del piso por `EPS`. Con `soft=0` la rampa mide una diezmilésima
   de unidad de mundo en vez de cero: la diferencia no se ve ni se mide, pero está.

Todo lo que en el tab es un campo editable sale como **parámetro con nombre** del material, y el
nombre es el del nodo más el del campo (`Slope1_Min`, `Noise1_Scale`). Así la máscara se retoca en una
instancia sin recompilar y sin volver a correr el grafo — y se sigue leyendo cuál campo del tab es.
"""

from __future__ import annotations

from .shader import Arista, GrafoMaterial, Nodo

# Cuánto se separa el techo del piso de una rampa para que nunca sea una división por cero.
EPS = 1e-4
GRADOS_POR_RADIAN = 57.29577951308232

# Las ops del tab que aportan gris. El resto de los nodos del flow (fuentes, transforms, máscaras
# duras) no lo tocan: el compilador los atraviesa.
OPS_WEIGHT = ("weight_slope", "weight_height", "weight_noise", "weight_radial",
              "weight_invert", "weight_power", "weight_curve", "weight_combine", "weight_cull")

# El prefijo legible de cada op en los nombres de parámetro.
ETIQUETAS = {"weight_slope": "Slope", "weight_height": "Height", "weight_noise": "Noise",
             "weight_radial": "Radial", "weight_invert": "Invert", "weight_power": "Power",
             "weight_curve": "Curve", "weight_combine": "Combine", "weight_cull": "Cull"}


def _desplazamiento(seed: int) -> tuple[float, float, float]:
    """El corrimiento del espacio de ruido que hace las veces de semilla.

    Con `seed=0` es el origen — eso es lo que permite comparar el IR contra el ruido de CPU en el
    test de equivalencia. Para el resto de las semillas sólo garantiza que dos semillas distintas den
    dibujos distintos, que es para lo que se usa el campo.
    """
    return ((seed * 127.1) % 997.0, (seed * 311.7) % 991.0, 0.0)


class _Lienzo:
    """Junta nodos y cables, y los acomoda solo en columnas por profundidad.

    Los ids se generan acá: un nodo del tab se expande a diez del material, así que ponerles nombre a
    mano no escala. La columna sale de la entrada más profunda, y la fila de cuántos nodos ya hay en
    esa columna — alcanza para que el grafo se pueda leer al abrirlo en el editor.
    """

    def __init__(self):
        self.nodos: list[Nodo] = []
        self.aristas: list[Arista] = []
        self._columna: dict[str, int] = {}
        self._ocupacion: dict[int, int] = {}
        self._contador = 0

    def nodo(self, tipo: str, entradas: dict | None = None, **props) -> str:
        entradas = entradas or {}
        self._contador += 1
        id_ = f"{tipo[:6].lower()}{self._contador}"

        columna = 0
        for origen in entradas.values():
            fuente = origen[0] if isinstance(origen, tuple) else origen
            columna = max(columna, self._columna.get(fuente, 0) + 1)
        self._columna[id_] = columna
        fila = self._ocupacion.get(columna, 0)
        self._ocupacion[columna] = fila + 1

        self.nodos.append(Nodo(id=id_, tipo=tipo, props=props,
                               x=-2400 + columna * 230, y=fila * 120))
        for pin, origen in entradas.items():
            fuente, canal = origen if isinstance(origen, tuple) else (origen, "")
            self.aristas.append(Arista(desde=fuente, hasta=id_, entrada=pin, salida=canal))
        return id_

    def salida(self, desde: str, propiedad: str) -> None:
        self.aristas.append(Arista(desde=desde, hasta=propiedad))

    def const(self, valor: float) -> str:
        return self.nodo("Constant", r=float(valor))

    def param(self, nombre: str, valor: float) -> str:
        return self.nodo("ScalarParameter", parameter_name=nombre, default_value=float(valor))

    def rampa(self, piso: str, techo: str, valor: str) -> str:
        """`smoothstep(piso, techo, valor)` con el techo empujado `EPS` arriba del piso.

        Sin eso, un `soft=0` o un radio con `soft=0` dejan Min == Max y el `smoothstep` de HLSL
        divide por cero: NaN que se propaga a todo el material y se ve como una malla negra.
        """
        minimo = self.nodo("Add", {"A": piso, "B": self.const(EPS)})
        techo_seguro = self.nodo("Max", {"A": techo, "B": minimo})
        return self.nodo("SmoothStep", {"Min": piso, "Max": techo_seguro, "Value": valor})

    def banda(self, valor: str, etiqueta: str, lo: float, hi: float, soft: float) -> str:
        """La banda 0..1 de `flow._band`: 1 dentro de [lo, hi], con bordes de ancho `soft`."""
        piso = self.param(f"{etiqueta}_Min", lo)
        techo = self.param(f"{etiqueta}_Max", hi)
        borde = self.param(f"{etiqueta}_Soft", soft)
        sube = self.rampa(self.nodo("Subtract", {"A": piso, "B": borde}), piso, valor)
        baja = self.rampa(techo, self.nodo("Add", {"A": techo, "B": borde}), valor)
        return self.nodo("Multiply", {"A": sube, "B": self.nodo("OneMinus", {"None": baja})})


class _Compilador:
    def __init__(self, lienzo: _Lienzo):
        self.l = lienzo
        self.notas: list[str] = []
        self.recortes: list[str] = []      # los `weight_cull`, que alimentan la máscara de opacidad
        self.compiladas: list[str] = []    # las ops traducidas, en orden
        self._contadores: dict[str, int] = {}
        self._compartidos: dict[str, str] = {}

    # --- fuentes que se emiten una sola vez aunque las use media docena de ops ---

    def posicion(self) -> str:
        if "pos" not in self._compartidos:
            self._compartidos["pos"] = self.l.nodo("WorldPosition")
        return self._compartidos["pos"]

    def altura(self) -> str:
        if "z" not in self._compartidos:
            self._compartidos["z"] = self.l.nodo(
                "ComponentMask", {"None": self.posicion()}, r=False, g=False, b=True, a=False)
        return self._compartidos["z"]

    def plano_xy(self) -> str:
        if "xy" not in self._compartidos:
            self._compartidos["xy"] = self.l.nodo(
                "ComponentMask", {"None": self.posicion()}, r=True, g=True, b=False, a=False)
        return self._compartidos["xy"]

    def pendiente(self) -> str:
        """Grados desde la horizontal, la misma cuenta que `scatter._grados_pendiente`.

        Ahí es `90 - degrees(asin(|nz|))`; acá `degrees(acos(|nz|))`, que es lo mismo escrito para
        que la GPU lo haga en un nodo en vez de tres.
        """
        if "pendiente" not in self._compartidos:
            normal = self.l.nodo("VertexNormalWS")
            nz = self.l.nodo("ComponentMask", {"None": normal},
                             r=False, g=False, b=True, a=False)
            radianes = self.l.nodo("Arccosine", {"None": self.l.nodo("Abs", {"None": nz})})
            self._compartidos["pendiente"] = self.l.nodo(
                "Multiply", {"A": radianes, "B": self.l.const(GRADOS_POR_RADIAN)})
        return self._compartidos["pendiente"]

    # --- las ops ---

    def etiqueta(self, kind: str) -> str:
        base = ETIQUETAS.get(kind, kind)
        self._contadores[base] = self._contadores.get(base, 0) + 1
        return f"{base}{self._contadores[base]}"

    def emitir(self, kind: str, params: dict, base: str | None) -> str | None:
        """Traduce una op del tab. `base` es el gris que entra (None = la cadena arranca acá)."""
        etiqueta = self.etiqueta(kind)
        self.compiladas.append(etiqueta)

        # Las que REFORMAN el gris que ya venía: sin entrada arrancan del 1.0 con el que nace un punto.
        if kind in ("weight_invert", "weight_power", "weight_curve"):
            entrada = base if base is not None else self.l.const(1.0)
            if kind == "weight_invert":
                return self.l.nodo("OneMinus", {"None": entrada})
            if kind == "weight_power":
                k = self.l.param(f"{etiqueta}_K", max(0.01, float(params.get("k", 2.0))))
                return self.l.nodo("Power", {"Base": self.l.nodo("Saturate", {"None": entrada}),
                                             "Exp": k})
            piso = self.l.param(f"{etiqueta}_Min", float(params.get("min", 0.0)))
            techo = self.l.param(f"{etiqueta}_Max", float(params.get("max", 1.0)))
            if float(params.get("min", 0.0)) > float(params.get("max", 1.0)):
                self.notas.append(
                    f"{etiqueta}: la rampa está invertida (min > max). En CPU eso da una rampa "
                    "descendente; el material la aproxima como un borde duro en min.")
            return self.l.rampa(piso, techo, entrada)

        # El aplicador: no cambia el gris, decide qué se recorta.
        if kind == "weight_cull":
            entrada = base if base is not None else self.l.const(1.0)
            umbral = self.l.param(f"{etiqueta}_Threshold", float(params.get("threshold", 0.5)))
            self.recortes.append(self.l.nodo("Step", {"Y": umbral, "X": entrada}))
            if float(params.get("soft", 0.0)) >= 0.5:
                self.notas.append(
                    f"{etiqueta}: el modo por densidad (soft ≥ 0.5) tira una moneda por PUNTO, y un "
                    "shader no tiene puntos. El material recorta con umbral duro.")
            return entrada

        # Las que APORTAN un gris nuevo: se multiplican contra el que venía (encadenar = AND suave).
        mascara = self._mascara(kind, params, etiqueta)
        if mascara is None:
            return base
        if base is None:
            return mascara
        return self.l.nodo("Multiply", {"A": base, "B": mascara})

    def _mascara(self, kind: str, params: dict, etiqueta: str) -> str | None:
        if kind == "weight_slope":
            return self.l.banda(self.pendiente(), etiqueta,
                                float(params.get("min", 0.0)), float(params.get("max", 90.0)),
                                float(params.get("soft", 5.0)))
        if kind == "weight_height":
            return self.l.banda(self.altura(), etiqueta,
                                float(params.get("min", 0.0)), float(params.get("max", 500.0)),
                                float(params.get("soft", 50.0)))
        if kind == "weight_noise":
            return self._ruido(params, etiqueta)
        if kind == "weight_radial":
            return self._radial(params, etiqueta)
        return None

    def _ruido(self, params: dict, etiqueta: str) -> str:
        """El `value_noise` de Jam, con la escala como parámetro en vez de propiedad.

        La propiedad `scale` de `Noise` se hornea al compilar el shader, así que multiplicar la
        posición por `1/escala` es lo que deja mover la escala desde una instancia.
        """
        escala = self.l.param(f"{etiqueta}_Scale", max(1.0, float(params.get("scale", 500.0))))
        frecuencia = self.l.nodo("Divide", {"A": self.l.const(1.0), "B": escala})
        dx, dy, dz = _desplazamiento(int(params.get("seed", 0)))
        corrido = self.l.nodo("Add", {"A": self.posicion(),
                                      "B": self.l.nodo("Constant3Vector", constant=(dx, dy, dz))})
        # Aplanar a XY: la máscara de CPU es 2D, y sin esto el ruido cambiaría con la altura.
        aplanado = self.l.nodo("Multiply", {
            "A": corrido, "B": self.l.nodo("Constant3Vector", constant=(1.0, 1.0, 0.0))})
        escalado = self.l.nodo("Multiply", {"A": aplanado, "B": frecuencia})
        crudo = self.l.nodo("Noise", {"World Position": escalado},
                            scale=1.0, noise_function="NOISEFUNCTION_VALUE_ALU",
                            turbulence=False, levels=1, output_min=0.0, output_max=1.0)
        contraste = self.l.param(f"{etiqueta}_Contrast",
                                 max(0.01, float(params.get("contrast", 1.0))))
        return self.l.nodo("Power", {"Base": crudo, "Exp": contraste})

    def _radial(self, params: dict, etiqueta: str) -> str:
        centro = self.l.nodo("AppendVector", {
            "A": self.l.param(f"{etiqueta}_Cx", float(params.get("cx", 0.0))),
            "B": self.l.param(f"{etiqueta}_Cy", float(params.get("cy", 0.0)))})
        distancia = self.l.nodo("Distance", {"A": self.plano_xy(), "B": centro})
        radio = self.l.param(f"{etiqueta}_Radius", max(1.0, float(params.get("radius", 300.0))))
        borde = self.l.param(f"{etiqueta}_Soft", float(params.get("soft", 0.5)))
        interior = self.l.nodo("Multiply", {
            "A": radio,
            "B": self.l.nodo("OneMinus", {"None": self.l.nodo("Saturate", {"None": borde})})})
        return self.l.nodo("OneMinus", {"None": self.l.rampa(interior, radio, distancia)})

    def combinar(self, pesos: list[str], params: dict) -> str | None:
        """`weight_combine`: junta el gris de varias ramas paralelas, como en CPU."""
        pesos = [p for p in pesos if p is not None]
        if not pesos:
            return None
        etiqueta = self.etiqueta("weight_combine")
        self.compiladas.append(etiqueta)
        modo = str(params.get("mode", "mul"))
        tipos = {"mul": "Multiply", "add": "Add", "max": "Max", "min": "Min"}
        # El `t` del lerp se emite UNA vez aunque haya cinco ramas: dos nodos con el mismo nombre de
        # parámetro comparten valor en UE, pero aparecerían repetidos en la firma del material.
        peso_lerp = (self.l.param(f"{etiqueta}_T", float(params.get("t", 0.5)))
                     if modo not in tipos and len(pesos) > 1 else "")
        acumulado = pesos[0]
        for otro in pesos[1:]:
            if modo in tipos:
                acumulado = self.l.nodo(tipos[modo], {"A": acumulado, "B": otro})
            else:
                acumulado = self.l.nodo("LinearInterpolate", {
                    "A": acumulado, "B": otro, "Alpha": peso_lerp})
        return acumulado


def desde_flow(flujo, final: str = "", *, nombre: str = "M_JamMascara",
               color_a=(0.30, 0.29, 0.27, 1.0), color_b=(0.68, 0.58, 0.40, 1.0),
               rugosidad: float = 0.9) -> dict:
    """Compila a material la cadena de Weight que termina en `final`.

    Sin `final` toma el único nodo que nadie consume; si hay varios, lo dice en vez de elegir por su
    cuenta. Devuelve ``{grafo, notas, ops}``: `notas` son las diferencias que el material no puede
    salvar (ver la cabecera del módulo), y vienen vacías cuando la traducción es exacta.
    """
    variables = flujo._valores()
    escalares = flujo.escalares_de_valor(variables)

    def entradas_de(nid: str) -> list[str]:
        return [a for a, ap, b, bp in flujo.enlaces if b == nid and bp == "in"]

    consumidos = {a for a, ap, b, bp in flujo.enlaces if bp == "in"}
    if not final:
        candidatos = [nid for nid, n in flujo.nodos.items()
                      if nid not in consumidos and n["kind"] not in ("number", "math", "text")]
        if len(candidatos) != 1:
            return {"error": "no está claro dónde termina la cadena: "
                             f"{sorted(candidatos) or 'no hay ningún nodo terminal'}. "
                             "Pasá el nodo final."}
        final = candidatos[0]
    if final not in flujo.nodos:
        return {"error": f"«{final}» no es un nodo del grafo"}

    lienzo = _Lienzo()
    compilador = _Compilador(lienzo)
    memoria: dict[str, str | None] = {}
    en_curso: set[str] = set()

    def peso(nid: str) -> str | None:
        """El id del nodo del material que vale lo que el `weight` del punto en ese nodo del tab."""
        if nid in memoria:
            return memoria[nid]
        if nid in en_curso:      # `Flow.validar` ya rechaza ciclos; esto evita colgarse si cambia
            return None
        en_curso.add(nid)
        kind = flujo.nodos[nid]["kind"]
        entradas = entradas_de(nid)
        pesos = [peso(e) for e in entradas]
        params = flujo.params_efectivos(nid, variables, escalares)

        if kind == "weight_combine":
            salida = compilador.combinar(pesos, params)
        elif kind in OPS_WEIGHT:
            salida = compilador.emitir(kind, params, pesos[0] if pesos else None)
        else:
            # No es una op de Weight: no toca el gris, sólo lo deja pasar. Una fuente arranca sin gris
            # (el punto nace en 1.0) y eso se representa con None para no emitir un `× 1` inútil.
            salida = next((p for p in pesos if p is not None), None)
            if len(entradas) > 1 and sum(p is not None for p in pesos) > 1:
                compilador.notas.append(
                    f"«{nid}» ({kind}) junta varias ramas y no es un weight_combine: el material "
                    "toma la primera que trae gris.")
        en_curso.discard(nid)
        memoria[nid] = salida
        return salida

    mascara = peso(final)
    if mascara is None:
        return {"error": "no hay ninguna op de Weight aguas arriba de "
                         f"«{final}»: el material sería un color plano"}

    gris = lienzo.nodo("Saturate", {"None": mascara})
    tinta_a = lienzo.nodo("VectorParameter", parameter_name="ColorA",
                          default_value=tuple(float(c) for c in color_a))
    tinta_b = lienzo.nodo("VectorParameter", parameter_name="ColorB",
                          default_value=tuple(float(c) for c in color_b))
    lienzo.salida(lienzo.nodo("LinearInterpolate",
                              {"A": tinta_a, "B": tinta_b, "Alpha": gris}), "MP_BASE_COLOR")
    lienzo.salida(lienzo.param("Rugosidad", rugosidad), "MP_ROUGHNESS")

    blend, recorte = "", ""
    if compilador.recortes:
        recorte = compilador.recortes[0]
        for otro in compilador.recortes[1:]:
            recorte = lienzo.nodo("Multiply", {"A": recorte, "B": otro})
        lienzo.salida(recorte, "MP_OPACITY_MASK")
        blend = "BLEND_MASKED"

    return {"grafo": GrafoMaterial(nombre=nombre, nodos=tuple(lienzo.nodos),
                                   aristas=tuple(lienzo.aristas), blend_mode=blend),
            "notas": compilador.notas,
            "ops": compilador.compiladas,
            "mascara": gris,
            "recorte": recorte,
            # Qué nodo del material corresponde a cada nodo del tab. Es lo que deja comparar la
            # traducción PASO a PASO en vez de sólo al final: un error que el gris final disimula
            # —`weight_power` sin saturar, que el `Saturate` de la salida vuelve a tapar— se ve
            # enseguida mirando el valor en el nodo donde ocurre.
            "por_nodo": {nid: ir for nid, ir in memoria.items() if ir is not None}}
