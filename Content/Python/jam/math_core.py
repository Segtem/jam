"""Valores matemáticos del Graph/Flow, puros y declarativos.

Un nodo de valor no ejecuta una herramienta de Unreal ni transporta un stream de puntos: produce un
dato que puede entrar a cualquier pin compatible. Este módulo es la única tabla de verbos, defaults,
tipos y cálculo; ``flow`` y ``graph`` sólo adaptan su forma de guardar nodos/enlaces.

Los verbos explícitos no usan ``eval``. La única excepción es el nodo legado ``math`` (Expresión),
cuyo evaluador llega como callback para conservar compatibilidad sin acoplar este núcleo a Flow.
"""

from __future__ import annotations

import math
from collections.abc import Callable


class ValorError(ValueError):
    """Un valor es inválido y el diagnóstico pertenece a un pin concreto."""

    def __init__(self, pin: str, mensaje: str):
        self.pin = pin
        self.mensaje = mensaje
        super().__init__(f"{pin}: {mensaje}")


class ValorPendiente(Exception):
    """Una expresión o un cable depende de otro valor que todavía no se resolvió."""


def _division(dividendo: float, divisor: float) -> float:
    if divisor == 0.0:
        raise ValorError("divisor", "no puede ser cero")
    return dividendo / divisor


def _modulo(valor: float, modulo: float) -> float:
    """Módulo euclídeo con la semántica de Python: el resultado tiene el signo del módulo."""
    if modulo == 0.0:
        raise ValorError("modulo", "no puede ser cero")
    return valor % modulo


def _potencia(base: float, exponente: float) -> float:
    try:
        return math.pow(base, exponente)
    except ValueError:
        raise ValorError(
            "base", "base y exponente no producen un resultado real") from None
    except OverflowError:
        raise ValorError("resultado", "la potencia excede el rango numérico") from None


def _raiz_cuadrada(radicando: float) -> float:
    if radicando < 0.0:
        raise ValorError("radicando", "no puede ser negativo")
    return math.sqrt(radicando)


def _limitar(valor: float, minimo: float, maximo: float) -> float:
    """Acota un número a un rango. Un rango dado vuelta es un ERROR, no algo que se acomoda solo.

    La alternativa —intercambiar `minimo` y `maximo` en silencio— hace que un cable mal conectado
    siga produciendo números plausibles, que es la peor forma de fallar: no hay síntoma hasta que
    alguien mira la geometría y no entiende. Falla nombrando el pin responsable.
    """
    if minimo > maximo:
        raise ValorError("minimo", "no puede ser mayor que el máximo")
    return maximo if valor > maximo else (minimo if valor < minimo else valor)


def _interpolar(desde: float, hasta: float, factor: float) -> float:
    """Mezcla dos números. El factor NO se acota a 0..1 a propósito.

    Extrapolar es útil —`factor` 1.5 continúa la recta más allá del destino, que es como se
    exageran transiciones— y acotarlo en silencio le sacaría esa capacidad a quien la busca. Para
    acotarlo está `math_saturate`, que se ve en el grafo.

    La forma es `desde + (hasta - desde) * factor` y no `desde*(1-f) + hasta*f`: la primera devuelve
    EXACTAMENTE `hasta` cuando el factor es 1, y la segunda puede errarle por redondeo.
    """
    return desde + (hasta - desde) * factor


def _remapear(valor: float, desde_min: float, desde_max: float,
              hasta_min: float, hasta_max: float) -> float:
    """Lleva un número de un rango a otro. Un rango de origen vacío es un error.

    Si `desde_min` y `desde_max` son iguales no hay proporción que calcular: todo el origen es un
    solo punto. Devolver el mínimo del destino sería inventar una respuesta para una pregunta que no
    la tiene.
    """
    ancho = desde_max - desde_min
    if ancho == 0.0:
        raise ValorError("desde_max", "el rango de origen no puede ser vacío")
    return hasta_min + (valor - desde_min) * (hasta_max - hasta_min) / ancho


