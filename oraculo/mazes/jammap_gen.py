"""Generación de JamMaps con ORÁCULO-EN-EL-LOOP (habilidad A, estilo ReAct / SG-Agent).

El LLM PROPONE un JamMap (el DSL de Capa 0, posiblemente COMPUESTO: escaleras/portales/gravedad/
multi-piso, según el vocabulario elegido para la corrida), el ORÁCULO lo VERIFICA (`parse` + `solve_3d`),
y si falla se le devuelve el ERROR DEL PROPIO JUEGO para que reintente. Anti-inyección
([[no-injection-free-creation]]): el feedback es la regla verificable (no parsea / no es ganable),
NUNCA diseño inyectado — el LLM crea libre dentro del vocabulario y el BFS mide.

Espeja el loop 2D de `layer0/loop.py` (`_gen_maze`/`eval_maze`/`_create_verify_one`) pero sobre el grafo
3D (`Maze3D`) y el DSL JamMap. El `client` (LLM) se inyecta → el loop se testea con un cliente falso;
una corrida real le pasa `llm.make_client(...)`.
"""
from __future__ import annotations

import asyncio
from typing import Any

from oraculo.mazes.ascii_map import parse, parse_space, render
from oraculo.mazes.couple import (
    coupling_necessity,
    parse_consumes,
    parse_power_couplings,
    powered_horizon_necessity,
    powered_survival_horizon,
    powered_survival_necessity,
    solve_coupled,
    solve_powered_survival,
)
from oraculo.mazes.electric import parse_electric_channel, render_electric_channel
from oraculo.mazes.jammap_grammar import conforms
from oraculo.mazes.maze3d import GOAL, PLAYER, maze3d_descriptors, solve_3d
from oraculo.mazes.resource import (
    ResourceChannel,
    ResourceSpec,
    evaluate_channel,
    parse_resource_channel,
    render_resource_channel,
)


def _count_char(maze, ch: str) -> int:
    return sum(row.count(ch) for floor in maze.floors for row in floor)


# Piso de largo del gate de interés: aunque una mecánica sea NECESARIA, un nivel CHICO no es un juego.
# Antes era 4 (el mínimo donde cabe un desvío contrafáctico), pero el generador abusaba de mapas diminutos
# (cuartitos de 4-5 pasos). Subido a 8 para forzar VIAJE — niveles amplios, no puzzles de un par de pasos.
# El feedback `too_short` le pide al LLM agrandar y alejar la meta. [[entretenido-necesidad-contrafactual]]
MIN_INTERESTING_STEPS = 8

