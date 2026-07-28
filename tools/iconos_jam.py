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
TINTA = "#2A2E33"  # trazo neutro para lo estructural

CABECERA = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"\n'
    '     fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
)


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
    "jam-mesh-color": svg(malla("M5 7h14v10H5z"),
                          f'<rect x="5" y="7" width="4.6" height="10" fill="{F}" stroke="none"/>'
                          f'<rect x="9.6" y="7" width="4.6" height="10" fill="{SERIE}" stroke="none"/>'),
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

    # ── debug ───────────────────────────────────────────────────────────────────
    "jam-debug": svg(f'<circle cx="12" cy="12" r="7" stroke="{TINTA}" stroke-width="1.4"/>',
                     frame(12, 14, F, 4), punto(12, 12, P, 1.4)),
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