def _redondear(valor: float) -> float:
    """Redondeo al entero más cercano, con el medio ALEJÁNDOSE del cero.

    `round()` de Python redondea el medio al par —`round(0.5)` es 0 y `round(1.5)` es 2—, que es
    correcto para estadística y desconcertante en un grafo: quien escribe 0,5 espera 1. Peor, el
    error no es constante, así que se ve como «a veces redondea mal».

    Acá el medio se aleja del cero, que es la convención que la gente aprende en la escuela y la que
    usan `FMath::RoundHalfFromZero` de Unreal y la mayoría de las calculadoras.
    """
    return math.floor(valor + 0.5) if valor >= 0.0 else math.ceil(valor - 0.5)


def _tangente(radianes: float) -> float:
    """Tangente. Cerca del polo devuelve un número enorme y eso NO es un error.

    En π/2 la tangente no existe, pero en flotantes ese punto exacto no se alcanza casi nunca: lo
    que llega son valores cercanos, donde la tangente REALMENTE vale millones. Poner un umbral para
    rechazarlos sería inventar un límite que la matemática no tiene y romper usos legítimos.
    Lo que sí se ataja es que el resultado deje de ser finito.
    """
    resultado = math.tan(radianes)
    if not math.isfinite(resultado):
        raise ValorError("radianes", "la tangente no es finita en ese ángulo")
    return resultado


# Registro público. El orden sólo es de declaración; ``ribbon.py`` decide el orden visual.
def _booleano(valor) -> bool:
    """Qué cuenta como «sí» cuando el valor llega desde el lienzo o desde un archivo.

    El canvas y los `.jamgraph` guardan los params como TEXTO, así que un interruptor prendido puede
    llegar como `True`, `"true"` o `"1"`. La conversión de Python no sirve: `bool("false")` es
    **True**, porque toda cadena no vacía lo es. Un interruptor apagado que se lee prendido al abrir
    el archivo es de los defectos más difíciles de ver, porque el nodo se dibuja bien.
    """
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return bool(valor)
    return str(valor).strip().lower() in ("1", "true", "si", "sí", "yes", "on", "verdadero")


def _arco(nombre_pin: str, funcion, valor: float) -> float:
    """Arcoseno/arcocoseno con el dominio verificado: fuera de -1..1 no existe ángulo.

    `math.asin(2)` tira `ValueError` con un texto del intérprete que no nombra el pin. Acá el
    diagnóstico dice DÓNDE está el problema, que es lo único accionable en un grafo de 30 nodos.
    """
    if not -1.0 <= valor <= 1.0:
        raise ValorError(nombre_pin, "tiene que estar entre -1 y 1 para que exista el ángulo")
    return funcion(valor)


def _atan2(y: float, x: float) -> float:
    """Ángulo del vector (x, y), con el CUADRANTE correcto y sin dividir por cero.

    Es la que de verdad se usa para apuntar: `atan(y/x)` pierde el cuadrante —confunde arriba con
    abajo— y explota cuando x es cero, que es justo el caso de mirar en vertical. El orden de los
    pines es `y` primero, como en toda la matemática y como en `FMath::Atan2`.
    """
    return math.atan2(y, x)


#: Un tiempo es SEGUNDOS, un `N` común, y no un tipo propio.
#:
#: Grasshopper tiene un tipo fecha/hora porque modela calendarios —salida del sol, estaciones—. Acá
#: lo que se necesita son DURACIONES: cuánto dura una extracción, cada cuánto rota una patrulla. Un
#: tipo nuevo obligaría a duplicar sumar, restar, interpolar y comparar; en segundos, todo eso ya
#: funciona. Los cuatro verbos de abajo son sólo la traducción a algo que una persona pueda leer.
SEGUNDOS_POR_HORA = 3600.0
SEGUNDOS_POR_MINUTO = 60.0


def _a_segundos(horas: float, minutos: float, segundos: float) -> float:
    """Suma sin normalizar: 90 minutos son 90 minutos.

    No se rechaza `minutos=90` ni se lo convierte a «1 hora 30» porque sumar es exactamente lo que
    alguien quiere al escribir «dos horas y 90 minutos». Normalizar sería decidir por el otro.
    """
    return (horas * SEGUNDOS_POR_HORA + minutos * SEGUNDOS_POR_MINUTO + segundos)


