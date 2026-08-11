"""¿La patrulla se mueve como una MULTITUD o como una formación? — UE 5.8.1, PIE real.

La Fase 4 anterior dejó una patrulla que funciona: 4/4 entidades inicializadas, movidas y revertidas
dentro del radio. Pero todas arrancaban en `Distance = 0` con `Direction = 1` y la misma velocidad,
así que salían juntas, tocaban el extremo en el mismo frame y volvían juntas. Cada individuo estaba
bien; el conjunto se veía como una coreografía, que es exactamente lo que delata a una multitud
sintética.

Esta sonda mide dos cosas que ninguna de las anteriores podía:

  1. **Dispersión** — que las fases y las velocidades sean distintas entre entidades.
  2. **Determinismo** — que una SEGUNDA población sobre los mismos transforms dé exactamente las
     mismas fases. Sin esto la variación sería ruido, y una escena no se vería igual dos veces.

El segundo punto es el que justifica derivar la variación del ORIGEN de spawn y no del índice de la
entidad: el orden en que Mass crea y ordena entidades es un detalle interno.

    UnrealEditor-Cmd <proyecto>.uproject -run=pythonscript \
        -script=<plugin>/tools/experiments/verifica_mass_variacion_58.py \
        -RenderOffScreen -unattended -nosplash -stdout

Salida en el `BotOO*.log` más reciente, EXCLUYENDO `BotOO-CRC.log`.
"""

from __future__ import annotations

import json
import time

import unreal

from jam import mass_core


CONFIG = "/Jam/Mass/MC_JamAmbientPatrol.MC_JamAmbientPatrol"
ENTIDADES = 6
LIMITE_SEGUNDOS = 120.0
FALLAS = []
ESTADO = {"desde": time.monotonic(), "callback": None, "fase": "iniciar_pie",
          "ticks": 0, "lecturas": [], "vuelta": 0}


def log(mensaje: str) -> None:
    unreal.log(f"[VARIACION] {mensaje}")


def exigir(condicion: bool, descripcion: str) -> None:
    log(("  OK   " if condicion else "  FALLA") + f" · {descripcion}")
    if not condicion:
        FALLAS.append(descripcion)


def _facts(texto) -> dict:
    return json.loads(str(texto))


def transforms_fijos():
    """Transforms deterministas y SEPARADOS entre sí.

    Separados importa: la variación se deriva del origen redondeado a centímetros, así que dos
    entidades en el mismo punto comparten fase legítimamente. Con todas apiladas la sonda mediría
    esa coincidencia y no la variación.
    """
    salida = []
    for indice in range(ENTIDADES):
        salida.append(unreal.Transform(
            location=unreal.Vector(1000.0 + indice * 250.0, indice * 130.0, 100.0),
            rotation=unreal.Rotator(0.0, indice * 60.0, 0.0)))
    return salida


def medir(mundo) -> None:
    """Todo esto corre DENTRO de PIE: sin PIE los processors de Mass no tickean y la fase de cada
    entidad se queda en su valor por defecto. La primera versión de esta sonda midió el mundo del
    editor y leyó seis ceros — no porque la variación fallara, sino porque nunca se había inicializado."""
    config = _facts(unreal.JamMassLibrary.inspect_config(mundo, CONFIG))
    log(f"config: variación declarada = {config.get('patrol_variation')}")
    exigir(bool(config.get("has_patrol")), "el config conserva la patrulla")
    exigir(float(config.get("patrol_variation") or 0.0) > 0.0,
           "el config declara una variación mayor que cero")

    # El cerebro puro decide si ese config puede publicarse exigiendo variación.
    juicio = mass_core.make_config(CONFIG, config, require_variation=True)
    exigir("error" not in juicio,
           f"mass_config con require_variation acepta el asset ({juicio.get('error', 'ok')})")

    lecturas = ESTADO["lecturas"]
    for vuelta, inspeccion in enumerate(lecturas, start=1):
        veredicto = mass_core.judge_variation(
            inspeccion.get("patrol_phases"), inspeccion.get("patrol_speed_scales"),
            expected=ENTIDADES)
        if "error" in veredicto:
            log(f"FALLA vuelta {vuelta}: {veredicto['error']}")
            FALLAS.append(veredicto["error"])
            continue
        log(f"vuelta {vuelta}: {veredicto['fases_distintas']}/{ENTIDADES} fases distintas · "
            f"{veredicto['escalas_distintas']}/{ENTIDADES} escalas distintas · "
            f"rango de fase {veredicto['rango_de_fase']:.3f}")
        exigir(not veredicto["en_fase"],
               f"vuelta {vuelta}: la población NO se mueve en fase")
        exigir(veredicto["fases_distintas"] == ENTIDADES,
               f"vuelta {vuelta}: cada entidad tiene su propia fase")
        exigir(veredicto["escalas_distintas"] == ENTIDADES,
               f"vuelta {vuelta}: cada entidad tiene su propia velocidad")

    if len(lecturas) == 2:
        primera = [round(float(v), 6) for v in (lecturas[0].get("patrol_phases") or [])]
        segunda = [round(float(v), 6) for v in (lecturas[1].get("patrol_phases") or [])]
        exigir(primera == segunda and bool(primera),
               "dos poblaciones sobre los mismos transforms dan las MISMAS fases (determinista)")
        log(f"determinismo: {primera} vs {segunda}")

    log("-" * 70)
    if FALLAS:
        log(f"JAM_MASS_VARIACION_58 ROJO — {len(FALLAS)} falla(s)")
        for falla in FALLAS:
            log(f"  · {falla}")
    else:
        log("JAM_MASS_VARIACION_58 TODO VERDE")


