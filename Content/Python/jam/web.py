"""jam.web — servidor HTTP dentro del editor que sirve una UI WEB que habla `jam.api`.

La prueba VISUAL de "UI fuera de Unreal": abrís http://127.0.0.1:8790 en el navegador y manejás Jam.
La página y los endpoints salen del mismo origen (sin CORS). Cada endpoint marshalla al game thread
(`jam.serve.en_game_thread`) y llama al contrato `jam.api`. Arrancar: `py import jam.web; jam.web.iniciar()`.

Endpoints:  GET /  (la página) · GET /spec · GET /assets?q= ·
            POST /run · /run_graph · /confirm · /discard  (body = comando/JSON)
"""

from __future__ import annotations

import http.server
import os
import threading
import urllib.parse

import unreal

from . import api, serve

_PORT = 8790
_DIR = os.path.join(os.path.dirname(__file__), "web")
_SRV = {"server": None}


def _html() -> str:
    try:
        with open(os.path.join(_DIR, "index.html"), encoding="utf-8") as fh:
            return fh.read()
    except Exception as e:  # noqa: BLE001
        return f"<pre>no encontré web/index.html: {e}</pre>"


class _Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code: int, body, ctype: str) -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            return self._send(200, _html(), "text/html; charset=utf-8")
        if parsed.path == "/spec":
            r = serve.en_game_thread(api.spec) or "{}"
            return self._send(200, r, "application/json; charset=utf-8")
        if parsed.path == "/assets":
            q = urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
            r = serve.en_game_thread(lambda: api.assets(q)) or "[]"
            return self._send(200, r, "application/json; charset=utf-8")
        return self._send(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        n = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        if parsed.path == "/run":
            r = serve.en_game_thread(lambda: api.run(body))
        elif parsed.path == "/run_graph":
            r = serve.en_game_thread(lambda: api.run_graph(body))
        elif parsed.path == "/confirm":
            r = serve.en_game_thread(api.confirm)
        elif parsed.path == "/discard":
            r = serve.en_game_thread(api.discard)
        else:
            return self._send(404, "not found", "text/plain; charset=utf-8")
        return self._send(200, r or "(sin respuesta)", "text/plain; charset=utf-8")

    def log_message(self, *_a) -> None:   # silenciar el log del http.server
        pass


def iniciar(port: int = _PORT) -> None:
    """Arranca el servidor HTTP + la UI web. Idempotente."""
    serve.asegurar_tick()
    if _SRV["server"] is not None:
        unreal.log(f"[Jam] web: ya está en http://127.0.0.1:{port}")
        return
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    _SRV["server"] = server
    threading.Thread(target=server.serve_forever, daemon=True).start()
    unreal.log(f"[Jam] web: UI en http://127.0.0.1:{port} — abrila en el navegador")


def detener() -> None:
    if _SRV["server"] is not None:
        _SRV["server"].shutdown()
        _SRV["server"] = None
    unreal.log("[Jam] web: detenido")
