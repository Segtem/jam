"""Contrasta en PIE el perfil sin límite con el presupuesto LOD 1/1/1 de Jam."""

from __future__ import annotations

import json
import time
import traceback

import unreal


MARCADOR = "JAM_MASS_LOD_BUDGET_58"
CONTROL = "/Jam/Mass/MC_JamAmbientISM.MC_JamAmbientISM"
PRESUPUESTO = "/Jam/Mass/MC_JamAmbientBudget.MC_JamAmbientBudget"
DISTANCIAS = (100.0, 300.0, 500.0, 700.0)
LIMITE_SEGUNDOS = 30.0
ESTADO = {"desde": time.monotonic(), "callback": None, "fase": "iniciar_pie",
          "world": None, "population_id": None, "pie_ticks": 0,
          "ultimo": None, "error": None, "control_verde": False,
          "presupuesto_verde": False}


def _facts(raw) -> dict:
    return json.loads(str(raw))


def _limpiar() -> None:
    if ESTADO["world"] is not None and ESTADO["population_id"]:
        unreal.JamMassLibrary.clear_population(ESTADO["world"], ESTADO["population_id"])
    ESTADO["population_id"] = None


def _terminar() -> None:
    try:
        _limpiar()
        ESTADO["world"] = None
    finally:
        if ESTADO["callback"] is not None:
            unreal.unregister_slate_post_tick_callback(ESTADO["callback"])
            ESTADO["callback"] = None
        if ESTADO["error"]:
            unreal.log_error(f"{MARCADOR} ROJO — {ESTADO['error']}")
        else:
            unreal.log(
                f"{MARCADOR} TODO VERDE — control High=4 · presupuesto "
                "High/Medium/Low/Off=1/1/1/1 · ISM=3 · None=1 · limpieza completa")
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
        unreal.SystemLibrary.quit_editor()


def _fallar(exc: Exception) -> None:
    ESTADO["error"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    _limpiar()
    ESTADO["world"] = None
    if level.is_in_play_in_editor():
        level.editor_request_end_play()
        ESTADO["fase"] = "esperar_fin_con_error"
    else:
        _terminar()


def _spawn(world, config: str) -> None:
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    if controller is None:
        raise RuntimeError("PIE no produjo PlayerController")
    location, rotation = controller.get_player_view_point()
    forward = unreal.MathLibrary.get_forward_vector(rotation)
    transforms = [unreal.Transform(location=unreal.Vector(
        location.x + forward.x * distance,
        location.y + forward.y * distance,
        location.z + forward.z * distance)) for distance in DISTANCIAS]
    spawned = _facts(unreal.JamMassLibrary.spawn_configured_population(
        world, transforms, config))
    if not spawned.get("ok") or spawned.get("valid") != 4:
        raise RuntimeError(f"la población no nació completa con {config}: {spawned}")
    ESTADO["population_id"] = spawned["population_id"]


def _coincide(facts: dict, expected: dict) -> bool:
    return all(facts.get(field) == value for field, value in expected.items())


def _tick(_delta_seconds: float) -> None:
    try:
        level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        fase = ESTADO["fase"]
        if fase == "iniciar_pie":
            level.editor_request_begin_play()
            ESTADO["fase"] = "esperar_pie"
            return
        if fase in ("esperar_fin", "esperar_fin_con_error"):
            if level.is_in_play_in_editor() or unreal.EditorLevelLibrary.get_pie_worlds(False):
                return
            _terminar()
            return
        if time.monotonic() - ESTADO["desde"] > LIMITE_SEGUNDOS:
            raise TimeoutError(f"el presupuesto LOD no convergió: {ESTADO['ultimo']}")

        pie_worlds = unreal.EditorLevelLibrary.get_pie_worlds(False)
        if not pie_worlds:
            return
        world = pie_worlds[0]
        ESTADO["world"] = world
        ESTADO["pie_ticks"] += 1
        if ESTADO["pie_ticks"] < 20:
            return

        if fase == "esperar_pie":
            _spawn(world, CONTROL)
            ESTADO["fase"] = "esperar_control"
            return

        inspected = _facts(unreal.JamMassLibrary.inspect_population(
            world, ESTADO["population_id"]))
        ESTADO["ultimo"] = inspected
        if fase == "esperar_control":
            expected = {"valid": 4, "lod_high": 4, "lod_medium": 0, "lod_low": 0,
                        "lod_off": 0, "representation_ism": 4,
                        "representation_none": 0}
            if not _coincide(inspected, expected):
                return
            ESTADO["control_verde"] = True
            _limpiar()
            _spawn(world, PRESUPUESTO)
            ESTADO["fase"] = "esperar_presupuesto"
            return

        expected = {"valid": 4, "lod_high": 1, "lod_medium": 1, "lod_low": 1,
                    "lod_off": 1, "representation_ism": 3,
                    "representation_none": 1, "representation_fragments": 4,
                    "lod_fragments": 4, "mesh_desc_valid": 4}
        if not _coincide(inspected, expected):
            return
        ESTADO["presupuesto_verde"] = True
        cleared = _facts(unreal.JamMassLibrary.clear_population(
            world, ESTADO["population_id"]))
        if cleared.get("valid_before") != 4 or cleared.get("valid_after") != 0:
            raise RuntimeError(f"la población presupuestada no se limpió: {cleared}")
        ESTADO["population_id"] = None
        ESTADO["world"] = None
        level.editor_request_end_play()
        ESTADO["fase"] = "esperar_fin"
    except Exception as exc:  # noqa: BLE001 — el marcador en el log es el veredicto
        _fallar(exc)


unreal.EditorPythonScripting.set_keep_python_script_alive(True)
ESTADO["callback"] = unreal.register_slate_post_tick_callback(_tick)
