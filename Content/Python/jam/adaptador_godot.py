"""El adaptador de Godot, del lado del NÚCLEO (tarea `base-comun`, paso 2). Cerebro puro: sin `unreal`.

El núcleo corre FUERA de Godot —en este proceso de Python— y le habla por TCP al plugin de editor
de Jam para Godot (`Godot/addons/jam/`, 127.0.0.1:8792): una línea de JSON por pedido y otra por
respuesta. Lo que se calcula (la base común, las ops de Flow) se calcula acá; a Godot sólo le llegan
las PRIMITIVAS del contrato (`docs/contrato-motor.md`): mostrar una malla, descartar, fijar, contar
lo que hay, y para colocar: guardar una malla como asset, resolver un asset, instanciarlo, raycast.

El contrato habla en el marco del núcleo —el de Unreal: centímetros, Z arriba—. El plugin traduce a
Godot (metros, Y arriba) y devuelve los hechos traducidos de vuelta, así se comparan tal cual con los
que mide Unreal.
"""

from __future__ import annotations

import hashlib
import json
import socket

from . import colocacion, comun, flow, malla_core, registro

PUERTO = 8792
CONTRATO = 1
#: Las ops que hacen falta para `asset`, `mesh_to_static` y `place`. Un plugin viejo que no las
#: anuncia sigue sirviendo para lo demás: esos verbos quedan deshabilitados con su porqué.
OPS_COLOCAR = frozenset({"guardar_malla", "resolver_asset", "colocar", "raycast"})
VERBOS_COLOCAR = frozenset({"asset", "mesh_to_static", "place"})


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
        self._colocar = OPS_COLOCAR <= set(hola.get("primitivas", []))
        self._cajas: dict[str, colocacion.AABB] = {}   # ruta → caja local, para no repreguntar

    def capacidades(self) -> frozenset:
        """Lo que se puede correr con Godot del otro lado: la base común, las ops de Flow y las
        primitivas del contrato."""
        return frozenset(registro.COMUNES | (registro.PRIMITIVAS - VERBOS_COLOCAR)
                         | (VERBOS_COLOCAR if self._colocar else frozenset())
                         | {v for v, i in registro.REGISTRO.items() if i.get("_flow_op")})

    # ---- lo que el Compile le pregunta al motor ----

    def resolver_asset(self, nombre: str) -> str | None:
        r = self.cliente.pedir("resolver_asset", nombre=str(nombre))
        self._cajas[r["ruta"]] = colocacion.caja_de(r["min"], r["max"])
        return r["ruta"]

    @staticmethod
    def transformar_asset(verbo: str, _asset, params: dict) -> str | None:
        # La ruta real la da el motor al guardar; al Compile le alcanza saber que habrá una.
        return f"jam:{params.get('name', 'GeneratedMesh')}" if verbo == "mesh_to_static" else None

    def opciones_compile(self) -> dict:
        if not self._colocar:
            return {}
        return {"resolver_asset": self.resolver_asset, "transformar_asset": self.transformar_asset}

    def _caja(self, ruta: str):
        if ruta not in self._cajas:
            self.resolver_asset(ruta)
        return self._cajas[ruta]

    def implementacion(self, verbo: str):
        if verbo in comun.IMPLEMENTA:
            calcular = comun.IMPLEMENTA[verbo]

            def fn(entrada=None, **kw):
                try:
                    self._salidas[verbo], texto = calcular(entrada, **kw)
                except malla_core.MallaError as e:
                    raise RuntimeError(str(e)) from None
                return texto
            return fn
        if verbo == "mesh_preview":
            def mostrar(entrada=None, *, name="JamPreview"):
                if not isinstance(entrada, malla_core.Malla):
                    raise RuntimeError("mesh_preview necesita una malla M del núcleo")
                self._limpiar_preview()
                r = self.cliente.pedir("mostrar_malla", nombre=str(name or "JamPreview"),
                                       malla=malla_core.a_dict(entrada))
                self._salidas[verbo] = entrada
                h = r["hechos"]
                return (f"PREVIEW M ✓ — en Godot: {h['triangulos']} triángulos · "
                        f"{h['posiciones']} vértices · «{r['nodo']}»")
            return mostrar
        if verbo in VERBOS_COLOCAR and self._colocar:
            return getattr(self, "_" + verbo)
        if registro.REGISTRO.get(verbo, {}).get("_flow_op"):
            return _envolver_flow(verbo, self._salidas)
        raise RuntimeError(f"«{verbo}» no tiene implementación en Godot")

    # ---- colocar: el núcleo decide dónde (`jam.colocacion`), el motor instancia ----

    def _asset(self, entrada=None, *, name=""):
        ruta = self.resolver_asset(entrada or name)
        self._salidas["asset"] = ruta
        return f"ASSET ✓ — {ruta}"

    def _mesh_to_static(self, entrada=None, *, name="GeneratedMesh", **_otros):
        # folder/collision/… son de Unreal: cada motor guarda donde guarda sus assets.
        if not isinstance(entrada, malla_core.Malla):
            raise RuntimeError("mesh_to_static necesita una malla M del núcleo")
        r = self.cliente.pedir("guardar_malla", nombre=str(name), malla=malla_core.a_dict(entrada))
        h = malla_core.hechos(entrada)
        self._cajas[r["ruta"]] = colocacion.caja_de(h["min"], h["max"])
        self._salidas["mesh_to_static"] = r["ruta"]
        return f"STATIC MESH ✓ — {r['ruta']} · {malla_core.info(entrada)}"

    def _raycast(self, desde, hacia) -> dict:
        return self.cliente.pedir("raycast", rayos=[{"desde": list(desde), "hacia": list(hacia)}])[
            "golpes"][0]

    def _place(self, entrada=None, *, points=None, **params):
        rutas = [entrada] if isinstance(entrada, str) else [r for r in (entrada or []) if r]
        self._limpiar_preview()   # ANTES del raycast: el Preview del Run anterior no es suelo
        try:
            instancias, pisados = colocacion.planear(
                [self._caja(r) for r in rutas], puntos=points, raycast=self._raycast, **params)
        except colocacion.ErrorColocacion as e:
            raise RuntimeError(str(e)) from None
        medidas = []
        for i, ruta in enumerate(rutas):   # un grupo por asset: la primitiva coloca UN asset
            suyas = [dict(pos=x["pos"], yaw=x["yaw"], escala=x["escala"])
                     for x in instancias if x["asset"] == i]
            if suyas:
                nombre = "Jam_place_" + hashlib.sha1(
                    json.dumps([ruta, suyas]).encode()).hexdigest()[:8]
                medidas += self.cliente.pedir("colocar", ruta=ruta, nombre=nombre,
                                              instancias=suyas)["instancias"]
        self._salidas["place"] = medidas
        self.colocadas = getattr(self, "colocadas", []) + medidas
        motor = self.MOTOR.capitalize()
        return (f"PLACE ✓ — {len(medidas)} colocado(s)"
                + (f" en {len(list(points))} punto(s) · {pisados} pisado(s)" if points else "")
                + f" · en {motor}")

    def empezar_corrida(self) -> None:
        """Cada Run empieza sin el Preview del anterior, como en Unreal —donde el anterior sigue
        vivo pero el raycast lo ignora—: si no, `surface` se apoyaría en la copia vieja y cada Run
        subiría un poco. Lo fijado no se toca. Se descarta recién antes de lo primero que el Run
        muestra o coloca: una corrida que sólo calcula no molesta al motor.
        ponytail: no es transaccional; si el Run nuevo falla, el Preview anterior ya no está."""
        self._preview_limpio = False
        self.colocadas = []

    def _limpiar_preview(self) -> None:
        if not getattr(self, "_preview_limpio", True):
            self.cliente.pedir("descartar")
            self._preview_limpio = True

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
                              implementados=adaptador.capacidades(), **adaptador.opciones_compile())
    except graph.GraphValidationError as e:
        errores = [{"linea": lineas.get(n, 0), "columna": 0, "nodo": n, "mensaje": " · ".join(m)}
                   for n, m in e.diagnostics.items()]
        return {"ok": False, "report": str(e), "nodes": {}, "errores": errores}
    reporte, por_nodo = graph.ejecutar_detalle(g, plan, adaptador=adaptador)
    ok = not any(r.get("estado") == "error" for r in por_nodo.values())
    return {"ok": ok, "report": reporte, "nodes": por_nodo, "errores": []}
