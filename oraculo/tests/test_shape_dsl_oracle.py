"""Tests para el oráculo agnóstico de Shape DSL."""

import sys
from pathlib import Path

# jammesh vive fuera de src/ → al path (mismo patrón que los otros tests de jam_api)
ROOT = Path(__file__).resolve().parent.parent
JAMMESH_PATH = ROOT / "assets" / "props" / "jammesh"
if str(JAMMESH_PATH) not in sys.path:
    sys.path.insert(0, str(JAMMESH_PATH))

from core import Part  # noqa: E402

from src.jam_api.shape_dsl.ast import Assembly  # noqa: E402
from src.jam_api.shape_dsl.oracle import check_assembly  # noqa: E402

def test_oracle_positive_bed():
    assembly = Assembly(kind="bed", decls=())
    parts = [
        Part("frame", "wood", (0.0, 0.0, 0.3), (1.4, 2.0, 0.1)),
        Part("mattress", "sheet", (0.0, 0.0, 0.45), (1.4, 2.0, 0.2)),
        Part("leg_fl", "wood", (-0.65, 0.95, 0.125), (0.1, 0.1, 0.25)),
        Part("leg_fr", "wood", (0.65, 0.95, 0.125), (0.1, 0.1, 0.25)),
        Part("leg_bl", "wood", (-0.65, -0.95, 0.125), (0.1, 0.1, 0.25)),
        Part("leg_br", "wood", (0.65, -0.95, 0.125), (0.1, 0.1, 0.25)),
        Part("headboard", "wood", (0.0, 1.05, 0.4), (1.4, 0.1, 0.8)),
    ]
    fails = check_assembly(assembly, parts)
    assert not fails, f"La cama debería pasar: {fails}"

def test_oracle_positive_chair():
    assembly = Assembly(kind="chair", decls=())
    parts = [
        Part("seat", "wood", (0.0, 0.0, 0.425), (0.45, 0.45, 0.05)),
        Part("leg_fl", "wood", (-0.2, 0.2, 0.2), (0.05, 0.05, 0.4)),
        Part("leg_fr", "wood", (0.2, 0.2, 0.2), (0.05, 0.05, 0.4)),
        Part("leg_bl", "wood", (-0.2, -0.2, 0.2), (0.05, 0.05, 0.4)),
        Part("leg_br", "wood", (0.2, -0.2, 0.2), (0.05, 0.05, 0.4)),
        Part("back", "wood", (0.0, -0.25, 0.65), (0.45, 0.05, 0.5)),
    ]
    fails = check_assembly(assembly, parts)
    assert not fails, f"La silla debería pasar: {fails}"

def test_oracle_negative_floating_surface():
    assembly = Assembly(kind="table", decls=())
    parts = [
        Part("top", "wood", (0.0, 0.0, 0.8), (1.0, 1.0, 0.1)),
        Part("side_pillar", "wood", (0.55, 0.0, 0.45), (0.1, 1.0, 0.9)),
    ]
    fails = check_assembly(assembly, parts)
    assert any("top" in f and "no está sostenida desde abajo" in f for f in fails), fails

def test_oracle_negative_short_leg():
    assembly = Assembly(kind="stool", decls=())
    parts = [
        Part("seat", "wood", (0.0, 0.0, 0.5), (0.4, 0.4, 0.1)),
        Part("leg", "wood", (0.0, 0.0, 0.275), (0.1, 0.1, 0.45)),
    ]
    fails = check_assembly(assembly, parts)
    assert any("leg" in f and "no está aterrizada" in f for f in fails), fails

def test_oracle_negative_loose_panel():
    assembly = Assembly(kind="art", decls=())
    parts = [
        Part("base", "wood", (0.0, 0.0, 0.1), (1.0, 1.0, 0.2)),
        Part("panel", "wood", (2.0, 2.0, 1.0), (0.1, 1.0, 1.0)),
    ]
    fails = check_assembly(assembly, parts)
    assert any("panel" in f and "no está aterrizada" in f for f in fails), fails

def test_oracle_negative_sunken():
    assembly = Assembly(kind="bed", decls=())
    parts = [
        Part("frame", "wood", (0.0, 0.0, -0.1), (1.0, 1.0, 0.2)),
        Part("leg", "wood", (0.0, 0.0, 0.5), (0.1, 0.1, 1.0)),
    ]
    fails = check_assembly(assembly, parts)
    assert any("frame" in f and "hundida bajo el piso" in f for f in fails), fails

def test_oracle_negative_degenerate():
    assembly = Assembly(kind="thing", decls=())
    parts = [
        Part("base", "wood", (0.0, 0.0, 0.1), (1.0, 1.0, 0.2)),
        Part("point", "wood", (0.0, 0.0, 0.2), (0.0, 0.0, 0.0)),
    ]
    fails = check_assembly(assembly, parts)
    assert any("point" in f and "degenerada" in f for f in fails), fails

def test_oracle_negative_absurd_footprint():
    assembly = Assembly(kind="city", decls=())
    parts = [
        Part("floor", "wood", (0.0, 0.0, 0.1), (10.0, 10.0, 0.2)),
        Part("pillar", "wood", (0.0, 0.0, 0.5), (0.1, 0.1, 0.8)),
    ]
    fails = check_assembly(assembly, parts)
    assert any("excede huella" in f for f in fails), fails
