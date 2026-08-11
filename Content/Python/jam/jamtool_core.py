"""El `.jamtool`: una herramienta que se ARMA EN EL GRAPH y se importa a la Dash Bar.

Cerebro puro, sin `unreal`. La idea es la de Houdini y Grasshopper: colapsás una selección de nodos,
eso queda como un artefacto, y el artefacto aparece como una herramienta más. Jam ya tenía la mitad
—`Ctrl+G` colapsa, `funcion.firma()` da la firma tipada, `funcion_id` es una identidad estable
separada del nombre visible— y lo que falta es que ese cuerpo pueda **viajar solo** y **correrse
desde la barra**, donde no hay cables sino una selección.

Acá viven las tres piezas:

  · `exportar` / `importar`  — el artefacto portable, con esquema y dependencias declaradas.
  · `superficies_de_funcion` — dónde se ve una tool armada por el usuario.
  · `entrada_de_seleccion`   — qué input recibe la selección cuando corre desde la Dash Bar.

Ver `Vault-kb/01-Graph/2026-08-11-INFORME-Definicion-De-Tools-Y-Superficies-v1.0.md`.
"""

from __future__ import annotations

#: Versión del formato. Un `.jamtool` guardado hoy tiene que poder abrirse dentro de seis meses, y
#: para eso hace falta saber con qué reglas se escribió. Sube cuando cambie la FORMA, no cuando se
#: agregue una tool.
ESQUEMA = 1

#: Tipos que la Dash Bar puede resolver desde la selección de la escena. Un `input` de tipo `N`
#: (número) no puede salir de «lo que está seleccionado»: eso se pide como parámetro.
#:
#: `*` entra porque es el comodín que `funcion.firma()` pone cuando el borde no declara un tipo
#: concreto —que hoy es el caso más común—: un pin que acepta cualquier cosa acepta la selección.
#: Sin él, la tool recién colapsada no encontraba por dónde entrar y quedaba inaplicable en la barra.
TIPOS_DE_SELECCION = ("A", "A[]", "AF", "*")


class JamToolInvalido(ValueError):
    """El artefacto no se puede usar. Lleva el motivo en el mensaje, no un código."""


def entrada_de_seleccion(firma: dict) -> str | None:
    """Qué input recibe la selección de la escena al correr desde la Dash Bar.

    En el Graph una función se alimenta por cables. En la barra no hay cables: hay lo que el usuario
    tiene seleccionado. Alguien tiene que decidir por dónde entra eso.

    La regla es explícita-con-default: si la firma declara `entrada_seleccion`, manda eso; si no, el
    PRIMER input cuyo tipo pueda venir de la escena. Con un solo input compatible las dos reglas dan
    lo mismo y el autor no declara nada; con dos, el default elegiría por orden de dibujo —que es un
    detalle visual, no una decisión— y por eso conviene poder decirlo.

    Devuelve `None` cuando ningún input puede alimentarse de la selección: esa tool no se aplica a lo
    seleccionado, y la barra tiene que pedirle todo por parámetros en vez de inventar una entrada.
    """
    # `funcion.firma()` emite `entradas` con campo `name`; se aceptan las dos formas para que este
    # núcleo sirva tal cual con el camino real y no sólo con datos de test.
    entradas = list(firma.get("entradas") or firma.get("inputs") or ())
    declarada = str(firma.get("entrada_seleccion") or "").strip()
    if declarada:
        for entrada in entradas:
            if _nombre(entrada) == declarada:
                return declarada
        raise JamToolInvalido(
            f"la tool declara «{declarada}» como entrada de selección y no tiene un input con ese nombre")
    for entrada in entradas:
        if str(entrada.get("tipo") or "") in TIPOS_DE_SELECCION:
            return _nombre(entrada)
    return None


def _nombre(entrada: dict) -> str:
    return str(entrada.get("name") or entrada.get("nombre") or "")


def superficies_de_funcion(preset: dict) -> frozenset[str]:
    """Dónde se ve una tool armada por el usuario.

    Por defecto vive sólo en el Graph: una función recién colapsada es un paso intermedio de lo que
    alguien está construyendo, y llenar la barra con eso sería el mismo error que tenía el registro
    —aparecer por omisión—. Publicarla a la Dash Bar es un acto deliberado.
    """
    declaradas = preset.get("superficies")
    if declaradas is not None:
        return frozenset(str(s) for s in declaradas)
    return frozenset({"graph"})


