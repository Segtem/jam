"""Previsualización 2D: ver la máscara y el desplegado sin abrir nada. CEREBRO PURO (0 `unreal`).

Lo que falta cuando se trabaja en el canvas de Jam no es un visor 3D —el viewport del editor ya es
eso, y mejor— sino un lugar donde MIRAR las dos cosas que no tienen dónde verse:

* una **máscara**: un campo escalar 0..1. Hoy la única forma de saber cómo quedó es correr el
  scatter y contar piedras, o compilar el material y girar la cámara.
* un **desplegado de UVs**: las islas en el cuadrado 0..1. El editor de UVs de UE existe, pero abre
  sobre un StaticMesh ya horneado — o sea, después de decidir.

Jam puede hacer la primera mejor que nadie porque `shader.evaluar` corre el IR del material en CPU:
la imagen sale del MISMO grafo que se va a compilar, sin GPU y sin crear un asset.

La salida es un PNG, escrito con `zlib` de la biblioteca estándar. Es a propósito: un formato que
cualquier cosa abre, generado sin dependencias, desde código puro que se puede probar sin editor.
"""

from __future__ import annotations

import struct
import zlib

# Rampa de grises → color, para que una máscara se lea de un vistazo. Es la misma idea que un mapa
# de calor: el ojo distingue mucho peor el 0.6 del 0.7 en gris que en color.
#
# Los extremos son los que importan: NEGRO donde la máscara vale 0 y BLANCO donde vale 1, con el
# medio en tonos fríos→cálidos. Así «dónde no llega» y «dónde satura» se ven sin mirar la leyenda.
RAMPA = (
    (0.00, (12, 14, 18)),
    (0.25, (34, 68, 108)),
    (0.50, (58, 124, 122)),
    (0.75, (196, 156, 78)),
    (1.00, (245, 245, 240)),
)


def color_de(valor: float, rampa=RAMPA) -> tuple[int, int, int]:
    """Interpola la rampa. Fuera de 0..1 se recorta, y eso ES informativo: una máscara que se pasa
    se ve saturada de blanco o de negro, que es exactamente lo que hay que notar."""
    v = 0.0 if valor < 0.0 else (1.0 if valor > 1.0 else float(valor))
    for i in range(len(rampa) - 1):
        t0, c0 = rampa[i]
        t1, c1 = rampa[i + 1]
        if v <= t1:
            k = 0.0 if t1 == t0 else (v - t0) / (t1 - t0)
            return tuple(int(round(c0[j] + (c1[j] - c0[j]) * k)) for j in range(3))
    return rampa[-1][1]


def png(ancho: int, alto: int, pixeles) -> bytes:
    """Codifica un PNG RGB de 8 bits. `pixeles` es una lista de filas de `(r, g, b)`.

    Se escribe a mano con `zlib` (biblioteca estándar) en vez de depender de Pillow: Jam corre
    dentro del Python de Unreal, donde instalar paquetes es una pelea que no vale la pena por un
    formato de cincuenta líneas.
    """
    if ancho <= 0 or alto <= 0:
        raise ValueError("el PNG necesita ancho y alto positivos")
    if len(pixeles) != alto:
        raise ValueError(f"se esperaban {alto} filas y llegaron {len(pixeles)}")

    crudo = bytearray()
    for fila in pixeles:
        if len(fila) != ancho:
            raise ValueError(f"una fila tiene {len(fila)} píxeles y el ancho es {ancho}")
        crudo.append(0)                      # filtro «None» por fila, que es lo que exige el formato
        for r, g, b in fila:
            crudo += bytes((r & 255, g & 255, b & 255))

    def trozo(tipo: bytes, datos: bytes) -> bytes:
        return (struct.pack(">I", len(datos)) + tipo + datos
                + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF))

    cabecera = struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0)   # 8 bits, color RGB
    return (b"\x89PNG\r\n\x1a\n"
            + trozo(b"IHDR", cabecera)
            + trozo(b"IDAT", zlib.compress(bytes(crudo), 6))
            + trozo(b"IEND", b""))


def campo(evaluar, ancho: int = 256, alto: int = 256, *,
          desde=(0.0, 0.0), hasta=(1.0, 1.0), rampa=RAMPA) -> list:
    """Muestrea `evaluar(x, y)` en una grilla y devuelve los píxeles.

    La fila 0 del PNG es la de ARRIBA, y en un mapa la Y crece hacia arriba: se invierte al recorrer
    para que la imagen salga con la misma orientación que el mundo y no espejada. Es el tipo de
    detalle que no rompe nada y hace que todo se lea al revés.
    """
    ancho, alto = int(ancho), int(alto)
    x0, y0 = float(desde[0]), float(desde[1])
    x1, y1 = float(hasta[0]), float(hasta[1])
    filas = []
    for j in range(alto):
        v = (alto - 1 - j) / max(1, alto - 1)
        y = y0 + (y1 - y0) * v
        fila = []
        for i in range(ancho):
            u = i / max(1, ancho - 1)
            fila.append(color_de(evaluar(x0 + (x1 - x0) * u, y), rampa))
        filas.append(fila)
    return filas


