"""Letras de pin para el modo compacto del canvas, al estilo de Grasshopper.

Un nodo colapsado no tiene lugar para «recompute_tangents»: muestra una LETRA por pin, como los
`G`/`X`/`Y`/`Z` de Grasshopper. Esa letra tiene que ser estable (la misma en cada apertura del
grafo) y única dentro del nodo, o dos pines quedarían indistinguibles justo cuando lo único que se
ve es la letra.

Cerebro puro: viaja en el spec para que el C++ sólo la dibuje. La regla vive UNA vez.
"""

from __future__ import annotations

#: Sufijos de eje: en `size_x` lo que distingue no es la inicial —que choca con `size_y`— sino el
#: eje. Es además la letra que alguien esperaría ver.
EJES = ("x", "y", "z", "w")


def _candidatas(nombre: str):
    """Letras a probar para un pin, de la más informativa a la menos."""
    limpio = str(nombre).strip().lower()
    if not limpio:
        return
    partes = [p for p in limpio.replace("-", "_").split("_") if p]
    # 1. El eje, si el nombre termina en uno: `size_x` → X, y no la S que comparte con `size_y`.
    if partes and partes[-1] in EJES:
        yield partes[-1].upper()
        # 1b. Inicial + eje, para el SEGUNDO grupo de ejes del mismo nodo. `mesh_box` tiene
        # `size_x/y/z` y `steps_x/y/z`: el primero se queda X/Y/Z y el segundo, sin esto, caía en
        # S/T/E —letras sueltas de «steps» que no dicen nada—. Con esto queda SX/SY/SZ, que se lee.
        if len(partes) > 1:
            yield partes[0][0].upper() + partes[-1].upper()
    # 2. La inicial de cada palabra: `recompute_tangents` → R, después T.
    for p in partes:
        yield p[0].upper()
    # 3. Cualquier otra letra del nombre, por si las iniciales ya están tomadas.
    for c in limpio:
        if c.isalpha():
            yield c.upper()
    # 4. Último recurso: dígitos. Feo, pero único — y sólo aparece con muchos pines parecidos.
    for d in "0123456789":
        yield d


def letras_de_pines(nombres) -> dict:
    """`{nombre_de_pin: letra}` — única dentro del nodo y estable para el mismo orden de pines.

    «Letra» es casi siempre UNA; puede ser dos cuando hay dos grupos de ejes en el mismo nodo
    (`SX`, `SY`…), porque ahí una sola no alcanza para decir cuál es cuál.

    El primer pin que pide una letra se la queda: por eso el resultado depende del ORDEN, que es el
    de las filas del nodo y no cambia entre corridas. Si dos pines se disputan la `S`, la gana el de
    arriba y el otro busca la siguiente candidata, igual que en Grasshopper.
    """
    usadas = set()
    salida: dict[str, str] = {}
    for nombre in nombres:
        elegida = "?"
        for c in _candidatas(nombre):
            if c not in usadas:
                elegida = c
                break
        usadas.add(elegida)
        salida[str(nombre)] = elegida
    return salida
