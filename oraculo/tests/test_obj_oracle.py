"""El oráculo geométrico, probado contra mallas sintéticas donde la respuesta se conoce de antemano.

Si el oráculo no distingue un muro macizo de uno con vano, no sirve para juzgar a Houdini.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.foundry.obj_oracle import (check_bbox, check_door_openings, check_geometry,
                                    check_uvs, contar_choques, parse_obj)

# IR con una puerta en el centro de un muro que corre a lo largo de X, en (2, 0).
_IR = {
    "walls": [[0.0, 0.0, 4.0, 0.0, 0]],
    "doors": [{"x": 2.0, "y": 0.0, "z": 0, "axis": "x", "width": 1.0, "door_id": "a"}],
}


def _escribir(tmp_path: Path, texto: str) -> Path:
    p = tmp_path / "geo.obj"
    p.write_text(texto, encoding="utf-8")
    return p


# Un muro MACIZO: caja de 4×0.1×2.7 (Houdini es Y-up), sin vano.
_MURO_MACIZO = """
g wall
v 0.0 0.0 -0.05
v 4.0 0.0 -0.05
v 4.0 2.7 -0.05
v 0.0 2.7 -0.05
v 0.0 0.0 0.05
v 4.0 0.0 0.05
v 4.0 2.7 0.05
v 0.0 2.7 0.05
vt 0.0 0.0
vt 1.0 0.0
vt 1.0 1.0
vt 0.0 1.0
f 1/1 2/2 3/3 4/4
f 5/1 8/4 7/3 6/2
"""

# El MISMO muro, partido en dos jambas: queda un vano libre entre x=1.5 y x=2.5.
_MURO_CON_VANO = """
g wall
v 0.0 0.0 -0.05
v 1.5 0.0 -0.05
v 1.5 2.7 -0.05
v 0.0 2.7 -0.05
v 2.5 0.0 -0.05
v 4.0 0.0 -0.05
v 4.0 2.7 -0.05
v 2.5 2.7 -0.05
vt 0.0 0.0
vt 1.0 0.0
vt 1.0 1.0
vt 0.0 1.0
f 1/1 2/2 3/3 4/4
f 5/1 6/2 7/3 8/4
"""


def test_parse_obj_lee_vertices_uvs_y_grupos(tmp_path: Path) -> None:
    mesh = parse_obj(_escribir(tmp_path, _MURO_MACIZO))
    assert len(mesh.vertices) == 8
    assert len(mesh.uvs) == 4
    assert len(mesh.faces) == 2
    assert set(mesh.face_groups) == {"wall"}


def test_rayo_atraviesa_el_vano(tmp_path: Path) -> None:
    mesh = parse_obj(_escribir(tmp_path, _MURO_CON_VANO))
    # Rayo por el centro del vano (x=2), a la altura del picaporte, cruzando en Z.
    assert contar_choques(mesh, (2.0, 1.0, -2.0), (0.0, 0.0, 1.0)) == 0


def test_rayo_choca_contra_el_muro_macizo(tmp_path: Path) -> None:
    mesh = parse_obj(_escribir(tmp_path, _MURO_MACIZO))
    assert contar_choques(mesh, (2.0, 1.0, -2.0), (0.0, 0.0, 1.0)) > 0


def test_puerta_tapiada_es_rechazada(tmp_path: Path) -> None:
    """El caso que hoy emite Houdini: muro entero + marco encima, sin hueco."""
    mesh = parse_obj(_escribir(tmp_path, _MURO_MACIZO))
    razones = check_door_openings(mesh, _IR)
    assert razones and "TAPIADA" in razones[0]


def test_puerta_abierta_pasa(tmp_path: Path) -> None:
    mesh = parse_obj(_escribir(tmp_path, _MURO_CON_VANO))
    assert check_door_openings(mesh, _IR) == []


def test_sin_uvs_es_rechazado(tmp_path: Path) -> None:
    sin_vt = "\n".join(l for l in _MURO_CON_VANO.splitlines() if not l.startswith("vt"))
    sin_vt = sin_vt.replace("/1", "").replace("/2", "").replace("/3", "").replace("/4", "")
    mesh = parse_obj(_escribir(tmp_path, sin_vt))
    razones = check_uvs(mesh)
    assert razones and "sin UVs" in razones[0]


def test_uv_degenerada_es_rechazada(tmp_path: Path) -> None:
    """Todos los vértices al mismo punto UV: la textura colapsa a un píxel."""
    plano = _MURO_CON_VANO.replace("vt 1.0 0.0", "vt 0.0 0.0").replace(
        "vt 1.0 1.0", "vt 0.0 0.0").replace("vt 0.0 1.0", "vt 0.0 0.0")
    mesh = parse_obj(_escribir(tmp_path, plano))
    razones = check_uvs(mesh)
    assert razones and "degenerada" in razones[0]


def test_uvs_sanas_pasan(tmp_path: Path) -> None:
    mesh = parse_obj(_escribir(tmp_path, _MURO_CON_VANO))
    assert check_uvs(mesh) == []


def test_densidad_de_texel_dispar_es_rechazada(tmp_path: Path) -> None:
    """Dos caras de igual área en el mundo pero con UVs de escala muy distinta."""
    obj = """
g wall
v 0.0 0.0 0.0
v 1.0 0.0 0.0
v 1.0 1.0 0.0
v 0.0 1.0 0.0
v 2.0 0.0 0.0
v 3.0 0.0 0.0
v 3.0 1.0 0.0
v 2.0 1.0 0.0
vt 0.0 0.0
vt 1.0 0.0
vt 1.0 1.0
vt 0.0 1.0
vt 0.0 0.0
vt 20.0 0.0
vt 20.0 20.0
vt 0.0 20.0
f 1/1 2/2 3/3 4/4
f 5/5 6/6 7/7 8/8
"""
    mesh = parse_obj(_escribir(tmp_path, obj))
    razones = check_uvs(mesh)
    assert razones and "téxel" in razones[0]


def test_bbox_de_la_malla_contra_el_ir(tmp_path: Path) -> None:
    mesh = parse_obj(_escribir(tmp_path, _MURO_CON_VANO))
    assert check_bbox(mesh, _IR) == []


def test_bbox_a_otra_escala_es_rechazada(tmp_path: Path) -> None:
    grande = "\n".join(
        (f"v {float(l.split()[1]) * 10} {l.split()[2]} {l.split()[3]}" if l.startswith("v ") else l)
        for l in _MURO_CON_VANO.splitlines()
    )
    mesh = parse_obj(_escribir(tmp_path, grande))
    razones = check_bbox(mesh, _IR)
    assert razones and "bbox" in razones[0]


def test_malla_vacia_es_rechazada(tmp_path: Path) -> None:
    mesh = parse_obj(_escribir(tmp_path, "g wall\n"))
    assert check_bbox(mesh, _IR) != []


def test_check_geometry_compone_los_tres(tmp_path: Path) -> None:
    """El muro macizo pasa bbox y UVs, pero cae por la puerta tapiada."""
    razones = check_geometry(_escribir(tmp_path, _MURO_MACIZO), _IR)
    assert len(razones) == 1 and "TAPIADA" in razones[0]