# Vocabulario de elementos componibles: cada corrida DECLARA cuáles están disponibles (la intención),
# y el LLM los usa libremente. Base (#/./@/G) siempre. El doc se inyecta al prompt.
ELEMENT_DOCS = {
    "stairs": ("Escaleras DIRECCIONALES (suben un piso): '^' sube al norte, 'v' al sur, '>' al este, "
               "'<' al oeste. El tope queda DIAGONAL-ARRIBA y en el piso de arriba se marca con un hueco "
               "'o' (¡ponelo! es donde llega la escalera). OJO: la escalera abre un POZO ('O') en la celda "
               "JUSTO ENCIMA de su base (hueco de escalera) — esa celda NO se puede pisar en el piso de "
               "arriba (te caés), así que NO pongas el camino crítico ahí; rodealo. 'H' = conector vertical recto."),
    "portals": ("Portales (arista entre celdas ARBITRARIAS, incluso de otro piso). Se declaran en "
                "CABECERA, antes de los pisos: '@portal x,y,z -> x,y,z' (bidireccional) o "
                "'@portal x,y,z -> x,y,z one_way'."),
    "gravity": ("Gravedad (mapas no-euclidianos): '~' marca una ZONA de caída. Al entrar caés CONTINUO "
                "en la dirección de la gravedad hasta una superficie (no una celda, hasta el fondo). Por "
                "default cae hacia ABAJO (al piso de abajo). Para otra dirección (flip no-euclidiano): "
                "cabecera '@gravity x,y,z up|north|south|east|west'."),
    "keys": ("Llaves y puertas (progresión tipo Valve): una LLAVE es una letra MINÚSCULA (a, b, c…) que "
             "agarrás al pisarla; una PUERTA es la MISMA letra en MAYÚSCULA (A, B, C…) y sólo la cruzás si "
             "ya tenés su llave. Poné la llave ANTES de su puerta en el camino, o el nivel no se puede ganar."),
    "switches": ("Botones y compuertas remotas (tipo Half-Life): un BOTÓN es '&' y una COMPUERTA es '='. "
                 "El botón prende un flag de mundo que abre su compuerta REMOTA (mismo flag). El cableado va "
                 "en CABECERA: '@switch x,y,z f1' (el botón) y '@gate x,y,z f1' (la compuerta del mismo flag). "
                 "El jugador tiene que pisar el botón antes de poder cruzar la compuerta."),
    "ladder": ("Escalera VERTICAL trepable (estilo terraza): 'I' sube RECTO al mismo (x,y) del piso de "
               "arriba (la trepás de frente). El tope, en el piso de arriba, se marca con el hueco 'o'. "
               "Distinta de '^v<>' (que suben en diagonal) y de 'H' (rampa): la 'I' es vertical."),
    "conduit": ("Conducto / vent (tipo Half-Life): 'c' es un pasaje de TECHO BAJO por el que hay que "
                "AGACHARSE para pasar. Es una celda transitable normal (no bloquea el camino), pero da "
                "exploración y atajos bajos. Poné varias 'c' en fila para un túnel angosto."),
    "hazard": ("Trampa MORTAL: 'X' es una celda que mata si la pisás (¡perdés!). El camino tiene que "
               "ESQUIVARLA — dejá siempre una ruta segura hasta G. Opcional condicional tipo Half-Life: "
               "cabecera '@hazard x,y,z f1' la vuelve mortal SÓLO mientras el flag f1 esté apagado; un "
               "botón '&' (@switch ... f1) la DESARMA. Sin cabecera, la 'X' es mortal siempre."),
    "seams": ("Costura IMPOSIBLE (espacio NO-EUCLIDIANO, tipo Antichamber/Backrooms): une dos celdas como "
              "si fueran CONTINUAS (caminás y emergés sin corte) en una dirección. Cabecera: "
              "'@seam x,y,z -> x,y,z north|south|east|west|up|down'. Si esa continuidad CONTRADICE la "
              "grilla (cerrás un loop y volvés desplazado), el espacio se vuelve imposible de dibujar plano "
              "— eso es lo bueno. Marcador visual '%' en ambos extremos. La winnability la mide el BFS igual."),
    "resource": ("Recursos / SUPERVIVENCIA (tipo VotV/Penumbra): además de la estructura, el jugador debe "
                 "SOSTENER un presupuesto. Declarás un canal APARTE '[Recurso 0]' (después de los pisos) con "
                 "directivas: '@drain <rec> <n>' (se gasta por paso) · '@cap <rec> <n>' (tope) · "
                 "'@start <rec> <n>' (inicial) · '@budget <rec> >= <lo> over days=<N>' (GANAR = sobrevivir N "
                 "pasos manteniendo <rec> >= <lo>) · '@source x,y,z <rec> +<delta>' (celda que recarga: comida/"
                 "generador). Poné SUFICIENTES @source (y bien ubicadas) para que se PUEDA sobrevivir los N "
                 "pasos — pero no de más: si sobra sin las fuentes, no cuenta."),
    "electric": ("Energía / POTENCIA (tipo VotV: el generador alimenta la puerta del server). Canal APARTE "
                 "'[Electrico N]' (mismo tamaño y coords que el [Piso N]) con su grilla de CABLES: 'S'=fuente "
                 "de energía · 'L'=carga (lámpara/equipo) · '-' '|' '+'=cable · '.'/'#'=sin cable. Una carga "
                 "está alimentada sólo si un camino de cables la une a una 'S'. ACOPLE con la navegación: "
                 "'@power x,y,z <flag>' = la carga en (x,y,z), si está alimentada, prende <flag>; una compuerta "
                 "'@gate cx,cy,cz <flag>' abre sólo con ese flag → para cruzarla, el cableado TIENE que alimentar "
                 "la carga (si no, el nivel no se gana). Dos vías: '@breaker x,y,z <flag>' = un tramo de cable "
                 "que conduce sólo si el jugador prendió antes un '@switch ... <flag>' (cerrá el breaker para "
                 "energizar). NO dejes el switch del breaker detrás de la compuerta que él mismo alimenta (deadlock). "
                 "Si además hay canal '[Recurso 0]', podés ACOPLARLOS: '@consume x,y,z <rec> <delta>' = la carga en "
                 "(x,y,z), MIENTRAS está alimentada, gasta <delta> del recurso por paso (negativo = quema fuel/"
                 "refrigerante; el server encendido cuesta) — así prender el server para abrir la compuerta CUESTA. "
                 "SOBRECARGA (opcional): '@capacity x,y,z <n>' = la fuente 'S' en (x,y,z) abastece capacidad <n>; "
                 "'@demand x,y,z <n>' = la carga 'L' consume <n> (default 1). Si un circuito cuya 'S' tiene "
                 "'@capacity' pide MÁS de lo que da, la PROTECCIÓN por sobrecarga DESENERGIZA todo ese circuito "
                 "(como un fusible que se corta) — repartí las cargas entre varias fuentes o subí la capacidad. "
                 "'@priority x,y,z <n>' (opcional) = prioridad de una carga (mayor = más importante): si el circuito "
                 "se sobrecarga y hay prioridades, en vez de apagarse entero hace LOAD-SHEDDING (mantiene las cargas "
                 "de mayor prioridad que entran en la capacidad y tira las demás) — así una carga crítica sigue "
                 "alimentada aunque una decorativa se caiga."),
}
ELEMENTS = tuple(ELEMENT_DOCS)

# Ejemplos few-shot por elemento (VERIFICADOS ganables). Enseñan el FORMATO del DSL, no la solución
# (el modelo hace otro distinto). Sin ellos qwen3-coder casi no compone (medido: 0/3 → 1/3 con stairs).
_EX_STAIRS = ["[Piso 0]", "####", "#@.#", "#^.#", "####",
              "[Piso 1]", "####", "#oG#", "#..#", "####"]   # 'o' = hueco donde llega el '^' de abajo
_EX_PORTAL = ["@portal 1,1,0 -> 3,1,0",
              "[Piso 0]", "#######", "#@#..G#", "#######"]
_EX_GRAVITY = ["[Piso 0]", "####", "#G.#", "####",
               "[Piso 1]", "####", "#@~#", "####"]
_EX_KEYS = ["[Piso 0]", "#######", "#@a.AG#", "#######"]   # llave 'a' antes de la puerta 'A' que tapa G
_EX_SWITCH = ["@switch 2,1,0 f1", "@gate 4,1,0 f1",
              "[Piso 0]", "#######", "#@&.=G#", "#######"]   # botón '&' prende f1 → abre la compuerta '='
_EX_HAZARD = ["[Piso 0]", "#####", "#@..#", "#.X.#", "#..G#", "#####"]   # 'X' mortal: el camino la esquiva
_EX_LADDER = ["[Piso 0]", "####", "#@I#", "####",
              "[Piso 1]", "####", "#oG#", "####"]   # 'I' = escalera vertical; 'o' = hueco donde llega arriba
_EX_CONDUIT = ["[Piso 0]", "#######", "#@cccG#", "#######"]   # túnel bajo de conductos 'c' (se cruza agachado)
_EX_SEAM = ["@seam 1,1,0 -> 3,1,0 east",
            "[Piso 0]", "#####", "#@.G#", "#####"]   # costura: hay camino normal Y la costura cierra un loop imposible (no-euclidiano)
_EX_RESOURCE = ["[Piso 0]", "#########", "#@.....G#", "#########",
                "[Recurso 0]", "@drain hambre 1", "@cap hambre 8", "@start hambre 6",
                "@budget hambre >= 1 over days=10",
                "@source 4,1,0 hambre +6"]   # fuente sostenible → se sobrevive ≥10 pasos (oscilando cerca de la comida)
