"""Contratos puros de MassEntity: receta durable y handle efímero de población."""

from __future__ import annotations

from dataclasses import dataclass
import math


MAX_ENTITIES = 4096
POSITION_TOLERANCE_CM = 0.001
UNLIMITED_LOD_COUNT = 2_147_483_647


@dataclass(frozen=True)
class MassProbeBatch:
    """Frames validados que el adaptador traduce a ``FTransform``."""

    frames: tuple
    position_sum: tuple[float, float, float]

    def __len__(self) -> int:
        return len(self.frames)


@dataclass(frozen=True)
class MassSpec:
    """Receta durable MS; no contiene handles ni objetos de Unreal."""

    frames: tuple
    config_path: str | None
    seed: int
    budget: int
    position_sum: tuple[float, float, float]
    representation: str | None = None
    behavior: str | None = None

    def __len__(self) -> int:
        return len(self.frames)


@dataclass(frozen=True)
class MassHandle:
    """Referencia MH a una población viva; sólo tiene sentido dentro de su mundo."""

    population_id: str
    world_id: str
    requested: int
    position_sum: tuple[float, float, float]
    representation: str | None = None
    behavior: str | None = None


@dataclass(frozen=True)
class MassConfig:
    """Referencia durable MC a un ``UMassEntityConfigAsset`` ya validado."""

    config_path: str
    representation: str | None = None
    mesh_paths: tuple[str, ...] = ()
    lod_distances: tuple[float, ...] = ()
    lod_max_counts: tuple[int, ...] = ()
    behavior: str | None = None
    patrol_speed: float | None = None
    patrol_radius: float | None = None
    patrol_variation: float | None = None


