"""jam.serve — game-thread bridge + receptor TCP para clientes FUERA de Unreal.

Prueba de que la UI puede vivir afuera sin depender del C++/Slate. Las ops de actores de UE deben
correr en el hilo del juego; acá está la máquina que lo garantiza: los servidores (TCP acá, HTTP en
`jam.web`) corren en hilos aparte y ENCOLAN callables; un callback de Slate post-tick los drena y los
ejecuta en el GAME THREAD. `en_game_thread(fn)` es el punto de entrada compartido.

Transporte TCP (127.0.0.1:8791): comando = 1 línea (\\n); respuesta = texto + NUL (\\x00).
"""

from __future__ import annotations

import queue
import socket
import threading

import unreal

from . import api

_PORT_DEFECTO = 8791
_PENDIENTES: "queue.Queue" = queue.Queue()   # (thunk, holder, ev)
_TICK = {"handle": None}
_S = {"sock": None, "corriendo": False}


# ---- máquina de game thread (compartida por TCP y HTTP) ----

def _tick(_delta) -> None:
    """Game thread: drena la cola y corre cada callable pendiente."""
    while True:
        try:
            thunk, holder, ev = _PENDIENTES.get_nowait()
        except queue.Empty:
            return
        try:
            holder["r"] = thunk()
        except Exception as e:  # noqa: BLE001
            holder["r"] = f"[error] {type(e).__name__}: {e}"
        ev.set()


def asegurar_tick() -> None:
    """Registra el drenaje en el game thread una sola vez."""
    if _TICK["handle"] is None:
        _TICK["handle"] = unreal.register_slate_post_tick_callback(_tick)


def en_game_thread(thunk, timeout: float = 30.0):
    """Encola un callable para correr en el game thread; espera y devuelve su resultado."""
    holder: dict = {}
    ev = threading.Event()
    _PENDIENTES.put((thunk, holder, ev))
    if not ev.wait(timeout):
        return "(timeout: el editor no respondió — ¿está vivo y ticando?)"
    return holder.get("r")


# ---- receptor TCP ----

def _atender(conn) -> None:
    with conn:
        f = conn.makefile("rwb")
        for raw in f:
            cmd = raw.decode("utf-8", "replace").strip()
            if not cmd:
                continue
            if cmd == "__quit__":
                break
            resp = en_game_thread(lambda c=cmd: api.run(c)) or "(sin respuesta del editor)"
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
    asegurar_tick()
    if _S["corriendo"]:
        unreal.log("[Jam] serve: ya está escuchando")
        return
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.listen(4)
    _S.update(sock=sock, corriendo=True)
    threading.Thread(target=_loop, args=(sock,), daemon=True).start()
    unreal.log(f"[Jam] serve: escuchando en 127.0.0.1:{port} — cliente externo → jam.api → oráculo")


def detener() -> None:
    _S["corriendo"] = False
    if _S["sock"] is not None:
        try:
            _S["sock"].close()
        except Exception:  # noqa: BLE001
            pass
        _S["sock"] = None
    unreal.log("[Jam] serve: detenido")
