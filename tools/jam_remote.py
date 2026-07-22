#!/usr/bin/env python3
"""Jam CLI externo — maneja Jam desde FUERA de Unreal, por la ejecución remota del editor.

Prueba de que la UI puede vivir fuera de UE: este proceso es python3 PELADO (no importa `unreal`);
habla con el editor vivo por el protocolo remoto de PythonScriptPlugin y llama al contrato `jam.api`.
El editor tiene que estar abierto con `bRemoteExecution=True` (ya configurado en BotOO).

Uso:
    python3 jam_remote.py "scatter count=20 area=650"     # un comando
    python3 jam_remote.py                                  # REPL: comandos DSL, 'quit' para salir
"""

import os
import sys
import time

ENGINE = os.environ.get("JAM_ENGINE", os.path.expanduser("~/Dev/engines/UnrealEngine_5.7"))
sys.path.insert(0, os.path.join(
    ENGINE, "Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python"))
import remote_execution as re  # noqa: E402


def conectar(timeout: float = 20.0):
    """Descubre el editor por multicast y abre la conexión de comandos."""
    conn = re.RemoteExecution()
    conn.start()
    t0 = time.time()
    while not conn.remote_nodes and time.time() - t0 < timeout:
        time.sleep(0.3)
    if not conn.remote_nodes:
        conn.stop()
        raise RuntimeError("no encontré el editor (¿abierto? ¿bRemoteExecution=True en DefaultEngine.ini?)")
    conn.open_command_connection(conn.remote_nodes[0]["node_id"])
    return conn


def _llamar(conn, py: str) -> str:
    r = conn.run_command(py, exec_mode=re.MODE_EXEC_FILE, raise_on_failure=False)
    out = "".join(e.get("output", "") for e in (r.get("output") or []))
    if not r.get("success"):
        out = "[remote error] " + out
    return out.rstrip()


def run(conn, command: str) -> str:
    esc = command.replace("\\", "\\\\").replace("'", "\\'")
    return _llamar(conn, f"import jam.api as _a\nprint(_a.run('{esc}'))")


def spec(conn) -> str:
    return _llamar(conn, "import jam.api as _a\nprint(_a.spec())")


def main() -> None:
    conn = conectar()
    node = conn.remote_nodes[0].get("node_id", "?")
    print(f"[jam] conectado al editor ({node[:8]}…) — cliente 100% fuera de Unreal")
    try:
        if len(sys.argv) > 1:
            print(run(conn, " ".join(sys.argv[1:])))
        else:
            print("Jam CLI externo — comandos DSL (o «help»), «quit» para salir.")
            while True:
                try:
                    linea = input("jam> ").strip()
                except EOFError:
                    break
                if linea in ("quit", "exit"):
                    break
                if linea:
                    print(run(conn, linea))
    finally:
        conn.close_command_connection()
        conn.stop()


if __name__ == "__main__":
    main()
