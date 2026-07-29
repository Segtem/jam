"""Genera los iconos propios de Jam a partir de un VOCABULARIO, como Grasshopper.

La lección de la hoja de iconos de Grasshopper no son los dibujos sino cómo están hechos: cada icono
**diagrama el dato**, no una metáfora. «Divide Curve» es literalmente una curva con puntos encima. Por
eso quinientos iconos siguen siendo distinguibles — están compuestos de un vocabulario compartido.

Acá ese vocabulario es el SISTEMA DE TIPOS de Jam, con los mismos colores que usan los pines y los
cables. Consecuencia doble: dos verbos con firma distinta tienen iconos distintos **por
construcción**, y el icono enseña el tipo — aprendés los colores una vez y todos se leen solos.

    P  punto      círculo relleno            S  curva      línea fina
    F  frame      ángulo de dos ejes         M  malla      facetas
    N[] serie     barritas de alturas        A  asset      cajita

Uso:  python3 tools/iconos_jam.py            → escribe los SVG en Resources/Icons/Lucide/
"""

from __future__ import annotations

import pathlib


# Colores de tipo, convertidos del lineal que usa `SJamGraphEditor::DataColor` a sRGB.
P = "#65B1D1"     # puntos
SERIE = "#F6C86F"  # N[]
ASSET = "#7CBF90"  # A
AF = "#A6D490"     # asset por frame
H = "#6FBCB5"      # HISM
S = "#CBAD69"      # spline
F = "#DA90B8"      # frames
M = "#50C8CE"      # malla
NUM = "#EAB559"    # N (número)
TEXTO = "#BF95D4"  # T (texto)
MATERIAL = "#C48659"  # MT (grafo de material, todavía sin hornear)
TINTA = "#2A2E33"  # trazo neutro para lo estructural

CABECERA = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"\n'
    '     fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
)

# El fondo REAL sobre el que se dibujan estos iconos, para revisarlos como se van a ver:
#
#     rsvg-convert -w 96 -h 96 -b "#F0F0F2" Resources/Icons/Lucide/jam-algo.svg -o /tmp/x.png
#
# `SJamGraphEditor::MakeBadge` le pone fondo casi BLANCO (0.94,0.94,0.95) a los iconos propios —los
# de Lucide, que son máscaras teñidas, van sobre el color de la categoría—. Revisarlos sobre el gris
# oscuro del canvas engaña en las dos direcciones: TINTA parece invisible cuando en realidad es lo
# que mejor se lee, y un color claro parece brillante cuando se va a lavar.
FONDO_DE_REVISION = "#F0F0F2"


# ---- vocabulario: cada función dibuja UN concepto, siempre igual ----

def punto(x, y, color=P, r=1.7):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" stroke="none"/>'


def curva(d, color=S, ancho=1.8):
    return f'<path d="{d}" stroke="{color}" stroke-width="{ancho}"/>'


def frame(x, y, color=F, largo=4.5):
    """Un frame se dibuja como su ángulo de ejes: eso es lo que un frame ES."""
    return (f'<path d="M{x} {y}v-{largo}" stroke="{color}" stroke-width="1.6"/>'
            f'<path d="M{x} {y}h{largo}" stroke="{color}" stroke-width="1.6"/>')


def malla(d, color=M, relleno=True):
    fill = f'fill="{color}" fill-opacity="0.35"' if relleno else 'fill="none"'
    return f'<path d="{d}" stroke="{color}" stroke-width="1.6" {fill}/>'


def barra(x, y0, alto, color=SERIE):
    return f'<path d="M{x} {y0}v-{alto}" stroke="{color}" stroke-width="2"/>'


def caja(x, y, w, h, color=ASSET):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="1" '
            f'stroke="{color}" stroke-width="1.6" fill="{color}" fill-opacity="0.25"/>')


def flecha(x0, y0, x1, y1, color=TINTA):
    return (f'<path d="M{x0} {y0}H{x1}" stroke="{color}" stroke-width="1.4"/>'
            f'<path d="m{x1 - 2} {y1 - 2} 2 2-2 2" stroke="{color}" stroke-width="1.4"/>')


def suelo(d="M2 18h20", color=TINTA, ancho=1.5):
    """La superficie sobre la que pasa todo: el suelo del scatter, la pendiente de una máscara."""
    return f'<path d="{d}" stroke="{color}" stroke-width="{ancho}"/>'


def apagado(x, y, color=P, r=1.7):
    """Un punto que la máscara descartó: se dibuja hueco, no se borra.

    Distinguir «lo filtró» de «nunca estuvo» es la misma idea que el `minimo` del debug de puntos.
    """
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{color}" '
            f'stroke-width="1.2" stroke-opacity="0.55"/>')


def pesado(x, y, peso, color=P):
    """Un punto cuyo TAMAÑO es su peso — el mismo mapeo que usa el ayudante de debug."""
    return punto(x, y, color, r=max(0.7, 0.7 + 2.0 * peso))


# Nada de <text>: el rasterizador de SVG de Unreal es nanosvg, que entiende path/rect/circle/
# ellipse/line/polygon/polyline/g y NADA más. Un <text> se parsea sin error y sale en blanco.
# `test_paleta.ElementosSoportadosTests` lo fija.


def fila(xs, y, color=P, r=1.7):
    return "".join(punto(x, y, color, r) for x in xs)


