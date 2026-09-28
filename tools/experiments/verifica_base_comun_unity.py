"""Unreal ↔ Unity real, con el cálculo en Python puro (tarea base-comun).

    python tools/experiments/verifica_base_comun_unity.py
    python tools/experiments/verifica_base_comun_unity.py --mutante
    python tools/experiments/verifica_base_comun_unity.py --ventana

Lee los tres casos medidos en Unreal, ejecuta el mismo grafo por TCP, guarda la escena,
cierra Unity por su PID y vuelve a abrirla en OTRO proceso para medir los Mesh persistidos.
Batchmode usa un -executeMethod con bucle principal, sin depender de EditorApplication.update.
--ventana comprueba el otro camino, con update real. --mutante invierte los índices EN EL
ADAPTADOR C#, reinicia Unity y exige que la comparación dé ROJO (salida 1); restaura el fuente
con copia y finally, también ante SIGTERM/SIGINT. No modifica el juez ni los hechos de Unreal.
Resultados y logs quedan en JamUnity. Las áreas admiten 1e-6 relativo por los float32 del motor.
La orientación radial sólo juzga estas cajas convexas: no prueba mallas cóncavas ni render píxel.
"""

from __future__ import annotations

import argparse
import atexit
from contextlib import contextmanager
import hashlib
import json
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

JAM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(JAM / "Content/Python"))
sys.modules["unreal"] = None

from jam import adaptador_unity as au  # noqa: E402

UNREAL = Path.home() / "Dev/games/JamPlayground/Saved/jam_caja_comun.json"
PROYECTO = Path.home() / "Dev/games/JamUnity"
UNITY = Path.home() / "Dev/engines/unity/6000.3.24f1/Editor/Unity"
FUENTE = JAM / "Unity/Assets/Jam/Editor/JamServidor.cs"


@contextmanager
def mutar(activo):
    if not activo:
        yield
        return
    original = FUENTE.read_bytes()
    sano = b"new[] { t[0], t[1], t[2] }"
    roto = b"new[] { t[0], t[2], t[1] }"
    if original.count(sano) != 1:
        raise RuntimeError("No se encontró exactamente un punto para mutar el winding.")
    # Fuera de Assets: Unity no debe importar el respaldo ni generarle un .meta.
    respaldo = PROYECTO / "jam-winding.cs.bak"
    if respaldo.exists():
        raise RuntimeError(f"Hay una restauración pendiente: {respaldo}")
    respaldo.write_bytes(original)

    def restaurar():
        if respaldo.exists():
            FUENTE.write_bytes(respaldo.read_bytes())
            respaldo.unlink()

    atexit.register(restaurar)
    try:
        FUENTE.write_bytes(original.replace(sano, roto))
        yield
    finally:
        restaurar()
        atexit.unregister(restaurar)


@contextmanager
def editor(ventana, etiqueta):
    try:
        ocupante = socket.create_connection(("127.0.0.1", au.PUERTO), timeout=0.2)
    except OSError:
        pass
    else:
        ocupante.close()
        raise RuntimeError("El puerto 8793 ya está ocupado; cerrá ese Unity antes de la prueba.")
    log = PROYECTO / f"jam-unity-{etiqueta}.log"
    args = [str(UNITY), "-projectPath", str(PROYECTO), "-logFile", str(log)]
    if ventana:
        args += ["-executeMethod", "Jam.JamServidor.AbrirEscena"]
    else:
        args += ["-batchmode", "-nographics", "-executeMethod", "Jam.JamServidor.Lote"]
    proceso = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cliente = None
    try:
        limite = time.monotonic() + 180
        while time.monotonic() < limite:
            if proceso.poll() is not None:
                raise RuntimeError(f"Unity terminó con {proceso.returncode}: {log}")
            try:
                cliente = au.Cliente(plazo=10)
                break
            except au.ErrorAdaptador:
                time.sleep(0.25)
        if cliente is None:
            raise RuntimeError(f"Unity no abrió el puerto: {log}")
        hola = cliente.pedir("hola")
        if hola.get("pid") != proceso.pid or hola.get("motor") != "unity":
            raise RuntimeError("Respondió otro proceso; esta corrida no mide el Unity lanzado.")
        yield cliente, hola
    finally:
        if cliente is not None:
            try:
                if not ventana and proceso.poll() is None:
                    cliente.pedir("salir")
            except (OSError, au.ErrorAdaptador):
                pass
            finally:
                cliente.cerrar()
        if ventana and proceso.poll() is None:
            proceso.terminate()
        try:
            proceso.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proceso.terminate()
            try:
                proceso.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait(timeout=10)
        # En GUI, el proceso principal puede terminar antes de liberarse el socket
        # heredado por auxiliares del editor. Esperar la liberación, sin matar otros PID.
        limite = time.monotonic() + 10
        while time.monotonic() < limite:
            try:
                with socket.create_connection(("127.0.0.1", au.PUERTO), timeout=0.2):
                    pass
            except OSError:
                break
            time.sleep(0.1)


