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


# Registro público. El orden sólo es de declaración; ``ribbon.py`` decide el orden visual.
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
    return _numero(resultado, "resultado", tabla, eval_expr)


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
            errores[nid] = ["valor o expresión sin resolver"]
    return tabla, por_nodo, errores