def make_config(config_path, facts: dict, *, require_ism=False,
                require_lod_budget=False, require_patrol=False,
                require_variation=False) -> dict:
    """Publica MC sólo si MassGameplay resolvió un template espacial válido."""
    ruta = str(config_path or "").strip()
    if not ruta.startswith("/") or "." not in ruta.rsplit("/", 1)[-1]:
        return {"error": "mass_config necesita la ruta de objeto completa de un asset Mass."}
    if not isinstance(facts, dict) or not facts.get("ok"):
        return {"error": str(facts.get("error") if isinstance(facts, dict)
                             else "MassGameplay no devolvió hechos de configuración")}
    defects = []
    if facts.get("config_path") != ruta:
        defects.append("config_path no coincide con el asset pedido")
    if not facts.get("template_valid"):
        defects.append("el template Mass no es válido")
    if not facts.get("has_transform"):
        defects.append("el template no contiene FTransformFragment")
    if not isinstance(facts.get("trait_count"), int) or facts["trait_count"] < 1:
        defects.append("la configuración no contiene traits")

    representation = None
    mesh_paths = tuple(str(path) for path in facts.get("mesh_paths", ()) if path)
    raw_distances = facts.get("lod_distances", ())
    lod_distances = tuple(float(value) for value in raw_distances
                          if isinstance(value, (int, float)))
    expected_lod = ("StaticMeshInstance", "StaticMeshInstance", "StaticMeshInstance", "None")
    lod_representation = tuple(facts.get("lod_representation", ()))
    raw_max_counts = facts.get("lod_max_counts", ())
    valid_max_counts = (isinstance(raw_max_counts, (list, tuple))
                        and len(raw_max_counts) == 4
                        and all(isinstance(value, int) and not isinstance(value, bool)
                                and 0 <= value <= UNLIMITED_LOD_COUNT
                                for value in raw_max_counts))
    lod_max_counts = tuple(raw_max_counts) if valid_max_counts else ()
    visual_defects = []
    if not facts.get("has_representation"):
        visual_defects.append("el template no contiene FMassRepresentationFragment")
    if not facts.get("has_lod") or not facts.get("has_viewer"):
        visual_defects.append("el template no contiene el contrato LOD/viewer")
    if not facts.get("has_actor_fragment"):
        visual_defects.append("el template no contiene FMassActorFragment")
    if not mesh_paths:
        visual_defects.append("la representación no contiene Static Mesh")
    if lod_representation != expected_lod:
        visual_defects.append("los LOD no siguen ISM/ISM/ISM/None")
    if (len(lod_distances) != 4 or not all(math.isfinite(value) for value in lod_distances)
            or lod_distances[0] != 0.0
            or not all(a < b for a, b in zip(lod_distances, lod_distances[1:]))):
        visual_defects.append("las distancias LOD no son 0 < Medium < Low < Off")
    ism_defects = list(visual_defects)
    if not facts.get("stationary"):
        ism_defects.append("la representación no es Stationary")
    if not ism_defects:
        representation = "ism"

    behavior = None
    patrol_speed = facts.get("patrol_speed")
    patrol_radius = facts.get("patrol_radius")
    patrol_variation = facts.get("patrol_variation")
    patrol_defects = list(visual_defects)
    if not facts.get("moving_ism"):
        patrol_defects.append("la patrulla no usa una representación ISM dinámica")
    if not facts.get("has_patrol"):
        patrol_defects.append("el template no contiene la patrulla ambiental")
    for name, value in (("velocidad", patrol_speed), ("radio", patrol_radius)):
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or not math.isfinite(float(value)) or float(value) <= 0.0):
            patrol_defects.append(f"la patrulla necesita {name} positiva y finita")
    # La variación se juzga aparte de la patrulla: una población en fase es una patrulla VÁLIDA,
    # sólo que se mueve como una formación. Exigirla siempre rompería la Fase 4 anterior, que quedó
    # verde sin ella; mezclarlas en el mismo requisito borraría esa distinción.
    variation_defects = []
    if (not isinstance(patrol_variation, (int, float)) or isinstance(patrol_variation, bool)
            or not math.isfinite(float(patrol_variation))):
        variation_defects.append("la variación de patrulla debe ser un número finito")
    elif not 0.0 <= float(patrol_variation) <= 1.0:
        variation_defects.append("la variación de patrulla debe estar entre 0 y 1")
    elif float(patrol_variation) <= 0.0:
        variation_defects.append(
            "la variación de patrulla es 0: toda la población se mueve en fase, como una formación")

    if not patrol_defects:
        representation = "ism_dynamic"
        behavior = "patrol"
        patrol_speed = float(patrol_speed)
        patrol_radius = float(patrol_radius)
    if require_ism:
        defects.extend(ism_defects)
    if require_lod_budget:
        if ism_defects:
            defects.extend(defect for defect in ism_defects if defect not in defects)
        if not valid_max_counts:
            defects.append("el presupuesto LOD necesita cuatro máximos enteros no negativos")
        elif (lod_max_counts[3] != UNLIMITED_LOD_COUNT
              or any(value == UNLIMITED_LOD_COUNT for value in lod_max_counts[:3])):
            defects.append("el presupuesto LOD debe acotar High/Medium/Low y dejar Off ilimitado")
    if require_patrol:
        defects.extend(defect for defect in patrol_defects if defect not in defects)
    if require_variation:
        defects.extend(defect for defect in patrol_defects if defect not in defects)
        defects.extend(defect for defect in variation_defects if defect not in defects)
    if defects:
        return {"error": "; ".join(defects)}
    return {"config": MassConfig(
        config_path=ruta,
        representation=representation,
        mesh_paths=mesh_paths,
        lod_distances=lod_distances,
        lod_max_counts=lod_max_counts,
        behavior=behavior,
        patrol_speed=patrol_speed if behavior else None,
        patrol_radius=patrol_radius if behavior else None,
        patrol_variation=(float(patrol_variation)
                          if behavior and not variation_defects else None),
    )}


def prepare(frame_set) -> dict:
    """Valida el dato F sin importar Unreal y construye la entrada acotada de la sonda."""
    from .curve import FrameSet

    if not isinstance(frame_set, FrameSet) or not frame_set.frames:
        return {"error": "mass_probe necesita un stream F válido y no vacío."}
    if len(frame_set.frames) > MAX_ENTITIES:
        return {"error": f"mass_probe no puede crear más de {MAX_ENTITIES} entidades."}

    sums = [0.0, 0.0, 0.0]
    for index, frame in enumerate(frame_set.frames):
        values = (*frame.position, *frame.tangent, *frame.outward, frame.scale)
        if len(frame.position) != 3 or len(frame.tangent) != 3 or len(frame.outward) != 3:
            return {"error": f"el frame {index} no tiene vectores de tres componentes."}
        try:
            values = tuple(float(value) for value in values)
        except (TypeError, ValueError):
            return {"error": f"el frame {index} contiene un valor no numérico."}
        if not all(math.isfinite(value) for value in values):
            return {"error": f"el frame {index} contiene un valor no finito."}
        if float(frame.scale) <= 0.0:
            return {"error": f"el frame {index} tiene escala no positiva."}
        for axis in range(3):
            sums[axis] += float(frame.position[axis])

    return {"batch": MassProbeBatch(tuple(frame_set.frames), tuple(sums))}