def _linea(filas, x0: int, y0: int, x1: int, y1: int, color) -> None:
    """Bresenham. Se dibuja a mano porque el trazo tiene que ser de UN píxel: una isla de UV se
    juzga por dónde está su borde, y un antialias la engorda lo suficiente como para tapar el hueco
    entre dos islas que se tocan."""
    alto, ancho = len(filas), len(filas[0]) if filas else 0
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    error = dx + dy
    while True:
        if 0 <= y0 < alto and 0 <= x0 < ancho:
            filas[y0][x0] = color
        if x0 == x1 and y0 == y1:
            return
        doble = 2 * error
        if doble >= dy:
            error += dy
            x0 += sx
        if doble <= dx:
            error += dx
            y0 += sy


def islas_uv(triangulos, ancho: int = 512, alto: int = 512, *,
             fondo=(18, 20, 24), reja=(38, 42, 48), borde=(80, 200, 206),
             afuera=(216, 92, 92), cuadros: int = 8) -> list:
    """Dibuja el desplegado: el cuadrado 0..1, una reja de referencia y el contorno de cada triángulo.

    `triangulos` es una lista de tres pares `(u, v)`. Lo que hay que poder ver de un vistazo son dos
    cosas, y por eso están marcadas distinto: la **reja** da la escala (con ella se juzga si el
    tamaño de las islas es parejo, que es la densidad de texel) y lo que cae **fuera del 0..1** se
    dibuja en rojo, porque ahí la textura se repite y el desplegado no sirve para atlas ni horneado.
    """
    ancho, alto = int(ancho), int(alto)
    filas = [[fondo for _ in range(ancho)] for _ in range(alto)]

    for k in range(1, max(1, int(cuadros))):
        p = int(round(k * (ancho - 1) / cuadros))
        q = int(round(k * (alto - 1) / cuadros))
        for j in range(alto):
            filas[j][p] = reja
        for i in range(ancho):
            filas[q][i] = reja

    def a_pixel(uv):
        u, v = float(uv[0]), float(uv[1])
        return (int(round(u * (ancho - 1))), int(round((1.0 - v) * (alto - 1))))

    for tri in triangulos:
        fuera = any(not (0.0 <= float(c) <= 1.0) for uv in tri for c in uv)
        color = afuera if fuera else borde
        puntos = [a_pixel(uv) for uv in tri]
        for i in range(3):
            (x0, y0), (x1, y1) = puntos[i], puntos[(i + 1) % 3]
            _linea(filas, x0, y0, x1, y1, color)
    return filas


def mascara_de_grafo(grafo, nodo: str, evaluar, *, ancho: int = 256, alto: int = 256,
                     extension: float = 1000.0, z: float = 0.0) -> list:
    """Renderiza un nodo de un `GrafoMaterial` como imagen, evaluando el IR en CPU.

    Es lo que ninguna otra herramienta puede dar: la imagen sale del MISMO grafo que se va a
    compilar, sin GPU, sin crear un asset y antes de decidir nada. `evaluar` se recibe por parámetro
    —en vez de importar `jam.shader`— para que este módulo no sepa nada de materiales y sirva igual
    para cualquier campo escalar.

    El plano se muestrea en XY alrededor del origen, que es donde vive una máscara de terreno.
    """
    mitad = float(extension) * 0.5

    def punto(x, y):
        valores = evaluar(grafo, {"posicion": (x, y, float(z)), "normal": (0.0, 0.0, 1.0)})
        salida = valores.get(nodo)
        return salida[0] if salida else 0.0

    return campo(punto, ancho, alto, desde=(-mitad, -mitad), hasta=(mitad, mitad))


# ---------------------------------------------------------------------------------------------
# Qué se puede previsualizar de cada tipo de dato
# ---------------------------------------------------------------------------------------------
#
# El criterio: sólo tiene sentido dibujar en 2D lo que NO se puede ver en el viewport. Una malla
# colocada ya se ve; su desplegado de UVs no. Un material aplicado ya se ve; la máscara que lo
# decide, no. Por eso la lista es corta a propósito.

QUE_SE_VE = {
    "M": "el desplegado de UVs de la malla",
    "MT": "la máscara que calcula el grafo de material",
}


def texto_de_ayuda(tipo: str) -> str:
    """Qué se va a dibujar, o por qué no hay nada que dibujar.

    Decir «este tipo no se previsualiza en 2D porque ya lo ves en el viewport» es información; un
    panel en blanco es un bug aparente.
    """
    if tipo in QUE_SE_VE:
        return QUE_SE_VE[tipo]
    return (f"«{tipo}» no se dibuja en 2D: lo que produce ya se ve en el viewport. "
            f"Acá sólo van {', '.join(QUE_SE_VE.values())}.")