def _parte_del_tiempo(total: float, unidad: str) -> float:
    """La hora, el minuto o el segundo de una duración en segundos.

    Trunca hacia el CERO y no hacia abajo, para que una duración negativa —un contador que se pasó—
    dé `-1 h 30 m` y no `-2 h 30 m`. Con `//` de Python pasaría lo segundo, que es correcto como
    módulo euclídeo y absurdo leído como reloj.
    """
    signo = -1.0 if total < 0.0 else 1.0
    resto = abs(float(total))
    if unidad == "horas":
        return signo * math.floor(resto / SEGUNDOS_POR_HORA)
    if unidad == "minutos":
        return signo * math.floor((resto % SEGUNDOS_POR_HORA) / SEGUNDOS_POR_MINUTO)
    return signo * (resto % SEGUNDOS_POR_MINUTO)


def _casi_igual(a: float, b: float, tolerancia: float) -> bool:
    """Igualdad de flotantes con tolerancia EXPLÍCITA y visible en el nodo.

    `0.1 + 0.2 == 0.3` es falso en cualquier lenguaje con flotantes, y en un grafo eso se ve como
    «el condicional no funciona». La tolerancia es un parámetro y no una constante escondida para
    que quien compara distancias en centímetros pueda subirla sin tocar código.
    """
    if tolerancia < 0.0:
        raise ValueError("la tolerancia no puede ser negativa")
    return abs(a - b) <= tolerancia