_EX_ELECTRIC = ["[Piso 0]", "###########", "#@.......G#", "###########",
                "@gate 5,1,0 server",
                "[Electrico 0]", "###########", "#S-------L#", "###########",
                "@power 9,1,0 server"]   # el generador S alimenta L(9)→prende 'server'→abre la compuerta(5)→se llega a G


def build_jammap_prompt(*, elements: tuple[str, ...] = (), n_floors: int = 1,
                        idx: int = 0, feedback: str | None = None,
                        context_dsls: tuple[str, ...] = (), survive_days: int = 0,
                        space: str | None = None) -> tuple[str, str]:
    """Arma (system, user) para que el LLM genere un JamMap ganable con el vocabulario dado.
    `elements` = subconjunto de ELEMENTS habilitado para la corrida (declara la intención, no la solución).
    `survive_days` > 0 = la corrida EXIGE supervivencia: el LLM debe agregar un canal '[Recurso 0]' que se
    pueda sobrevivir ese nº de pasos (gateado por el oráculo de recurso).
    `space` = la corrida declara el TIPO de espacio (hospital/school/…): el esqueleto se genera SABIENDO
    qué va a ser (mismo anti-inyección que elements: declara categoría con gate verificable, no layout)."""
    lines = [
        "Sos un diseñador de niveles. Escribís SOLO en JamMap (un DSL de mapa), sin prosa.",
        "",
        "JamMap describe un nivel como pisos de grilla ASCII. Glifos base:",
        "  #=muro  .=pasillo  @=player (EXACTAMENTE uno)  G=meta (EXACTAMENTE una)",
        "Formato (un bloque [Piso N] por piso; las filas SOLO con glifos). Hacé niveles AMPLIOS, así:",
        "  [Piso 0]",
        "  #########",
        "  #@......#",
        "  #.#####.#",
        "  #.....#.#",
        "  #####.#.#",
        "  #.....#.#",
        "  #.#####.#",
        "  #......G#",
        "  #########",
    ]
    enabled = [e for e in elements if e in ELEMENT_DOCS]
    if enabled:
        lines.append("")
        lines.append("Elementos disponibles en esta corrida (usalos si aportan, no es obligatorio):")
        lines += [f"  - {ELEMENT_DOCS[e]}" for e in enabled]
    lines += [
        "",
        "REGLAS: EXACTAMENTE un @ y una G en TODO el mapa (no una por piso); el nivel DEBE ser GANABLE "
        "(un camino transitable de @ a G).",
        "TAMAÑO: hacé un nivel AMPLIO — grilla de al menos 9x9 celdas por piso, con un camino a la meta "
        "de 10 pasos o MÁS (poné @ y G LEJOS, con pasillos y recovecos). NO hagas cuartitos de 3x3 o 5x5: "
        "un nivel chico es ABURRIDO y lo voy a rechazar.",
    ]
    if enabled and n_floors > 1:
        lines.append("Si usás varios pisos, CONECTALOS con escaleras (^v<>) o portales; un piso sin "
                     "conexión es inalcanzable. Poné @ y G en pisos distintos para forzar el viaje.")
    if survive_days > 0:
        lines.append("")
        lines.append(f"SUPERVIVENCIA OBLIGATORIA en esta corrida: agregá un canal '[Recurso 0]' (después de "
                     f"los pisos) y hacé que el nivel se pueda SOBREVIVIR al menos {survive_days} pasos con "
                     f"'@budget <rec> >= 1 over days={survive_days}'. Ubicá '@source' (comida/generador) en el "
                     "recorrido para que el presupuesto alcance. Lo verifica el oráculo de recurso: si no se "
                     "sobrevive, lo rechazo.")
    if space:
        from oraculo.mazes.pcg_vocab import SPACES as _SPACES
        st = _SPACES.get(space)
        if st is not None:
            req = ", ".join(f"{k}>={v}" for k, v in st.required.items())
            lines.append("")
            lines.append(f"ESPACIO DECLARADO en esta corrida: el esqueleto se va a materializar como "
                         f"{space.upper()} (programa mínimo: {req}). Poné la directiva '@space {space}' en la "
                         f"cabecera y hacé un nivel con al menos {sum(st.required.values())} celdas transitables "
                         "(cada celda se vuelve un cuarto real). NO diseñes el interior: sólo el esqueleto — "
                         "el tipado de salas y los props vienen en la materialización, con su propio oráculo.")
    # un ejemplo few-shot por elemento habilitado (válido y ganable; el modelo hace otro distinto)
    examples: list[tuple[str, list[str]]] = []
    if "stairs" in enabled and n_floors > 1:
        examples.append(("una escalera (sube de piso)", _EX_STAIRS))
    if "ladder" in enabled and n_floors > 1:
        examples.append(("una escalera vertical 'I' (sube recto de piso)", _EX_LADDER))
    if "portals" in enabled:
        examples.append(("un portal (une celdas separadas por muros)", _EX_PORTAL))
    if "gravity" in enabled:
        examples.append(("gravedad (cae al piso de abajo por '~')", _EX_GRAVITY))
    if "keys" in enabled:
        examples.append(("llave 'a' y puerta 'A' (la llave antes de la puerta)", _EX_KEYS))
    if "switches" in enabled:
        examples.append(("botón '&' y compuerta '=' remota (cableadas por @switch/@gate)", _EX_SWITCH))
    if "hazard" in enabled:
        examples.append(("una trampa mortal 'X' que el camino esquiva", _EX_HAZARD))
    if "conduit" in enabled:
        examples.append(("un conducto bajo 'c' (se cruza agachado)", _EX_CONDUIT))
    if "seams" in enabled:
        examples.append(("una costura imposible '@seam' (espacio no-euclidiano)", _EX_SEAM))
    if "resource" in enabled or survive_days > 0:
        examples.append(("un canal de recurso/supervivencia '[Recurso 0]' con fuentes", _EX_RESOURCE))
    if "electric" in enabled:
        examples.append(("un canal eléctrico '[Electrico 0]' que alimenta una compuerta (@power/@gate)", _EX_ELECTRIC))
    for label, ex in examples:
        lines += ["", f"EJEMPLO con {label} — válido y ganable, hacé OTRO distinto:"] + ex
    lines.append("Respondé SOLO el JamMap.")
    system = "\n".join(lines)

    user = (f"Creá el nivel #{idx + 1}: un JamMap ORIGINAL y ganable"
            + (f" de hasta {n_floors} pisos" if n_floors > 1 else "")
            + ". Variá el trazado."
            + _gallery_block(context_dsls)          # novelty-aware scratch: diverger de lo ya cubierto
            + "\nRespondé SOLO el JamMap.")
    if feedback:
        user += (f"\n\n# CORRECCIÓN (tu intento anterior falló la verificación automática):\n{feedback}\n"
                 "Regenerá el JamMap COMPLETO ya corregido, SOLO el JamMap.")
    return system, user


