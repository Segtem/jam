#!/usr/bin/env python3
"""Jam CLI externo (TCP) — maneja Jam desde FUERA de Unreal.

Cliente 100% fuera del editor (python3 PELADO, no importa `unreal`): se conecta al receptor
`jam.serve` (127.0.0.1:8791) y manda comandos DSL al contrato `jam.api`. El editor debe estar abierto
con el receptor iniciado (`py import jam.serve; jam.serve.iniciar()`).

Uso:
    python3 jam.py "scatter count=20 area=650"     # un comando
    python3 jam.py                                  # REPL: comandos DSL, «quit» para salir
"""

import os
import socket
import sys

HOST = os.environ.get("JAM_HOST", "127.0.0.1")
PORT = int(os.environ.get("JAM_PORT", "8791"))


def run(command: str, *, host: str = HOST, port: int = PORT, timeout: float = 30.0) -> str:
    s = socket.create_connection((host, port), timeout=timeout)
    try:
        s.sendall((command + "\n").encode("utf-8"))
        buf = b""
        while b"\x00" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
    finally:
        s.close()
    return buf.split(b"\x00", 1)[0].decode("utf-8", "replace")


def main() -> None:
    try:
        if len(sys.argv) > 1:
            print(run(" ".join(sys.argv[1:])))
        else:
            print(f"[jam] cliente externo → {HOST}:{PORT} (100% fuera de Unreal). «quit» para salir.")
            while True:
                try:
                    linea = input("jam> ").strip()
                except EOFError:
                    break
                if linea in ("quit", "exit"):
                    break
                if linea:
                    print(run(linea))
    except (ConnectionRefusedError, socket.timeout, OSError) as e:
        print(f"[jam] no pude conectar al editor ({HOST}:{PORT}): {e}\n"
              f"      abrí BotOO y corré:  py import jam.serve; jam.serve.iniciar()")
        sys.exit(1)


if __name__ == "__main__":
    main()