def _terminar() -> None:
    if ESTADO["callback"] is not None:
        unreal.unregister_slate_post_tick_callback(ESTADO["callback"])
        ESTADO["callback"] = None
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def _tick(_delta) -> None:
    try:
        level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        fase = ESTADO["fase"]
        if fase == "iniciar_pie":
            log("=" * 70)
            level.editor_request_begin_play()
            ESTADO["fase"] = "esperar_pie"
            return
        if fase == "esperar_fin":
            if level.is_in_play_in_editor() or unreal.EditorLevelLibrary.get_pie_worlds(False):
                return
            _terminar()
            return
        if time.monotonic() - ESTADO["desde"] > LIMITE_SEGUNDOS:
            raise TimeoutError("PIE no llegó a producir una lectura de variación")

        mundos = unreal.EditorLevelLibrary.get_pie_worlds(False)
        if not mundos:
            return
        mundo = mundos[0]
        ESTADO["ticks"] += 1
        # Unos ticks de margen para que Mass registre sus processors antes de crear la población.
        if ESTADO["ticks"] < 20:
            return

        if ESTADO["vuelta"] < 2:
            # Crear y leer en el MISMO tick da seis ceros: el processor de patrulla todavía no corrió
            # sobre la población recién creada, así que `bInitialized` sigue en false y la fase es su
            # valor por defecto. Hay que devolver el control al motor entre una cosa y la otra.
            if ESTADO.get("pendiente") is None:
                creada = _facts(unreal.JamMassLibrary.spawn_configured_population(
                    mundo, transforms_fijos(), CONFIG))
                if not creada.get("ok") or creada.get("valid") != ENTIDADES:
                    raise RuntimeError(f"la población no nació completa: {creada}")
                ESTADO["pendiente"] = creada["population_id"]
                ESTADO["ticks"] = 0
                return
            if ESTADO["ticks"] < 5:
                return
            inspeccion = _facts(unreal.JamMassLibrary.inspect_population(
                mundo, ESTADO["pendiente"]))
            if inspeccion.get("patrol_initialized") != ENTIDADES:
                raise RuntimeError(
                    f"la patrulla no se inicializó tras varios ticks: {inspeccion}")
            ESTADO["lecturas"].append(inspeccion)
            unreal.JamMassLibrary.clear_population(mundo, ESTADO["pendiente"])
            ESTADO["pendiente"] = None
            ESTADO["vuelta"] += 1
            ESTADO["ticks"] = 0
            return

        medir(mundo)
        level.editor_request_end_play()
        ESTADO["fase"] = "esperar_fin"
    except Exception as exc:  # noqa: BLE001 — el marcador del log es el veredicto
        log(f"JAM_MASS_VARIACION_58 ROJO — {type(exc).__name__}: {exc}")
        try:
            level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
            if level.is_in_play_in_editor():
                level.editor_request_end_play()
        finally:
            ESTADO["fase"] = "esperar_fin"


unreal.EditorPythonScripting.set_keep_python_script_alive(True)
ESTADO["callback"] = unreal.register_slate_post_tick_callback(_tick)
