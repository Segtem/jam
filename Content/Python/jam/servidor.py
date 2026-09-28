"""El editor de nodos de Jam, en la web, FUERA del motor. Cerebro puro: sin `unreal`.

Etapa 3 de `fuera-del-motor`. Un solo editor (`web/editor.html`) para los tres motores:

- En Unreal lo sirve la puerta que Jam ya abre dentro del editor (`jam.web`, 127.0.0.1:8790), con el
  núcleo corriendo en el Python del editor.
- En Godot y Unity lo sirve ESTE proceso: el núcleo corre acá y le habla al plugin del motor por el
  contrato (`adaptador_godot` / `adaptador_unity`). Lo lanza el menú «Jam ▸ Abrir editor» del motor.

    python -m jam.servidor --motor godot [--puerto 8795] [--abrir]

El protocolo es el de `jam.web`: `POST /api/<función>` con `{"args": [...]}` → `{"resultado": "<json>"}`,
con una lista cerrada de funciones (`Nucleo.PUBLICAS`). Así el editor no sabe qué motor tiene detrás.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import shutil
import subprocess
import threading
import webbrowser
from pathlib import Path

WEB = Path(__file__).resolve().parent / "web"
#: Uno por motor, para que los dos editores puedan estar abiertos a la vez (Unreal usa 8790).
PUERTOS = {"godot": 8795, "unity": 8796}
PUERTO = PUERTOS["godot"]


class Nucleo:
    """El núcleo de Jam con un motor del otro lado del contrato."""

    PUBLICAS = frozenset({"estado", "spec_editor", "compilar_grafo", "correr_grafo",
                          "texto_de_grafo", "grafo_de_texto", "preview", "ejemplos", "ejemplo",
                          "grafo_inicial"})

    def __init__(self, motor: str):
        self.motor = motor
        self._adaptador = None
        self._lock = threading.Lock()

    # ---- el motor ----

    def _modulo(self):
        from . import adaptador_godot, adaptador_unity
        return adaptador_godot if self.motor == "godot" else adaptador_unity

    def adaptador(self):
        """Conecta la primera vez y reconecta si el motor se cerró: el editor web puede quedar abierto
        mientras el humano reinicia Godot."""
        mod = self._modulo()
        if self._adaptador is None:
            clase = mod.AdaptadorGodot if self.motor == "godot" else mod.AdaptadorUnity
            self._adaptador = clase(mod.Cliente(plazo=60))
        return self._adaptador

    def _implementados(self):
        try:
            return self.adaptador().capacidades()
        except Exception:  # noqa: BLE001 — sin motor se juzga por lo declarado
            return None

    # ---- lo que llama el editor ----

    def estado(self) -> dict:
        try:
            self.adaptador()
            return {"motor": self.motor, "conectado": True}
        except Exception as e:  # noqa: BLE001
            self._adaptador = None
            return {"motor": self.motor, "conectado": False, "error": str(e)}

    def spec_editor(self) -> dict:
        from . import registro
        return registro.spec_canvas(self.motor, self._implementados())

    def compilar_grafo(self, grafo_json: str) -> dict:
        from . import graph, registro
        g = graph.JamGraph.from_json(grafo_json)
        try:
            graph.compilar(g, registro=registro.REGISTRO, motor=self.motor,
                           implementados=self._implementados())
        except graph.GraphValidationError as e:
            nodos = {n: {"estado": "error", "texto": " · ".join(m)} for n, m in e.diagnostics.items()
                     if n in g.nodes}
            for n in g.nodes:
                nodos.setdefault(n, {"estado": "ok", "texto": "Compile ✓"})
            return {"ok": False, "report": str(e), "nodes": nodos}
        return {"ok": True, "report": f"COMPILE ✓ — {len(g.nodes)} nodos",
                "nodes": {n: {"estado": "ok", "texto": "Compile ✓"} for n in g.nodes}}

    def correr_grafo(self, grafo_json: str) -> dict:
        from . import graph, registro
        compilado = self.compilar_grafo(grafo_json)
        if not compilado["ok"]:
            return compilado
        g = graph.JamGraph.from_json(grafo_json)
        try:
            ad = self.adaptador()
        except Exception as e:  # noqa: BLE001
            self._adaptador = None
            return {"ok": False, "report": f"RUN ✗ — {e}", "nodes": {}}
        plan = graph.compilar(g, registro=registro.REGISTRO, motor=self.motor,
                              implementados=ad.capacidades())
        with self._lock:
            reporte, por_nodo = graph.ejecutar_detalle(g, plan, adaptador=ad)
        ok = not any(r.get("estado") == "error" for r in por_nodo.values())
        return {"ok": ok, "report": reporte, "nodes": por_nodo}

    def texto_de_grafo(self, grafo_json: str) -> dict:
        from . import graph, texto
        try:
            return {"ok": True, "texto": texto.imprimir(graph.JamGraph.from_json(grafo_json))}
        except ValueError as e:
            return {"ok": False, "error": str(e)}

    def grafo_de_texto(self, texto_: str, base_json: str = "") -> dict:
        from . import texto
        try:
            g = texto.aplicar(texto_, base_json)
        except texto.ErrorTexto as e:
            return {"ok": False, "graph": None, "errores": [
                {"linea": e.linea, "columna": e.columna, "nodo": "", "mensaje": e.mensaje}]}
        compilado = self.compilar_grafo(json.dumps(g))
        lineas = texto.lineas(texto_)
        errores = [{"linea": lineas.get(n, 0), "columna": 0, "nodo": n, "mensaje": r["texto"]}
                   for n, r in compilado["nodes"].items() if r["estado"] == "error"]
        return {"ok": not errores, "graph": g, "errores": errores}

    def ejemplos(self) -> list:
        from . import ejemplos
        return ejemplos.listar(self.motor, self._implementados())

    def ejemplo(self, nombre: str) -> dict:
        from . import ejemplos
        return ejemplos.grafo(nombre)

    def grafo_inicial(self) -> dict:
        """Lo que muestra el editor al abrirse: la vitrina de la base común, que corre en todos."""
        from . import ejemplos
        return {"nombre": ejemplos.INICIAL, "graph": ejemplos.grafo(ejemplos.INICIAL)}

    def preview(self, accion: str) -> dict:
        op = {"bake": "fijar", "discard": "descartar"}.get(accion)
        if op is None:
            return {"ok": False, "error": "accion es bake o discard"}
        try:
            return self.adaptador().cliente.pedir(op)
        except Exception as e:  # noqa: BLE001
            self._adaptador = None
            return {"ok": False, "error": str(e)}


def _handler(nucleo: Nucleo):
    class Handler(http.server.BaseHTTPRequestHandler):
        def _enviar(self, codigo: int, cuerpo: bytes, tipo: str) -> None:
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            ruta = self.path.split("?", 1)[0]
            archivo = WEB / ("editor.html" if ruta in ("/", "/editor") else ruta.lstrip("/"))
            archivo = archivo.resolve()
            if WEB not in archivo.parents or not archivo.is_file():
                return self._enviar(404, b"no encontrado", "text/plain; charset=utf-8")
            tipo = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}.get(
                archivo.suffix, "application/octet-stream")
            return self._enviar(200, archivo.read_bytes(), tipo + "; charset=utf-8")

        def do_POST(self):
            nombre = self.path.split("?", 1)[0].removeprefix("/api/")
            if nombre not in Nucleo.PUBLICAS:
                return self._enviar(404, json.dumps({"error": f"«{nombre}» no es pública"}).encode(),
                                    "application/json")
            n = int(self.headers.get("Content-Length", 0) or 0)
            try:
                args = [str(a) for a in (json.loads(self.rfile.read(n) or b"{}").get("args") or [])]
                resultado = getattr(nucleo, nombre)(*args)
            except Exception as e:  # noqa: BLE001 — el editor muestra el error, no se cae
                resultado = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            cuerpo = json.dumps({"resultado": json.dumps(resultado, ensure_ascii=False)},
                                ensure_ascii=False).encode("utf-8")
            return self._enviar(200, cuerpo, "application/json; charset=utf-8")

        def log_message(self, *_a):
            pass
    return Handler


def abrir_ventana(url: str) -> None:
    """Una ventana propia, sin barras (modo aplicación de Chromium/Chrome), para que se sienta una
    ventana del motor; si no hay, el navegador por defecto."""
    for nav in ("chromium", "google-chrome-stable", "google-chrome", "brave"):
        if shutil.which(nav):
            subprocess.Popen([nav, f"--app={url}", "--new-window"], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
            return
    webbrowser.open(url)


def servir(motor: str, puerto: int = PUERTO, abrir: bool = False) -> None:
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", puerto), _handler(Nucleo(motor)))
    url = f"http://127.0.0.1:{puerto}/"
    print(f"JAM_EDITOR {motor} en {url}", flush=True)
    if abrir:
        abrir_ventana(url)
    servidor.serve_forever()


def main(argv=None) -> None:
    import sys
    sys.modules.setdefault("unreal", None)   # el núcleo corre sin Unreal: si algo lo pide, que falle acá
    a = argparse.ArgumentParser(description="Editor web de Jam con Godot o Unity del otro lado.")
    a.add_argument("--motor", choices=("godot", "unity"), required=True)
    a.add_argument("--puerto", type=int, default=int(os.environ.get("JAM_EDITOR_PUERTO", 0)) or None)
    a.add_argument("--abrir", action="store_true", help="abre la ventana del editor")
    args = a.parse_args(argv)
    servir(args.motor, args.puerto or PUERTOS[args.motor], args.abrir)


if __name__ == "__main__":
    main()