def verbos_usados(cuerpo: dict) -> list[str]:
    """Los verbos que el cuerpo necesita para correr, ordenados y sin repetir.

    Viajan DENTRO del artefacto para que al importarlo se pueda decir «te falta esto» antes de
    ejecutar, en vez de fallar a mitad de camino con un error del compilador. Es lo mismo que hace
    un `.hda` al declarar de qué depende.
    """
    nodos = (cuerpo or {}).get("nodes") or {}
    encontrados = set()
    for nodo in nodos.values():
        if not isinstance(nodo, dict):
            continue
        verbo = nodo.get("verb") or nodo.get("kind")
        # `input` y `output` son los BORDES de la firma, no verbos que haya que tener instalados.
        if verbo and verbo not in ("input", "output"):
            encontrados.add(str(verbo))
    return sorted(encontrados)


def exportar(preset: dict) -> dict:
    """Un preset de función → el artefacto portable.

    No se serializa el preset tal cual: lo que viaja lleva su esquema, su identidad estable y sus
    dependencias declaradas. Un archivo que no se puede validar al abrirlo es un archivo que falla
    tarde y sin explicación.
    """
    if preset.get("kind") != "funcion":
        raise JamToolInvalido("sólo una función (un grafo con firma) puede exportarse como .jamtool")
    funcion_id = str(preset.get("funcion_id") or "").strip()
    if not funcion_id:
        raise JamToolInvalido("la función no tiene identidad estable (`funcion_id`)")
    nombre = str(preset.get("nombre") or "").strip()
    if not nombre:
        raise JamToolInvalido("la función no tiene nombre visible")
    cuerpo = preset.get("grafo") or preset.get("cuerpo")
    if not isinstance(cuerpo, dict) or not (cuerpo.get("nodes") or {}):
        raise JamToolInvalido("la función no tiene cuerpo")

    return {
        "esquema": ESQUEMA,
        # La identidad NO es el nombre: renombrar no puede romper los grafos que ya la llaman. Es la
        # misma razón por la que un componente de Grasshopper se identifica por GUID.
        "funcion_id": funcion_id,
        "nombre": nombre,
        "categoria": str(preset.get("categoria") or ""),
        "descripcion": str(preset.get("descripcion") or ""),
        "firma": preset.get("firma") or {},
        "superficies": sorted(superficies_de_funcion(preset)),
        "requiere": verbos_usados(cuerpo),
        "grafo": cuerpo,
    }


def importar(artefacto: dict, *, verbos_disponibles=None) -> dict:
    """Valida un `.jamtool` y devuelve el preset listo para guardar.

    Falla temprano y con el motivo puesto. `verbos_disponibles` es opcional: cuando se pasa, se
    comprueba que estén TODOS los que el artefacto declara necesitar, así el usuario se entera al
    importar y no cuando le da Run.
    """
    if not isinstance(artefacto, dict):
        raise JamToolInvalido("el archivo no contiene un objeto")
    esquema = artefacto.get("esquema")
    if esquema != ESQUEMA:
        raise JamToolInvalido(
            f"esquema {esquema!r}: este Jam entiende .jamtool de esquema {ESQUEMA}")
    for campo in ("funcion_id", "nombre", "grafo"):
        if not artefacto.get(campo):
            raise JamToolInvalido(f"al .jamtool le falta «{campo}»")

    if verbos_disponibles is not None:
        faltan = [v for v in (artefacto.get("requiere") or []) if v not in set(verbos_disponibles)]
        if faltan:
            raise JamToolInvalido(
                "esta tool necesita verbos que este Jam no tiene: " + ", ".join(sorted(faltan)))

    # Se valida acá y no al ejecutar: una entrada de selección que apunta a un input inexistente es
    # un archivo roto, y conviene saberlo al importarlo.
    entrada_de_seleccion(artefacto.get("firma") or {})

    return {
        "kind": "funcion",
        "funcion_id": str(artefacto["funcion_id"]),
        "nombre": str(artefacto["nombre"]),
        "categoria": str(artefacto.get("categoria") or ""),
        "descripcion": str(artefacto.get("descripcion") or ""),
        "firma": artefacto.get("firma") or {},
        "superficies": sorted(artefacto.get("superficies") or ("graph",)),
        "grafo": artefacto["grafo"],
    }
