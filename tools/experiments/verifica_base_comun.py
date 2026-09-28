"""La base común corre igual en Unreal y en otro motor (tarea `base-comun`), medido por los DOS.

    python tools/experiments/verifica_base_comun.py --motor godot
    python tools/experiments/verifica_base_comun.py --motor unity

1. Lee lo que midió Unreal sobre la caja del núcleo: `~/Dev/games/JamPlayground/Saved/
   jam_caja_comun.json` (lo escribe `verifica_caja_comun_58.py`, que se corre antes en el editor).
2. Levanta Godot headless con `~/Dev/games/JamGodot` (plugin Jam), corre el MISMO texto con el
   núcleo en este proceso —`caja = mesh_box …` → `mesh_preview @caja`— y pide los hechos que Godot
   mide sobre las mallas que guardó.
3. Compara: triángulos, vértices y caja envolvente iguales; área con tolerancia relativa 1e-6
   (Godot guarda float32); toda cara frontal hacia afuera según la convención de Godot.
Sale 0 si los dos motores dan lo mismo.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

JAM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(JAM / "Content/Python"))
sys.modules["unreal"] = None   # el núcleo corre SIN Unreal: es la prueba

import argparse  # noqa: E402

from jam import adaptador_godot as ag  # noqa: E402
from jam import adaptador_unity as au  # noqa: E402

UNREAL = Path.home() / "Dev/games/JamPlayground/Saved/jam_caja_comun.json"
PROYECTO = Path.home() / "Dev/games/JamGodot"
UNITY = Path.home() / "Dev/engines/unity/6000.3.24f1/Editor/Unity"
PROYECTO_UNITY = Path.home() / "Dev/games/JamUnity"


def _lanzar(motor: str):
    """(proceso, módulo del adaptador) del motor, headless. Unity: el bucle de lote de Codex
    (`Jam.JamServidor.Lote`), que atiende en el hilo principal hasta «salir»."""
    if motor == "godot":
        return subprocess.Popen(["godot", "--headless", "--editor", "--path", str(PROYECTO)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL), ag
    log = PROYECTO_UNITY / "jam-unity-cruzada.log"
    return subprocess.Popen([str(UNITY), "-projectPath", str(PROYECTO_UNITY), "-logFile", str(log),
                             "-batchmode", "-nographics", "-executeMethod", "Jam.JamServidor.Lote"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL), au


FIXTURE = JAM / "Content/Python/tests/fixtures/primitivas_unreal.json"
PIPE = JAM / "Content/Python/tests/fixtures/pipe_unreal.json"
CAJA = "caja = mesh_box size_x=100 size_y=60 size_z=40\n"


def _params(params: dict) -> str:
    return " ".join(f"{k}={str(v).lower() if isinstance(v, bool) else v}" for k, v in params.items())


def _cerrada(tris: list[dict]) -> bool:
    """¿La malla que volcó Unreal es cerrada? Cada arista (por posición, a 0,001 cm) aparece en
    exactamente dos triángulos no degenerados. El volumen de una malla ABIERTA no está definido
    —depende del origen—, así que sólo se compara el de las cerradas."""
    from collections import Counter
    aristas = Counter()
    for t in tris:
        p = [tuple(round(c, 3) for c in q) for q in t["p"]]
        if len(set(p)) < 3:
            continue
        for a, b in ((p[0], p[1]), (p[1], p[2]), (p[2], p[0])):
            aristas[frozenset((a, b))] += 1
    return bool(aristas) and all(n == 2 for n in aristas.values())


def _textos() -> list[tuple[str, str, dict]]:
    """(nombre, texto, hechos de Unreal) de cada caso: las tres cajas medidas y todo el fixture de
    primitivas que ya es común (generadores, mesh_transform sobre la caja, mesh_merge)."""
    from jam import registro
    salida = []
    for i, caso in enumerate(json.loads(UNREAL.read_text())["casos"]):
        u = caso["nucleo"]
        salida.append((f"caja{i}", f"m = mesh_box {_params(caso['caso'])}\n",
                       {"triangulos": u["triangulos"], "posiciones": u["vertices"], "min": u["min"],
                        "max": u["max"], "area": u["area_volumen"][0], "volumen": u["area_volumen"][1],
                        "cerrada": True}))
    for i, caso in enumerate(json.loads(FIXTURE.read_text())["casos"]):
        v = caso["verbo"]
        if v not in registro.COMUNES or "error" in caso:
            continue
        if v == "mesh_transform":
            texto = CAJA + f"m = mesh_transform @caja {_params(caso['params'])}\n"
        elif v == "mesh_merge":
            texto = CAJA + "otra = mesh_transform @caja x=200 yaw=30\nm = mesh_merge @caja @otra\n"
        else:
            texto = f"m = {v} {_params(caso['params'])}\n"
        salida.append((f"{v}{i}", texto, {**caso["motor"], "cerrada": _cerrada(caso["motor"]["tris"])}))
    # El tubo, sobre las curvas que se pueden ESCRIBIR con verbos comunes (la esquina de 90° del
    # fixture no: la cubre el juez de tests/test_malla_tubo.py).
    curvas = {"recta": 'curva = curve_line desde="0,0,0" hasta="0,0,300"\n',
              "bezier": "curva = curve_bezier end_x=200 end_z=300 bend_x=150 bend_y=60 segments=12\n"}
    for i, caso in enumerate(json.loads(PIPE.read_text())["casos"]):
        if caso["curva"] in curvas and "error" not in caso:
            salida.append((f"mesh_pipe_{caso['curva']}{i}",
                           curvas[caso["curva"]] + f"m = mesh_pipe @curva {_params(caso['params'])}\n",
                           {**caso["motor"], "cerrada": _cerrada(caso["motor"]["tris"])}))
    return salida


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--motor", choices=("godot", "unity"), default="godot")
    motor = a.parse_args().motor
    if json.loads(UNREAL.read_text()).get("veredicto") != "VERDE":
        raise SystemExit(f"la medición de Unreal no es VERDE: {UNREAL}")
    proceso, mod = _lanzar(motor)
    fallas, filas = [], []
    cliente = None
    try:
        for _ in range(240):
            try:
                cliente = mod.Cliente(plazo=30)
                break
            except mod.ErrorAdaptador:
                time.sleep(1)
        else:
            raise SystemExit(f"{motor} no abrió el puerto del plugin Jam")
        adaptador = (ag.AdaptadorGodot if motor == "godot" else au.AdaptadorUnity)(cliente)
        casos = _textos()
        for nombre, texto, _u in casos:
            r = ag.correr_texto(texto + f"ver = mesh_preview @m name={nombre}\n", adaptador)
            if not r["ok"]:
                fallas.append(f"{nombre}: no corrió en {motor}: {r['errores'] or r['report']}")
        en_godot = {m["nodo"]: m["hechos"] for m in cliente.pedir("hechos")["mallas"]}
        for nombre, _texto, u in casos:
            g = en_godot.get(nombre, {})
            filas.append({"caso": nombre, "unreal": {k: u[k] for k in ("triangulos", "posiciones", "min", "max", "area", "volumen")},
                          motor: g})
            cerca = lambda a, b: all(abs(x - y) <= 1e-3 for x, y in zip(a, b))  # noqa: E731
            if (g.get("triangulos"), g.get("posiciones")) != (u["triangulos"], u["posiciones"]) or not (
                    cerca(g.get("min", []), u["min"]) and cerca(g.get("max", []), u["max"])):
                fallas.append(f"{nombre}: Unreal y {motor} miden distinto")
            if abs(g.get("area", 0) - u["area"]) > 1e-5 * max(1.0, u["area"]):
                fallas.append(f"{nombre}: área {g.get('area')} contra {u['area']}")
            # El volumen CON SIGNO, sumado con la convención de caras frontales de Godot: coincide
            # con el de Unreal sólo si Godot dibuja las mismas caras. (Contra el centro de la caja
            # envolvente no sirve: en un merge de dos piezas el centro cae entre las dos.)
            if u["cerrada"] and abs(g.get("volumen", float("nan")) - u["volumen"]) > \
                    1e-5 * max(1.0, abs(u["volumen"])) + 1e-3:
                fallas.append(f"{nombre}: volumen con signo {g.get('volumen')} contra {u['volumen']} "
                              "(caras dadas vuelta si el signo no coincide)")
        cliente.pedir("descartar")
    finally:
        if cliente is not None:
            if motor == "unity":
                try:
                    cliente.pedir("salir")
                except (OSError, mod.ErrorAdaptador):
                    pass
            cliente.cerrar()
        if motor == "godot":
            proceso.terminate()
        try:
            proceso.wait(60)
        except subprocess.TimeoutExpired:
            proceso.terminate()
            proceso.wait(20)
    print(json.dumps({"veredicto": "VERDE" if not fallas else "ROJO", "motor": motor, "casos": filas,
                      "fallas": fallas}, ensure_ascii=False, indent=1))
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
