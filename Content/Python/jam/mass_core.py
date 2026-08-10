"""Contratos puros de MassEntity: receta durable y handle efímero de población."""

from __future__ import annotations

from dataclasses import dataclass
import math


MAX_ENTITIES = 4096
POSITION_TOLERANCE_CM = 0.001


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

    def __len__(self) -> int:
        return len(self.frames)


@dataclass(frozen=True)
class MassHandle:
    """Referencia MH a una población viva; sólo tiene sentido dentro de su mundo."""

    population_id: str
    world_id: str
    requested: int
    position_sum: tuple[float, float, float]


@dataclass(frozen=True)
class MassConfig:
    """Referencia durable MC a un ``UMassEntityConfigAsset`` ya validado."""

    config_path: str


def make_config(config_path, facts: dict) -> dict:
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
    if defects:
        return {"error": "; ".join(defects)}
    return {"config": MassConfig(ruta)}


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
    return {"spec": MassSpec(batch.frames, ruta, seed, budget, batch.position_sum)}


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
    return {"handle": MassHandle(population_id, world_id, len(spec), spec.position_sum)}


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
        "transform_mismatches": 0,
    }
    for field, value in expected.items():
        if facts.get(field) != value:
            defects.append(f"{field}={facts.get(field)!r}, esperado {value!r}")
    for axis, value in zip("xyz", handle.position_sum):
        observed = facts.get(f"observed_sum_{axis}")
        if not isinstance(observed, (int, float)) or abs(observed - value) > POSITION_TOLERANCE_CM:
            defects.append(f"observed_sum_{axis} no conserva los fragments")
    return {"ok": not defects, "defects": defects,
            "info": f"{handle.requested} entidades vivas · transforms conservados"}


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