def make_spec(frame_set, *, config=None, config_path="", seed=7, budget=MAX_ENTITIES) -> dict:
    """Construye MS con límites explícitos y una configuración MC opcional."""
    try:
        budget = int(budget)
        seed = int(seed)
    except (TypeError, ValueError):
        return {"error": "mass_spec necesita seed y presupuesto enteros."}
    if budget < 1 or budget > MAX_ENTITIES:
        return {"error": f"mass_spec exige un presupuesto entre 1 y {MAX_ENTITIES}."}
    prepared = prepare(frame_set)
    if "error" in prepared:
        return {"error": prepared["error"].replace("mass_probe", "mass_spec")}
    batch = prepared["batch"]
    if len(batch) > budget:
        return {"error": f"mass_spec recibió {len(batch)} frames para un presupuesto de {budget}."}
    if config not in (None, "") and not isinstance(config, MassConfig):
        return {"error": "mass_spec necesita un MC válido en config."}
    ruta_legacy = str(config_path or "").strip() or None
    ruta_mc = config.config_path if isinstance(config, MassConfig) else None
    if ruta_mc and ruta_legacy and ruta_mc != ruta_legacy:
        return {"error": "mass_spec recibió dos configuraciones Mass distintas."}
    ruta = ruta_mc or ruta_legacy
    representation = config.representation if isinstance(config, MassConfig) else None
    behavior = config.behavior if isinstance(config, MassConfig) else None
    return {"spec": MassSpec(
        batch.frames, ruta, seed, budget, batch.position_sum, representation, behavior)}


def handle_from_spawn(spec: MassSpec, facts: dict) -> dict:
    """Valida la creación real y recién entonces publica un MH."""
    if not isinstance(facts, dict) or not facts.get("ok"):
        return {"error": str(facts.get("error") if isinstance(facts, dict) else
                             "el puente Mass no devolvió hechos")}
    defects = []
    for field, expected in (("requested", len(spec)), ("created", len(spec)),
                            ("valid", len(spec))):
        if facts.get(field) != expected:
            defects.append(f"{field}={facts.get(field)!r}, esperado {expected}")
    population_id = str(facts.get("population_id") or "")
    world_id = str(facts.get("world_id") or "")
    if not population_id:
        defects.append("population_id vacío")
    if not world_id:
        defects.append("world_id vacío")
    if spec.config_path:
        if facts.get("config_path") != spec.config_path:
            defects.append("config_path no coincide con MS")
        if facts.get("spawner_class") != "JamMassSpawner":
            defects.append("la población configurada no nació mediante JamMassSpawner")
    if defects:
        return {"error": "; ".join(defects)}
    return {"handle": MassHandle(
        population_id, world_id, len(spec), spec.position_sum,
        spec.representation, spec.behavior)}


def judge_inspect(handle: MassHandle, facts: dict) -> dict:
    """Juzga identidad, mundo, cantidad y transforms de una población todavía viva."""
    if not isinstance(facts, dict) or not facts.get("ok"):
        return {"ok": False, "defects": [str(
            facts.get("error") if isinstance(facts, dict) else "inspección Mass sin hechos")]}
    defects = []
    expected = {
        "population_id": handle.population_id,
        "world_id": handle.world_id,
        "requested": handle.requested,
        "valid": handle.requested,
    }
    if handle.behavior is None:
        expected["transform_mismatches"] = 0
    for field, value in expected.items():
        if facts.get(field) != value:
            defects.append(f"{field}={facts.get(field)!r}, esperado {value!r}")
    if handle.behavior is None:
        for axis, value in zip("xyz", handle.position_sum):
            observed = facts.get(f"observed_sum_{axis}")
            if not isinstance(observed, (int, float)) or abs(observed - value) > POSITION_TOLERANCE_CM:
                defects.append(f"observed_sum_{axis} no conserva los fragments")
    if handle.representation in ("ism", "ism_dynamic"):
        for field in ("representation_fragments", "lod_fragments", "mesh_desc_valid"):
            if facts.get(field) != handle.requested:
                defects.append(f"{field}={facts.get(field)!r}, esperado {handle.requested}")
    if handle.behavior == "patrol":
        for field in ("patrol_fragments", "patrol_initialized", "patrol_moved"):
            if facts.get(field) != handle.requested:
                defects.append(f"{field}={facts.get(field)!r}, esperado {handle.requested}")
        if facts.get("patrol_out_of_bounds") != 0:
            defects.append("la patrulla salió de su radio")
    return {"ok": not defects, "defects": defects,
            "info": (f"{handle.requested} entidades vivas · "
                     f"{'patrulla acotada' if handle.behavior == 'patrol' else 'transforms conservados'}")}


