"""Dónde se ve cada tool, y si su declaración está completa. Cerebro puro, sin `unreal`.

Relevado en `Vault-kb/01-Graph/2026-08-11-INFORME-Definicion-De-Tools-Y-Superficies-v1.0.md`: una
tool se declaraba en hasta cuatro lugares y su superficie se decidía **en negativo** con
`graph_only`, puesto en 93 de 113 entradas. Con ese default, una tool nueva aparecía en la Dash Bar
por olvido y no por decisión, y nadie medía si su declaración estaba entera.

Acá viven las dos respuestas: `superficies_de` dice dónde va una tool, y `auditar` es el oráculo del
registro que faltaba. Ninguna de las dos toca el motor, así que se pueden testear sin abrir Unreal.
"""

from __future__ import annotations

#: Las superficies donde puede aparecer una tool.
#:
#: `graph` es el canvas de nodos; `dash` es la barra de acciones sueltas. No son la misma cosa ni
#: quieren lo mismo: en el Graph una tool es un nodo que recibe cables y participa de una cadena, y
#: en la barra es un gesto que se aplica a lo que está seleccionado ahora.
SUPERFICIES = ("dash", "graph")


def superficies_de(info: dict) -> frozenset[str]:
    """Dónde se ve esta tool, en POSITIVO.

    Se lee `superficies` si está declarada. Si no, se deriva del viejo `graph_only` para que las
    entradas sin migrar sigan funcionando igual: es la única forma de mudar 113 tools sin una
    ventana en la que el ribbon quede a medias.

    La diferencia con `graph_only` no es cosmética. Preguntar «¿dónde va?» obliga a contestar; el
    campo negativo se contestaba solo, y mal: el default hacía aparecer en la barra todo lo que
    alguien olvidara marcar.
    """
    declaradas = info.get("superficies")
    if declaradas is not None:
        return frozenset(str(s) for s in declaradas)
    return frozenset({"graph"} if info.get("graph_only") else {"dash", "graph"})


#: Los tipos de entrada que una línea de consola SÍ puede dar.
#:
#: `A` es un asset: se nombra y listo (`drop SM_Barrel`). `""` es no necesitar ninguna. Todos los
#: demás —`M` una malla dinámica, `S` una curva, `P` puntos, `F` frames, `MT` un grafo de material—
#: son valores que nacen y mueren adentro de una corrida del Graph: no tienen nombre que escribir.
TIPOS_QUE_LA_CONSOLA_PUEDE_DAR = ("", "A")


def cable_que_falta(info: dict) -> str:
    """El tipo de entrada que este verbo sólo puede recibir por un CABLE, o `""` si no necesita.

    Contesta la pregunta que le faltaba a la consola: `mesh_extrude` está en el registro, así que
    hoy la consola lo acepta, le resuelve un asset cualquiera de la biblioteca y se lo pasa donde
    iba una malla. Lo que sale es «biblioteca vacía» o un error de tipo — dos mensajes que mandan a
    buscar el problema donde no está.

    **Se DERIVA, no se declara.** Los dos datos ya están en el registro y los calcula el motor de
    tools: `min_inputs` (cuántos cables exige) e `in_name` (de qué tipo). Etiquetar a mano los 166
    verbos sería inventar 166 oportunidades de equivocarse, y el que agregue el 167 no se enteraría.
    Si algún día hace falta una lista curada de qué luce bien en la consola —distinto de qué PUEDE
    correr—, eso es una superficie declarada y va en `superficies_de`, no acá.

    No juzga si el verbo es ÚTIL en la consola: `mesh_box` construye una malla que no va a ningún
    lado y aun así se deja pasar, porque contesta con la verdad («BOX M ✓ 12 triángulos») en vez de
    fallar raro. Acá sólo se ataja lo que es demostrablemente imposible.
    """
    if int(info.get("min_inputs", 0) or 0) < 1:
        return ""
    tipo = str(info.get("in_name", "") or "")
    return "" if tipo in TIPOS_QUE_LA_CONSOLA_PUEDE_DAR else tipo