VALORES: dict[str, dict] = {
    "number": {
        "label": "Número", "cat": "Params", "source": True, "out_name": "N",
        "params": {"name": "n", "value": 0.0, "min": 0.0, "max": 100.0},
        "tipos": {"name": "T", "value": "N", "min": "N", "max": "N"},
        "doc": "variable: un número con nombre y rango (Number Slider)",
    },
    "text": {
        "label": "Texto", "cat": "Params", "source": True, "out_name": "T",
        "params": {"name": "t", "value": ""},
        "tipos": {"name": "T", "value": "T"},
        "doc": "variable de texto con nombre para anclas, assets y modos",
    },
    "boolean": {
        "label": "Interruptor", "cat": "Params", "source": True, "out_name": "B",
        "params": {"name": "b", "value": False},
        "tipos": {"name": "T", "value": "B"},
        "doc": "variable booleana con nombre: sí/no para manejar un parámetro desde el lienzo",
    },
    "math_add": {
        "label": "Sumar", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"a": 0.0, "b": 0.0}, "tipos": {"a": "N", "b": "N"},
        "etiquetas_params": {"a": "a (Número)", "b": "b (Número)"},
        "out_label": "resultado",
        "operacion": lambda a, b: a + b,
        "doc": "suma dos números: a + b",
    },
    "math_subtract": {
        "label": "Restar", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"minuendo": 0.0, "sustraendo": 0.0},
        "tipos": {"minuendo": "N", "sustraendo": "N"},
        "etiquetas_params": {
            "minuendo": "minuendo (Número)", "sustraendo": "sustraendo (Número)"},
        "out_label": "resultado",
        "operacion": lambda minuendo, sustraendo: minuendo - sustraendo,
        "doc": "resta en orden: minuendo − sustraendo",
    },
    "math_multiply": {
        "label": "Multiplicar", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"a": 1.0, "b": 1.0}, "tipos": {"a": "N", "b": "N"},
        "etiquetas_params": {"a": "a (Número)", "b": "b (Número)"},
        "out_label": "resultado",
        "operacion": lambda a, b: a * b,
        "doc": "multiplica dos números: a × b",
    },
    "math_divide": {
        "label": "Dividir", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"dividendo": 0.0, "divisor": 1.0},
        "tipos": {"dividendo": "N", "divisor": "N"},
        "etiquetas_params": {
            "dividendo": "dividendo (Número)", "divisor": "divisor (Número)"},
        "out_label": "resultado",
        "operacion": _division,
        "doc": "divide en orden: dividendo ÷ divisor; divisor cero es error",
    },
    "math_negate": {
        "label": "Negar", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"valor": 0.0}, "tipos": {"valor": "N"},
        "etiquetas_params": {"valor": "valor (Número)"},
        "out_label": "resultado",
        "operacion": lambda valor: -valor,
        "doc": "invierte el signo de un número: −valor",
    },
    "math_absolute": {
        "label": "Absoluto", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"valor": 0.0}, "tipos": {"valor": "N"},
        "etiquetas_params": {"valor": "valor (Número)"},
        "out_label": "resultado",
        "operacion": abs,
        "doc": "distancia de un número a cero: |valor|",
    },
    "math_modulo": {
        "label": "Módulo", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"valor": 0.0, "modulo": 1.0},
        "tipos": {"valor": "N", "modulo": "N"},
        "etiquetas_params": {
            "valor": "valor (Número)", "modulo": "módulo (Número)"},
        "out_label": "resultado",
        "operacion": _modulo,
        "doc": "resto euclídeo: valor módulo divisor; módulo cero es error",
    },
    "math_power": {
        "label": "Potencia", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"base": 1.0, "exponente": 2.0},
        "tipos": {"base": "N", "exponente": "N"},
        "etiquetas_params": {
            "base": "base (Número)", "exponente": "exponente (Número)"},
        "out_label": "resultado",
        "operacion": _potencia,
        "doc": "eleva la base al exponente; sólo produce resultados reales finitos",
    },
    "math_sqrt": {
        "label": "Raíz cuadrada", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"radicando": 0.0}, "tipos": {"radicando": "N"},
        "etiquetas_params": {"radicando": "radicando (Número)"},
        "out_label": "resultado",
        "operacion": _raiz_cuadrada,
        "doc": "raíz cuadrada real; un radicando negativo es error",
    },
    "math_min": {
        "label": "Mínimo", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"a": 0.0, "b": 0.0},
        "tipos": {"a": "N", "b": "N"},
        "etiquetas_params": {"a": "a (Número)", "b": "b (Número)"},
        "out_label": "menor",
        "operacion": min,
        "doc": "el menor de dos números",
    },
    "math_max": {
        "label": "Máximo", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"a": 0.0, "b": 0.0},
        "tipos": {"a": "N", "b": "N"},
        "etiquetas_params": {"a": "a (Número)", "b": "b (Número)"},
        "out_label": "mayor",
        "operacion": max,
        "doc": "el mayor de dos números",
    },
    "math_clamp": {
        "label": "Limitar", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"valor": 0.0, "minimo": 0.0, "maximo": 1.0},
        "tipos": {"valor": "N", "minimo": "N", "maximo": "N"},
        "etiquetas_params": {"valor": "valor (Número)", "minimo": "mínimo (Número)", "maximo": "máximo (Número)"},
        "out_label": "limitado",
        "operacion": _limitar,
        "doc": "acota un número a un rango; un rango dado vuelta es error, no se acomoda solo",
    },
    "math_saturate": {
        "label": "Saturar", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"valor": 0.0},
        "tipos": {"valor": "N"},
        "etiquetas_params": {"valor": "valor (Número)"},
        "out_label": "0..1",
        "operacion": lambda valor: _limitar(valor, 0.0, 1.0),
        "doc": "acota un número a 0..1; el caso tan común que merece su propio nodo",
    },
    "math_lerp": {
        "label": "Interpolar", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"desde": 0.0, "hasta": 1.0, "factor": 0.5},
        "tipos": {"desde": "N", "hasta": "N", "factor": "N"},
        "etiquetas_params": {"desde": "desde (Número)", "hasta": "hasta (Número)", "factor": "factor (Número)"},
        "out_label": "mezcla",
        "operacion": _interpolar,
        "doc": "mezcla dos números; el factor NO se acota, así que 1.5 extrapola a propósito",
    },
    "math_remap": {
        "label": "Remapear", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"valor": 0.0, "desde_min": 0.0, "desde_max": 1.0, "hasta_min": 0.0, "hasta_max": 100.0},
        "tipos": {"valor": "N", "desde_min": "N", "desde_max": "N", "hasta_min": "N", "hasta_max": "N"},
        "etiquetas_params": {"valor": "valor (Número)", "desde_min": "desde mín (Número)", "desde_max": "desde máx (Número)", "hasta_min": "hasta mín (Número)", "hasta_max": "hasta máx (Número)"},
        "out_label": "remapeado",
        "operacion": _remapear,
        "doc": "lleva un número de un rango a otro; un rango de origen vacío es error",
    },
    "math_floor": {
        "label": "Piso", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"valor": 0.0},
        "tipos": {"valor": "N"},
        "etiquetas_params": {"valor": "valor (Número)"},
        "out_label": "piso",
        "operacion": lambda valor: float(math.floor(valor)),
        "doc": "el entero más cercano hacia abajo; con negativos se aleja del cero (-2.1 da -3)",
    },
    "math_ceil": {
        "label": "Techo", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"valor": 0.0},
        "tipos": {"valor": "N"},
        "etiquetas_params": {"valor": "valor (Número)"},
        "out_label": "techo",
        "operacion": lambda valor: float(math.ceil(valor)),
        "doc": "el entero más cercano hacia arriba; con negativos se acerca al cero (-2.9 da -2)",
    },
    "math_round": {
        "label": "Redondear", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"valor": 0.0},
        "tipos": {"valor": "N"},
        "etiquetas_params": {"valor": "valor (Número)"},
        "out_label": "redondeado",
        "operacion": _redondear,
        "doc": "al entero más cercano, con el medio ALEJÁNDOSE del cero: 0.5 da 1, no 0",
    },
    "math_radians": {
        "label": "Grados a radianes", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"grados": 0.0},
        "tipos": {"grados": "N"},
        "etiquetas_params": {"grados": "grados (Número)"},
        "out_label": "radianes",
        "operacion": math.radians,
        "doc": "convierte grados a radianes, que es lo que consumen seno, coseno y tangente",
    },
    "math_degrees": {
        "label": "Radianes a grados", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"radianes": 0.0},
        "tipos": {"radianes": "N"},
        "etiquetas_params": {"radianes": "radianes (Número)"},
        "out_label": "grados",
        "operacion": math.degrees,
        "doc": "convierte radianes a grados, que es como se piensan las rotaciones en el editor",
    },
    "math_sin": {
        "label": "Seno", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"radianes": 0.0},
        "tipos": {"radianes": "N"},
        "etiquetas_params": {"radianes": "radianes (Número)"},
        "out_label": "seno",
        "operacion": math.sin,
        "doc": "seno de un ángulo EN RADIANES; para grados, encadenar «Grados a radianes»",
    },
    "math_cos": {
        "label": "Coseno", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"radianes": 0.0},
        "tipos": {"radianes": "N"},
        "etiquetas_params": {"radianes": "radianes (Número)"},
        "out_label": "coseno",
        "operacion": math.cos,
        "doc": "coseno de un ángulo EN RADIANES; para grados, encadenar «Grados a radianes»",
    },
    "math_tan": {
        "label": "Tangente", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"radianes": 0.0},
        "tipos": {"radianes": "N"},
        "etiquetas_params": {"radianes": "radianes (Número)"},
        "out_label": "tangente",
        "operacion": _tangente,
        "doc": "tangente de un ángulo EN RADIANES; cerca del polo da números enormes y eso no es un error",
    },
    "math_asin": {
        "label": "Arcoseno", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"seno": 0.0},
        "tipos": {"seno": "N"},
        "etiquetas_params": {"seno": "seno (Número)"},
        "out_label": "radianes",
        "operacion": lambda seno: _arco("seno", math.asin, seno),
        "doc": "ángulo en radianes cuyo seno es el dado; fuera de -1..1 no existe y es error",
    },
    "math_acos": {
        "label": "Arcocoseno", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"coseno": 1.0},
        "tipos": {"coseno": "N"},
        "etiquetas_params": {"coseno": "coseno (Número)"},
        "out_label": "radianes",
        "operacion": lambda coseno: _arco("coseno", math.acos, coseno),
        "doc": "ángulo en radianes cuyo coseno es el dado; fuera de -1..1 no existe y es error",
    },
    "math_atan": {
        "label": "Arcotangente", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"tangente": 0.0},
        "tipos": {"tangente": "N"},
        "etiquetas_params": {"tangente": "tangente (Número)"},
        "out_label": "radianes",
        "operacion": math.atan,
        "doc": "ángulo en radianes cuya tangente es la dada; siempre entre -90° y 90°",
    },
    "math_atan2": {
        "label": "Ángulo de un vector", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"y": 0.0, "x": 1.0},
        "tipos": {"y": "N", "x": "N"},
        "etiquetas_params": {"y": "y (Número)", "x": "x (Número)"},
        "out_label": "radianes",
        "operacion": _atan2,
        "doc": "ángulo del vector (x, y) con el CUADRANTE correcto; es la que sirve para apuntar",
    },
    "time_construct": {
        "label": "Armar tiempo", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"horas": 0.0, "minutos": 0.0, "segundos": 0.0},
        "tipos": {"horas": "N", "minutos": "N", "segundos": "N"},
        "etiquetas_params": {"horas": "horas (Número)", "minutos": "minutos (Número)", "segundos": "segundos (Número)"},
        "out_label": "segundos",
        "operacion": _a_segundos,
        "doc": "horas, minutos y segundos a segundos totales; no normaliza: 90 minutos son 90 minutos",
    },
    "time_horas": {
        "label": "Horas de", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"total": 0.0},
        "tipos": {"total": "N"},
        "etiquetas_params": {"total": "total (Número)"},
        "out_label": "horas",
        "operacion": lambda total: _parte_del_tiempo(total, "horas"),
        "doc": "las horas enteras de una duración en segundos",
    },
    "time_minutos": {
        "label": "Minutos de", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"total": 0.0},
        "tipos": {"total": "N"},
        "etiquetas_params": {"total": "total (Número)"},
        "out_label": "minutos",
        "operacion": lambda total: _parte_del_tiempo(total, "minutos"),
        "doc": "los minutos de una duración, ya descontadas las horas",
    },
    "time_segundos": {
        "label": "Segundos de", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"total": 0.0},
        "tipos": {"total": "N"},
        "etiquetas_params": {"total": "total (Número)"},
        "out_label": "segundos",
        "operacion": lambda total: _parte_del_tiempo(total, "segundos"),
        "doc": "los segundos de una duración, ya descontados los minutos",
    },
    # ---- comparaciones: las ÚNICAS que producen un booleano ----
    # Hasta acá ningún nodo producía `B`, así que un condicional no tenía a qué cablearse: era un
    # checkbox eligiendo rama, apenas mejor que recablear a mano. Estas son las que le dan sentido.
    "compare_greater": {
        "label": "Mayor que", "cat": "Maths", "source": True, "out_name": "B",
        "params": {"a": 0.0, "b": 0.0}, "tipos": {"a": "N", "b": "N"},
        "etiquetas_params": {"a": "a (Número)", "b": "b (Número)"},
        "out_label": "a > b",
        "operacion": lambda a, b: a > b,
        "doc": "verdadero cuando a es estrictamente mayor que b",
    },
    "compare_less": {
        "label": "Menor que", "cat": "Maths", "source": True, "out_name": "B",
        "params": {"a": 0.0, "b": 0.0}, "tipos": {"a": "N", "b": "N"},
        "etiquetas_params": {"a": "a (Número)", "b": "b (Número)"},
        "out_label": "a < b",
        "operacion": lambda a, b: a < b,
        "doc": "verdadero cuando a es estrictamente menor que b",
    },
    "compare_greater_equal": {
        "label": "Mayor o igual", "cat": "Maths", "source": True, "out_name": "B",
        "params": {"a": 0.0, "b": 0.0},
        "tipos": {"a": "N", "b": "N"},
        "etiquetas_params": {"a": "a (Número)", "b": "b (Número)"},
        "out_label": "a ≥ b",
        "operacion": lambda a, b: a >= b,
        "doc": "verdadero cuando a es mayor que b o igual",
    },
    "compare_less_equal": {
        "label": "Menor o igual", "cat": "Maths", "source": True, "out_name": "B",
        "params": {"a": 0.0, "b": 0.0},
        "tipos": {"a": "N", "b": "N"},
        "etiquetas_params": {"a": "a (Número)", "b": "b (Número)"},
        "out_label": "a ≤ b",
        "operacion": lambda a, b: a <= b,
        "doc": "verdadero cuando a es menor que b o igual",
    },
    "compare_equal": {
        "label": "Igual a", "cat": "Maths", "source": True, "out_name": "B",
        "params": {"a": 0.0, "b": 0.0, "tolerancia": 1e-06},
        "tipos": {"a": "N", "b": "N", "tolerancia": "N"},
        "etiquetas_params": {
            "a": "a (Número)", "b": "b (Número)", "tolerancia": "tolerancia (Número)"},
        "out_label": "a = b",
        "operacion": _casi_igual,
        "doc": "verdadero cuando a y b difieren menos que la tolerancia; comparar flotantes con «==» "
               "da falso por un error de redondeo que nadie ve",
    },
    # Compatibilidad: sigue siendo el nodo de texto libre, ahora presentado como opción avanzada.
    "math": {
        "label": "Expresión", "cat": "Maths", "source": True, "out_name": "N",
        "params": {"name": "m", "expr": "0"},
        "tipos": {"name": "T", "expr": "T"},
        "doc": "expresión avanzada sobre variables: sin/cos/sqrt/min/max/clamp/lerp/remap/rand",
    },
}