def _extract_jammap(text: str) -> str:
    """Extrae el DSL de la respuesta del LLM: saca fences ```; arranca en la 1ª directiva/piso."""
    t = text.replace("```jammap", "```").replace("```text", "```")
    if "```" in t:
        for p in t.split("```"):
            if "[Piso" in p or "@portal" in p or "@gravity" in p:
                t = p
                break
    for marker in ("@portal", "@gravity", "[Piso"):
        i = t.find(marker)
        if i >= 0:
            return t[i:].strip()
    return t.strip()


def eval_jammap(dsl: str) -> dict[str, Any]:
    """Embudo de verificación del JamMap (sync, CPU-bound): interpretable (parse) → ganable (BFS) →
    INTERESANTE (las mecánicas importan, necesidad contrafáctica) + descriptores. El éxito ya no es
    sólo 'ganable' sino 'ganable Y no aburrido' — el oráculo pasó de gate de validez a gate de interés
    ([[no-injection-free-creation]]: medimos necesidad desde afuera, no inyectamos diseño)."""
    try:
        maze = parse(dsl)
    except (ValueError, KeyError, IndexError) as exc:
        return {"stage": "parse_error", "winnable": False, "interesting": False,
                "reason": f"{type(exc).__name__}: {exc}"}
    np, ng = _count_char(maze, PLAYER), _count_char(maze, GOAL)
    if np != 1 or ng != 1:
        return {"stage": "semantic", "winnable": False, "interesting": False,
                "reason": f"debe haber EXACTAMENTE un @ (player) y una G (meta); hay {np} @ y {ng} G"}
    # ── @SPACE declarado (contrato con JamPCG): vocabulario cerrado + realizabilidad ─────────────────
    # "Arreglar JamDSL" (Brian 2026-07-02): el tipo de espacio deja de ser post-hoc — el esqueleto lo
    # DECLARA y el oráculo lo gatea acá (declara CATEGORÍA, no layout: sólo se exige que los cuartos
    # alcancen para el programa mínimo; el tipado/props/program_satisfied van en la materialización).
    space = parse_space(dsl)
    if space is not None:
        from oraculo.mazes.pcg_vocab import SPACES as _SPACES
        if space not in _SPACES:
            return {"stage": "semantic", "winnable": False, "interesting": False,
                    "reason": f"@space '{space}' fuera del vocabulario ({', '.join(sorted(_SPACES))})"}
        need = sum(_SPACES[space].required.values())
        n_open = len(maze.open_cells())
        if n_open < need:
            return {"stage": "space_unrealizable", "winnable": False, "interesting": False,
                    "maze": maze, "dsl": render(maze) + f"\n@space {space}",
                    "desc": maze3d_descriptors(maze), "solution_length": None,
                    "space": space, "space_need": need, "space_open": n_open}
    channel = parse_resource_channel(dsl)                  # canal RECURSO (si el DSL lo trae), aspecto aparte
    electric = parse_electric_channel(dsl)                 # canal ELÉCTRICO + su acople (@power) con la nav
    couplings = parse_power_couplings(dsl)
    consumes = parse_consumes(dsl)                         # acople RECURSO↔ELÉCTRICO (@consume: la carga quema recurso)
    coupled = electric is not None and bool(couplings)
    powered_coupled = channel is not None and electric is not None and bool(consumes)  # el sistema tipo-VotV completo
    canonical = render(maze)                              # preservar los canales en el DSL canónico (render() es sólo nav)
    if space is not None:
        canonical += f"\n@space {space}"
    if channel is not None:
        canonical += "\n" + "\n".join(render_resource_channel(channel))
    if electric is not None:
        canonical += "\n" + "\n".join(render_electric_channel(electric))
    if couplings:
        canonical += "\n" + "\n".join(f"@power {x},{y},{z} {f}" for (x, y, z), f in sorted(couplings.items()))
    if consumes:
        canonical += "\n" + "\n".join(f"@consume {x},{y},{z} {r} {d:+d}"
                                      for (x, y, z), ds in sorted(consumes.items()) for r, d in sorted(ds.items()))
    # ── ACOPLE RECURSO↔ELÉCTRICO en modo SURVIVE-N (el server + '@budget over days') → AGUANTAR N pasos ──
    # Si el canal recurso declara 'days' (VotV: sobrevivir N, no llegar a G), la winnability es el HORIZONTE
    # gestionando el server (prenderlo cuesta recurso; apagarlo — si hay @breaker — lo salva). [[canal-recurso]]
    if powered_coupled and channel.days is not None:
        hz = powered_survival_horizon(maze, channel, electric, couplings, consumes)
        if hz.get("truncated"):                            # búsqueda truncada → horizonte NO certificado → rechazar
            return {"stage": "unverified", "winnable": False, "interesting": False,
                    "maze": maze, "dsl": canonical, "desc": maze3d_descriptors(maze),
                    "solution_length": None, "states_explored": hz.get("states_explored")}
        sustainable = hz["horizon"] == float("inf")
        pnec = powered_horizon_necessity(maze, channel, electric, couplings, consumes, channel.days)
        survival = {"mode": "survive", "days": channel.days, "sustainable": sustainable,
                    "horizon": None if sustainable else int(hz["horizon"])}
        if not pnec["ok"]:                                 # no se aguantan los N pasos → derrota (el burn agota)
            return {"stage": "unsurvivable", "winnable": False, "interesting": False,
                    "maze": maze, "dsl": canonical, "desc": maze3d_descriptors(maze),
                    "solution_length": None, "powered": pnec, "survival": survival}
        desc = maze3d_descriptors(maze)
        long_enough = channel.days >= MIN_INTERESTING_STEPS
        interesting = long_enough and pnec["matters"]      # el consumo cambia si se aguanta o acorta el horizonte
        return {"stage": "interesting" if interesting else "boring",
                "winnable": True, "interesting": interesting,
                "too_short": pnec["matters"] and not long_enough,
                "power_trivial": not pnec["matters"],      # se aguanta igual sin el consumo → acople decorativo
                "powered": pnec, "survival": survival,
                "maze": maze, "dsl": canonical, "desc": desc, "solution_length": None}

    # WINNABILITY según el acople presente: recurso↔eléctrico (reach-G gestionando el consumo) > eléctrico→nav > nav
    if powered_coupled:
        sol = solve_powered_survival(maze, channel, electric, couplings, consumes)
    elif coupled:
        sol = solve_coupled(maze, electric, couplings)   # una compuerta puede necesitar potencia
    else:
        sol = solve_3d(maze)
    if sol["solvable"] is not True:
        # distinguir la causa: el consumo eléctrico agotó el recurso · el cableado no alimenta · nav roto
        stage, extra = "unwinnable", {}
        if powered_coupled:
            pnec = powered_survival_necessity(maze, channel, electric, couplings, consumes)
            extra = {"powered": pnec}
            if pnec["binding_fail"]:                      # ganable sin el consumo pero NO con él → el burn te mató
                stage = "unsurvivable"
        elif coupled:
            nec = coupling_necessity(maze, electric, couplings)
            extra = {"coupling": nec}
            if nec["broken"]:                            # ganable SI estuviera alimentado, pero el cableado falla
                stage = "unpowered"
        return {"stage": stage, "winnable": False, "interesting": False,
                "maze": maze, "dsl": canonical, "desc": maze3d_descriptors(maze),
                "solution_length": None, **extra}
    desc = maze3d_descriptors(maze)
    steps = sol["optimal_steps"] or 0
    long_enough = steps >= MIN_INTERESTING_STEPS          # un viaje mínimo (no un puzzle de 2 pasos)

    # ── ACOPLE RECURSO↔ELÉCTRICO (server consume/genera) → gate combinado (interesting = el consumo IMPORTA) ──
    if powered_coupled:
        pnec = powered_survival_necessity(maze, channel, electric, couplings, consumes)
        interesting = long_enough and pnec["matters"]     # el consumo cambia el veredicto o el óptimo
        return {"stage": "interesting" if interesting else "boring",
                "winnable": True, "interesting": interesting,
                "too_short": pnec["matters"] and not long_enough,
                "power_trivial": not pnec["matters"],     # se gana igual sin el consumo → acople decorativo
                "powered": pnec, "levels_at_goal": sol.get("levels_at_goal"),
                "maze": maze, "dsl": canonical, "desc": desc,
                "solution_length": sol["optimal_steps"]}

    # ── CANAL RECURSO presente → gate de SUPERVIVENCIA (winnable = nav-ganable Y sobrevivible) ──────
    if channel is not None:
        surv = evaluate_channel(maze, channel)
        if not surv["ok"]:                                # no se sobrevive el presupuesto → derrota
            return {"stage": "unsurvivable", "winnable": False, "interesting": False,
                    "maze": maze, "dsl": canonical, "desc": desc, "survival": surv,
                    "solution_length": sol["optimal_steps"]}
        # necesidad CONTRAFÁCTICA del recurso: ¿sobrevive SIN las fuentes? → entonces son decorativas (aburrido)
        bare = ResourceChannel(ResourceSpec(channel.spec.resources, {}), days=channel.days)
        survival_matters = not evaluate_channel(maze, bare)["ok"]
        interesting = long_enough and survival_matters
        return {"stage": "interesting" if interesting else "boring",
                "winnable": True, "interesting": interesting,
                "too_short": survival_matters and not long_enough,
                "survival_trivial": not survival_matters,
                "maze": maze, "dsl": canonical, "desc": desc, "survival": surv,
                "solution_length": sol["optimal_steps"]}

    # ── ACOPLE ELÉCTRICO presente → gate de POTENCIA (interesting = el cableado IMPORTA, contrafáctico) ──
    if coupled:
        nec = coupling_necessity(maze, electric, couplings)
        power_matters = nec["binding"]                    # inganable sin potencia pero ganable con el cableado real
        interesting = long_enough and power_matters
        return {"stage": "interesting" if interesting else "boring",
                "winnable": True, "interesting": interesting,
                "too_short": power_matters and not long_enough,
                "power_trivial": nec["trivial"],          # se gana aun sin alimentar nada → eléctrico decorativo
                "coupling": nec, "maze": maze, "dsl": canonical, "desc": desc,
                "solution_length": sol["optimal_steps"]}

    # ── sin canal recurso/eléctrico → gate de interés de NAVEGACIÓN (como antes) ─────────────────────
    has_necessary = desc.get("interest_score", 0) > 0     # al menos una mecánica NECESARIA (contrafáctico)
    clean = desc.get("decorative_items", 0) == 0          # y NINGÚN item desparramado (cada uno IMPORTA)
    interesting = has_necessary and long_enough and clean
    # scattered = importa Y es largo, pero hay items de relleno → feedback distinto (sacá los que no cuentan)
    scattered = has_necessary and long_enough and not clean
    return {"stage": "interesting" if interesting else "boring",
            "winnable": True, "interesting": interesting,
            "too_short": has_necessary and not long_enough,
            "scattered": scattered,
            "maze": maze, "dsl": canonical, "desc": desc,
            "solution_length": sol["optimal_steps"]}