def judge_clear(handle: MassHandle, facts: dict) -> dict:
    """Exige que Clear deje cero entidades válidas; repetirlo puede ser idempotente."""
    if not isinstance(facts, dict) or not facts.get("ok"):
        return {"ok": False, "defects": [str(
            facts.get("error") if isinstance(facts, dict) else "limpieza Mass sin hechos")]}
    defects = []
    if facts.get("population_id") != handle.population_id:
        defects.append("la limpieza respondió por otra población")
    if facts.get("world_id") != handle.world_id:
        defects.append("la limpieza respondió por otro mundo")
    if facts.get("valid_after") != 0:
        defects.append(f"valid_after={facts.get('valid_after')!r}, esperado 0")
    valid_before = facts.get("valid_before")
    if valid_before not in (0, handle.requested):
        defects.append(f"valid_before={valid_before!r}, esperado 0 o {handle.requested}")
    return {"ok": not defects, "defects": defects,
            "info": f"{valid_before or 0} entidades destruidas · 0 vivas"}


def judge(batch: MassProbeBatch, facts: dict) -> dict:
    """Juzga hechos del puente C++; nunca consulta el mundo por su cuenta."""
    if not isinstance(facts, dict):
        return {"ok": False, "defects": ["el puente Mass no devolvió hechos"]}
    if not facts.get("ok"):
        return {"ok": False, "defects": [str(facts.get("error") or "MassEntity falló")]}

    count = len(batch)
    defects = []
    expected_counts = {
        "requested": count,
        "created": count,
        "valid_before": count,
        "same_archetype": count,
        "transform_mismatches": 0,
        "valid_after": 0,
    }
    for field, expected in expected_counts.items():
        if facts.get(field) != expected:
            defects.append(f"{field}={facts.get(field)!r}, esperado {expected}")

    for axis, expected in zip("xyz", batch.position_sum):
        input_value = facts.get(f"input_sum_{axis}")
        observed = facts.get(f"observed_sum_{axis}")
        if not isinstance(input_value, (int, float)) or abs(input_value - expected) > POSITION_TOLERANCE_CM:
            defects.append(f"input_sum_{axis} no conserva la entrada")
        if not isinstance(observed, (int, float)) or abs(observed - expected) > POSITION_TOLERANCE_CM:
            defects.append(f"observed_sum_{axis} no conserva los fragments")

    return {
        "ok": not defects,
        "defects": defects,
        "info": (f"{count} entidades · 1 arquetipo · transforms conservados · "
                 "limpieza completa"),
    }


def judge_variation(phases, speed_scales, *, expected: int) -> dict:
    """¿La población se mueve como una multitud o como una formación?

    Que las entidades se muevan no alcanza: con la fase en cero todas salen juntas, llegan al
    extremo en el mismo frame y vuelven juntas. Eso se ve como una coreografía y es el defecto que
    esta medida existe para atrapar.

    Se juzgan las listas crudas, no un promedio: la media de un conjunto de fases idénticas es
    perfectamente razonable y escondería exactamente el caso que importa.
    """
    if not isinstance(phases, list) or not isinstance(speed_scales, list):
        return {"error": "la variación necesita las listas de fases y escalas"}
    if len(phases) != expected or len(speed_scales) != expected:
        return {"error": (f"se esperaban {expected} fases y escalas, "
                          f"llegaron {len(phases)} y {len(speed_scales)}")}
    for nombre, valores in (("fase", phases), ("escala", speed_scales)):
        for valor in valores:
            if (not isinstance(valor, (int, float)) or isinstance(valor, bool)
                    or not math.isfinite(float(valor))):
                return {"error": f"una {nombre} no es un número finito: {valor!r}"}

    fases = [float(valor) for valor in phases]
    escalas = [float(valor) for valor in speed_scales]
    # Se cuentan valores DISTINTOS y no una desviación: con dos entidades una desviación no
    # significa gran cosa, mientras que "cuántas comparten fase" se lee igual con 2 que con 2000.
    fases_distintas = len({round(valor, 4) for valor in fases})
    escalas_distintas = len({round(valor, 4) for valor in escalas})
    return {
        "fases_distintas": fases_distintas,
        "escalas_distintas": escalas_distintas,
        "rango_de_fase": max(fases) - min(fases) if fases else 0.0,
        "en_fase": fases_distintas <= 1 and len(fases) > 1,
        "fases": fases,
        "escalas": escalas,
    }