VALOR_KINDS = tuple(VALORES)
DEFAULTS = {verbo: dict(meta["params"]) for verbo, meta in VALORES.items()}


def tipo_salida(verbo: str) -> str | None:
    meta = VALORES.get(verbo)
    return meta.get("out_name") if meta else None


def tipo_param(verbo: str, pin: str) -> str | None:
    meta = VALORES.get(verbo)
    return meta.get("tipos", {}).get(pin) if meta else None


def _numero(valor, pin: str, tabla: dict, eval_expr: Callable) -> float:
    """Literal o expresión → número finito. Una referencia ausente queda pendiente otra pasada."""
    original = valor
    if isinstance(valor, str):
        texto = valor.strip()
        try:
            valor = float(texto)
        except ValueError:
            expresion = texto[1:] if texto.startswith("=") else texto
            valor = eval_expr(expresion, {
                k: v for k, v in tabla.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            })
            if valor is None:
                raise ValorPendiente() from None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ValorError(pin, f"número inválido: «{original}»") from None
    if not math.isfinite(numero):
        raise ValorError(pin, f"el número debe ser finito: «{original}»")
    return numero


def evaluar(verbo: str, params: dict, tabla: dict, eval_expr: Callable) -> object:
    """Evalúa un nodo ya con defaults/cables aplicados; puede quedar pendiente o fallar por pin."""
    meta = VALORES[verbo]
    if verbo == "text":
        return str(params.get("value", ""))
    if verbo == "number":
        return _numero(params.get("value", 0.0), "value", tabla, eval_expr)
    if verbo == "boolean":
        # No pasa por `_numero`: lo aplastaría a 1.0/0.0 y dejaría de ser booleano para el resto
        # del sistema — el mismo motivo por el que las comparaciones se saltean esa conversión.
        return _booleano(params.get("value", False))
    if verbo == "math":
        expr = str(params.get("expr", "0"))
        valor = eval_expr(expr, {
            k: v for k, v in tabla.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        })
        if valor is None:
            raise ValorPendiente()
        return _numero(valor, "expr", tabla, eval_expr)

    argumentos = [
        _numero(params.get(pin, meta["params"][pin]), pin, tabla, eval_expr)
        for pin in meta["params"]
    ]
    try:
        resultado = meta["operacion"](*argumentos)
    except ValorError:
        raise
    except (ArithmeticError, ValueError) as exc:
        raise ValorError("resultado", str(exc)) from exc
    if meta.get("out_name") == "B":
        # Un booleano NO pasa por `_numero`: lo aplastaría a 1.0/0.0 y dejaría de ser un booleano
        # para el resto del sistema. Lo decide `out_name` y no una lista de verbos, así una
        # comparación nueva no necesita acordarse de tocar esto.
        return bool(resultado)
    return _numero(resultado, "resultado", tabla, eval_expr)


