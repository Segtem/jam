"""Calibración del verificador de winnability (AP-0) — fixtures de regresión.

Análogo a los "test lemmas" del paper AlphaProof Nexus (arXiv:2605.22763): antes
de confiar en lo que el verificador dice de un juego *generado*, probamos que
sobre juegos *conocidos* reporta lo correcto. Si un cambio en
winnability_probe.gd o en la cadena de inyectores rompe el oráculo, se caza acá.

Tier 1 (autorado a medida): el par golden / dead_exit difiere SOLO en goal.gd.
- golden_platformer    → el player alcanza el goal cableado → won=True
- dead_exit_platformer → el player alcanza el goal MUERTO (H7) → won=False

En ambos el player llega (player_moved=True): el negativo del segundo es por el
cable de victoria faltante, no por inmovilidad. Eso verifica que el probe no
falsea una victoria por mera proximidad al goal.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from oraculo.qa.winnability import check_winnability

_GODOT = shutil.which("godot4") or shutil.which("godot")
_HAS_GODOT = _GODOT
_FIXTURES = Path(__file__).parent / "fixtures" / "winnability"


def _import_project(proj: Path) -> None:
    # Los fixtures con assets reales (webp/ogg) necesitan un pase de import para
    # generar el cache .godot/ — sin él, los recursos "no existen" y el parse
    # cascada al class_name. No versionamos .godot/ (es cache), así que el test lo
    # genera en la copia tmp. Los fixtures de solo ColorRect no lo necesitan.
    subprocess.run(
        [_GODOT, "--headless", "--path", str(proj), "--import"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180,
    )


def _run(
    name: str, tmp_path: Path, main_scene: str | None = None,
    max_frames: int = 800, import_first: bool = False,
):
    # Copiar a tmp: check_winnability inyecta el probe y muta project.godot
    # (lo restaura al final), pero no queremos tocar el fixture versionado.
    proj = tmp_path / name
    shutil.copytree(_FIXTURES / name, proj)
    if main_scene is not None:
        pg = proj / "project.godot"
        import re
        pg.write_text(
            re.sub(r'run/main_scene="[^"]+"', f'run/main_scene="res://{main_scene}"', pg.read_text())
        )
    if import_first:
        _import_project(proj)
    return check_winnability(proj, timeout=60, max_frames=max_frames)


@pytest.mark.skipif(not _HAS_GODOT, reason="godot no instalado")
def test_golden_platformer_is_won(tmp_path):
    """Golden: el probe maneja al player hasta el goal cableado → won=True."""
    res = _run("golden_platformer", tmp_path)
    assert res.ran, f"el probe no reportó: {res.error}"
    assert res.won, f"esperaba won=True, telemetry={res.telemetry}"
    assert res.player_moved, "el player debería haberse movido hasta el goal"
    assert "level_complete" in res.win_via or "current_level" in res.win_via
    # Gradiente (Hito 0): won ⟹ progress forzado a 1.0 (alcanzó la meta de verdad).
    assert res.progress == 1.0, f"won=True debería dar progress=1.0, got {res.progress}"


@pytest.mark.skipif(not _HAS_GODOT, reason="godot no instalado")
def test_dead_exit_platformer_is_not_won(tmp_path):
    """Dead exit (H7): el player LLEGA al goal pero el exit no está cableado a la
    victoria → won=False. Distingue 'exit muerto' de 'juego roto'."""
    res = _run("dead_exit_platformer", tmp_path)
    assert res.ran, f"el probe no reportó: {res.error}"
    assert not res.won, f"esperaba won=False (exit muerto), telemetry={res.telemetry}"
    assert res.player_moved, "el negativo debe ser por el cable faltante, no por inmovilidad"
    # Gradiente (Hito 0): el player LLEGA al goal → progress≈1.0 PERO won=False. El
    # gradiente distingue la causa del negativo: acá el cable muerto (llegó, no ganó),
    # no la navegación. Es la versión "alta" del gradiente con won=False.
    assert res.progress >= 0.9, (
        f"el player llega al exit muerto → progress≈1.0 esperado, got {res.progress}"
    )


@pytest.mark.skipif(not _HAS_GODOT, reason="godot no instalado")
def test_mini_platformer_level1_is_won(tmp_path):
    """Mini platformer (juego real: vidas, monedas, roca, enemigo, 3 niveles).
    El probe debe ganar el nivel 1 — saltar la roca, juntar monedas, sobrevivir
    al enemigo y llegar al exit → won=True (current_level avanza 1→2). Calibra el
    verificador sobre un juego con más superficie que el par mínimo."""
    res = _run("mini_platformer", tmp_path)
    assert res.ran, f"el probe no reportó: {res.error}"
    assert res.won, f"esperaba won=True en el nivel 1, telemetry={res.telemetry}"
    assert res.player_moved
    assert not res.lost, "no debería hacer game over en el nivel 1 (tiene 3 vidas)"
    assert "level_complete" in res.win_via or "current_level" in res.win_via
    assert res.progress == 1.0, f"won=True debería dar progress=1.0, got {res.progress}"


@pytest.mark.skipif(not _HAS_GODOT, reason="godot no instalado")
def test_godot_official_demo_is_won(tmp_path):
    """Tier 2 — demo OFICIAL de Godot completado a ganable.

    `godot_platformer/` es el demo `2d/platformer` oficial (MIT), que de fábrica
    es un sandbox cerrado sin victoria ("one closed level, and the player is
    invincible"). Se lo COMPLETÓ con una bandera de meta: el jugador (puesto en el
    grupo `player`) llega a la meta → `goal.gd` emite `reached` → `game.gd` emite
    `level_complete` en /root/Game → el probe reporta won=True.

    Ancla de realismo: a diferencia del Tier 1 (autorado a medida, oráculo
    trivial), acá el verificador se calibra sobre código de terceros real —
    tilemap, slopes, doble salto, enemigos físicos. Necesita pase de import
    (assets webp/ogg).

    RECALIBRADO (2026-06-10, cierra el ⚠️ de Brian "meta trivial"): la bandera ya
    no está en piso plano — está sobre la plataforma one-way de y=320px y ganar
    exige TREPAR dos pisos de la escalera. Ejercita el modo trepado completo del
    probe: desvío al borde con cielo libre (el underside de la plataforma gruesa
    actúa de techo y mata vy — no se sube por el interior), salto sostenido (el
    player corta el salto al soltar: velocity.y *= 0.6), doble salto re-presionado
    en el apex vía parse_input_event (con action_press el edge just_pressed duraba
    2 frames de física y el segundo consumía el doble en el despegue), y ascenso
    pegado a la pared lateral (que desliza y conserva vy) con goal-seek metiendo
    al player encima al pasar el tope."""
    res = _run("godot_platformer", tmp_path, max_frames=1500, import_first=True)
    assert res.ran, f"el probe no reportó: {res.error}"
    assert res.won, f"esperaba won=True (meta TREPADA alcanzada), telemetry={res.telemetry}"
    assert res.player_moved, "el player debería haberse movido hasta la meta"
    assert not res.lost
    assert "level_complete" in res.win_via, f"win_via inesperado: {res.win_via}"
    assert res.progress == 1.0, f"won=True debería dar progress=1.0, got {res.progress}"
    # La meta está 2 pisos arriba: won=True sin trepado real es imposible. El
    # climb_rise lo blinda (la bandera está a ~350px sobre el spawn).
    assert res.telemetry.get("climb_rise", 0) > 300, (
        f"won=True con climb_rise<=300 es sospechoso (¿meta movida?): {res.telemetry}"
    )


@pytest.mark.skipif(not _HAS_GODOT, reason="godot no instalado")
def test_brett_real_game_victory_is_detected(tmp_path):
    """Tier 3 — juego open-source REAL (brettchalupa, CC0) completado a ganable.

    El starter kit no terminaba: la puerta del level_3 volvía al level_2 (loop sin
    victoria). Se lo COMPLETÓ con un final: `victory.tscn` emite `Global.level_complete`
    (autoload persistente, ∈ WIN_SIGNALS). Este test corre directo la pantalla de
    victoria y verifica que el verificador la detecta → won=True. Prueba dos cosas a
    la vez: que el juego ahora TIENE un estado de victoria, y que el contrato del
    probe (engancharse a /root/Global a través de cambios de escena) funciona."""
    res = _run("brett_platformer", tmp_path, main_scene="victory.tscn",
               max_frames=300, import_first=True)
    assert res.ran, f"el probe no reportó: {res.error}"
    assert res.won, f"esperaba won=True (victoria detectada), telemetry={res.telemetry}"
    assert "level_complete" in res.win_via, f"win_via inesperado: {res.win_via}"
    assert res.progress == 1.0, f"won=True debería dar progress=1.0, got {res.progress}"


@pytest.mark.skipif(not _HAS_GODOT, reason="godot no instalado")
def test_brett_real_game_level3_is_won(tmp_path):
    """Tier 3 — el probe ATRAVIESA el nivel REAL completo → won=True (HITO 2026-06-10).

    Este test fue el techo de destreza (won=False honesto): el probe cruzaba el pozo
    del level_3 de una parábola… y aterrizaba a 13px de la META (Door2, x≈800) para
    seguir saltando a la derecha hasta salirse del nivel — la meta quedaba ATRÁS.
    El trace de trayectoria (JAM_WIN_TRACE) destapó que el déficit NO era de salto
    sino de DIRECCIÓN: el probe era un caminante derecha-ciego.

    Fix (goal-seeking): el probe ya localizaba la meta para el gradiente espacial
    (_find_goal); ahora también la USA para navegar — avanza hacia su X, el contador
    de atasco mide acercamiento a la meta (no avance a la derecha), y cerca de la
    meta no re-salta por gap (el salto de ~200px sobrevuela la puerta). Con eso el
    nivel real de terceros (brettchalupa, CC0) se gana end-to-end: pozo → puerta →
    victory.tscn → Global.level_complete."""
    res = _run("brett_platformer", tmp_path, main_scene="level_3.tscn",
               max_frames=900, import_first=True)
    assert res.ran, f"el probe no reportó: {res.error}"
    assert res.player_moved, "el probe debería moverse (no es un fallo de arranque)"
    assert res.won, (
        f"REGRESIÓN del goal-seeking: el probe ganaba el level_3 real (hito "
        f"2026-06-10) y dejó de hacerlo. telemetry={res.telemetry}"
    )
    assert "level_complete" in res.win_via, f"win_via inesperado: {res.win_via}"
    assert len(res.script_errors) == 0, f"el juego real no debería tener errores: {res.script_errors[:3]}"
    assert res.progress == 1.0, f"won=True debería dar progress=1.0, got {res.progress}"


@pytest.mark.skipif(not _HAS_GODOT, reason="godot no instalado")
def test_unreachable_goal_gradient_is_partial(tmp_path):
    """Hito 0 (pre-req AP-2) — gap INFRANQUEABLE: el goal está cableado (si se tocara,
    ganaría) pero separado por un gap de 300px, muy por encima del salto del player
    (~172px). El probe NUNCA cruza → won=False, pero el gradiente espacial reporta un
    progress PARCIAL (ni 0 ni 1): cubrió una fracción de la distancia y se quedó en el
    borde. Es la versión espacial del dead_exit (allá el cable muerto con progress≈1;
    acá el goal inalcanzable con progress medio) y el caso que verifica que el gradiente
    BAJA de forma coherente cuando el booleano won ya dice 'no'.

    Prueba la propiedad clave del Hito 0: progress distingue tres regímenes —
    won=True (1.0) · casi-ganable/dead-exit (~0.9-1.0, won=False) · inalcanzable
    (parcial, won=False) — donde antes solo había un acantilado binario."""
    res = _run("unreachable_platformer", tmp_path)
    assert res.ran, f"el probe no reportó: {res.error}"
    assert not res.won, f"el gap es infranqueable → esperaba won=False, telemetry={res.telemetry}"
    assert res.player_moved, "el player debería moverse (no es un fallo de arranque)"
    assert len(res.script_errors) == 0, f"el fixture no debería tener errores: {res.script_errors[:3]}"
    assert res.telemetry.get("goal_found") is True, "la meta debería localizarse para el gradiente"
    # El corazón del Hito 0: progress es un gradiente HONESTO, ni colapsado a 0 (avanzó
    # de verdad) ni falseado a 1 (no llegó). El umbral superior 0.85 lo separa de los
    # casi-ganables (dead_exit≈1.0, brett level_3≈0.97).
    assert 0.1 < res.progress < 0.85, (
        f"esperaba un gradiente parcial (gap infranqueable, ni 0 ni 1), got {res.progress}"
    )


@pytest.mark.skipif(not _HAS_GODOT, reason="godot no instalado")
@pytest.mark.parametrize(
    "level,max_frames,min_lives",
    [("level_1.tscn", 1200, 3), ("level_2.tscn", 1500, 3), ("level_3.tscn", 1800, 2)],
)
def test_mini_platformer_each_level_is_winnable(tmp_path, level, max_frames, min_lives):
    """Cada nivel es independientemente ganable por el probe — incluso los que
    tienen pozos y enemigos. Clave anti-falso-negativo: el budget de frames se
    dimensiona a lo que el nivel necesita (nivel 3 cruza 2 pozos → ~1000 frames).
    Un `won=False` con budget chico sería un FALSO negativo del verificador, no un
    nivel inganable.

    `min_lives` blinda la DESTREZA del probe (Approach B): los pozos se cruzan con
    salto limpio (0 vidas) y los enemigos se saltan por encima. El probe pierde a lo
    sumo 1 vida por enemigo no esquivado — nivel 1/2 (1 enemigo) terminan 3/3, nivel
    3 (2 enemigos) ≥2/3. Si una regresión del esquive baja esto, `won` no cambiaría
    pero el test sí lo caza. Ver el approach en la KB."""
    res = _run("mini_platformer", tmp_path, main_scene=level, max_frames=max_frames)
    assert res.ran, f"{level}: el probe no reportó: {res.error}"
    assert res.won, f"{level}: esperaba won=True, telemetry={res.telemetry}"
    assert not res.lost, f"{level}: no debería hacer game over"
    lives = (res.telemetry or {}).get("lives", -1)
    assert lives >= min_lives, (
        f"{level}: esperaba lives>={min_lives} (destreza del probe), got {lives} — "
        f"posible regresión del esquive de enemigos/pozos. telemetry={res.telemetry}"
    )
