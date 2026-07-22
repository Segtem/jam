"""jam.serve — receptor TCP localhost: expone el contrato `jam.api` a un proceso FUERA de Unreal.

Prueba de que la UI puede vivir afuera sin depender del C++/Slate ni del multicast del remote-exec de
UE (que pide config de red con root). Un cliente externo (python3 pelado, o una web) se conecta a
127.0.0.1:PORT, manda una línea de comando DSL y recibe el veredicto.

Marshalling al game thread: las ops de actores de UE deben correr en el hilo del juego. El server
corre en un hilo aparte y ENCOLA los comandos; un callback de Slate post-tick los drena y ejecuta
`jam.api` en el game thread. Framing: comando = 1 línea (\\n); respuesta = texto + NUL (\\x00).
"""

from __future__ import annotations

import queue
import socket
import threading

import unreal

from . import api

_PORT_DEFECTO = 8791
_PENDIENTES: "queue.Queue" = queue.Queue()
_S = {"sock": None, "hilo": None, "tick": None, "corriendo": False}


def _tick(_delta) -> None:
    """Game thread: drena la cola y corre jam.api por cada comando pendiente."""
    while True:
        try:
            cmd, holder, ev = _PENDIENTES.get_nowait()
        except queue.Empty:
            return
        try:
            holder["r"] = api.run(cmd)
        except Exception as e:  # noqa: BLE001
            holder["r"] = f"[error] {type(e).__name__}: {e}"
        ev.set()


def _atender(conn) -> None:
    with conn:
        f = conn.makefile("rwb")
        for raw in f:
            cmd = raw.decode("utf-8", "replace").strip()
            if not cmd:
                continue
            if cmd == "__quit__":
                break
            holder: dict = {}
            ev = threading.Event()
            _PENDIENTES.put((cmd, holder, ev))
            ev.wait(timeout=30.0)
            resp = holder.get("r", "(sin respuesta del editor)")
            f.write(resp.encode("utf-8") + b"\x00")
            f.flush()


def _loop(sock) -> None:
    while _S["corriendo"]:
        try:
            conn, _ = sock.accept()
        except OSError:
            break
        threading.Thread(target=_atender, args=(conn,), daemon=True).start()


def iniciar(port: int = _PORT_DEFECTO) -> None:
    """Arranca el receptor TCP + el drenaje en game thread. Idempotente."""
    if _S["corriendo"]:
        unreal.log(f"[Jam] serve: ya está escuchando")
        return
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.listen(4)
    _S.update(sock=sock, corriendo=True)
    _S["hilo"] = threading.Thread(target=_loop, args=(sock,), daemon=True)
    _S["hilo"].start()
    _S["tick"] = unreal.register_slate_post_tick_callback(_tick)
    unreal.log(f"[Jam] serve: escuchando en 127.0.0.1:{port} — cliente externo → jam.api → oráculo")


def detener() -> None:
    _S["corriendo"] = False
    if _S["tick"] is not None:
        unreal.unregister_slate_post_tick_callback(_S["tick"])
        _S["tick"] = None
    if _S["sock"] is not None:
        try:
            _S["sock"].close()
        except Exception:  # noqa: BLE001
            pass
        _S["sock"] = None
    unreal.log("[Jam] serve: detenido")