def feedback_for_jammap(res: dict) -> str:
    """El error del PROPIO JUEGO para devolverle al LLM (no diseño inyectado)."""
    if res["stage"] == "parse_error":
        return (f"El JamMap no se pudo interpretar: {res['reason']}. Respetá el formato: un bloque "
                "'[Piso N]' por piso y filas SOLO con glifos; los portales van en cabecera '@portal'.")
    if res["stage"] == "semantic":
        return (f"{res['reason']}. Dejá UN solo @ y UNA sola G en todo el mapa (en cualquier piso).")
    if res["stage"] == "unwinnable":
        return ("El JamMap NO es ganable: el BFS no encuentra camino del player (@) a la meta (G). "
                "Asegurate de que haya un camino transitable; si separás regiones con muros, conectalas "
                "con una escalera o un portal.")
    if res["stage"] == "space_unrealizable":
        return (f"Declaraste '@space {res.get('space')}' pero el esqueleto tiene {res.get('space_open')} "
                f"celdas transitables y el programa mínimo necesita {res.get('space_need')} cuartos "
                "(cada celda transitable se vuelve un cuarto al materializar). Agrandá el nivel o sacá "
                "la directiva @space.")
    if res["stage"] == "unverified":
        return ("El nivel es DEMASIADO GRANDE para verificar la supervivencia: el oráculo de horizonte se "
                "truncó antes de certificar si se aguantan los pasos exigidos (no se acepta un OK sin "
                "verificar). Achicá el mapa, reducí los recursos/rangos ('@cap'/'@start') o los switches para "
                "que el espacio de estados sea tratable.")
    if res["stage"] == "unsurvivable":
        if res.get("powered"):                     # acople recurso↔eléctrico: el server quemó el recurso
            return ("El nivel es navegable y la compuerta se alimenta, PERO el CONSUMO eléctrico agota el "
                    "recurso antes de llegar: la carga que abre la compuerta quema el recurso mientras está "
                    "encendida ('@consume') y no alcanza. Subí el '@start'/'@cap' del recurso, agregá una "
                    "'@source' (recarga) sobre el camino, bajá el '@consume', o —si hay '@breaker'— dejá que "
                    "el jugador APAGUE el server cuando no lo necesite (que no queme de más).")
        surv = res.get("survival", {})
        days = surv.get("days")
        return ("El nivel es navegable PERO NO se puede SOBREVIVIR el presupuesto de recurso: el oráculo "
                f"de supervivencia da derrota (objetivo: aguantar {days} pasos). Agregá más '@source' "
                "(comida/generador) sobre el recorrido, subí su '+delta' o el '@cap', o bajá el '@drain', "
                "para que el recurso no se agote antes de cumplir el '@budget'.")
    if res["stage"] == "unpowered":
        return ("El nivel sería ganable si la compuerta tuviera potencia, PERO el cableado eléctrico NO "
                "alimenta la carga que la abre: el oráculo de potencia da que la carga ('@power') NO está "
                "conectada a una fuente 'S' por cables (o un '@breaker' quedó abierto / su switch es "
                "inalcanzable). Completá el cable de 'S' a la carga, o —si hay '@breaker'— asegurate de que "
                "el jugador PUEDA pisar su '@switch' ANTES de la compuerta (no lo dejes detrás de ella: eso "
                "es un deadlock).")
    if res["stage"] == "boring" and res.get("survival_trivial"):
        return ("El nivel es ganable y sobrevivible, PERO la supervivencia es TRIVIAL: se aguanta el "
                "presupuesto INCLUSO SIN las fuentes (el '@start' ya alcanza, las '@source' no cambian nada). "
                "Subí el '@drain' o el 'days' del '@budget', o bajá el '@start', para que las fuentes sean "
                "NECESARIAS — que sin pasar por la comida/generador NO se sobreviva.")
    if res["stage"] == "boring" and res.get("power_trivial") and res.get("powered"):
        return ("El nivel es ganable PERO el acople recurso↔eléctrico es DECORATIVO: se gana IGUAL con o sin "
                "el consumo del server ('@consume' no cambia nada — sobra recurso). Subí el '@consume' o el "
                "'@drain', o bajá el '@start'/'@cap', para que mantener el server encendido CUESTE de verdad "
                "— que gestionar la energía sea NECESARIO para llegar a la meta.")
    if res["stage"] == "boring" and res.get("power_trivial"):
        return ("El nivel es ganable PERO el canal eléctrico es DECORATIVO: se llega a la meta INCLUSO sin "
                "alimentar nada (la compuerta que depende de '@power' no está sobre el único camino, o hay "
                "una ruta alterna sin energía). Hacé que la compuerta alimentada por el cableado esté sobre "
                "el ÚNICO camino a la meta — que sin energizar la carga el nivel NO se pueda ganar.")
    if res["stage"] == "boring":
        ln = res.get("solution_length")
        if res.get("scattered"):                   # importa y es largo, pero hay items de RELLENO (desparramados)
            cells = res.get("desc", {}).get("decorative_cells", [])
            where = ", ".join(f"({c[0]},{c[1]},{c[2]})" for c in cells[:6]) or "varios"
            return (f"El nivel es ganable e interesante PERO tiene items DESPARRAMADOS que no cambian nada: "
                    f"en {where}. Si saco cada uno, se gana igual y en los mismos {ln} pasos — están sólo "
                    "para decir que están. Un mapa LÓGICO no tiene relleno: SACÁ esos items, o hacé que CADA "
                    "uno IMPORTE (que su llave/puerta/botón/trampa fuerce un desvío o gatee un camino sin el "
                    "cual no se gana). Menos items, pero que todos cuenten.")
        if res.get("too_short"):                   # la mecánica SÍ importa, pero el nivel es trivialmente corto
            return (f"El nivel ES ganable y la mecánica importa, pero es DEMASIADO CORTO: se gana en {ln} "
                    f"pasos (mínimo {MIN_INTERESTING_STEPS}). Un puzzle de 2-3 pasos no es un nivel. "
                    "Agrandá el mapa y alejá la meta del player para que el desvío que fuerza la mecánica "
                    "sea un VIAJE, no un par de pasos.")
        dec = res.get("desc", {}).get("decorative_mechanics", [])
        decs = ", ".join(dec) if dec else "todas las que pusiste"
        return (f"El nivel ES ganable pero ABURRIDO: se llega a la meta en {ln} pasos sin que las "
                f"mecánicas importen ({decs} son DECORATIVAS — si las saco, se gana igual de fácil). "
                "Rediseñá para que al MENOS una mecánica sea NECESARIA: que la llave/puerta, el "
                "botón/compuerta o la trampa obliguen un DESVÍO más largo, o que sin ella el nivel NO "
                "se pueda ganar. La meta NO debe alcanzarse caminando derecho.")
    return ""


