"""Tests de winnability (Fase H) — inyección, parsing, restauración + integración."""
import json
import shutil
from pathlib import Path

import pytest

from oraculo.qa.winnability import (
    WinnabilityResult,
    check_winnability,
    _inject_probe,
    _restore_project,
    _parse_report,
    _extract_script_errors,
    _AUTOLOAD_NAME,
    _PROBE_DEST_REL,
    _REPORT_PREFIX,
)

_PG_MINIMAL = """\
config_version=5

[application]

run/main_scene="res://scenes/level_1.tscn"
config/name="Test"
"""

_PG_WITH_AUTOLOAD = """\
config_version=5

[application]

config/name="Test"

[autoload]

GameManager="*res://autoloads/game_manager.gd"
"""


def _mk_project(tmp_path: Path, pg_text: str) -> Path:
    (tmp_path / "project.godot").write_text(pg_text)
    return tmp_path


# --- inyección de autoload ---

def test_inject_creates_probe_and_autoload_section(tmp_path):
    proj = _mk_project(tmp_path, _PG_MINIMAL)
    ok, original = _inject_probe(proj)
    assert ok
    assert (proj / _PROBE_DEST_REL).exists()
    text = (proj / "project.godot").read_text()
    assert "[autoload]" in text
    assert f'{_AUTOLOAD_NAME}="*res://{_PROBE_DEST_REL}"' in text
    assert original == _PG_MINIMAL


def test_inject_preserves_existing_autoloads(tmp_path):
    proj = _mk_project(tmp_path, _PG_WITH_AUTOLOAD)
    ok, _ = _inject_probe(proj)
    assert ok
    text = (proj / "project.godot").read_text()
    # El GameManager preexistente sigue + nuestro probe agregado
    assert 'GameManager="*res://autoloads/game_manager.gd"' in text
    assert f'{_AUTOLOAD_NAME}="*res://{_PROBE_DEST_REL}"' in text
    # El probe se inserta dentro de la sección [autoload] existente
    assert text.count("[autoload]") == 1


def test_inject_missing_project_godot(tmp_path):
    ok, original = _inject_probe(tmp_path)   # sin project.godot
    assert not ok
    assert original == ""


def test_restore_removes_probe_and_restores_text(tmp_path):
    proj = _mk_project(tmp_path, _PG_MINIMAL)
    _, original = _inject_probe(proj)
    assert (proj / _PROBE_DEST_REL).exists()
    _restore_project(proj, original)
    assert not (proj / _PROBE_DEST_REL).exists()
    assert (proj / "project.godot").read_text() == _PG_MINIMAL


# --- parsing del reporte ---

def test_parse_report_extracts_json():
    out = (
        "Godot Engine v4.6\n"
        + _REPORT_PREFIX + '{"won": true, "win_via": "signal:level_complete", "frames": 200}\n'
        "exiting.\n"
    )
    rep = _parse_report(out)
    assert rep is not None
    assert rep["won"] is True
    assert rep["win_via"] == "signal:level_complete"


def test_parse_report_none_when_absent():
    assert _parse_report("nada que ver acá\notra línea") is None


def test_parse_report_ignores_malformed_json():
    assert _parse_report(_REPORT_PREFIX + "{no es json}") is None


def test_parse_report_handles_prefixed_line():
    # Godot a veces antepone basura en la misma línea
    out = "  [debug] " + _REPORT_PREFIX + '{"won": false}'
    rep = _parse_report(out)
    assert rep == {"won": False}


def test_extract_script_errors():
    out = (
        "SCRIPT ERROR: Parse Error: bla\n"
        "todo bien\n"
        "Failed to load script res://x.gd\n"
    )
    errs = _extract_script_errors(out)
    assert len(errs) == 2


# --- dataclass / propiedad winnable ---

def test_winnable_requires_ran_and_won():
    assert WinnabilityResult(ran=True, won=True).winnable is True
    assert WinnabilityResult(ran=True, won=False).winnable is False
    assert WinnabilityResult(ran=False, won=True).winnable is False   # no corrió → no cuenta


def test_to_dict_shape():
    r = WinnabilityResult(ran=True, won=True, win_via="signal:victory", frames=120)
    d = r.to_dict()
    assert d["winnable"] is True
    assert d["win_via"] == "signal:victory"
    assert set(d) >= {"ran", "won", "lost", "winnable", "frames", "telemetry"}


# --- degradación con gracia ---

def test_check_winnability_no_project(tmp_path, monkeypatch):
    # Forzar godot "presente" para llegar al chequeo de project.godot
    monkeypatch.setattr("oraculo.qa.winnability._godot_bin", lambda: "/usr/bin/godot")
    res = check_winnability(tmp_path)
    assert res.ran is False
    assert "project.godot" in res.error


def test_check_winnability_no_godot(tmp_path, monkeypatch):
    monkeypatch.setattr("oraculo.qa.winnability._godot_bin", lambda: None)
    res = check_winnability(_mk_project(tmp_path, _PG_MINIMAL))
    assert res.ran is False
    assert "godot" in res.error