def svg(*piezas) -> str:
    return CABECERA + "\n  " + "\n  ".join(piezas) + "\n</svg>\n"


# ---- los iconos del tab Mesh ----
# Cada uno diagrama su firma. Los que antes compartían pictograma ahora difieren porque difiere
# lo que dibujan, no porque se les haya elegido otra metáfora.

ARCO = "M3 17c4-1 6-9 12-11"

ICONOS = {
    # ── primitivas: la forma, sin más ──────────────────────────────────────────────
    "jam-box": svg(malla("M5 9l7-4 7 4v7l-7 4-7-4z"), curva("M5 9l7 4 7-4M12 13v7", M, 1.2)),
    "jam-sphere": svg(malla("M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z"),
                      curva("M4 12h16M12 4c3 4 3 12 0 16", M, 1.1)),
    "jam-sphere-box": svg(malla("M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z"),
                          curva("M6 7h12M6 17h12M7 6v12M17 6v12", M, 1.1)),
    "jam-cylinder": svg(malla("M6 7h12v10a6 2 0 0 1-12 0z"),
                        f'<ellipse cx="12" cy="7" rx="6" ry="2" stroke="{M}" '
                        f'stroke-width="1.6" fill="{M}" fill-opacity="0.35"/>'),
    "jam-cone": svg(malla("M12 4l6 13a6 2 0 0 1-12 0z")),
    "jam-capsule": svg(malla("M8 9a4 4 0 0 1 8 0v6a4 4 0 0 1-8 0z"),
                       curva("M8 9h8M8 15h8", M, 1.1)),
    "jam-torus": svg(f'<ellipse cx="12" cy="12" rx="8.5" ry="4.5" stroke="{M}" '
                     f'stroke-width="1.6" fill="{M}" fill-opacity="0.28"/>',
                     f'<ellipse cx="12" cy="12" rx="3" ry="1.5" stroke="{M}" '
                     f'stroke-width="1.4" fill="none"/>'),
    "jam-disc": svg(f'<circle cx="12" cy="12" r="8" stroke="{M}" stroke-width="1.6" '
                    f'fill="{M}" fill-opacity="0.3"/>',
                    f'<circle cx="12" cy="12" r="3" stroke="{M}" stroke-width="1.4" fill="none"/>'),
    "jam-quad": svg(malla("M5 6h14v12H5z")),
    "jam-round-rect": svg(malla("M8 6h8a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3V9a3 3 0 0 1 3-3z")),
    "jam-grid": svg(malla("M4 6h16v12H4z", M, False),
                    curva("M9 6v12M14 6v12M4 10h16M4 14h16", M, 1.1)),
    "jam-triangle": svg(malla("M12 5l7 13H5z")),
    "jam-stairs": svg(malla("M4 19h5v-4h5v-4h6V6", M, False),
                      curva("M4 19h5v-4h5v-4h6", M, 1.8)),
    "jam-stairs-curved": svg(curva("M4 19h4l1-4 4-1 1-4 4-1 1-4", M, 1.8),
                             curva("M4 19a15 15 0 0 1 15-15", TINTA, 1.0)),

    # ── curvas: la línea y lo que se le hace ──────────────────────────────────────
    "jam-curve": svg(curva(ARCO), punto(3, 17, S), punto(15, 6, S)),
    "jam-curve-child": svg(curva(ARCO), curva("M9 12c2 3 5 2 7 4", S, 1.4),
                           punto(16, 16, S, 1.4)),
    # El desvío se lee CONTRA el trazo ideal: sin la recta gris, una curva ondulada es sólo otra curva.
    "jam-curve-noise": svg(curva("M12 20V4", "#DDDDE2", 1.5),
                           curva("M12 20c-4-3 4-5 1-8s3-4 0-8", S, 1.8)),
    "jam-curve-branches": svg(curva("M12 20V5", S),
                              curva("M12 15l5-3M12 11l-5-3M12 8l4-3", S, 1.3)),
    "jam-revolve": svg(curva("M14 5c-3 3-3 11 0 14", S, 1.6),
                       f'<ellipse cx="9" cy="12" rx="5" ry="8" stroke="{M}" stroke-width="1.5" '
                       f'fill="{M}" fill-opacity="0.25"/>',
                       curva("M9 3v18", TINTA, 1.0)),

    # ── frames: el ángulo de ejes es la firma ────────────────────────────────────
    "jam-curve-frames": svg(curva(ARCO), frame(6, 15), frame(10, 12), frame(14, 8)),
    "jam-distribute-frames": svg(frame(5, 17), frame(10, 17), frame(15, 17),
                                 curva("M3 20h18", TINTA, 1.0)),
    "jam-transform-frames": svg(frame(6, 17), frame(14, 12),
                                flecha(9, 15, 13, 15)),
    "jam-branch-from-frames": svg(frame(5, 18), curva("M5 18c3 0 5-4 9-6", S, 1.6),
                                  punto(14, 12, S, 1.5)),
    "jam-points-to-frames": svg(punto(5, 17), punto(5, 12), punto(5, 7),
                                flecha(8, 12, 12, 12), frame(16, 16), frame(16, 10)),

    # ── malla desde otra cosa ────────────────────────────────────────────────────
    "jam-pipe": svg(curva(ARCO, TINTA, 1.0),
                    malla("M3 19c4-1 6-9 12-11l1.6 3C11 13 9 20 4 21z")),
    "jam-pipe-profile": svg(curva(ARCO, TINTA, 1.0),
                            malla("M3 19c4-1 6-9 12-11l1-2.4C10 8 8 18 3.6 21z"),
                            barra(20, 18, 8), barra(22, 18, 4)),
    "jam-mesh-from-asset": svg(caja(4, 8, 7, 7), flecha(12, 12, 15, 12),
                               malla("M17 8h5v8h-5z")),
    "jam-along-curve": svg(curva(ARCO, TINTA, 1.0),
                           malla("M4 16h3v3H4z"), malla("M9 12h3v3H9z"), malla("M14 7h3v3h-3z")),
    "jam-copy-to-frames": svg(frame(5, 18), frame(11, 15), frame(17, 11),
                              malla("M3 15h3v3H3z"), malla("M9 12h3v3H9z"), malla("M15 8h3v3h-3z")),
    "jam-copy-variants": svg(frame(5, 18), frame(12, 14),
                             malla("M3 15h3v3H3z"), caja(10, 10, 4, 4, AF)),
    "jam-leaf": svg(curva("M12 20V6", S, 1.6),
                    malla("M12 14c-4 0-6-2-7-5 4 0 6 2 7 5z"),
                    malla("M12 10c4 0 6-2 7-5-4 0-6 2-7 5z")),

    # ── operadores sobre malla ───────────────────────────────────────────────────
    "jam-mesh-transform": svg(malla("M4 12h6v6H4z", M, False), malla("M12 6h8v8h-8z"),
                              flecha(10, 12, 13, 12)),
    # El gradiente en bandas, no con <linearGradient>: nanosvg lo ignoraría o lo rendería distinto,
    # y a 24 px cuatro bandas se leen igual de bien.
    "jam-mesh-vertex-gradient": svg(
        malla("M6 4h12v16H6z", M, False),
        *[f'<rect x="6.8" y="{y}" width="10.4" height="3.6" fill="{M}" '
          f'fill-opacity="{o}" stroke="none"/>'
          for y, o in ((4.8, 0.95), (8.6, 0.65), (12.4, 0.35), (16.2, 0.12))]),
    "jam-mesh-color": svg(malla("M5 7h14v10H5z"),
                          f'<rect x="5" y="7" width="4.6" height="10" fill="{F}" stroke="none"/>'
                          f'<rect x="9.6" y="7" width="4.6" height="10" fill="{SERIE}" stroke="none"/>'),
    # Viento sobre un pivote: la rama doblada, la recta gris de dónde estaba, y el punto fijo
    # abajo. Es exactamente lo que hace el material — girar SOBRE ese punto, no trasladar.
    "jam-material-wind": svg(curva("M12 20V6", "#DDDDE2", 1.4),
                             curva("M12 20c0-6 3-8 7-10", S, 1.9),
                             punto(12, 20, TINTA, 2.0),
                             curva("M3 9c2-1.5 4-1.5 6 0", TINTA, 1.2)),
    # ── Shader: armar el grafo de material nodo por nodo ─────────────────────────
    # El tipo MT (grafo de material) se dibuja como lo que es: cajitas cableadas. Cada verbo muestra
    # QUÉ le hace al grafo — agrega una caja, agrega un cable, lo enchufa a la salida, lo hornea.
    "jam-material-node": svg(caja(3, 5, 5, 4, MATERIAL), caja(3, 14, 5, 4, MATERIAL),
                             curva("M8 7h4v5M8 16h4v-5", TINTA, 1.3),
                             caja(15, 9.5, 6, 5, MATERIAL),
                             punto(19.5, 5.5, ASSET, 2.4),
                             curva("M18.2 5.5h2.6M19.5 4.2v2.6", "#DDDDE2", 1.3)),
    "jam-material-connect": svg(caja(2.5, 5, 5, 4, MATERIAL), caja(16.5, 14, 5, 4, MATERIAL),
                                curva("M7.5 7c7 0 4 9 9 9", ASSET, 1.9),
                                punto(7.5, 7, ASSET, 1.5), punto(16.5, 16, ASSET, 1.5)),
    # `output` es un ENCHUFE (el pin de la salida del material, hueco); `build` es la BOLA de
    # material ya horneada, llena y con su brillo. Con los dos como anillo se veían iguales.
    "jam-material-output": svg(caja(2.5, 9.5, 5, 5, MATERIAL),
                               curva("M7.5 12h7", TINTA, 1.4),
                               f'<circle cx="18.5" cy="12" r="4.2" stroke="{ASSET}" '
                               f'stroke-width="1.7" fill="none"/>',
                               punto(18.5, 12, ASSET, 1.3)),
    "jam-material-build": svg(caja(2, 3.5, 4, 3.5, MATERIAL), caja(2, 10.5, 4, 3.5, MATERIAL),
                              caja(2, 17, 4, 3.5, MATERIAL),
                              curva("M6 5.5h2.5v13H6M6 12.5h2.5", TINTA, 1.1),
                              f'<circle cx="16" cy="12" r="6" stroke="{ASSET}" '
                              f'stroke-width="1.7" fill="{ASSET}" fill-opacity="0.75"/>',
                              curva("M13.5 9.2a3.5 3.5 0 0 1 3-1.1", "#DDDDE2", 1.3)),
    # ── UVs procedurales: proyectar, desplegar, empaquetar ──────────────────────
    # Los tres dibujan el MISMO cuadrado 0..1 en distinto estado, que es lo que los diferencia:
    # proyectado desde una caja, desplegado en islas sueltas, y empaquetado sin desperdicio.
    "jam-mesh-uv-box": svg(malla("M8 8h10v10H8z", M, False),
                           malla("M4 5h10v10H4z", M),
                           curva("M4 5l4-3h10l-4 3M18 15l-4 3M14 15v3", TINTA, 1.1)),
    "jam-mesh-uv-unwrap": svg(malla("M4 4h16v16H4z", M, False),
                              malla("M6 6h5v6H6z", M), malla("M13 7h5v4h-5z", M),
                              malla("M7 14h9v4H7z", M)),
    "jam-mesh-uv-pack": svg(malla("M4 4h16v16H4z", M, False),
                            malla("M5 5h8v7H5z", M), malla("M14 5h5v7h-5z", M),
                            malla("M5 13h6v6H5z", M), malla("M12 13h7v6h-7z", M)),

    # ── la PALETA de nodos de material: un icono por nodo ───────────────────────
    # Los operadores se dibujan con su SÍMBOLO, que es lo que un artista ya sabe leer. Nada de
    # <text>: nanosvg no lo rasteriza, así que el «×» son dos trazos cruzados y el «÷» una línea
    # con dos puntos. Los demás diagraman su dato, como el resto del vocabulario.
    "jam-mat-const": svg(punto(12, 12, NUM, 4.2)),
    "jam-mat-color": svg(caja(6, 6, 12, 12, MATERIAL)),
    "jam-mat-scalar": svg(punto(12, 12, NUM, 4.2),
                          f'<circle cx="12" cy="12" r="7.5" stroke="{TINTA}" '
                          f'stroke-width="1.3" stroke-dasharray="2.5 2.5" fill="none"/>'),
    "jam-mat-vector": svg(caja(6, 6, 12, 12, MATERIAL),
                          f'<circle cx="12" cy="12" r="9.5" stroke="{TINTA}" '
                          f'stroke-width="1.3" stroke-dasharray="2.5 2.5" fill="none"/>'),

    "jam-mat-add": svg(curva("M12 5v14M5 12h14", TINTA, 2.0)),
    "jam-mat-sub": svg(curva("M5 12h14", TINTA, 2.0)),
    "jam-mat-mul": svg(curva("M7 7l10 10M17 7L7 17", TINTA, 2.0)),
    "jam-mat-div": svg(curva("M5 12h14", TINTA, 2.0), punto(12, 7, TINTA, 1.7),
                       punto(12, 17, TINTA, 1.7)),
    # El lerp es lo único que no es un símbolo: es la BARRA que va de un color al otro.
    "jam-mat-lerp": svg(caja(3, 9, 7, 6, MATERIAL), caja(14, 9, 7, 6, ASSET),
                        curva("M10 12h4", TINTA, 1.4)),
    "jam-mat-power": svg(curva("M4 20c8 0 12-4 12-16", NUM, 2.0),
                         curva("M4 20h16", TINTA, 1.2)),
    "jam-mat-clamp": svg(curva("M4 17h5l6-10h5", NUM, 1.9),
                         curva("M4 20V4M20 20V4", TINTA, 1.2)),
    "jam-mat-oneminus": svg(caja(3, 8, 8, 8, TINTA), caja(13, 8, 8, 8, NUM)),
    "jam-mat-saturate": svg(curva("M3 18h5l8-12h5", NUM, 1.9),
                            curva("M3 18h18M3 6h18", TINTA, 1.0)),

    "jam-mat-texture": svg(malla("M4 6h16v12H4z", M, False),
                           f'<rect x="4" y="6" width="8" height="6" fill="{M}" '
                           f'fill-opacity="0.45" stroke="none"/>',
                           f'<rect x="12" y="12" width="8" height="6" fill="{M}" '
                           f'fill-opacity="0.45" stroke="none"/>'),
    "jam-mat-uv": svg(malla("M5 5h14v14H5z", M, False),
                      curva("M5 19L19 5", M, 1.2), punto(5, 19, P, 1.6), punto(19, 5, P, 1.6)),
    "jam-mat-panner": svg(malla("M4 7h12v10H4z", M, False),
                          curva("M8 12h8", TINTA, 1.3), flecha(12, 12, 20, 12)),
    "jam-mat-noise": svg(curva("M3 15c2-6 4 4 6-2s3 5 5-1 3 4 7-1", TINTA, 1.5),
                         curva("M3 20c2-4 4 2 6-1s3 3 5-1 3 2 7-1", TINTA, 1.1)),

    "jam-mat-append": svg(punto(5, 8, NUM, 2.0), punto(5, 16, NUM, 2.0),
                          curva("M8 8h4v8h-4", TINTA, 1.3),
                          caja(14, 8, 6, 8, MATERIAL)),
    "jam-mat-mask": svg(caja(3, 8, 4, 8, MATERIAL), caja(9, 8, 4, 8, TINTA),
                        caja(15, 8, 4, 8, TINTA)),
    "jam-mat-normalize": svg(flecha(4, 18, 18, 18, S),
                             curva("M4 18L14 8", S, 1.9), punto(14, 8, S, 1.7),
                             f'<circle cx="4" cy="18" r="11" stroke="{TINTA}" '
                             f'stroke-width="1.0" fill="none"/>'),
    "jam-mat-dot": svg(curva("M4 18L16 8", S, 1.7), curva("M4 18L18 15", S, 1.7),
                       punto(4, 18, TINTA, 1.6)),

    "jam-mat-worldpos": svg(f'<circle cx="12" cy="12" r="8" stroke="{TINTA}" stroke-width="1.3"/>',
                            curva("M4 12h16M12 4c3 4 3 12 0 16", TINTA, 1.0),
                            punto(15, 8, P, 2.0)),
    "jam-mat-vnormal": svg(suelo("M3 18h18"), curva("M12 18V6", F, 1.9),
                           curva("M9 9l3-3 3 3", F, 1.6)),
    "jam-mat-vcolor": svg(malla("M5 7h14v10H5z", M, False),
                          punto(9, 11, P, 2.2), punto(15, 11, ASSET, 2.2),
                          punto(12, 15, NUM, 2.2)),
    "jam-mat-time": svg(f'<circle cx="12" cy="12" r="8" stroke="{TINTA}" stroke-width="1.5"/>',
                        curva("M12 7v5l4 2", NUM, 1.7)),
    "jam-mat-fresnel": svg(f'<circle cx="12" cy="12" r="8" stroke="{TINTA}" stroke-width="1.2"/>',
                           f'<circle cx="12" cy="12" r="8" stroke="{NUM}" stroke-width="2.6" '
                           f'fill="none" stroke-dasharray="4 6.3"/>',
                           punto(12, 12, TINTA, 3.0)),

    # Reusar: una FUNCIÓN es un grafo que se empaqueta y se vuelve un nodo con nombre; la LLAMADA
    # es esa caja usada desde otro grafo, con sus pines descubiertos.
    "jam-material-function": svg(caja(2.5, 4, 4, 3.5, MATERIAL), caja(2.5, 10.5, 4, 3.5, MATERIAL),
                                 caja(2.5, 17, 4, 3.5, MATERIAL),
                                 curva("M6.5 5.75h2v13h-2M6.5 12.25h2", TINTA, 1.1),
                                 flecha(11, 12, 14, 12),
                                 caja(15, 7.5, 6.5, 9, ASSET)),
    "jam-material-call": svg(caja(7.5, 6.5, 9, 11, ASSET),
                             punto(7.5, 9.5, MATERIAL, 1.5), punto(7.5, 14, MATERIAL, 1.5),
                             curva("M3 9.5h4M3 14h4", TINTA, 1.2),
                             punto(16.5, 12, MATERIAL, 1.5), curva("M17 12h4", TINTA, 1.2)),
    # La instancia: el mismo material, con las perillas movidas.
    "jam-material-instance": svg(f'<circle cx="8" cy="12" r="5" stroke="{ASSET}" '
                                 f'stroke-width="1.6" fill="{ASSET}" fill-opacity="0.7"/>',
                                 flecha(14, 12, 16.5, 12),
                                 curva("M19 5v14", TINTA, 1.2),
                                 punto(19, 8, NUM, 1.9), punto(19, 15.5, NUM, 1.9)),
    "jam-mesh-material": svg(malla("M5 7h14v10H5z"),
                             f'<circle cx="12" cy="12" r="3.4" fill="{SERIE}" stroke="none"/>'),
    "jam-mesh-uv": svg(malla("M5 6h14v12H5z", M, False),
                       curva("M5 10h14M5 14h14M10 6v12M14 6v12", M, 1.0),
                       flecha(8, 20, 16, 20)),
    "jam-mesh-normals": svg(curva("M4 17h16", M, 1.8),
                            curva("M7 17V9M7 9l-2 2M7 9l2 2", M, 1.4),
                            curva("M14 17V9M14 9l-2 2M14 9l2 2", M, 1.4)),
    "jam-mesh-merge": svg(malla("M4 7h8v8H4z"), malla("M11 10h9v8h-9z")),
    "jam-mesh-bark": svg(malla("M7 4h10v16H7z", M, False),
                         curva("M11 4c-1.2 4 1 6 0 8s1 4 0 8M15 4c1.2 4-1 6 0 8s-1 4 0 8", M, 1.3)),
    "jam-mesh-to-static": svg(malla("M6 4h12v7H6z"), curva("M12 11v5M9 14l3 3 3-3", TINTA, 1.5),
                              caja(6, 17, 12, 3, ASSET)),
    "jam-mesh-compare": svg(malla("M4 6h7v12H4z"), malla("M13 8h7v10h-7z", M, False),
                            curva("M12 4v16", TINTA, 1.0)),

    # ── assets y variantes ───────────────────────────────────────────────────────
    "jam-asset-set": svg(caja(3, 8, 6, 8), caja(9.5, 8, 6, 8), caja(16, 8, 5, 8)),
    "jam-choose-asset": svg(caja(3, 5, 6, 6), caja(3, 13, 6, 6),
                            flecha(10, 12, 14, 12), caja(15, 9, 6, 6, AF)),
    "jam-hism": svg(caja(3, 13, 5, 6, H), caja(9.5, 10, 5, 9, H), caja(16, 6, 5, 13, H)),

    # ── serie escalar ────────────────────────────────────────────────────────────
    "jam-graph-curve": svg(curva("M4 18c5 0 6-10 16-12", SERIE, 1.8),
                           barra(7, 18, 4), barra(11, 18, 7), barra(15, 18, 9)),

    # ── Content: el asset ────────────────────────────────────────────────────────
    "jam-asset": svg(caja(6, 6, 12, 12)),
    "jam-pick": svg(caja(4, 5, 11, 11),
                    curva("M14 13l6 6M14 13v5M14 13h5", TINTA, 1.5)),

    # ── Place: una pieza y la superficie donde va ────────────────────────────────
    "jam-place": svg(suelo(), caja(8, 10, 8, 8)),
    "jam-drop": svg(suelo(), caja(8, 4, 8, 6),
                    curva("M12 11v4M9.5 13.5 12 16l2.5-2.5", TINTA, 1.5)),
    "jam-snap": svg(suelo(), caja(3, 11, 7, 7), caja(10, 11, 7, 7),
                    curva("M10 8v12", TINTA, 1.2)),

    # ── Scatter: muchas piezas repartidas ────────────────────────────────────────
    "jam-scatter": svg(suelo(), caja(3, 13, 4, 5), caja(9, 12, 4, 6), caja(16, 14, 4, 4)),
    "jam-spline-tool": svg(curva("M3 17c5-1 7-8 18-10", S, 1.6),
                           caja(3, 14, 4, 4), caja(10, 10, 4, 4), caja(17, 5, 4, 4)),
    "jam-pcg": svg(suelo(),
                   *[caja(x, y, 3, 3) for x in (4, 9, 14) for y in (7, 12)]),

    # ── Create ───────────────────────────────────────────────────────────────────
    "jam-create-spline": svg(curva("M3 18c5 0 6-11 18-13"),
                             punto(3, 18, S), punto(11, 11, S, 1.4), punto(21, 5, S)),
    "jam-fracture": svg(malla("M11 3l-8 5.5 3 4 5-3z"),
                        malla("M13.5 3.5l7.5 5.5-2 4.5-5.5-3.5z"),
                        malla("M6.5 14.5l4.5-2.5 1 8-4-2.5z"),
                        malla("M13.5 12.5l5 1.5-1.5 4-3.5 3z")),
    "jam-nanite": svg(malla("M12 4l8 5v6l-8 5-8-5V9z", M, False),
                      curva("M4 9l8 5 8-5M12 4v16M4 15l8-6 8 6M8 6.5v11M16 6.5v11", M, 0.9)),
    "jam-replace": svg(caja(2, 8, 7, 8, "#DDDDE2"), flecha(10, 12, 14, 12), caja(15, 8, 7, 8)),

    # ── Edit ─────────────────────────────────────────────────────────────────────
    "jam-ghost": svg(f'<rect x="6" y="6" width="12" height="12" rx="1" stroke="{ASSET}" '
                     f'stroke-width="1.6" stroke-dasharray="3 2" fill="none"/>'),
    "jam-gizmo": svg(curva("M12 20V8", "#DD6F81", 1.8), curva("M12 20h9", TINTA, 1.8),
                     curva("M12 20 5 23", P, 1.8), punto(12, 20, TINTA, 1.6)),
    "jam-pivot": svg(caja(6, 6, 12, 12), punto(12, 12, TINTA, 2.2)),
    "jam-pivot-set": svg(caja(6, 5, 12, 12), punto(12, 11, "#DDDDE2", 2.0),
                         punto(12, 20, TINTA, 2.2), curva("M12 14v4", TINTA, 1.3)),
    "jam-normalize": svg(caja(6, 4, 12, 12), punto(12, 10, "#DDDDE2", 1.8),
                         curva("M12 12v6M9.5 16 12 18.5 14.5 16", TINTA, 1.4),
                         suelo("M4 20h16")),

    # ── Vector: el generador dibuja su propia disposición ────────────────────────
    "jam-pts-line": svg(fila((4, 8, 12, 16, 20), 12)),
    "jam-pts-circle": svg(*[punto(12 + 7.5 * __import__("math").cos(a * 3.14159 / 4),
                                  12 + 7.5 * __import__("math").sin(a * 3.14159 / 4))
                            for a in range(8)]),
    "jam-pts-rect": svg(*[punto(x, y) for x in (5, 12, 19) for y in (5, 12, 19)]),
    "jam-pts-arc": svg(curva("M4 19a11 11 0 0 1 16-10", TINTA, 1.0),
                       punto(4, 19), punto(7, 12.5), punto(13, 8.5), punto(20, 9)),

    # ── Mask: filtran; el descartado queda HUECO ─────────────────────────────────
    "jam-mask-slope": svg(suelo("M2 19 22 7"), punto(6, 16), punto(11, 13),
                          apagado(16, 10), apagado(20, 8)),
    "jam-mask-height": svg(curva("M2 12h20", TINTA, 1.2),
                           punto(6, 7), punto(12, 6), punto(18, 8),
                           apagado(7, 17), apagado(14, 18)),
    "jam-mask-noise": svg(punto(5, 8), apagado(11, 6), punto(17, 9),
                          apagado(6, 15), punto(13, 17), apagado(19, 15)),
    "jam-mask-density": svg(punto(5, 8), punto(9, 7), punto(6, 13),
                            apagado(7, 10), apagado(8, 11),
                            punto(16, 9), punto(19, 15), punto(15, 17)),

    # ── Weight: el peso se dibuja como TAMAÑO, igual que en el debug ─────────────
    "jam-weight-slope": svg(suelo("M2 19 22 7"), pesado(6, 16, 1.0), pesado(11, 13, 0.6),
                            pesado(16, 10, 0.3), pesado(20, 8, 0.1)),
    "jam-weight-height": svg(pesado(6, 18, 0.1), pesado(11, 14, 0.4),
                             pesado(16, 10, 0.7), pesado(20, 6, 1.0)),
    "jam-weight-noise": svg(pesado(5, 9, 0.8), pesado(11, 7, 0.2), pesado(17, 10, 0.9),
                            pesado(7, 16, 0.3), pesado(14, 18, 0.7)),
    "jam-weight-radial": svg(f'<circle cx="12" cy="12" r="8.5" stroke="{TINTA}" '
                             f'stroke-width="1.0" fill="none"/>',
                             pesado(12, 12, 1.0), pesado(6, 12, 0.5), pesado(18, 12, 0.5),
                             pesado(12, 5, 0.2), pesado(12, 19, 0.2)),
    "jam-weight-curve": svg(curva("M3 19c6 0 8-12 18-14", SERIE, 1.6),
                            pesado(5, 17, 0.2), pesado(11, 12, 0.6), pesado(18, 7, 1.0)),
    "jam-weight-invert": svg(pesado(6, 8, 1.0), pesado(6, 17, 0.2),
                             flecha(10, 12, 14, 12),
                             pesado(19, 8, 0.2), pesado(19, 17, 1.0)),
    "jam-weight-power": svg(curva("M4 19 20 5", "#DDDDE2", 1.5),
                            curva("M4 19c10 0 12-3 16-14", SERIE, 1.8),
                            pesado(4, 19, 0.1), pesado(20, 5, 1.0)),
    "jam-weight-combine": svg(pesado(4, 7, 0.7), pesado(4, 17, 0.4),
                              curva("M7 7c4 0 4 5 7 5M7 17c4 0 4-5 7-5", TINTA, 1.2),
                              pesado(17, 12, 1.0)),
    "jam-weight-cull": svg(pesado(5, 12, 1.0), pesado(10, 12, 0.7),
                           apagado(15, 12, P, 1.2), apagado(20, 12, P, 1.0),
                           curva("M13 6v12", TINTA, 1.2)),

    # ── Sets: operaciones sobre la LISTA ─────────────────────────────────────────
    "jam-cull-nth": svg(punto(4, 12), apagado(9, 12), punto(14, 12), apagado(19, 12)),
    "jam-relax": svg(punto(9, 12), punto(15, 12),
                     curva("M7 12H3M17 12h4", TINTA, 1.3),
                     curva("M4 10l-1 2 1 2M20 10l1 2-1 2", TINTA, 1.3)),
    "jam-reverse": svg(fila((4, 9, 14, 19), 8),
                       curva("M20 15H5M8 12l-3 3 3 3", TINTA, 1.4)),
    "jam-shift": svg(fila((5, 10, 15, 20), 10),
                     curva("M20 14c0 4-15 4-15 0M5 14v-1", TINTA, 1.3),
                     curva("M2.5 12.5 5 10l2.5 2.5", TINTA, 1.3)),
    "jam-sub-list": svg(apagado(4, 12), punto(9, 12), punto(14, 12), apagado(19, 12),
                        curva("M7 6v12M16 6v12", TINTA, 1.2)),

    # ── Transform ────────────────────────────────────────────────────────────────
    "jam-move": svg(fila((4, 8), 15, "#DDDDE2"), fila((14, 18), 9),
                    flecha(9, 12, 13, 12)),
    "jam-jitter": svg(punto(5, 11), punto(11, 14), punto(17, 10),
                      curva("M5 11l1.5-2M11 14l-2-1.5M17 10l1.5 2", TINTA, 1.2)),
    "jam-rotate-pts": svg(curva("M12 4a8 8 0 1 1-7 4", TINTA, 1.3),
                          curva("M4 5v4h4", TINTA, 1.3),
                          punto(12, 4), punto(19, 12), punto(12, 20)),
    "jam-scale-pts": svg(punto(12, 12, P, 1.4),
                         punto(5, 5), punto(19, 5), punto(5, 19), punto(19, 19),
                         curva("M9 9 6 6M15 9l3-3M9 15l-3 3M15 15l3 3", TINTA, 1.1)),

    # ── Combine ──────────────────────────────────────────────────────────────────
    "jam-merge-pts": svg(fila((4, 8), 6), fila((4, 8), 18),
                         curva("M11 6c4 0 4 6 7 6M11 18c4 0 4-6 7-6", TINTA, 1.3),
                         punto(20, 12)),
    "jam-weave": svg(punto(4, 7), punto(4, 17),
                     curva("M7 7c5 0 5 10 10 10M7 17c5 0 5-10 10-10", TINTA, 1.3),
                     punto(19, 17), punto(19, 7)),

    # ── Display / Params / Maths ─────────────────────────────────────────────────
    "jam-info": svg(fila((4, 8, 12), 17), barra(17, 19, 5), barra(20, 19, 9)),
    "jam-number": svg(curva("M3 12h18", TINTA, 1.4),
                      f'<rect x="12" y="8" width="4" height="8" rx="1" fill="{NUM}" stroke="none"/>'),
    "jam-text": svg(curva("M5 7h14M12 7v11", TEXTO, 2.0)),
    "jam-math": svg(curva("M4 8h7M7.5 4.5v7", NUM, 2.0),
                    curva("M14 14l6 6M20 14l-6 6", NUM, 2.0)),

    # ── Source / Output ──────────────────────────────────────────────────────────
    "jam-source-surface": svg(suelo("M2 17c5-6 9 2 20-5", TINTA, 1.6),
                              punto(5, 14), punto(10, 14.5), punto(15, 11), punto(20, 8)),
    "jam-instance": svg(punto(4, 17, P, 1.4), punto(11, 17, P, 1.4), punto(18, 17, P, 1.4),
                        caja(2.5, 10, 4, 4), caja(9.5, 10, 4, 4), caja(16.5, 10, 4, 4)),
    # El gemelo de `instance`: los mismos pesos, pero abajo no CAEN objetos — se PINTA el suelo, y
    # la pintura mengua con el peso. Por eso es una banda continua pegada al suelo y no tres cajas:
    # con cajas se leía igual que `instance`, que es justo lo que este verbo no hace.
    "jam-weight-material": svg(pesado(5, 6, 1.0), pesado(12, 6, 0.55), pesado(19, 6, 0.15),
                               malla("M3 19V11.5h6V14.5h5V17h6V19z", ASSET),
                               suelo("M2 19h20")),

    # ── debug ───────────────────────────────────────────────────────────────────
    "jam-debug": svg(f'<circle cx="12" cy="12" r="7" stroke="{TINTA}" stroke-width="1.4"/>',
                     frame(12, 14, F, 4), punto(12, 12, P, 1.4)),

    # ── tab Aprender: los ejemplos ──────────────────────────────────────────────
    # Un ejemplo no es un verbo, así que su icono no puede diagramar una firma. Lo que dibuja es el
    # RESULTADO — lo que vas a ver en pantalla al correrlo —, que es lo que hace elegir cuál abrir.
    "jam-ej-primeros-pasos": svg(malla("M7 10l5-3 5 3v6l-5 3-5-3z"),
                                 curva("M7 10l5 3 5-3M12 13v6", M, 1.1),
                                 flecha(2, 12, 5.5, 12),
                                 punto(20.5, 12, ASSET, 1.6)),
    "jam-ej-pino": svg(malla("M12 3l4 6h-8zM12 8l5 7H7zM12 13l6 7H6z"),
                       curva("M12 20v2", TINTA, 1.4)),
    "jam-ej-ramificado": svg(curva("M12 21V7", S, 1.9),
                             curva("M12 14l5-4M12 11l-4-3M12 17l-5-2", S, 1.4),
                             punto(17, 10, S, 1.3), punto(8, 8, S, 1.3), punto(7, 15, S, 1.3)),
    "jam-ej-frames": svg(curva("M4 20c3-8 9-12 16-14", S, 1.5),
                         frame(6, 17, F, 3.6), frame(11, 12, F, 3.6), frame(17, 8, F, 3.6)),
    "jam-ej-dos-niveles": svg(curva("M12 21V9", S, 1.9),
                              curva("M12 15l4-3M12 12l-4-2", S, 1.4),
                              fila((16, 8, 12), 6, H, 1.9),
                              punto(14, 3.5, H, 1.9), punto(10, 3.5, H, 1.9)),
    # Los dos tutoriales de material: uno arma un shader y lo pone sobre algo; el otro despliega.
    "jam-ej-primer-material": svg(caja(2.5, 5, 5, 4, MATERIAL), caja(2.5, 14, 5, 4, MATERIAL),
                                  curva("M7.5 7h2v9h-2M7.5 11.5h2", TINTA, 1.1),
                                  flecha(11, 11.5, 13.5, 11.5),
                                  f'<circle cx="18" cy="11.5" r="4.6" stroke="{ASSET}" '
                                  f'stroke-width="1.7" fill="{ASSET}" fill-opacity="0.75"/>',
                                  curva("M15.8 9.2a3.2 3.2 0 0 1 2.7-1", "#DDDDE2", 1.2)),
    "jam-ej-uvs": svg(malla("M3 4h8v8H3z", M, False), curva("M3 4l8 8", M, 1.1),
                      flecha(12, 8, 14.5, 8),
                      malla("M16 4h6v4h-6z", M), malla("M16 9h3v4h-3z", M),
                      malla("M20 9h2v4h-2z", M), malla("M16 14h6v3h-6z", M)),
    "jam-ej-debug": svg(punto(5, 6, P, 1.5), frame(5, 13, F, 3.2), curva("M4 20h5", S, 1.5),
                        curva("M13 4v16", TINTA, 1.0),
                        f'<circle cx="18" cy="12" r="4.5" stroke="{TINTA}" stroke-width="1.4"/>',
                        punto(18, 12, P, 1.5)),
}


def main() -> int:
    destino = pathlib.Path(__file__).resolve().parents[1] / "Resources" / "Icons" / "Lucide"
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, contenido in ICONOS.items():
        (destino / f"{nombre}.svg").write_text(contenido, encoding="utf-8")
    print(f"{len(ICONOS)} iconos escritos en {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
