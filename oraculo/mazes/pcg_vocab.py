"""Vocabulario CANÓNICO de JamPCG-DSL — el lado DEMANDA de la curaduría de assets. Ver [[jampcg-dsl-direction]].

Cierra el conjunto FINITO de tags semánticos que el DSL puede pedir: qué TIPOS de espacio existen (`@space`), qué
TIPOS de sala (`@room_type`) y qué TAGS de prop (`@prop`). Es un ESQUEMA (qué CATEGORÍAS existen y son fabricables),
NO una inyección de layout ([[tipo-de-espacio-semantico]]: 'declara categoría, no diseño'; [[no-injection-free-creation]]):
el DSL sigue libre de colocar DÓNDE quiera, y el oráculo BFS sigue verificando la winnability. El vocabulario sólo
acota QUÉ kinds hay, para que el `manifest` (bind tag→asset) tenga un dominio conocido y la curaduría sepa qué falta.

Disciplina anti-Goodhart: la validación es ADVISORY (reporta lo que cae fuera del vocabulario, como `missing_*` de
`fabricate` — no rompe). Un tag off-vocabulary es una SEÑAL (extendé el vocabulario a propósito, o es ruido), no un
error fatal — nunca bloqueamos que el generador proponga un kind nuevo. La misma fuente alimenta el `SpaceProgram`
(`space_program_for`), así 'qué DEBE tener un hospital' vive en UN solo lugar canónico.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PropTag:
    """Un TAG de prop canónico: su semántica, si BLOQUEA por defecto (una cama ocupa la celda; un cuadro no)
    y su COLOCACIÓN (cómo se orienta/ubica según el contexto de muros de la celda — corte V1 'vestido con
    sentido'). `blocks` es el DEFAULT del vocabulario — el DSL puede override por colocación.
    `placement`:
      - `wall`   = contra un muro, mirando hacia adentro del cuarto (cama, escritorio, gabinete, cartel…)
      - `along`  = sigue el EJE del pasillo (instalaciones de techo: cañería, conducto, bandeja)
      - `ceiling`= centrado al techo (panel de luz)
      - `center` = centrado en la celda, sin orientar (mesa, rejilla de piso)
    `rooms` (corte V2 'densidad por tipo de sala'): tipos de sala donde el prop por DENSIDAD tiene sentido
    (una cañería a la vista corre por el CORREDOR, no por el quirófano; una planta va en el vestíbulo, no en
    el pasillo). Vacío = a cualquier lado (panel de luz, rejilla). Sólo restringe la colocación PROCEDURAL
    (por densidad); los props explícitos `@prop ... at` van donde el DSL diga. Es afinidad de CATEGORÍA
    (semántica del tag), no layout → anti-inyección intacto: el oráculo sigue verificando footprints.
    `procedural` (corte D3): el VISUAL lo fabrica el RECEPTOR desde el contenido (como los cables o la luz de
    los paneles), sin asset del binding → `fabricate` lo deja pasar con mesh=None (no es missing) y el
    gap-report no lo cuenta como gap de curaduría. Si algún día se le bindea un mesh, el binding gana.
    """
    tag: str
    blocks: bool
    desc: str
    placement: str = "center"
    rooms: tuple[str, ...] = ()
    procedural: bool = False


@dataclass(frozen=True)
class SpaceType:
    """Un TIPO de espacio canónico: qué tipos de sala y tags de prop le son PROPIOS, y su PROGRAMA (cantidades
    mínimas por tipo de sala + ADYACENCIAS requeridas que lo hacen un espacio VÁLIDO — la fuente de
    `space_program_for`). `deco` declara el dressing procedural por densidad propio del espacio, siempre
    no-bloqueante. Las adyacencias declaran RELACIONES de categoría ('la enfermería cuida una sala' =
    nurse_station pegada a un ward), no posiciones: el generador elige dónde, el oráculo verifica el grafo."""
    name: str
    desc: str
    room_types: tuple[str, ...]
    props: tuple[str, ...]
    deco: tuple[str, ...] = ()
    required: dict[str, int] = field(default_factory=dict)
    adjacencies: tuple[tuple[str, str], ...] = ()   # pares de tipos que deben quedar pegados (≥1 instancia)
    circulation: tuple[str, ...] = ()               # tipos de circulación: toda otra sala debe tocar uno
    forbidden: tuple[tuple[str, str], ...] = ()      # pares que NO pueden quedar pegados (zonificación)
    access_depth: dict[str, int] = field(default_factory=dict)  # tipo → profundidad mínima desde la
                                                    # entrada (gradiente público→privado)
    ratio: tuple[tuple[str, str, int], ...] = ()     # (servido, por, n): ≥1 servido cada n de por
    zones: dict[str, tuple[str, ...]] = field(default_factory=dict)  # zona (ala) → tipos; zonas
                                                    # distintas no se pegan directo (transición por pasillo)


# ── POOL GLOBAL de TIPOS DE SALA (compartidos entre espacios: un 'entrance' es entrance en todos) ──
ROOM_TYPES: dict[str, str] = {
    # comunes a varios espacios
    "entrance": "acceso/vestíbulo del espacio",
    "hallway": "pasillo de circulación",
    "corridor": "corredor (variante clínica/industrial de hallway)",
    "restroom": "baño / sanitarios",
    "storage": "depósito / almacén",
    "office": "oficina de personal",
    # hospital
    "ward": "sala de internación (camas)",
    "nurse_station": "puesto de enfermería",
    "operating_room": "quirófano",
    "exam_room": "consultorio / sala de examen",
    "waiting_room": "sala de espera",
    # escuela
    "classroom": "aula",
    "laboratory": "laboratorio",
    "gym": "gimnasio",
    "cafeteria": "comedor / cantina",
    "library": "biblioteca",
    # oficina
    "cubicle": "box de trabajo",
    "meeting_room": "sala de reuniones",
    "reception": "recepción",
    "break_room": "sala de descanso",
    "server_room": "sala de servidores",
    # casa
    "bedroom": "dormitorio",
    "kitchen": "cocina",
    "bathroom": "baño (vivienda)",
    "living_room": "living / estar",
    "garage": "garaje",
    "closet": "placard / vestidor",
}


# ── POOL GLOBAL de TAGS DE PROP (compartidos: 'bed' vale para hospital y casa) ──
PROP_TAGS: dict[str, PropTag] = {t.tag: t for t in (
    # mobiliario que OCUPA (footprint bloqueante) → contra un muro (wall) salvo la mesa (center)
    PropTag("bed", True, "cama", placement="wall"),
    PropTag("gurney", True, "camilla", placement="wall"),
    PropTag("desk", True, "escritorio", placement="wall"),
    PropTag("cabinet", True, "armario / gabinete", placement="wall"),
    PropTag("sink", True, "pileta / lavabo", placement="wall"),
    PropTag("table", True, "mesa", placement="center"),
    PropTag("sofa", True, "sofá", placement="wall"),
    PropTag("fridge", True, "heladera", placement="wall"),
    PropTag("stove", True, "cocina (electrodoméstico)", placement="wall"),
    PropTag("shelf", True, "estantería", placement="wall"),
    PropTag("bookshelf", True, "biblioteca (mueble)", placement="wall"),
    PropTag("locker", True, "casillero", placement="wall"),
    PropTag("server_rack", True, "rack de servidores", placement="wall"),
    PropTag("water_cooler", True, "dispenser de agua", placement="wall"),
    PropTag("desk_student", True, "pupitre", placement="center"),
    # decoración que NO bloquea (colgada, plana o esquivable)
    PropTag("monitor", False, "monitor / pantalla de pared", placement="wall"),
    PropTag("iv_stand", False, "portasueros", placement="wall"),
    PropTag("chair", False, "silla", placement="center",
            rooms=("classroom", "meeting_room", "waiting_room", "cafeteria", "break_room", "cubicle", "office")),
    PropTag("chalkboard", False, "pizarrón (de pared)", placement="wall"),
    PropTag("whiteboard", False, "pizarra blanca (de pared)", placement="wall"),
    PropTag("tv", False, "televisor (de pared)", placement="wall"),
    PropTag("plant", False, "planta decorativa", placement="wall",
            rooms=("entrance", "reception", "waiting_room", "living_room", "break_room")),
    PropTag("light_panel", False, "panel de luz (de techo)", placement="ceiling"),   # rooms=() → todo cuarto
    PropTag("sign", False, "cartel / señalética", placement="wall",
            rooms=("corridor", "hallway", "entrance", "reception")),                  # señalética = circulación
    # instalaciones (dressing industrial de época: el look VotV/Half-Life de servicios a la vista) → siguen el
    # pasillo Y sólo aparecen en la CIRCULACIÓN (corredor/hallway), no en salas limpias (quirófano, aula)
    PropTag("pipe", False, "cañería de techo", placement="along", rooms=("corridor", "hallway")),
    PropTag("duct", False, "conducto de ventilación (techo)", placement="along", rooms=("corridor", "hallway")),
    PropTag("vent", False, "rejilla de piso", placement="center"),                    # rejillas = a cualquier lado
    PropTag("cable_tray", False, "bandeja portacables (techo)", placement="along", rooms=("corridor", "hallway")),
    # D3: dressing VERTICAL — columna piso→techo que ata los pisos visualmente (el hueco/escalera deja de ser
    # el único indicio de que hay un arriba). Visual PROCEDURAL del receptor (columna greybox, sin binding).
    PropTag("pipe_vertical", False, "cañería vertical (piso a techo)", placement="wall",
            rooms=("corridor", "hallway"), procedural=True),
)}


# ── ESPACIOS CANÓNICOS (qué salas/props le son propios + su programa mínimo) ──
SPACES: dict[str, SpaceType] = {s.name: s for s in (
    SpaceType(
        "hospital", "centro de salud",
        room_types=("entrance", "corridor", "ward", "nurse_station", "operating_room",
                    "exam_room", "waiting_room", "restroom", "storage", "office"),
        props=("bed", "gurney", "monitor", "iv_stand", "desk", "chair", "cabinet",
               "sink", "sign", "light_panel", "pipe", "duct", "vent", "cable_tray", "pipe_vertical"),
        deco=("light_panel", "pipe", "cable_tray", "sign", "duct", "vent"),
        required={"entrance": 1, "ward": 2, "nurse_station": 1},
        adjacencies=(("nurse_station", "ward"),),   # la enfermería CUIDA una sala: tienen que estar pegadas
        # circulation/forbidden quedan VACÍOS en el canónico por ahora: el hospital RICO que las usa
        # (ver vault SPEC-abstracciones-de-sentido) necesita el generador program-aware para acertarlo
        # a partir de un laberinto. Las abstracciones ya viven en el framework (SpaceProgram) y se testean.
    ),
    SpaceType(
        "school", "establecimiento educativo",
        room_types=("entrance", "hallway", "classroom", "laboratory", "gym",
                    "cafeteria", "library", "office", "restroom", "storage"),
        props=("desk_student", "desk", "chalkboard", "locker", "bookshelf", "table", "chair",
               "cabinet", "monitor", "shelf", "sink", "plant", "sign", "light_panel",
               "pipe", "duct", "vent", "cable_tray", "pipe_vertical"),
        deco=("light_panel", "sign", "vent", "plant"),
        required={"entrance": 1, "classroom": 2},
        adjacencies=(("classroom", "hallway"),),    # un aula da a un pasillo (no un aula-isla)
    ),
    SpaceType(
        "office", "edificio de oficinas",
        room_types=("entrance", "hallway", "reception", "cubicle", "meeting_room",
                    "break_room", "server_room", "restroom", "storage"),
        props=("desk", "chair", "server_rack", "water_cooler", "whiteboard", "cabinet",
               "monitor", "table", "tv", "fridge", "sink", "shelf", "plant", "sign", "light_panel",
               "pipe", "duct", "vent", "cable_tray", "pipe_vertical"),
        deco=("light_panel", "cable_tray", "sign", "vent", "plant"),
        required={"entrance": 1, "reception": 1, "cubicle": 2},
        adjacencies=(("reception", "entrance"),),   # la recepción recibe: pegada al acceso
    ),
    SpaceType(
        "house", "vivienda",
        room_types=("entrance", "hallway", "bedroom", "kitchen", "bathroom",
                    "living_room", "garage", "closet"),
        props=("bed", "sofa", "table", "chair", "fridge", "stove", "sink", "tv",
               "shelf", "cabinet", "plant", "vent"),
        deco=("plant", "vent"),
        required={"bedroom": 1, "kitchen": 1, "bathroom": 1},
    ),
)}


# ── RECETAS DE AMOBLADO por TIPO DE SALA (corte V3 'vestido con sentido') ──
@dataclass(frozen=True)
class RoomRecipe:
    """Receta de amoblado CUARTO-LOCAL: qué props propone un tipo de sala, EN ORDEN (los primeros toman las
    mejores posiciones = paredes lejanas a la circulación). `pairs` = un prop NO-bloqueante que acompaña a cada
    primario (el portasueros junto a la cama, el monitor sobre el escritorio). La receta PROPONE en coords del
    cuarto; el oráculo re-verifica el footprint (`reverify`) → una receta que tapia el cuarto se descarta. Es
    CATEGORÍA/RELACIÓN (qué mobiliario tiene un ward), no layout inyectado ([[no-injection-free-creation]]):
    los items se FILTRAN a la paleta del @space en tiempo de amoblado (una escuela no tiene 'desk', un hospital
    no tiene 'sofa'), y la winnability la sigue decidiendo el BFS."""
    items: tuple[str, ...]                                     # props primarios, en orden de prioridad
    pairs: dict[str, str] = field(default_factory=dict)       # primario → acompañante NO-bloqueante (par semántico)


ROOM_RECIPES: dict[str, RoomRecipe] = {
    # circulación: hallway/corridor quedan sin receta; se visten por densidad/deco del espacio.
    # comunes
    "entrance": RoomRecipe(("plant", "sign")),
    "restroom": RoomRecipe(("sink", "sink", "cabinet")),
    "storage": RoomRecipe(("shelf", "shelf", "cabinet", "locker")),
    "office": RoomRecipe(("desk", "cabinet"), {"desk": "monitor"}),
    # hospital
    "ward": RoomRecipe(("bed", "bed", "bed", "bed", "bed", "bed"), {"bed": "iv_stand"}),  # camas + portasueros
    "exam_room": RoomRecipe(("gurney", "cabinet"), {"gurney": "monitor"}),
    "operating_room": RoomRecipe(("gurney", "cabinet"), {"gurney": "monitor"}),
    "nurse_station": RoomRecipe(("desk", "cabinet"), {"desk": "monitor"}),
    "waiting_room": RoomRecipe(("chair", "chair", "sign")),
    # escuela
    "classroom": RoomRecipe((
        "desk_student", "desk_student", "desk_student", "desk_student",
        "desk_student", "desk_student", "desk_student", "chalkboard",
    ), {"desk_student": "chair"}),
    "laboratory": RoomRecipe(("table", "cabinet"), {"table": "monitor"}),
    "gym": RoomRecipe(("locker", "locker", "locker")),
    "library": RoomRecipe(("bookshelf", "bookshelf", "bookshelf", "bookshelf", "bookshelf", "table"),
                          {"table": "chair"}),
    "cafeteria": RoomRecipe(("table", "table", "table", "table"), {"table": "chair"}),
    # oficina
    "reception": RoomRecipe(("desk",), {"desk": "monitor"}),
    "cubicle": RoomRecipe(("desk", "desk", "desk"), {"desk": "monitor"}),
    "meeting_room": RoomRecipe(("table", "whiteboard"), {"table": "tv"}),
    "break_room": RoomRecipe(("fridge", "table"), {"table": "chair"}),
    "server_room": RoomRecipe(("server_rack", "server_rack", "server_rack",
                               "server_rack", "server_rack", "server_rack")),
    # casa
    "bedroom": RoomRecipe(("bed", "cabinet"), {"bed": "tv"}),
    "kitchen": RoomRecipe(("fridge", "stove", "sink")),
    "bathroom": RoomRecipe(("sink", "cabinet", "shelf")),
    "living_room": RoomRecipe(("sofa", "table"), {"sofa": "tv"}),
    "garage": RoomRecipe(("shelf", "shelf", "cabinet")),
    "closet": RoomRecipe(("shelf", "cabinet", "cabinet")),
}


def recipe_for(room_type: str, space: str | None = None) -> RoomRecipe | None:
    """La receta de un tipo de sala, con sus items/pares FILTRADOS a la paleta del `space` (si se da). Devuelve
    None si el tipo no tiene receta, o si tras filtrar no queda ningún item propio del espacio."""
    r = ROOM_RECIPES.get(room_type)
    if r is None:
        return None
    if space is None or space not in SPACES:
        return r
    palette = set(SPACES[space].props)
    items = tuple(t for t in r.items if t in palette)
    if not items:
        return None
    pairs = {k: v for k, v in r.pairs.items() if k in palette and v in palette}
    return RoomRecipe(items=items, pairs=pairs)


# ── ACCESORES ──
def known_spaces() -> set[str]:
    return set(SPACES)


def known_room_types() -> set[str]:
    return set(ROOM_TYPES)


def known_prop_tags() -> set[str]:
    return set(PROP_TAGS)


def prop_blocks_default(tag: str) -> bool | None:
    """Semántica de bloqueo canónica de un tag (None si el tag no está en el vocabulario)."""
    pt = PROP_TAGS.get(tag)
    return pt.blocks if pt else None


def space_program_for(space: str) -> "Any":
    """Deriva el `SpaceProgram` (gate de `program_satisfied`) desde el vocabulario canónico: 'qué DEBE tener un
    hospital válido' vive acá, no disperso en cada test. `KeyError` si el espacio no está en el vocabulario."""
    from src.mazes.pcg import SpaceProgram
    st = SPACES[space]
    return SpaceProgram(space=st.name, required=dict(st.required), adjacent=tuple(st.adjacencies),
                        circulation=tuple(st.circulation), forbidden=tuple(st.forbidden),
                        access_depth=dict(st.access_depth), ratio=tuple(st.ratio),
                        zones=dict(st.zones))


# ── VALIDACIÓN (advisory: reporta lo que cae fuera del vocabulario, no rompe) ──
def _tags_of(obj: Any) -> list[str]:
    """Tags de prop de un `PcgProgram` (PropRule.tag) o `ContentSpec` (Prop.tag) — ambos exponen `.props[i].tag`."""
    return [p.tag for p in getattr(obj, "props", [])]


def validate_vocabulary(obj: Any) -> dict[str, Any]:
    """¿Todo lo que pide `obj` (un `PcgProgram` o un `ContentSpec`) está en el vocabulario CANÓNICO? Advisory:
    devuelve lo que cae fuera para la CURADURÍA (no bloquea la generación — el norte es crear libre y medir).

    Dos niveles: `unknown_*` = tag/tipo que NO existe en el pool global (candidato a agregar al vocabulario, o
    ruido); `off_space_*` = existe en el pool pero NO figura entre los propios del `@space` declarado (mezcla
    inusual — legítima al componer ciudades, pero se marca). `ok` = no hay `unknown_*` (el vocabulario está cerrado)."""
    space = getattr(obj, "space", None)
    room_types = set(getattr(obj, "room_types", {}).values())
    prop_tags = set(_tags_of(obj))

    unknown_space = bool(space) and space not in SPACES
    unknown_room_types = sorted(room_types - known_room_types())
    unknown_prop_tags = sorted(prop_tags - known_prop_tags())

    off_space_room_types: list[str] = []
    off_space_prop_tags: list[str] = []
    if space in SPACES:                                   # con un @space válido, marcar lo ajeno a ese espacio
        st = SPACES[space]
        off_space_room_types = sorted((room_types & known_room_types()) - set(st.room_types))
        off_space_prop_tags = sorted((prop_tags & known_prop_tags()) - set(st.props))

    ok = not (unknown_space or unknown_room_types or unknown_prop_tags)
    return {
        "ok": ok, "space": space, "unknown_space": unknown_space,
        "unknown_room_types": unknown_room_types, "unknown_prop_tags": unknown_prop_tags,
        "off_space_room_types": off_space_room_types, "off_space_prop_tags": off_space_prop_tags,
    }
