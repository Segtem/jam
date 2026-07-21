"""Integración H8: el probe cruza GAPs saltables y gana (godot real).

El probe original NUNCA podía saltar: tapeaba jump con action_press+action_release
en el MISMO frame, lo que no dispara is_action_just_pressed del player. Tras el fix
(pulso de 1 frame + salto reactivo por raycast solo ante obstáculo), cruza gaps.
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


def _build(tmp_path: Path, gap_left: float, gap_right: float, exit_x: float) -> Path:
    from src.gdscript.player_group import ensure_player_grouped
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
    aw = gap_left
    bw = exit_x + 120 - gap_right
    (proj / "scenes" / "levels" / "level_1.tscn").write_text(
        '[gd_scene load_steps=4 format=3]\n'
        '[ext_resource type="PackedScene" path="res://scripts/player.tscn" id="p"]\n'
        f'[sub_resource type="RectangleShape2D" id="a"]\nsize = Vector2({aw}, 40)\n'
        f'[sub_resource type="RectangleShape2D" id="b"]\nsize = Vector2({bw}, 40)\n\n'
        '[node name="level_1" type="Node2D"]\n\n'
        f'[node name="A" type="StaticBody2D" parent="."]\nposition = Vector2({aw / 2}, 400)\n\n'
        '[node name="AC" type="CollisionShape2D" parent="A"]\nshape = SubResource("a")\n\n'
        f'[node name="B" type="StaticBody2D" parent="."]\nposition = Vector2({gap_right + bw / 2}, 400)\n\n'
        '[node name="BC" type="CollisionShape2D" parent="B"]\nshape = SubResource("b")\n\n'
        '[node name="Player" parent="." instance=ExtResource("p")]\nposition = Vector2(40, 360)\n\n'
        f'[node name="ExitFlag" type="Marker2D" parent="."]\nposition = Vector2({exit_x}, 360)\n'
    )
    (proj / "project.godot").write_text(
        'config_version=5\n\n[application]\n\n'
        'run/main_scene="res://scenes/levels/level_1.tscn"\n\n'
        '[display]\n\nwindow/size/viewport_width=480\nwindow/size/viewport_height=640\n\n'
        '[autoload]\nGameManager="*res://autoloads/game_manager.gd"\n'
    )
    ensure_player_grouped(proj)
    ensure_exit_trigger(proj)
    GodotAdapter().ensure_input_actions(str(proj))
    return proj


@pytest.mark.skipif(not _HAS_GODOT, reason="godot no instalado")
def test_probe_crosses_jumpable_gap_and_wins(tmp_path):
    """Gap de 100px (saltable) → el probe salta en el borde, cruza y gana."""
    from src.qa.winnability import check_winnability
    proj = _build(tmp_path, gap_left=200, gap_right=300, exit_x=480)
    res = check_winnability(proj, timeout=40, max_frames=600)
    assert res.won, f"esperaba won=True, telemetry={res.telemetry}"
    assert res.telemetry.get("current_level") == 2


@pytest.mark.skipif(not _HAS_GODOT, reason="godot no instalado")
def test_probe_does_not_win_impossible_gap(tmp_path):
    """Gap de 360px (más ancho que el salto) → no se puede cruzar, won=False."""
    from src.qa.winnability import check_winnability
    proj = _build(tmp_path, gap_left=200, gap_right=560, exit_x=740)
    res = check_winnability(proj, timeout=40, max_frames=600)
    assert not res.won, f"un gap incruzable no debería ganarse: {res.telemetry}"
