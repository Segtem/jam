"""El adaptador de Godot, del lado del NÚCLEO (tarea `base-comun`, paso 2). Cerebro puro: sin `unreal`.

El núcleo corre FUERA de Godot —en este proceso de Python— y le habla por TCP al plugin de editor
de Jam para Godot (`Godot/addons/jam/`, 127.0.0.1:8792): una línea de JSON por pedido y otra por
respuesta. Lo que se calcula (la base común, las ops de Flow) se calcula acá; a Godot sólo le llegan
las PRIMITIVAS del contrato: mostrar una malla, descartar, fijar, contar lo que hay.

El contrato habla en el marco del núcleo —el de Unreal: centímetros, Z arriba—. El plugin traduce a
Godot (metros, Y arriba) y devuelve los hechos traducidos de vuelta, así se comparan tal cual con los
que mide Unreal.
"""

from __future__ import annotations

import json
import socket

from . import comun, flow, malla_core, registro

PUERTO = 8792
CONTRATO = 1


class ErrorAdaptador(RuntimeError):
    """Godot no contestó, o contestó que no."""


class Cliente:
    """Una conexión al plugin de Godot. Un pedido por línea, una respuesta por línea."""

    def __init__(self, host: str = "127.0.0.1", puerto: int = PUERTO, plazo: float = 60.0):
        try:
            self._sock = socket.create_connection((host, puerto), timeout=plazo)
        except OSError as e:
            raise ErrorAdaptador(f"no hay un editor de Godot con Jam escuchando en {host}:{puerto} "
                                 f"({e}). Abrí el proyecto en el editor con el plugin Jam activo.") from None
        self._leer = self._sock.makefile("r", encoding="utf-8", newline="\n")

    def pedir(self, op: str, **datos) -> dict:
        self._sock.sendall((json.dumps({"op": op, **datos}) + "\n").encode("utf-8"))
        linea = self._leer.readline()
        if not linea:
            raise ErrorAdaptador(f"Godot cerró la conexión en «{op}»")
        r = json.loads(linea)
        if not r.get("ok"):
            raise ErrorAdaptador(f"Godot rechazó «{op}»: {r.get('error', r)}")
        return r

    def cerrar(self) -> None:
        self._leer.close()
        self._sock.close()


def _envolver_flow(kind: str, salidas: dict):
    implementacion, aridad = flow.OPS[kind]

    def fn(entrada=None, **params):
        entradas = [] if aridad == 0 else (
            [e for e in (entrada or []) if e is not None] if aridad == -1
            else ([entrada] if entrada is not None else []))
        salidas[kind] = implementacion(entradas, params)
        return f"{kind.replace('_', ' ').upper()} P ✓ — {len(salidas[kind])} puntos"
    return fn


class AdaptadorGodot:
    """Lo que `graph.ejecutar_detalle` le pide a un adaptador, con Godot del otro lado."""

    MOTOR = "godot"
    REGISTRO = registro.REGISTRO

    def __init__(self, cliente: Cliente):
        self.cliente = cliente
        self._salidas: dict = {}
        hola = cliente.pedir("hola")
        if hola.get("contrato") != CONTRATO:
            raise ErrorAdaptador(f"el plugin de Godot habla el contrato {hola.get('contrato')}, "
                                 f"el núcleo el {CONTRATO}: actualizá uno de los dos")
        self.version_godot = hola.get("version", "")

    def capacidades(self) -> frozenset:
        """Lo que se puede correr con Godot del otro lado: la base común, las ops de Flow y las
        primitivas del contrato."""
        return frozenset(registro.COMUNES | registro.PRIMITIVAS
                         | {v for v, i in registro.REGISTRO.items() if i.get("_flow_op")})

    def implementacion(self, verbo: str):
        if verbo in comun.IMPLEMENTA:
            calcular = comun.IMPLEMENTA[verbo]

            def fn(entrada=None, **kw):
                try:
                    self._salidas[verbo] = calcular(entrada, **kw)
                except malla_core.MallaError as e:
                    raise RuntimeError(str(e)) from None
                return f"{verbo.upper()} M ✓ — {malla_core.info(self._salidas[verbo])}"
            return fn
        if verbo == "mesh_preview":
            def mostrar(entrada=None, *, name="JamPreview"):
                if not isinstance(entrada, malla_core.Malla):
                    raise RuntimeError("mesh_preview necesita una malla M del núcleo")
                r = self.cliente.pedir("mostrar_malla", nombre=str(name or "JamPreview"),
                                       malla=malla_core.a_dict(entrada))
                self._salidas[verbo] = entrada
                h = r["hechos"]
                return (f"PREVIEW M ✓ — en Godot: {h['triangulos']} triángulos · "
                        f"{h['posiciones']} vértices · «{r['nodo']}»")
            return mostrar
        if registro.REGISTRO.get(verbo, {}).get("_flow_op"):
            return _envolver_flow(verbo, self._salidas)
        raise RuntimeError(f"«{verbo}» no tiene implementación en Godot")

    def limpiar_asset_producido_runtime(self, verbo: str) -> None:
        self._salidas.pop(verbo, None)

    def dato_producido_runtime(self, verbo: str, entrada=None):
        return self._salidas.get(verbo)


def correr_texto(texto_: str, adaptador) -> dict:
    """Un grafo escrito como texto, corrido con el núcleo y `adaptador` del otro lado.

    `{ok, report, nodes, errores}`, como `api.run_text`. El Compile juzga contra lo que el adaptador
    implementa: un verbo que Godot no tiene es un error con su porqué, no un fallo en el medio.
    """
    from . import graph, texto
    try:
        g = texto.leer(texto_)
    except texto.ErrorTexto as e:
        return {"ok": False, "report": str(e), "nodes": {},
                "errores": [{"linea": e.linea, "columna": e.columna, "nodo": "", "mensaje": e.mensaje}]}
    lineas = texto.lineas(texto_)
    try:
        plan = graph.compilar(g, registro=registro.REGISTRO, motor=adaptador.MOTOR,
                              implementados=adaptador.capacidades())
    except graph.GraphValidationError as e:
        errores = [{"linea": lineas.get(n, 0), "columna": 0, "nodo": n, "mensaje": " · ".join(m)}
                   for n, m in e.diagnostics.items()]
        return {"ok": False, "report": str(e), "nodes": {}, "errores": errores}
    reporte, por_nodo = graph.ejecutar_detalle(g, plan, adaptador=adaptador)
    ok = not any(r.get("estado") == "error" for r in por_nodo.values())
    return {"ok": ok, "report": reporte, "nodes": por_nodo, "errores": []}