def _msg_text(msg) -> str:
    return "".join(c.get("text", "") for c in msg.content if c.get("type") == "text")


def _rank(res: dict) -> tuple:
    """Para elegir el "mejor" intento fallido: interesante > aburrido(ganable) > inganable > parseable;
    a igualdad, camino más largo."""
    order = {"interesting": 4, "boring": 3, "unwinnable": 2, "parse_error": 0}
    return (order.get(res.get("stage", ""), 1), res.get("solution_length") or 0)


async def _gen_jammap(client, idx: int, elements: tuple[str, ...], n_floors: int,
                      feedback: str | None, temperature: float | None = None,
                      context_dsls: tuple[str, ...] = (), survive_days: int = 0,
                      space: str | None = None) -> str:
    system, user = build_jammap_prompt(elements=elements, n_floors=n_floors, idx=idx, feedback=feedback,
                                       context_dsls=context_dsls, survive_days=survive_days, space=space)
    msg = await client.complete(system, [{"role": "user", "content": user}], max_tokens=1400,
                                temperature=temperature)
    return _extract_jammap(_msg_text(msg))


def _retry_feedback(dsl: str, res: dict) -> str:
    """Feedback para reintentar. L1: si el texto tiene líneas que el parser DESCARTA EN SILENCIO (prosa,
    directiva malformada, grilla fuera de piso — `conforms()`), eso corrompe el nivel sin avisar y el
    feedback del BFS sale confuso ('semantic'/'unwinnable'). Damos el motivo PRECISO → mejor maestro, sin
    distorsionar el token stream (constrained-decoding no aplica: el modelo no hace parse_error)."""
    ok, why = conforms(dsl)
    if not ok:
        return (f"FORMATO inválido — {why}. El parser DESCARTA esa línea en silencio, así que el nivel no "
                "es lo que escribiste. La grilla sólo lleva glifos; las directivas @ van bien formadas y "
                "ANTES de los pisos. Regenerá SOLO el JamMap corregido.")
    return feedback_for_jammap(res)


