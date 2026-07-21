"""layout de chars → JamSpec de maze, jugable-verificable por JamEnv.

Convención de chars: `#`=muro, `P`=player (start), `G`=goal, ` ` o `.`=pasillo.
El maze gana con la regla `player hits goal → win_game` (el resto lo provee JamEnv:
movimiento top-down, colisiones por celda, BFS de winnability en gameenv/metrics).
"""
from __future__ import annotations

from src.jamscript.parser import JamRule, JamSpec, JamSprite

WALL, PLAYER, GOAL, OPEN = "#", "P", "G", "."
PLAYER_GLYPH = "@"   # glifo del DSL JamMap para el player (los layouts guardados usan '@', no 'P')


def maze_spec(layout: list[str], name: str = "maze") -> JamSpec:
    """Construye un JamSpec top-down de maze desde un layout de filas de chars.

    Acepta el player como `P` (canónico Maze3D) o `@` (glifo del DSL JamMap) — los layouts que
    guarda el archivo de Capa 0 usan `@`, así que sin este alias el player no se mapea (0 entidades)."""
    return JamSpec(
        name=name,
        genre="maze",
        gravity=False,
        sprites=[
            JamSprite("wall", "wall"),
            JamSprite("player", "player"),
            JamSprite("goal", "goal"),
        ],
        mapping={WALL: "wall", PLAYER: "player", PLAYER_GLYPH: "player", GOAL: "goal"},
        layout=layout,
        rules=[JamRule(actor="player", target="goal", effect="win_game")],
    )