def _por_que_no_resolvio(nodo: dict, campo_verbo: str, tabla: dict) -> str:
    """Por qué un nodo de valor quedó sin resolver, con el nombre exacto y qué SÍ existe.

    «valor o expresión sin resolver» era verdad pero inservible: el caso abrumadoramente común es
    un nombre de variable mal escrito, y el mensaje no decía cuál ni contra qué. Escribir variables
    a mano sin autocompletado hace que el typo sea LA falla típica, así que el diagnóstico tiene que
    resolverla sin salir del nodo.
    """
    import re

    generico = "valor o expresión sin resolver"
    if nodo.get(campo_verbo) != "math":
        # Los demás nodos de valor sólo quedan pendientes por un cable que no llegó (o un ciclo).
        return generico + " (¿un cable de entrada sin resolver, o un ciclo?)"

    expr = str(nodo.get("params", {}).get("expr", ""))
    # Nombres que la expresión menciona y que la tabla no tiene. Se descartan las funciones que el
    # evaluador provee, o `sqrt(x)` se reportaría como «variable desconocida».
    conocidas = {"sin", "cos", "tan", "sqrt", "abs", "min", "max", "clamp", "lerp", "remap",
                 "rand", "floor", "ceil", "round", "pi", "e"}
    citados = [m for m in re.findall(r"[A-Za-z_][A-Za-z_0-9]*", expr) if m not in conocidas]
    faltan = sorted({m for m in citados if m not in tabla})
    if not faltan:
        return generico
    # Sólo las NUMÉRICAS: un booleano no es usable en una expresión (ver `evaluar`), así que
    # ofrecerlo como alternativa mandaría a quien lee a un segundo error.
    disponibles = sorted(k for k, v in tabla.items()
                         if isinstance(v, (int, float)) and not isinstance(v, bool))
    hay = ", ".join(f"«{d}»" for d in disponibles) if disponibles else "ninguna todavía"
    nombres = ", ".join(f"«{f}»" for f in faltan)
    return (f"la expresión usa {nombres}, que no {'son' if len(faltan) > 1 else 'es'} una variable; "
            f"disponibles: {hay}")