# --- cache del endpoint /quality (_winnability_cached) ---

def test_winnability_cache_hit_skips_godot(tmp_path, monkeypatch):
    """Si existe .telemetry/winnability.json, se lee sin correr godot."""
    from src.api.server import _winnability_cached
    cache = tmp_path / ".telemetry" / "winnability.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"ran": True, "won": True, "winnable": True}))

    # Si llamara a check_winnability fallaría el test (no debe llamarlo en cache-hit)
    monkeypatch.setattr(
        "oraculo.qa.winnability.check_winnability",
        lambda *a, **k: pytest.fail("no debería correr godot en cache-hit"),
    )
    out = _winnability_cached(tmp_path)
    assert out["won"] is True


def test_winnability_cache_miss_computes_and_writes(tmp_path, monkeypatch):
    from src.api import server
    fake = WinnabilityResult(ran=True, won=False, frames=2400)
    monkeypatch.setattr(
        "oraculo.qa.winnability.check_winnability", lambda *a, **k: fake
    )
    out = server._winnability_cached(tmp_path)
    assert out["ran"] is True and out["won"] is False
    # Se cacheó a disco
    cache = tmp_path / ".telemetry" / "winnability.json"
    assert cache.exists()
    assert json.loads(cache.read_text())["frames"] == 2400


# --- integración real (requiere godot) ---

_HAS_GODOT = shutil.which("godot4") or shutil.which("godot")


@pytest.mark.skipif(not _HAS_GODOT, reason="godot no instalado")
def test_integration_probe_runs_and_reports(tmp_path):
    """Proyecto mínimo con GameManager que gana solo → el probe debe reportar won=True.

    Verifica el camino end-to-end: inyección de autoload + corrida headless +
    el probe se conecta a la señal level_complete y la detecta.
    """
    proj = tmp_path
    (proj / "autoloads").mkdir()
    # GameManager que emite level_complete tras unos frames (juego auto-ganable)
    (proj / "autoloads" / "game_manager.gd").write_text(
        "extends Node\n"
        "signal level_complete()\n"
        "var score := 0\n"
        "var lives := 3\n"
        "var current_level := 1\n"
        "var _f := 0\n"
        "func _ready() -> void:\n"
        "\tprocess_mode = Node.PROCESS_MODE_ALWAYS\n"
        "func _process(_d: float) -> void:\n"
        "\t_f += 1\n"
        "\tif _f == 150:\n"
        "\t\tcurrent_level += 1\n"
        "\t\tlevel_complete.emit()\n"
    )
    # Escena principal mínima (un Node vacío)
    (proj / "main.tscn").write_text(
        '[gd_scene format=3 uid="uid://test"]\n\n[node name="Main" type="Node"]\n'
    )
    (proj / "project.godot").write_text(
        'config_version=5\n\n[application]\n\n'
        'run/main_scene="res://main.tscn"\nconfig/name="WinTest"\n\n'
        '[autoload]\n\nGameManager="*res://autoloads/game_manager.gd"\n'
    )

    res = check_winnability(proj, timeout=40)
    assert res.ran, f"el probe no reportó: {res.error}\n{res.telemetry}"
    assert res.won, f"esperaba won=True, telemetry={res.telemetry}"
    assert "level_complete" in res.win_via or "current_level" in res.win_via
    # Y el probe debe haber limpiado tras de sí
    assert not (proj / _PROBE_DEST_REL).exists()


@pytest.mark.skipif(not _HAS_GODOT, reason="godot no instalado")
def test_integration_soft_lock_detected(tmp_path):
    """Player que existe pero NO se mueve ni progresa, corrido hasta el tope →
    soft_locked=True. Usa max_frames chico para que el test sea rápido."""
    proj = tmp_path
    (proj / "autoloads").mkdir()
    (proj / "autoloads" / "game_manager.gd").write_text(
        "extends Node\nvar score := 0\nvar lives := 3\nvar current_level := 1\n"
    )
    # Player Node2D inerte (en grupo "player", nunca se mueve)
    (proj / "player.gd").write_text(
        "extends Node2D\nfunc _ready() -> void:\n\tadd_to_group(\"player\")\n"
    )
    (proj / "main.tscn").write_text(
        '[gd_scene format=3 uid="uid://slk"]\n'
        '[ext_resource type="Script" path="res://player.gd" id="1"]\n\n'
        '[node name="Main" type="Node2D"]\n\n'
        '[node name="Player" type="Node2D" parent="."]\nscript = ExtResource("1")\n'
    )
    (proj / "project.godot").write_text(
        'config_version=5\n\n[application]\n\n'
        'run/main_scene="res://main.tscn"\nconfig/name="SoftLock"\n\n'
        '[autoload]\n\nGameManager="*res://autoloads/game_manager.gd"\n'
    )

    res = check_winnability(proj, timeout=30, max_frames=150)
    assert res.ran, f"no reportó: {res.error}"
    assert res.telemetry.get("player_exists") is True
    assert not res.won and not res.lost
    assert res.soft_locked, f"esperaba soft_locked, telemetry={res.telemetry}"
    assert not res.player_moved