async def create_verify_jammap(client, *, idx: int = 0, elements: tuple[str, ...] = (),
                               n_floors: int = 1, attempts: int = 4,
                               temperature: float | None = None,
                               context_dsls: tuple[str, ...] = (), survive_days: int = 0,
                               space: str | None = None) -> dict[str, Any]:
    """Oráculo-en-el-loop: hasta `attempts` propuestas del LLM, regenerando con el feedback del BFS.
    `context_dsls` = galería diversa del archivo (novelty-aware scratch: diverger de lo ya cubierto).
    `survive_days` > 0 = exige canal recurso sobrevivible (gateado). Devuelve {won, best, attempts, history}."""
    history: list[dict] = []
    feedback: str | None = None
    for _ in range(attempts):
        dsl = await _gen_jammap(client, idx, elements, n_floors, feedback, temperature, context_dsls,
                                survive_days, space)
        res = await asyncio.to_thread(eval_jammap, dsl)
        res["raw"] = dsl
        history.append(res)
        if res.get("interesting"):                 # éxito = ganable Y no aburrido (las mecánicas importan)
            return {"won": True, "best": res, "attempts": len(history), "history": history}
        feedback = _retry_feedback(dsl, res)
    best = max(history, key=_rank)
    return {"won": False, "best": best, "attempts": len(history), "history": history}


def _diversity_targets(seed_desc: dict | None) -> str:
    """Instrucciones CONCRETAS para empujar la mutación a OTRO nicho (no un clon del seed). Deriva metas
    de los descriptores del seed: largo notoriamente distinto, otra verticalidad, otra mecánica necesaria.
    Sin esto la mutación EXPLOTA un nicho (la corrida comparativa: cobertura 2 vs 4 desde cero)."""
    if not seed_desc:
        return ("Cambiá la ESTRUCTURA de forma marcada (otro largo, otra cantidad de pisos, otra mecánica "
                "necesaria) para que sea OTRO tipo de nivel, no una copia.")
    ln = seed_desc.get("solution_length") or 0
    nf = seed_desc.get("n_floors") or 1
    nec = seed_desc.get("necessary_mechanics") or []
    necs = ", ".join(nec) if nec else "ninguna marcada"
    long_hint = (f"apuntá a ~{max(ln * 2, ln + 6)} pasos o más" if ln < 12
                 else f"cambiá la forma (podés rondar {ln} pero con otro trazado)")
    floor_hint = ("subí a 2-3 pisos conectados con escaleras/conectores" if nf <= 1
                  else f"cambiá cómo se conectan los {nf} pisos (o probá con {nf - 1} ó {nf + 1})")
    return (
        "El seed se gana en "
        f"{ln} pasos, {nf} piso(s), mecánica(s) necesaria(s): {necs}. Hacé una variación que caiga en OTRO "
        "NICHO — cambiá AL MENOS UNA dimensión de forma MARCADA:\n"
        f"  - LARGO del camino: {long_hint}.\n"
        f"  - VERTICALIDAD: {floor_hint}.\n"
        "  - MECÁNICA: hacé NECESARIA una mecánica DISTINTA de la(s) del seed (si el seed gatea con llaves, "
        "probá switch/compuerta o trampa condicional; etc.).\n"
        "No copies el trazado del seed: tomá la IDEA y llevala a otra forma."
    )


