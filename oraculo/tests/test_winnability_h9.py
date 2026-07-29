"""Integración H9: el probe gana un nivel WFC real con plataformas flotantes.

Antes de H9 las plataformas flotantes (PLAT) quedaban a "altura intermedia": ni
saltables (dependía de la física que tunea el LLM) ni caminables por debajo
(bloqueaban el camino del suelo). Tras H9 el generador las eleva a un hueco de 64px
→ el probe pasa caminando por debajo y llega al exit, sin saltos obligatorios sobre
ellas. Aquí se usa una semilla con PLAT y SIN GAP para aislar la propiedad H9.
"""
import shutil
from pathlib import Path

import pytest

_HAS_GODOT = shutil.which("godot4") or shutil.which("godot")

_PLAYER_GD = (
    "extends CharacterBody2D\n"
    "const SPEED := 200.0\nconst JUMP := -400.0\nconst G := 980.0\n"
    "func _ready(): add_to_group('player')\n"
    "func _physics_process(d):\n"
    "\tif not is_on_floor(): velocity.y += G * d\n"
    "\tvelocity.x = Input.get_axis('ui_left', 'ui_right') * SPEED\n"
    "\tif is_on_floor() and Input.is_action_just_pressed('jump'): velocity.y = JUMP\n"
    "\tmove_and_slide()\n"
)
_PLAYER_TSCN = (
    '[gd_scene load_steps=3 format=3]\n'
    '[ext_resource type="Script" path="res://scripts/player.gd" id="1"]\n'
    '[sub_resource type="RectangleShape2D" id="c"]\nsize = Vector2(16, 24)\n\n'
    '[node name="Player" type="CharacterBody2D"]\nscript = ExtResource("1")\n\n'
    '[node name="Col" type="CollisionShape2D" parent="."]\nshape = SubResource("c")\n'
)


def _build_wfc_project(tmp_path: Path, seed: int, n_sections: int) -> Path:
    from src.pcg.platformer import generate_platformer_level, level_to_tscn, SEC_TILES, TILE
    from src.gdscript.player_group import ensure_player_grouped
    from src.gdscript.player_in_level import ensure_player_in_level
    from src.gdscript.exit_trigger import ensure_exit_trigger
    from src.adapters.godot import GodotAdapter

    proj = tmp_path
    (proj / "scenes" / "levels").mkdir(parents=True)
    (proj / "scripts").mkdir()
    (proj / "autoloads").mkdir()
    (proj / "autoloads" / "game_manager.gd").write_text(
        "extends Node\nsignal level_complete()\nvar current_level := 1\n"
        "var lives := 3\nvar score := 0\n"
        "func next_level():\n\tcurrent_level += 1\n\tlevel_complete.emit()\n"
    )
    (proj / "scripts" / "player.gd").write_text(_PLAYER_GD)
    (proj / "scripts" / "player.tscn").write_text(_PLAYER_TSCN)

    level = generate_platformer_level(n_sections=n_sections, seed=seed, difficulty=0.0)
    assert "PLAT" in level.sections, f"semilla {seed} no tiene PLAT: {level.sections}"
    assert "GAP" not in level.sections, f"semilla {seed} tiene GAP (debería aislar H9): {level.sections}"
    (proj / "scenes" / "levels" / "level_1.tscn").write_text(
        level_to_tscn(level, scene_name="level_1")
    )

    width = level.width_px
    (proj / "project.godot").write_text(
        'config_version=5\n\n[application]\n\n'
        'run/main_scene="res://scenes/levels/level_1.tscn"\n\n'
        f'[display]\n\nwindow/size/viewport_width={width}\nwindow/size/viewport_height=448\n\n'
        '[autoload]\nGameManager="*res://autoloads/game_manager.gd"\n'
    )
    ensure_player_in_level(proj)
    ensure_player_grouped(proj)
    ensure_exit_trigger(proj)
    GodotAdapter().ensure_input_actions(str(proj))
    return proj


@pytest.mark.skipif(not _HAS_GODOT, reason="godot no instalado")
def test_wfc_level_with_floating_platforms_is_winnable(tmp_path):
    """Nivel WFC con PLAT (sin GAP): el probe camina bajo las plataformas y gana."""
    from oraculo.qa.winnability import check_winnability
    proj = _build_wfc_project(tmp_path, seed=0, n_sections=10)
    res = check_winnability(proj, timeout=60, max_frames=1200)
    assert res.won, f"esperaba won=True (PLAT no debe bloquear), telemetry={res.telemetry}"
    assert res.telemetry.get("current_level") == 2