def comparar(casos, medidos, fallas, etapa):
    filas = []
    if len(medidos) != len(casos):
        fallas.append(f"{etapa}: se esperaban {len(casos)} mallas; se midieron {len(medidos)}")
    for i, caso in enumerate(casos):
        u, g = caso["nucleo"], medidos.get(f"caso{i}", {})
        area_u = u["area_volumen"][0]
        filas.append({"caso": caso["caso"], "unreal": {k: u[k] for k in
                      ("triangulos", "vertices", "min", "max")} | {"area": area_u}, "unity": g})
        if (g.get("triangulos"), g.get("posiciones"), g.get("min"), g.get("max")) != (
                u["triangulos"], u["vertices"], u["min"], u["max"]):
            fallas.append(f"{etapa}, caso {i}: Unreal y Unity miden distinta topología o caja")
        if abs(g.get("area", 0) - area_u) > 1e-6 * area_u:
            fallas.append(f"{etapa}, caso {i}: área {g.get('area')} contra {area_u}")
        if g.get("caras_hacia_afuera") != u["triangulos"]:
            fallas.append(f"{etapa}, caso {i}: caras frontales afuera "
                          f"{g.get('caras_hacia_afuera')}/{u['triangulos']}")
    return filas


def hechos(cliente):
    return {m["nodo"]: m["hechos"] for m in cliente.pedir("hechos")["mallas"]}


def probar_contrato(cliente):
    # Pedido incompleto: otro cliente debe poder ser atendido en el mismo hilo de editor.
    with socket.create_connection(("127.0.0.1", au.PUERTO), timeout=10) as parcial:
        parcial.sendall(b'{"op":')
        assert cliente.pedir("hola")["contrato"] == 1
        parcial.sendall(b'"hola"}\n{"op":"evaluar","codigo":"no ejecutar"}\n')
        with parcial.makefile("r", encoding="utf-8") as lector:
            assert json.loads(lector.readline())["ok"]
            assert not json.loads(lector.readline())["ok"]
    try:
        cliente.pedir("mostrar_malla", nombre="inválida", malla={"vertices": [], "triangulos": []})
    except au.ErrorAdaptador:
        pass
    else:
        raise RuntimeError("Unity aceptó una malla vacía.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mutante", action="store_true")
    parser.add_argument("--ventana", action="store_true")
    args = parser.parse_args()
    enlace = PROYECTO / "Assets/Jam"
    if not enlace.is_symlink() or enlace.resolve() != JAM / "Unity/Assets/Jam":
        raise SystemExit(f"{enlace} debe apuntar a {JAM / 'Unity/Assets/Jam'}")
    referencia = UNREAL.read_bytes()
    datos = json.loads(referencia)
    casos = datos.get("casos", [])
    if datos.get("veredicto") != "VERDE" or len(casos) != 3:
        raise SystemExit("La referencia de Unreal debe ser VERDE y contener las tres cajas.")
    etiqueta = "mutante" if args.mutante else ("ventana" if args.ventana else "sano")
    fallas, filas, reabiertas = [], [], []
    hola = {}
    try:
        with mutar(args.mutante):
            with editor(args.ventana, etiqueta) as (cliente, hola):
                probar_contrato(cliente)
                assert hola["cubo_nativo"] == {"triangulos": 12, "cruz_ba_ca_afuera": 12,
                                               "cruz_ca_ba_afuera": 0}, hola
                cliente.pedir("descartar")
                assert hechos(cliente) == {}, "descartar dejó mallas en la escena"
                adaptador = au.AdaptadorUnity(cliente)
                for i, caso in enumerate(casos):
                    params = " ".join(f"{k}={v}" for k, v in caso["caso"].items())
                    texto = f"caja = mesh_box {params}\nver = mesh_preview @caja name=caso{i}\n"
                    # Repetir nombre debe reemplazar: se miden tres mallas, no seis.
                    for _ in range(2):
                        r = au.correr_texto(texto, adaptador)
                        if not r["ok"]:
                            fallas.append(f"caso {i}: no corrió: {r['errores'] or r['report']}")
                filas = comparar(casos, hechos(cliente), fallas, "preview")
                fijo = cliente.pedir("fijar")
                assert fijo["fijados"] == 3, fijo
                assert fijo["escena"] == "Assets/Scenes/JamBaseComun.unity", fijo
            with editor(args.ventana, etiqueta + "-reabrir") as (cliente, _):
                reabiertas = comparar(casos, hechos(cliente), fallas, "escena reabierta")
    except Exception as e:
        fallas.append(f"{type(e).__name__}: {e}")
    resultado = {"veredicto": "ROJO" if fallas else "VERDE", "mutante": args.mutante,
                 "referencia": str(UNREAL), "sha256_referencia": hashlib.sha256(referencia).hexdigest(),
                 "hola": hola, "casos": filas, "reabiertas": reabiertas, "fallas": fallas}
    (PROYECTO / f"jam-base-comun-{etiqueta}.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=1))
    return 1 if fallas else 0


if __name__ == "__main__":
    def interrumpir(numero, marco):
        raise SystemExit(f"Interrumpido por señal {numero}; cierro mi Unity y restauro el mutante.")
    signal.signal(signal.SIGTERM, interrumpir)
    signal.signal(signal.SIGINT, interrumpir)
    sys.exit(main())
