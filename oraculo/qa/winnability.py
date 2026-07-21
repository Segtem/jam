"""
Winnability — Fase H (ADR-011): jugabilidad como dimensión medida in-engine.

El problema que resuelve: hasta acá el QA conductual dependía de pixel-diff sobre
screenshots X11-root (`tiles_explored=0%`, frágil) y el DoD solo verificaba que el
build arrancara sin Parse Error. Nada probaba que el juego se pueda **terminar**.

Cómo: inyecta `winnability_probe.gd` como autoload, corre el proyecto bajo
`godot --headless` (el game loop tickea y el input sintético funciona — a
diferencia de Pixel Composer), el probe maneja input y se conecta a las señales
win/lose del GameManager, y reporta por stdout.

Propiedad anti-Goodhart: `won=True` es un POSITIVO FUERTE (el juego alcanzó de
verdad la victoria bajo input automático — la métrica más difícil de gamear, no
falseás "un agente completó el nivel"). Su ausencia es señal débil, no un fallo.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_PROBE_SRC = Path(__file__).parent / "winnability_probe.gd"
_PROBE_DEST_REL = "qa_winnability_probe.gd"     # en la raíz del proyecto
_AUTOLOAD_NAME = "JamWinProbe"
_REPORT_PREFIX = "WINNABILITY_RESULT:"


@dataclass
class WinnabilityResult:
    ran: bool = False                 # el probe corrió y reportó
    won: bool = False                 # disparó la win condition (positivo fuerte)
    lost: bool = False                # disparó la lose condition (game over funciona)
    win_via: str = ""                 # cómo se detectó la victoria
    player_moved: bool = False        # el player se movió ante input (in-engine, no pixel-diff)
    soft_locked: bool = False         # corrió hasta el final sin que nada progrese (dead-end)
    progress: float = -1.0            # gradiente espacial hacia la meta [0,1] (AP-2); -1 = meta desconocida
    frames: int = 0
    script_errors: list[str] = field(default_factory=list)
    telemetry: dict = field(default_factory=dict)
    error: str = ""

    @property
    def winnable(self) -> bool:
        """True solo si el juego se pudo terminar de verdad bajo input automático."""
        return self.ran and self.won

    def to_dict(self) -> dict:
        return {
            "ran": self.ran, "won": self.won, "lost": self.lost,
            "winnable": self.winnable, "win_via": self.win_via,
            "player_moved": self.player_moved, "soft_locked": self.soft_locked,
            "progress": self.progress,
            "frames": self.frames, "script_errors": len(self.script_errors),
            "telemetry": self.telemetry, "error": self.error,
        }


def _godot_bin() -> str | None:
    return shutil.which("godot4") or shutil.which("godot")


def _gameplay_scene(project_dir: Path) -> str | None:
    """Busca la primera escena de gameplay (no menú) en el proyecto.

    Candidatos en orden de preferencia:
    1. main_level.tscn en cualquier directorio
    2. level_1.tscn o level1.tscn
    3. Cualquier .tscn que NO tenga "menu", "title", "splash", "ui" en su path
    Devuelve un path res:// o None.
    """
    candidates = ["main_level.tscn", "level_1.tscn", "level1.tscn", "game.tscn", "gameplay.tscn"]
    for name in candidates:
        found = list(project_dir.rglob(name))
        if found:
            rel = found[0].relative_to(project_dir)
            return f"res://{rel.as_posix()}"
    # Fallback: primer .tscn fuera de ui/ que no sea menú
    skip_kw = ("menu", "title", "splash", "ui", "hud", "overlay")
    for tscn in sorted(project_dir.rglob("*.tscn")):
        rel = tscn.relative_to(project_dir).as_posix().lower()
        if not any(kw in rel for kw in skip_kw):
            return f"res://{rel}"
    return None


def _inject_probe(project_dir: Path) -> tuple[bool, str]:
    """Copia el probe a la raíz y lo registra como autoload en project.godot.

    Devuelve (ok, original_project_godot_text) para poder restaurar después.
    Si la main_scene actual es un menú, la sobreescribe temporalmente con la
    primera escena de gameplay encontrada para que el probe llegue al juego
    sin tener que navegar la UI.
    """
    pg = project_dir / "project.godot"
    if not pg.exists():
        return False, ""
    original = pg.read_text(encoding="utf-8")
    shutil.copy2(_PROBE_SRC, project_dir / _PROBE_DEST_REL)

    autoload_line = f'{_AUTOLOAD_NAME}="*res://{_PROBE_DEST_REL}"'
    text = original
    if "[autoload]" in text:
        # Insertar la línea justo después del header [autoload]
        text = re.sub(r"(\[autoload\]\n)", r"\1" + autoload_line + "\n", text, count=1)
    else:
        text = text.rstrip() + f"\n\n[autoload]\n\n{autoload_line}\n"

    # Si la main_scene apunta a un menú, saltearlo apuntando directo al gameplay.
    # El original se restaura en _restore_project(). Esto evita que el probe
    # gaste frames en un menú que puede no tener botones accesibles por teclado
    # o cuya escena-destino tenga errores que silencien el change_scene_to_file.
    current_scene_m = re.search(r'run/main_scene\s*=\s*"([^"]+)"', text)
    if current_scene_m:
        current_scene = current_scene_m.group(1).lower()
        menu_kw = ("menu", "title", "splash", "main_menu", "intro")
        if any(kw in current_scene for kw in menu_kw):
            gameplay = _gameplay_scene(project_dir)
            if gameplay:
                text = re.sub(
                    r'(run/main_scene\s*=\s*)"[^"]+"',
                    rf'\1"{gameplay}"',
                    text,
                )

    pg.write_text(text, encoding="utf-8")
    return True, original


def _restore_project(project_dir: Path, original: str) -> None:
    """Quita el probe y restaura el project.godot original."""
    try:
        (project_dir / _PROBE_DEST_REL).unlink(missing_ok=True)
        if original:
            (project_dir / "project.godot").write_text(original, encoding="utf-8")
    except Exception:
        pass


def _parse_report(output: str) -> dict | None:
    for line in output.splitlines():
        idx = line.find(_REPORT_PREFIX)
        if idx != -1:
            payload = line[idx + len(_REPORT_PREFIX):].strip()
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                continue
    return None


def _extract_script_errors(output: str) -> list[str]:
    errs: list[str] = []
    for line in output.splitlines():
        if re.search(r"SCRIPT ERROR|Parse Error|Failed to load script|Invalid get index", line):
            errs.append(line.strip())
    return errs


def check_winnability(
    project_dir: Path, timeout: float = 60.0, max_frames: int | None = None
) -> WinnabilityResult:
    """Corre el proyecto headless con el probe y mide si se puede ganar.

    Degrada con gracia: si no hay godot o no hay project.godot, retorna ran=False
    sin forzar un falso positivo/negativo. `max_frames` acota el presupuesto de
    frames del probe (útil en tests; default 2400 ≈ 40s).
    """
    result = WinnabilityResult()
    godot = _godot_bin()
    if not godot:
        result.error = "godot no disponible"
        return result
    if not (project_dir / "project.godot").exists():
        result.error = "sin project.godot"
        return result

    ok, original = _inject_probe(project_dir)
    if not ok:
        result.error = "no se pudo inyectar el probe"
        return result

    try:
        env = dict(os.environ)
        env.pop("DISPLAY", None)        # headless real
        if max_frames is not None:
            env["JAM_WIN_MAX_FRAMES"] = str(max_frames)
        proc = subprocess.Popen(
            [godot, "--headless", "--path", str(project_dir)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
        )
        try:
            out, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
            result.error = "timeout (el probe no salió solo)"
    except Exception as e:
        result.error = str(e)
        return result
    finally:
        _restore_project(project_dir, original)

    result.script_errors = _extract_script_errors(out)
    report = _parse_report(out)
    if report is None:
        if not result.error:
            result.error = "el probe no reportó (¿el juego no arrancó?)"
        return result

    result.ran = True
    result.won = bool(report.get("won", False))
    result.lost = bool(report.get("lost", False))
    result.win_via = str(report.get("win_via", ""))
    result.player_moved = bool(report.get("player_moved", False))
    result.soft_locked = bool(report.get("soft_locked", False))
    result.progress = float(report.get("progress", -1.0))
    result.frames = int(report.get("frames", 0))
    result.telemetry = report
    return result
