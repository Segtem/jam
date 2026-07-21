"""Oráculo geométrico sobre el .obj cocinado: mide la MALLA, no lo que el generador dice de ella.

Tres preguntas que un manifest de conteos no puede responder:

  1. ¿Las puertas están realmente ABIERTAS? Se dispara un rayo por el eje de cada vano y se cuentan
     los choques contra caras del grupo `wall`. Un vano abierto da 0. Un muro macizo da 2 (entra y sale).
     Este es el chequeo que delata la geometría que HOY emite Houdini: cajas de muro enteras con un
     marco de puerta apoyado encima, sin hueco. El edificio se ve bien y no se puede caminar.

  2. ¿Hay UVs y sirven? Que existan `vt` no alcanza: un UV degenerado (área cero) hace que la textura
     de Substance colapse a un píxel. Se mide el área en UV de cada cara y la DENSIDAD DE TÉXEL
     (área_uv / área_mundo): si varía demasiado entre caras, el hormigón sale estirado en unas y
     comprimido en otras.

  3. ¿La envolvente sigue siendo la del IR? Espejo del chequeo que ya hace `unreal_space`.

Es deliberadamente independiente de Houdini y de Unreal: parsea el `.obj` con Python puro. Si mañana
la geometría la cocina otra herramienta, el oráculo no cambia. Esa es la constante del proyecto.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

# Un rayo que pasa exactamente por un vértice o una arista es ambiguo. Se dispara a la altura del
# picaporte y se toleran los roces con este epsilon.
EPS = 1e-9
ALTURA_RAYO_M = 1.0          # picaporte: bien dentro del vano (DOOR_HEIGHT = 2.1)
MARGEN_VANO_M = 0.15         # se ignora el borde del vano: ahí vive el marco, y es legítimo
ALCANCE_RAYO_M = 0.6         # medio tramo del rayo: cubre el espesor del muro, no el edificio entero

# Banda de densidad de téxel aceptable, como razón contra la mediana.
TEXEL_LO, TEXEL_HI = 0.25, 4.0


@dataclass
class ObjMesh:
    """Malla parseada de un .obj. `faces` guarda índices 0-based a `vertices` y `uvs`."""
    vertices: list[tuple[float, float, float]] = field(default_factory=list)
    uvs: list[tuple[float, float]] = field(default_factory=list)
    faces: list[list[int]] = field(default_factory=list)
    face_uvs: list[list[int]] = field(default_factory=list)
    face_groups: list[str] = field(default_factory=list)

    def faces_of(self, group: str) -> list[list[int]]:
        return [f for f, g in zip(self.faces, self.face_groups) if g == group]

    def bbox(self) -> tuple[float, float, float, float, float, float] | None:
        if not self.vertices:
            return None
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        zs = [v[2] for v in self.vertices]
        return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def parse_obj(path: str | Path) -> ObjMesh:
    """Parseo mínimo de .obj: `v`, `vt`, `g`/`usemtl` y `f` (con o sin índices de uv/normal)."""
    mesh = ObjMesh()
    grupo = "default"
    for linea in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        if not linea or linea[0] == "#":
            continue
        campos = linea.split()
        head = campos[0]
        if head == "v" and len(campos) >= 4:
            mesh.vertices.append((float(campos[1]), float(campos[2]), float(campos[3])))
        elif head == "vt" and len(campos) >= 3:
            mesh.uvs.append((float(campos[1]), float(campos[2])))
        elif head in ("g", "o", "usemtl") and len(campos) >= 2:
            grupo = campos[1]
        elif head == "f" and len(campos) >= 4:
            vids: list[int] = []
            tids: list[int] = []
            for tok in campos[1:]:
                partes = tok.split("/")
                vids.append(_idx(partes[0], len(mesh.vertices)))
                if len(partes) > 1 and partes[1]:
                    tids.append(_idx(partes[1], len(mesh.uvs)))
            mesh.faces.append(vids)
            mesh.face_uvs.append(tids)
            mesh.face_groups.append(grupo)
    return mesh


def _idx(token: str, total: int) -> int:
    """Los índices de .obj son 1-based, y los negativos cuentan desde el final."""
    i = int(token)
    return i - 1 if i > 0 else total + i


# ── rayos ────────────────────────────────────────────────────────────────────────────────────────

def _triangulos(face: list[int], verts: list[tuple[float, float, float]]):
    """Abanico desde el primer vértice: los quads de Houdini se parten en 2 triángulos."""
    for i in range(1, len(face) - 1):
        yield verts[face[0]], verts[face[i]], verts[face[i + 1]]


def _ray_triangulo(orig, direc, tri, t_max: float = float("inf")) -> bool:
    """Möller–Trumbore. True si el rayo corta el triángulo a distancia `t` con 0 < t <= t_max.

    `t_max` NO es un detalle: sin él el rayo sigue de largo y cuenta los muros del otro extremo del
    edificio. (Ese bug me hizo declarar "18/18 tapiadas" cuando el rayo cruzaba 4 muros en fila.)
    """
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
    e1 = (bx - ax, by - ay, bz - az)
    e2 = (cx - ax, cy - ay, cz - az)
    p = (direc[1] * e2[2] - direc[2] * e2[1],
         direc[2] * e2[0] - direc[0] * e2[2],
         direc[0] * e2[1] - direc[1] * e2[0])
    det = e1[0] * p[0] + e1[1] * p[1] + e1[2] * p[2]
    if abs(det) < EPS:
        return False                                  # rayo paralelo a la cara
    inv = 1.0 / det
    t_vec = (orig[0] - ax, orig[1] - ay, orig[2] - az)
    u = (t_vec[0] * p[0] + t_vec[1] * p[1] + t_vec[2] * p[2]) * inv
    if u < -EPS or u > 1.0 + EPS:
        return False
    q = (t_vec[1] * e1[2] - t_vec[2] * e1[1],
         t_vec[2] * e1[0] - t_vec[0] * e1[2],
         t_vec[0] * e1[1] - t_vec[1] * e1[0])
    v = (direc[0] * q[0] + direc[1] * q[1] + direc[2] * q[2]) * inv
    if v < -EPS or u + v > 1.0 + EPS:
        return False
    t = (e2[0] * q[0] + e2[1] * q[1] + e2[2] * q[2]) * inv
    return EPS < t <= t_max


def contar_choques(mesh: ObjMesh, orig, direc, grupo: str = "wall",
                   t_max: float = float("inf")) -> int:
    """Cuántas caras de `grupo` corta el rayo en (0, t_max]. Muro macizo = 2. Vano abierto = 0.

    `t_max` acota el tramo examinado al espesor del muro: sin eso el rayo atraviesa todo el edificio
    y cuenta muros ajenos al vano.
    """
    return sum(
        1
        for face in mesh.faces_of(grupo)
        for tri in _triangulos(face, mesh.vertices)
        if _ray_triangulo(orig, direc, tri, t_max)
    )


# ── chequeos ─────────────────────────────────────────────────────────────────────────────────────

def check_door_openings(mesh: ObjMesh, ir: dict, *, up_axis: str = "y") -> list[str]:
    """Cada puerta del IR debe ser un vano ATRAVESABLE, no un marco sobre un muro macizo.

    `up_axis` dice cuál eje del .obj es la altura ('y' en Houdini). El rayo se dispara
    perpendicular al muro, a `ALTURA_RAYO_M`, desde afuera hacia adentro.
    """
    razones: list[str] = []
    for i, door in enumerate(ir.get("doors", [])):
        x = float(door.get("x", 0.0))
        y = float(door.get("y", 0.0))
        axis = str(door.get("axis", "x"))
        # El muro corre a lo largo de `axis`; el rayo lo cruza perpendicularmente.
        if axis == "x":
            direc = (0.0, 0.0, 1.0) if up_axis == "y" else (0.0, 1.0, 0.0)
        else:
            direc = (1.0, 0.0, 0.0)
        centro = _punto(x, y, ALTURA_RAYO_M, up_axis)
        # Sólo el tramo que rodea al vano: `ALCANCE_RAYO_M` a cada lado del plano del muro.
        orig = tuple(c - d * ALCANCE_RAYO_M for c, d in zip(centro, direc))
        choques = contar_choques(mesh, orig, direc, t_max=2.0 * ALCANCE_RAYO_M)
        if choques:
            razones.append(
                f"puerta {i} (id={door.get('door_id')}) TAPIADA: el rayo choca {choques} "
                f"cara(s) de 'wall' al atravesar el vano en ({x}, {y})"
            )
    return razones


def _punto(x: float, y: float, altura: float, up_axis: str):
    return (x, altura, y) if up_axis == "y" else (x, y, altura)


def _area_2d(pts) -> float:
    """Área del polígono por la fórmula del cordón (shoelace)."""
    s = 0.0
    for i, (ux, uy) in enumerate(pts):
        vx, vy = pts[(i + 1) % len(pts)]
        s += ux * vy - vx * uy
    return abs(s) * 0.5


def _area_3d(face: list[int], verts) -> float:
    total = 0.0
    for (ax, ay, az), (bx, by, bz), (cx, cy, cz) in _triangulos(face, verts):
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        cxx = uy * vz - uz * vy
        cyy = uz * vx - ux * vz
        czz = ux * vy - uy * vx
        total += 0.5 * math.sqrt(cxx * cxx + cyy * cyy + czz * czz)
    return total


def check_uvs(mesh: ObjMesh, *, grupos=("wall", "floor", "ceiling")) -> list[str]:
    """UVs presentes, no degeneradas, y con densidad de téxel consistente.

    Que existan `vt` no alcanza: un UV de área cero colapsa la textura a un píxel, y una densidad
    dispar hace que el hormigón salga estirado en unas caras y comprimido en otras.
    """
    razones: list[str] = []
    if not mesh.uvs:
        return ["sin UVs: el .obj no declara ni un `vt` (la textura de Substance no se puede aplicar)"]

    densidades: list[float] = []
    degeneradas = 0
    sin_uv = 0
    for face, tids, grupo in zip(mesh.faces, mesh.face_uvs, mesh.face_groups):
        if grupo not in grupos:
            continue
        if len(tids) != len(face):
            sin_uv += 1
            continue
        uv_area = _area_2d([mesh.uvs[t] for t in tids])
        mundo = _area_3d(face, mesh.vertices)
        if uv_area <= EPS:
            degeneradas += 1
            continue
        if mundo > EPS:
            densidades.append(uv_area / mundo)

    if sin_uv:
        razones.append(f"{sin_uv} cara(s) de {grupos} sin índices de UV")
    if degeneradas:
        razones.append(f"{degeneradas} cara(s) con UV degenerada (área cero): la textura colapsa")
    if densidades:
        densidades.sort()
        mediana = densidades[len(densidades) // 2]
        if mediana > EPS:
            fuera = sum(1 for d in densidades if not (TEXEL_LO <= d / mediana <= TEXEL_HI))
            if fuera:
                razones.append(
                    f"{fuera}/{len(densidades)} cara(s) con densidad de téxel fuera de "
                    f"[{TEXEL_LO}, {TEXEL_HI}]× la mediana: la textura sale estirada"
                )
    return razones


def check_bbox(mesh: ObjMesh, ir: dict, *, tol: float = 0.75, up_axis: str = "y") -> list[str]:
    """La envolvente de la malla cocinada contra la que declaran los muros del IR."""
    caja = mesh.bbox()
    if caja is None:
        return ["malla vacía: el .obj no tiene vértices"]
    muros = ir.get("walls") or []
    if not muros:
        return []
    minx = min(min(w[0], w[2]) for w in muros)
    maxx = max(max(w[0], w[2]) for w in muros)
    miny = min(min(w[1], w[3]) for w in muros)
    maxy = max(max(w[1], w[3]) for w in muros)
    if up_axis == "y":
        got = (caja[0], caja[2], caja[3], caja[5])       # x, z (el piso), ignorando la altura
    else:
        got = (caja[0], caja[1], caja[3], caja[4])
    want = (minx, miny, maxx, maxy)
    if any(abs(g - w) > tol for g, w in zip(got, want)):
        return [f"bbox: malla {[round(v, 2) for v in got]} != ir {[round(v, 2) for v in want]}"]
    return []


def check_geometry(obj_path: str | Path, ir: dict, *, up_axis: str = "y") -> list[str]:
    """Todos los chequeos. Lista vacía = la geometría cocinada honra el IR."""
    mesh = parse_obj(obj_path)
    return (
        check_bbox(mesh, ir, up_axis=up_axis)
        + check_door_openings(mesh, ir, up_axis=up_axis)
        + check_uvs(mesh)
    )