# Semillas de BOOTSTRAP diversas (una por nicho) para arrancar la búsqueda CON diversidad y escapar el
# colapso del generador a 1 nicho (Artificial Hivemind, V0 del roadmap). Cada una verificada interesting Y
# ≥ MIN_INTERESTING_STEPS (no diminutas); nichos (largo, height_span, comp_sig): (6,0,8) (2,0,16) (2,1,4)
# (2,0,32). Práctica QD/FunSearch: sembrar con una población diversa válida; el oráculo igual juzga TODO lo
# que el LLM genere después → no es inyección de diseño, es población inicial.
DIVERSE_BOOTSTRAP: tuple[str, ...] = (
    ("[Piso 0]\n#############\n#@..........#\n#.#########.#\n#.#.......#.#\n#.#.#####.#.#\n"
     "#a#.....#...#\n#.#####.#.#A#\n#.......#.#G#\n#############"),                         # llaves, largo (6,0,8)
    "@switch 1,3,0 f1\n@gate 5,1,0 f1\n[Piso 0]\n#######\n#@...=#\n#.###G#\n#&...##\n#######",  # botón/compuerta (2,0,16)
    "[Piso 0]\n#######\n#@...H#\n#######\n[Piso 1]\n#######\n#G...o#\n#######",               # vertical (2,1,4)
    "[Piso 0]\n#######\n#@.X.G#\n#.###.#\n#.....#\n#######",                                   # trampa (2,0,32)
)


def _gallery_block(context_dsls: tuple[str, ...]) -> str:
    """In-context QD: muestra al LLM la VARIEDAD ya cubierta para que diverja de TODOS (no sólo del seed).
    SOTA: 'LLMs as in-context QD generators' — ver el archivo diverso mejora novedad + calidad."""
    if not context_dsls:
        return ""
    ejs = "\n".join(f"## ya en la galería #{i + 1}:\n{d.strip()}" for i, d in enumerate(context_dsls))
    return (
        "\n\n# Estos niveles YA están en la galería. Tu variación tiene que ser DISTINTA de TODOS ellos "
        "(otro largo / verticalidad / mecánica necesaria) — apuntá a un HUECO que ninguno cubre:\n"
        f"{ejs}"
    )


def build_mutation_prompt(*, seed_dsl: str, seed_desc: dict | None = None,
                          elements: tuple[str, ...] = (), n_floors: int = 1,
                          feedback: str | None = None,
                          context_dsls: tuple[str, ...] = (), survive_days: int = 0,
                          space: str | None = None) -> tuple[str, str]:
    """Arma (system, user) para que el LLM genere una mutación DIVERSITY-SEEKING de un JamMap: no un clon
    del seed sino una variación que caiga en OTRO nicho, manteniendo el interés (mecánica necesaria).
    `context_dsls` = elites diversos del archivo (in-context QD) para diverger de toda la galería."""
    system, _ = build_jammap_prompt(elements=elements, n_floors=n_floors, survive_days=survive_days,
                                    space=space)
    user = (
        "Acá hay un nivel que funciona (abajo). Hacé una VARIACIÓN DISTINTA (iluminación): mantené lo que "
        "lo hace interesante — al menos una mecánica NECESARIA (sin ella NO se gana, o el camino es mucho "
        "más largo) y que sea GANABLE y NO trivial (mínimo 4 pasos a la meta) — pero llevalo a OTRO tipo de "
        "nivel.\n\n"
        f"{_diversity_targets(seed_desc)}"
        f"{_gallery_block(context_dsls)}\n\n"
        "Respondé SOLO el JamMap.\n\n"
        f"# Nivel semilla:\n{seed_dsl}"
    )
    if feedback:
        user += (f"\n\n# CORRECCIÓN (tu intento anterior falló la verificación automática):\n{feedback}\n"
                 "Regenerá el JamMap COMPLETO ya corregido, SOLO el JamMap.")
    return system, user


async def _gen_mutated_jammap(client, seed_dsl: str, seed_desc: dict | None, elements: tuple[str, ...],
                              n_floors: int, feedback: str | None,
                              context_dsls: tuple[str, ...] = (), temperature: float | None = None,
                              survive_days: int = 0, space: str | None = None) -> str:
    system, user = build_mutation_prompt(seed_dsl=seed_dsl, seed_desc=seed_desc, elements=elements,
                                         n_floors=n_floors, feedback=feedback, context_dsls=context_dsls,
                                         survive_days=survive_days, space=space)
    msg = await client.complete(system, [{"role": "user", "content": user}], max_tokens=1400,
                                temperature=temperature)
    return _extract_jammap(_msg_text(msg))


async def mutate_jammap(client, *, seed_dsl: str, seed_desc: dict | None = None,
                        elements: tuple[str, ...] = (), n_floors: int = 1,
                        attempts: int = 4, context_dsls: tuple[str, ...] = (),
                        temperature: float | None = None, survive_days: int = 0,
                        space: str | None = None) -> dict[str, Any]:
    """Oráculo-en-el-loop para MUTAR un nivel existente (iluminación DIVERSITY-SEEKING: apunta a otro
    nicho que el seed). `seed_desc` = descriptores del seed para derivar las metas de diversidad.
    `context_dsls` = elites diversos del archivo (in-context QD) para diverger de toda la galería.
    Devuelve {won, best, attempts, history}."""
    history: list[dict] = []
    feedback: str | None = None
    for _ in range(attempts):
        dsl = await _gen_mutated_jammap(client, seed_dsl, seed_desc, elements, n_floors, feedback,
                                        context_dsls, temperature, survive_days, space)
        res = await asyncio.to_thread(eval_jammap, dsl)
        res["raw"] = dsl
        history.append(res)
        if res.get("interesting"):
            return {"won": True, "best": res, "attempts": len(history), "history": history}
        feedback = _retry_feedback(dsl, res)
    best = max(history, key=_rank)
    return {"won": False, "best": best, "attempts": len(history), "history": history}