def corre_en_consola(info: dict) -> bool:
    """¿Esta tool puede correr como una línea escrita, sin canvas?"""
    return not cable_que_falta(info)


def acepta_asset_como_entrada(info: dict) -> bool:
    """¿El slot de entrada de este verbo admite un asset?

    La consola tiene una convención vieja y cómoda: el token suelto de la línea es un asset y se le
    pasa al verbo como primer argumento. Anda mientras ese slot sea de assets. Cuando NO lo es, el
    asset entra donde iba otra cosa, y como es un string el verbo lo itera letra por letra: eso es
    lo que hacía que `scatter SM_Rock count=20` —el ejemplo que encabeza el docstring del DSL—
    muriera con `'str' object has no attribute 'pos'`.

    En esos casos el verbo corre SIN entrada (que es justo lo que significa `min_inputs` 0) y el
    asset queda para el paso que sí lo necesita: en `scatter` lo usa el `place` que la consola le
    compone atrás, que es quien pone las piedras.
    """
    return str(info.get("in_name", "") or "") in TIPOS_QUE_LA_CONSOLA_PUEDE_DAR


def auditar(registro: dict, *, categorias_ribbon=None, tipos_conocidos=None) -> list[str]:
    """El oráculo del registro: devuelve los defectos de declaración, uno por línea.

    Devuelve una LISTA y no un booleano porque un registro con doce huecos y uno con uno solo no
    son el mismo estado, y el que arregla necesita saber cuáles. Vacía significa sano.

    NO juzga si la tool hace lo que dice, ni si su doc es cierta, ni si conviene tenerla en la
    barra: eso es una decisión de producto. Sólo mide que la declaración esté completa y sea
    coherente consigo misma.
    """
    defectos = []
    categorias_ribbon = set(categorias_ribbon or ())
    tipos_conocidos = set(tipos_conocidos or ())

    for nombre in sorted(registro):
        info = registro[nombre]
        if not isinstance(info, dict):
            defectos.append(f"{nombre}: la entrada no es un diccionario")
            continue

        # Sin nombre visible, el ribbon pinta el nombre técnico. Es lo que mezcla «Simplificar por
        # triángulos» con `mesh_weld` crudo en el mismo subgrupo.
        if not str(info.get("label") or "").strip():
            defectos.append(f"{nombre}: sin `label`, el ribbon va a mostrar el nombre técnico")

        superficies = superficies_de(info)
        if not superficies:
            defectos.append(f"{nombre}: no declara ninguna superficie: no se ve en ningún lado")
        for superficie in sorted(superficies):
            if superficie not in SUPERFICIES:
                defectos.append(f"{nombre}: superficie desconocida «{superficie}»")

        categoria = str(info.get("cat") or "")
        if not categoria:
            defectos.append(f"{nombre}: sin `cat`")
        elif categorias_ribbon and categoria not in categorias_ribbon:
            defectos.append(
                f"{nombre}: su categoría «{categoria}» no existe en el ribbon; caería sin etiqueta")

        if not str(info.get("doc") or "").strip():
            defectos.append(f"{nombre}: sin `doc`; el tooltip queda vacío")

        params = info.get("params")
        if not isinstance(params, dict):
            defectos.append(f"{nombre}: `params` no es un diccionario")
            continue

        # Un dominio declarado sobre un parámetro que no existe es un dropdown que nunca aparece.
        for clave in (info.get("opciones") or {}):
            if clave not in params:
                defectos.append(f"{nombre}: `opciones` sobre «{clave}», que no es un parámetro")
        for clave in (info.get("etiquetas_params") or {}):
            if clave not in params:
                defectos.append(f"{nombre}: etiqueta sobre «{clave}», que no es un parámetro")
        for clave, tipo in (info.get("data_params") or {}).items():
            if clave not in params:
                defectos.append(f"{nombre}: `data_params` sobre «{clave}», que no es un parámetro")
            elif tipos_conocidos and tipo not in tipos_conocidos:
                defectos.append(f"{nombre}: el pin «{clave}» declara el tipo desconocido «{tipo}»")

    return defectos
