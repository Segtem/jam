"""Identidad de un resultado cocinado: qué se puede reusar y qué hay que rehacer.

Medido el 2026-08-11 en UE 5.8.1: compilar un grafo cuesta **0,1–0,3 ms** y correrlo **167–498 ms**.
El cerebro es gratis; el costo está entero dentro del motor, y escala con la cantidad de nodos que
se ejecutan. Por eso el caché NO es del compile —que ya no cuesta nada— sino de los RESULTADOS: la
geometría que el motor ya construyó para un nodo.

Este módulo sólo calcula identidades y decide qué quedó sucio. No guarda mallas ni toca `unreal`:
así el criterio de reuso se testea sin motor, que es la única forma de confiar en él —un caché que
devuelve un resultado viejo es un bug silencioso y carísimo de encontrar—.
"""

from __future__ import annotations

import hashlib
import json


def huella(verbo: str, params: dict, entradas: list[str]) -> str:
    """Identidad de un resultado: mismo verbo, mismos params y mismas entradas ⇒ misma huella.

    Las entradas entran por su HUELLA y no por su id: si un nodo de más arriba cambió, la huella de
    todo lo que cuelga de él cambia sola. Eso es lo que hace que ensuciar se propague sin tener que
    recorrer el grafo a mano.

    Los params se serializan ordenados y como texto porque el mismo valor puede llegar como `"20"` o
    como `20` según venga del canvas o de un archivo, y dos huellas distintas para el mismo grafo
    harían que el caché no sirva justo cuando más se lo necesita.
    """
    datos = {
        "verbo": str(verbo),
        "params": {str(k): str(v) for k, v in sorted((params or {}).items())},
        "entradas": list(entradas or ()),
    }
    crudo = json.dumps(datos, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()[:32]


def huellas_del_grafo(nodos: dict, aristas: list) -> dict[str, str]:
    """Huella de cada nodo, propagando desde las fuentes. Devuelve `{id: huella}`.

    Un nodo que participa de un ciclo NO recibe huella: sin un orden no hay identidad estable, y
    darle una cualquiera sería inventar que su resultado se puede reusar.
    """
    entradas_de: dict[str, list[str]] = {nid: [] for nid in nodos}
    for arista in aristas or ():
        if len(arista) >= 3:
            origen, destino = str(arista[0]), str(arista[2])
            if destino in entradas_de:
                entradas_de[destino].append(origen)

    huellas: dict[str, str] = {}
    pendientes = set(nodos)
    while pendientes:
        listos = [nid for nid in pendientes
                  if all(o in huellas for o in entradas_de.get(nid, ()))]
        if not listos:
            break  # lo que queda está en un ciclo: se deja sin huella a propósito
        for nid in sorted(listos):
            nodo = nodos[nid] or {}
            huellas[nid] = huella(
                nodo.get("verb") or nodo.get("kind") or "",
                nodo.get("params") or {},
                [huellas[o] for o in sorted(entradas_de.get(nid, ()))])
            pendientes.discard(nid)
    return huellas


def sucios(antes: dict, ahora: dict) -> list[str]:
    """Qué nodos hay que recocinar: los que cambiaron de huella y los que son nuevos.

    Ordenado para que el resultado sea reproducible; un plan de cocción que cambia de orden entre
    corridas es imposible de comparar cuando algo sale mal.
    """
    return sorted(nid for nid, h in (ahora or {}).items() if (antes or {}).get(nid) != h)


#: Salidas que son un DATO transitorio: viven en memoria y reusarlas equivale exactamente a
#: recomputarlas. `A` queda afuera aunque sea un dato, porque un verbo que produce un asset suele
#: haberlo escrito en Content, y reusar su resultado saltearía esa escritura.
SALIDAS_CACHEABLES = ("M", "S", "P", "F", "N", "N[]")


def es_cacheable(info: dict) -> bool:
    """¿Se puede reusar el resultado de este verbo sin cambiar lo que pasa en la escena?

    La pregunta NO es «¿es puro?» sino «¿saltearlo deja el mundo igual?». Un verbo que spawnea
    actores puede devolver el mismo dato dos veces y no por eso se lo puede saltear: la segunda
    corrida tiene que volver a poner los actores. Por eso el criterio mira la SALIDA —si es un dato
    transitorio— y no el determinismo de la función.

    Se empieza conservador a propósito. Un falso negativo cuesta tiempo de cocción; un falso
    positivo hace desaparecer geometría de la escena y se diagnostica como «a veces no aparece»,
    que es de lo peor que hay para depurar. Ampliar esta lista pide evidencia, no intuición.
    """
    if not isinstance(info, dict):
        return False
    if info.get("asset_argument"):
        return False
    # Que la salida sea un dato NO alcanza, y esto lo encontró un test contra el registro real:
    # `scatter` produce `P` —puntos— y ADEMÁS spawnea actores. Reusar su resultado devolvería los
    # mismos puntos y dejaría la escena sin nada, que es el falso positivo que hay que evitar.
    #
    # `graph_only` es hoy la marca más cercana a «esto vive en el canvas y no toca el nivel»: los
    # verbos de geometría la tienen y los de colocación no. Es un criterio prestado, no uno propio,
    # y por eso se declara acá: cuando el registro tenga un campo que diga exactamente «no tiene
    # efectos en la escena», este es el lugar que hay que cambiar.
    if not info.get("graph_only"):
        return False
    return str(info.get("out_name") or "") in SALIDAS_CACHEABLES
