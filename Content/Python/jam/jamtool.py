"""El `.jamtool` en el disco: guardar, leer y listar. Adaptador fino.

El juicio vive en `jamtool_core` —qué es un artefacto válido, qué verbos necesita, por dónde entra
la selección—. Acá sólo está el trato con el sistema de archivos, para que el núcleo se pueda
testear sin motor y este módulo sea lo único que toca rutas.

Un `.jamtool` es JSON: legible, versionado y diffeable. No es un formato binario a propósito —una
tool que alguien armó tiene que poder mirarse, compartirse por chat y meterse en un repo—.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import jamtool_core

#: Extensión del artefacto. Se comprueba al abrir: un `.json` cualquiera no es una tool.
EXTENSION = ".jamtool"


def escribir(preset: dict, destino) -> str:
    """Exporta un preset de función a un `.jamtool` en `destino`. Devuelve la ruta escrita."""
    artefacto = jamtool_core.exportar(preset)
    ruta = Path(destino)
    if ruta.suffix != EXTENSION:
        ruta = ruta.with_suffix(EXTENSION)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(artefacto, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8")
    return str(ruta)


def leer(origen, *, verbos_disponibles=None) -> dict:
    """Lee y VALIDA un `.jamtool`. Devuelve el preset listo para guardar.

    Los errores salen como `JamToolInvalido` con el motivo puesto: un archivo que no se puede usar
    tiene que decir por qué al abrirlo, no al ejecutarlo.
    """
    ruta = Path(origen)
    if ruta.suffix != EXTENSION:
        raise jamtool_core.JamToolInvalido(f"«{ruta.name}» no es un {EXTENSION}")
    if not ruta.is_file():
        raise jamtool_core.JamToolInvalido(f"no existe el archivo «{ruta}»")
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise jamtool_core.JamToolInvalido(f"no se pudo leer «{ruta.name}»: {exc}") from exc
    return jamtool_core.importar(datos, verbos_disponibles=verbos_disponibles)


def listar(carpeta) -> list[dict]:
    """Los `.jamtool` de una carpeta, con lo justo para mostrarlos sin abrirlos del todo.

    Un archivo ilegible NO rompe el listado: aparece con su error. Que una tool corrupta esconda a
    las otras diecinueve sería peor que mostrarla rota.
    """
    ruta = Path(carpeta)
    if not ruta.is_dir():
        return []
    salida = []
    for archivo in sorted(ruta.glob(f"*{EXTENSION}")):
        entrada = {"archivo": str(archivo), "nombre": archivo.stem}
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
            entrada.update({
                "nombre": str(datos.get("nombre") or archivo.stem),
                "funcion_id": str(datos.get("funcion_id") or ""),
                "esquema": datos.get("esquema"),
                "requiere": list(datos.get("requiere") or []),
                "superficies": list(datos.get("superficies") or []),
            })
        except (OSError, ValueError) as exc:
            entrada["error"] = f"ilegible: {exc}"
        salida.append(entrada)
    return salida