def resolver(nodos: dict, enlaces: list[tuple[str, str, str, str]], *, campo_verbo: str,
             eval_expr: Callable) -> tuple[dict, dict, dict[str, list[str]]]:
    """Resuelve el sub-DAG de valores de Graph o Flow.

    Devuelve ``(tabla_por_nombre, valores_por_nodo, errores_por_nodo)``. Los enlaces ya deben haber
    pasado el preflight del consumidor; sólo se consideran cables a parámetros, nunca el stream
    principal ``in``.
    """
    valor_nodos = {
        nid: nodo for nid, nodo in nodos.items() if nodo.get(campo_verbo) in VALORES
    }
    fuentes = {
        (destino, destino_pin): origen
        for origen, _origen_pin, destino, destino_pin in enlaces
        if destino_pin != "in"
    }
    tabla: dict[str, object] = {}
    por_nodo: dict[str, object] = {}
    errores: dict[str, list[str]] = {}

    for _ in range(len(valor_nodos) + 1):
        cambio = False
        for nid, nodo in valor_nodos.items():
            if nid in errores:
                continue
            verbo = nodo[campo_verbo]
            defaults = DEFAULTS[verbo]
            efectivos = dict(defaults)
            efectivos.update({
                pin: valor for pin, valor in nodo.get("params", {}).items() if pin in defaults
            })
            pendiente = False
            for pin in defaults:
                origen = fuentes.get((nid, pin))
                if origen is not None:
                    if origen not in por_nodo:
                        pendiente = True
                        break
                    efectivos[pin] = por_nodo[origen]
            if pendiente:
                continue

            nombre = str(efectivos.get("name") or nid)
            try:
                valor = evaluar(verbo, efectivos, tabla, eval_expr)
            except ValorPendiente:
                continue
            except ValorError as exc:
                errores[nid] = [str(exc)]
                continue
            if por_nodo.get(nid) != valor or tabla.get(nombre) != valor:
                por_nodo[nid] = valor
                tabla[nombre] = valor
                cambio = True
        if not cambio:
            break

    for nid in valor_nodos:
        if nid not in por_nodo and nid not in errores:
            errores[nid] = [_por_que_no_resolvio(valor_nodos[nid], campo_verbo, tabla)]
    return tabla, por_nodo, errores
