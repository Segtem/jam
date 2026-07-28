"""El contrato del compilador Weight → Material: el material tiene que VALER lo mismo que la máscara.

Un test de topología diría que está bien un material que conectó `Min` donde iba `Max`, que trabaja
en radianes donde iban grados o que se comió un `1 - x`. Por eso el grueso de este archivo no mira la
forma del grafo: evalúa el IR con `shader.evaluar` y lo compara contra `flow`, que es la definición
de la máscara, en los mismos puntos. Si los dos números coinciden, la traducción es correcta; si no,
el test dice en qué punto y por cuánto.

Lo que queda deliberadamente afuera de esa comparación —y está anotado donde corresponde— es el
DIBUJO del ruido: UE hashea distinto. Todo lo demás del nodo de ruido (escala, plano XY, rango 0..1,
contraste) sí se compara, pasándole a `evaluar` el ruido de Jam.
"""

from __future__ import annotations

import math
import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import flow, scatter_core as sc, shader, weight_material  # noqa: E402
from jam.geometry import Vec3  # noqa: E402


def muestra(x, y, z, *, inclinacion=0.0, weight=1.0):
    """Un punto con su normal, y la pendiente que esa normal implica.

    El orden importa: primero la NORMAL, después la pendiente. La pendiente no viaja al material —
    el shader la deduce de la normal del vértice—, así que si el test partiera de un número de
    pendiente inventado estaría comparando la máscara contra sí misma. `inclinacion` puede pasar de
    90°, que es como se representa un techo o un alero: la normal apunta para abajo.
    """
    rad = math.radians(inclinacion)
    normal = Vec3(math.sin(rad), 0.0, math.cos(rad))
    return sc.Sample(Vec3(x, y, z), normal, sc.grados_pendiente(normal),
                     sc.semilla_de(0, x, y), (0.0, 0.0), weight)


def entorno_de(s) -> dict:
    """El mismo punto, visto por el shader: posición de mundo y normal."""
    return {"posicion": (s.pos.x, s.pos.y, s.pos.z),
            "normal": (s.normal.x, s.normal.y, s.normal.z)}


def cadena(*pasos, final_extra=None):
    """Un Flow lineal: una fuente y las ops de Weight encadenadas. Devuelve (flujo, id_final).

    La fuente es `source_surface` a propósito: es la única que NO tiene implementación pura (la
    raycastea el adaptador), así que `peso_cpu` puede inyectar los puntos del test en su lugar. Con
    una fuente pura, el grafo generaría sus propios puntos y el test compararía dos cosas distintas
    creyendo que compara la misma —que es exactamente lo que pasó la primera vez.
    """
    f = flow.Flow()
    previo = f.add("source_surface", {}, nid="src")
    for i, (kind, params) in enumerate(pasos):
        actual = f.add(kind, params, nid=f"w{i}")
        f.connect(previo, actual)
        previo = actual
    if final_extra:
        ultimo = f.add(final_extra, {}, nid="fin")
        f.connect(previo, ultimo)
        previo = ultimo
    return f, previo


def compilar(*pasos, **kwargs):
    flujo, final = cadena(*pasos, **kwargs)
    return weight_material.desde_flow(flujo, final)


def _sat(v):
    return max(0.0, min(1.0, v))


def streams_cpu(flujo, muestras) -> dict:
    """El stream que deja CADA nodo del tab, corriendo las ops de verdad."""
    variables = flujo._valores()
    escalares = flujo.escalares_de_valor(variables)
    salidas = {}
    for nid in flujo.topo():
        kind = flujo.nodos[nid]["kind"]
        params = flujo.params_efectivos(nid, variables, escalares)
        entradas = [salidas.get(e, []) for e in
                    [a for a, ap, b, bp in flujo.enlaces if b == nid and bp == "in"]]
        if kind not in flow.OPS:          # la fuente: el stream de partida
            salidas[nid] = list(muestras)
            continue
        salidas[nid] = flow.OPS[kind][0](entradas, params)
    return salidas


def peso_cpu(flujo, final, muestras):
    """El `weight` que la cadena del tab le deja a cada punto.

    Saturado, porque es lo que el material hace con el gris antes de usarlo. En CPU el `weight` puede
    pasarse de 1 (`weight_combine add` suma sin techo) y recién se recorta donde se USA
    —`weight_power` satura, `weight_cull` compara—; el material lo recorta una vez al final. Para
    todo lo que ya vive en 0..1, saturar no cambia nada.
    """
    return [_sat(s.weight) for s in streams_cpu(flujo, muestras)[final]]


def ruido_de_jam(seed=0):
    """El `value_noise` de Jam como nodo `Noise`, con una exigencia: la Z tiene que llegar en cero.

    La máscara de CPU es 2D. Si el compilador se olvidara de aplanar la posición a XY, el ruido de la
    GPU cambiaría con la altura y un evaluador que ignore la Z no lo notaría nunca. Por eso acá se
    revisa en vez de ignorarla.
    """
    def ruido(x, y, z):
        if abs(z) > 1e-9:
            raise AssertionError(
                f"el nodo Noise recibió z={z}: la posición no se aplanó a XY, así que el ruido del "
                "material cambiaría con la altura y el del scatter no")
        return sc.value_noise(x, y, 1.0, seed)
    return ruido


def peso_gpu(compilado, muestras, *, seed=0):
    """El mismo número, sacado del IR del material."""
    grafo, mascara = compilado["grafo"], compilado["mascara"]
    ruido = ruido_de_jam(seed)
    return [shader.evaluar(grafo, entorno_de(s), ruido=ruido)[mascara][0] for s in muestras]


# Puntos repartidos en X, Y, Z y en inclinación. El barrido de inclinación llega a 150° a propósito:
# arriba de 90 la normal apunta para abajo (un techo), que es el caso donde el `abs` de la pendiente
# es la diferencia entre «tan plano como el piso» y «no lo agarra ninguna máscara».
PUNTOS = [muestra(x * 137.0 - 400.0, y * 91.0 - 300.0, x * 53.0 - 120.0,
                  inclinacion=(x * 23 + y * 31) % 151)
          for x in range(7) for y in range(5)]


class EquivalenciaTests(unittest.TestCase):
    """El corazón: el material vale lo mismo que la máscara, punto por punto."""

    def comparar(self, *pasos, puntos=None, tolerancia=1e-6, seed=0):
        puntos = puntos if puntos is not None else PUNTOS
        flujo, final = cadena(*pasos)
        compilado = weight_material.desde_flow(flujo, final)
        self.assertNotIn("error", compilado, compilado.get("error"))
        self.assertEqual(shader.verificar(compilado["grafo"]), [])
        esperado = peso_cpu(flujo, final, puntos)
        obtenido = peso_gpu(compilado, puntos, seed=seed)
        peor = max(abs(a - b) for a, b in zip(esperado, obtenido))
        self.assertLess(peor, tolerancia,
                        f"peor diferencia {peor:.6f} en {pasos}\n"
                        f"  cpu={[round(v, 4) for v in esperado[:6]]}\n"
                        f"  gpu={[round(v, 4) for v in obtenido[:6]]}")
        return compilado

    def test_slope_matches(self):
        """La pendiente es la que más chances tiene de salir mal: en CPU es un número del Sample y en
        GPU hay que sacarla de la normal, en grados y no en radianes."""
        self.comparar(("weight_slope", {"min": 10.0, "max": 55.0, "soft": 8.0}))

    def test_height_matches(self):
        self.comparar(("weight_height", {"min": -50.0, "max": 180.0, "soft": 40.0}))

    def test_radial_matches(self):
        self.comparar(("weight_radial", {"cx": 120.0, "cy": -60.0, "radius": 400.0, "soft": 0.4}))

    def test_radial_with_a_hard_edge_matches(self):
        """`soft=0` deja Min == Max en la rampa: es el caso que obliga al EPS."""
        self.comparar(("weight_radial", {"cx": 0.0, "cy": 0.0, "radius": 350.0, "soft": 0.0}))

    def test_the_noise_plumbing_matches(self):
        """El dibujo del ruido no puede coincidir (UE hashea distinto), pero todo lo que lo rodea sí:
        la escala, el aplanado a XY, el rango 0..1 y el contraste. Con `seed=0` el desplazamiento es
        nulo, así que alimentando el evaluador con el ruido de Jam los dos tienen que dar lo mismo."""
        self.comparar(("weight_noise", {"scale": 250.0, "seed": 0, "contrast": 1.6}))

    def test_the_reshapers_match(self):
        self.comparar(("weight_slope", {"min": 0.0, "max": 70.0, "soft": 10.0}),
                      ("weight_power", {"k": 2.5}))
        self.comparar(("weight_height", {"min": 0.0, "max": 200.0, "soft": 30.0}),
                      ("weight_invert", {}))
        self.comparar(("weight_radial", {"radius": 500.0, "soft": 0.5}),
                      ("weight_curve", {"min": 0.2, "max": 0.8}))

    def test_a_whole_chain_matches(self):
        """Cuatro ops encadenadas: es donde se ve si el AND suave se acumula igual en los dos lados."""
        self.comparar(("weight_slope", {"min": 5.0, "max": 60.0, "soft": 6.0}),
                      ("weight_height", {"min": -100.0, "max": 250.0, "soft": 45.0}),
                      ("weight_noise", {"scale": 300.0, "seed": 0, "contrast": 1.2}),
                      ("weight_power", {"k": 1.8}))

    def test_every_step_of_the_chain_matches_and_not_just_the_end(self):
        """Compara nodo POR nodo del tab contra el nodo del material que le corresponde.

        Mirar sólo el final deja pasar errores que el `Saturate` de la salida vuelve a tapar: sin el
        `Saturate` de `weight_power`, un gris de 1.4 elevado a 2 da 1.96 y el recorte final lo
        devuelve a 1, así que el material sale bien por una compensación y no porque esté bien.
        """
        f = flow.Flow()
        fuente = f.add("source_surface", {}, nid="src")
        a = f.add("weight_slope", {"min": 0.0, "max": 90.0, "soft": 5.0}, nid="a")
        b = f.add("weight_height", {"min": -500.0, "max": 500.0, "soft": 30.0}, nid="b")
        junta = f.add("weight_combine", {"mode": "add"}, nid="j")
        fuerte = f.add("weight_power", {"k": 2.0}, nid="p")
        for origen, destino in ((fuente, a), (fuente, b), (a, junta), (b, junta), (junta, fuerte)):
            f.connect(origen, destino)

        compilado = weight_material.desde_flow(f, fuerte)
        streams = streams_cpu(f, PUNTOS)
        ruido = ruido_de_jam(0)
        valores = [shader.evaluar(compilado["grafo"], entorno_de(s), ruido=ruido) for s in PUNTOS]
        self.assertGreater(max(s.weight for s in streams[junta]), 1.0,
                           "la suma no se pasa de 1: el caso no prueba nada")
        for nid, nodo_ir in compilado["por_nodo"].items():
            with self.subTest(nodo=nid, kind=f.nodos[nid]["kind"]):
                esperado = [s.weight for s in streams[nid]]
                obtenido = [v[nodo_ir][0] for v in valores]
                peor = max(abs(x - y) for x, y in zip(esperado, obtenido))
                self.assertLess(peor, 1e-6, f"«{nid}» difiere en {peor}")

    def test_a_weight_above_one_is_clamped_before_it_is_used(self):
        """`weight_combine add` puede pasar de 1. En CPU eso lo recorta la op que lo USA
        (`weight_power` satura antes de elevar); en el material lo recorta el `Saturate`. Sin ese
        recorte, un gris de 1.4 elevado a 2 da 1.96 y el material queda clavado en el color B."""
        f = flow.Flow()
        fuente = f.add("source_surface", {}, nid="src")
        a = f.add("weight_slope", {"min": 0.0, "max": 90.0, "soft": 5.0}, nid="a")
        b = f.add("weight_height", {"min": -500.0, "max": 500.0, "soft": 30.0}, nid="b")
        junta = f.add("weight_combine", {"mode": "add"}, nid="j")
        fuerte = f.add("weight_power", {"k": 2.0}, nid="p")
        f.connect(fuente, a)
        f.connect(fuente, b)
        f.connect(a, junta)
        f.connect(b, junta)
        f.connect(junta, fuerte)
        compilado = weight_material.desde_flow(f, fuerte)
        esperado = peso_cpu(f, fuerte, PUNTOS)
        obtenido = peso_gpu(compilado, PUNTOS)
        self.assertGreater(max(esperado), 0.9, "el caso no llega a saturar: no prueba nada")
        peor = max(abs(x - y) for x, y in zip(esperado, obtenido))
        self.assertLess(peor, 1e-6, f"peor diferencia {peor}")

    def test_combine_matches_in_every_mode(self):
        """Dos ramas paralelas que se juntan — el caso que no es una cadena sino un DAG."""
        for modo in ("mul", "add", "max", "min", "lerp"):
            with self.subTest(modo=modo):
                f = flow.Flow()
                fuente = f.add("source_surface", {}, nid="src")
                a = f.add("weight_slope", {"min": 0.0, "max": 45.0, "soft": 5.0}, nid="a")
                b = f.add("weight_height", {"min": 0.0, "max": 200.0, "soft": 30.0}, nid="b")
                junta = f.add("weight_combine", {"mode": modo, "t": 0.3}, nid="j")
                f.connect(fuente, a)
                f.connect(fuente, b)
                f.connect(a, junta)
                f.connect(b, junta)
                compilado = weight_material.desde_flow(f, junta)
                self.assertNotIn("error", compilado, compilado.get("error"))
                esperado = peso_cpu(f, junta, PUNTOS)
                obtenido = peso_gpu(compilado, PUNTOS)
                peor = max(abs(x - y) for x, y in zip(esperado, obtenido))
                self.assertLess(peor, 1e-6, f"modo {modo}: peor diferencia {peor}")

    def test_it_survives_a_non_weight_node_in_the_middle(self):
        """Un nodo que no es de Weight no cambia el gris: el compilador lo tiene que atravesar, no
        cortar la cadena ahí."""
        compilado = self.comparar(("weight_slope", {"min": 0.0, "max": 50.0, "soft": 5.0}),
                                  ("info", {}),
                                  ("weight_power", {"k": 2.0}))
        self.assertEqual(compilado["ops"], ["Slope1", "Power1"])

    def test_a_node_that_drops_points_is_traversed_too(self):
        """`cull_nth` tira puntos, así que no se puede comparar valor por valor (el stream de CPU
        sale más corto). Lo que sí se exige es que el gris siga cruzándolo: una máscara dura no
        cambia el gris de los puntos que deja pasar."""
        compilado = compilar(("weight_slope", {"min": 0.0, "max": 50.0, "soft": 5.0}),
                             ("cull_nth", {"n": 2}),
                             ("weight_power", {"k": 2.0}))
        self.assertEqual(compilado["ops"], ["Slope1", "Power1"])
        self.assertEqual(shader.verificar(compilado["grafo"]), [])


class MutacionTests(unittest.TestCase):
    """La comparación anterior sólo vale si es capaz de fallar. Acá se rompe a propósito."""

    def test_the_comparison_catches_a_swapped_input(self):
        flujo, final = cadena(("weight_slope", {"min": 10.0, "max": 55.0, "soft": 8.0}))
        compilado = weight_material.desde_flow(flujo, final)
        grafo = compilado["grafo"]
        # Cruzar Min por Value en la primera rampa: un error que la topología no ve (las dos aristas
        # existen, salen de donde tienen que salir y llegan a un pin que ese nodo tiene).
        rampa = next(n.id for n in grafo.nodos if n.tipo == "SmoothStep")
        cambio = {"Min": "Value", "Value": "Min"}
        cruzadas = tuple(
            shader.Arista(a.desde, a.hasta, cambio.get(a.entrada, a.entrada), a.salida)
            if a.hasta == rampa else a
            for a in grafo.aristas)
        roto = shader.GrafoMaterial(nombre="M", nodos=grafo.nodos, aristas=cruzadas)
        self.assertEqual(shader.verificar(roto), [],
                         "el grafo mutado sigue siendo estructuralmente válido: por eso hace falta "
                         "comparar VALORES")
        esperado = peso_cpu(flujo, final, PUNTOS)
        obtenido = [shader.evaluar(roto, entorno_de(s))[compilado["mascara"]][0] for s in PUNTOS]
        self.assertGreater(max(abs(a - b) for a, b in zip(esperado, obtenido)), 1e-3)

    def test_the_comparison_catches_radians_instead_of_degrees(self):
        """El bug más probable de la pendiente, y el que se ve «casi bien» en una captura."""
        flujo, final = cadena(("weight_slope", {"min": 10.0, "max": 55.0, "soft": 8.0}))
        grafo = weight_material.desde_flow(flujo, final)["grafo"]
        sin_conversion = tuple(
            shader.Nodo(n.id, n.tipo, dict(n.props, r=1.0), n.x, n.y)
            if n.tipo == "Constant" and n.props.get("r") == weight_material.GRADOS_POR_RADIAN else n
            for n in grafo.nodos)
        roto = shader.GrafoMaterial("M", sin_conversion, grafo.aristas)
        mascara = weight_material.desde_flow(flujo, final)["mascara"]
        esperado = peso_cpu(flujo, final, PUNTOS)
        obtenido = [shader.evaluar(roto, entorno_de(s))[mascara][0] for s in PUNTOS]
        self.assertGreater(max(abs(a - b) for a, b in zip(esperado, obtenido)), 1e-3)


class ContratoTests(unittest.TestCase):
    def test_every_editable_field_becomes_a_named_parameter(self):
        """La promesa del material: lo que en el tab es un campo, en el material es un parámetro que
        se retoca en una instancia. Y el nombre dice de qué nodo del tab salió."""
        compilado = compilar(("weight_slope", {"min": 12.0, "max": 48.0, "soft": 7.0}),
                             ("weight_noise", {"scale": 320.0, "seed": 3, "contrast": 1.4}))
        parametros = shader.firma(compilado["grafo"])["parametros"]
        for esperado in ("Slope1_Min", "Slope1_Max", "Slope1_Soft",
                         "Noise1_Scale", "Noise1_Contrast", "ColorA", "ColorB", "Rugosidad"):
            self.assertIn(esperado, parametros)

    def test_the_parameter_defaults_are_the_values_from_the_tab(self):
        compilado = compilar(("weight_slope", {"min": 12.0, "max": 48.0, "soft": 7.0}))
        valores = {n.props.get("parameter_name"): n.props.get("default_value")
                   for n in compilado["grafo"].nodos if n.tipo == "ScalarParameter"}
        self.assertEqual(valores["Slope1_Min"], 12.0)
        self.assertEqual(valores["Slope1_Max"], 48.0)
        self.assertEqual(valores["Slope1_Soft"], 7.0)

    def test_two_ops_of_the_same_kind_get_different_parameter_names(self):
        """Si los dos `weight_noise` se llamaran igual, mover uno movería el otro."""
        compilado = compilar(("weight_noise", {"scale": 100.0}),
                             ("weight_noise", {"scale": 900.0}))
        parametros = shader.firma(compilado["grafo"])["parametros"]
        self.assertIn("Noise1_Scale", parametros)
        self.assertIn("Noise2_Scale", parametros)
        self.assertEqual(len(parametros), len(set(parametros)), "hay parámetros repetidos")

    def test_two_seeds_give_two_different_noise_patterns(self):
        """El nodo `Noise` de UE no tiene semilla, así que la semilla del tab se vuelve un corrimiento
        del espacio de ruido. No reproduce el dibujo de CPU —eso está dicho en las notas del módulo—
        pero sí tiene que cumplir para lo que se usa el campo: dos semillas, dos dibujos.
        """
        def corrimiento(seed):
            grafo = compilar(("weight_noise", {"scale": 400.0, "seed": seed}))["grafo"]
            return [n.props["constant"] for n in grafo.nodos
                    if n.tipo == "Constant3Vector" and n.props["constant"] != (1.0, 1.0, 0.0)][0]

        self.assertEqual(corrimiento(0), (0.0, 0.0, 0.0),
                         "la semilla 0 tiene que ser el origen: es lo que hace comparable el ruido "
                         "del material con el de Jam")
        distintos = {corrimiento(s) for s in (1, 2, 3, 7, 11)}
        self.assertEqual(len(distintos), 5, f"dos semillas caen en el mismo lugar: {distintos}")

    def test_cull_becomes_an_opacity_mask_and_flips_the_blend_mode(self):
        """`weight_cull` es el aplicador: en el scatter tira puntos, en el material recorta píxeles.
        Sin `BLEND_MASKED` el cable a la opacidad no compila y el recorte no se ve."""
        compilado = compilar(("weight_noise", {"scale": 400.0}),
                             ("weight_cull", {"threshold": 0.6, "soft": 0.0}))
        grafo = compilado["grafo"]
        self.assertEqual(grafo.blend_mode, "BLEND_MASKED")
        self.assertIn("MP_OPACITY_MASK", shader.firma(grafo)["salidas"])
        self.assertEqual(compilado["notas"], [])

    def test_the_cull_keeps_exactly_the_points_the_scatter_would_keep(self):
        """El recorte no es «parecido» al del scatter: es el mismo umbral en el mismo sentido.

        Comparar sólo que existe la salida de opacidad deja pasar un `Step` con las entradas al
        revés, que recorta EXACTAMENTE lo contrario y se ve como un material perfectamente plausible.
        """
        f = flow.Flow()
        fuente = f.add("source_surface", {}, nid="src")
        gris = f.add("weight_slope", {"min": 0.0, "max": 60.0, "soft": 20.0}, nid="w")
        corte = f.add("weight_cull", {"threshold": 0.5, "soft": 0.0}, nid="c")
        f.connect(fuente, gris)
        f.connect(gris, corte)

        compilado = weight_material.desde_flow(f, corte)
        streams = streams_cpu(f, PUNTOS)
        sobrevivieron = {(s.pos.x, s.pos.y, s.pos.z) for s in streams[corte]}
        self.assertTrue(0 < len(sobrevivieron) < len(PUNTOS),
                        "el umbral no separa nada: el caso no prueba nada")
        for punto in PUNTOS:
            valores = shader.evaluar(compilado["grafo"], entorno_de(punto),
                                     ruido=ruido_de_jam(0))
            queda_en_gpu = valores[compilado["recorte"]][0] > 0.5
            queda_en_cpu = (punto.pos.x, punto.pos.y, punto.pos.z) in sobrevivieron
            self.assertEqual(queda_en_gpu, queda_en_cpu,
                             f"el punto {punto.pos} lo conserva uno y lo tira el otro")

    def test_cull_by_density_is_reported_instead_of_silently_approximated(self):
        """El modo por densidad no tiene equivalente en GPU. Lo importante no es que lo aproxime:
        es que lo DIGA, porque si no el material sale distinto del scatter y nadie sabe por qué."""
        compilado = compilar(("weight_noise", {"scale": 400.0}),
                             ("weight_cull", {"threshold": 0.5, "soft": 1.0}))
        self.assertTrue(any("densidad" in n for n in compilado["notas"]), compilado["notas"])

    def test_an_exact_translation_reports_no_notes(self):
        """Las notas son la lista de lo que NO se pudo traducir: cuando está vacía, es una promesa."""
        compilado = compilar(("weight_slope", {"min": 0.0, "max": 45.0, "soft": 5.0}),
                             ("weight_power", {"k": 2.0}))
        self.assertEqual(compilado["notas"], [])

    def test_the_mask_drives_the_base_colour(self):
        compilado = compilar(("weight_slope", {"min": 0.0, "max": 45.0, "soft": 5.0}))
        grafo = compilado["grafo"]
        self.assertIn("MP_BASE_COLOR", shader.firma(grafo)["salidas"])
        hacia_salida = [a for a in grafo.aristas if a.hasta == "MP_BASE_COLOR"]
        self.assertEqual(grafo.nodo(hacia_salida[0].desde).tipo, "LinearInterpolate")
        alfa = [a for a in grafo.aristas
                if a.hasta == hacia_salida[0].desde and a.entrada == "Alpha"]
        self.assertEqual([a.desde for a in alfa], [compilado["mascara"]])

    def test_a_chain_without_weight_ops_is_an_error_not_a_flat_material(self):
        flujo, final = cadena(("cull_nth", {"n": 2}))
        self.assertIn("error", weight_material.desde_flow(flujo, final))

    def test_it_refuses_to_guess_which_node_is_the_end(self):
        f = flow.Flow()
        fuente = f.add("source_surface", {}, nid="src")
        for i in range(2):
            hoja = f.add("weight_power", {"k": 2.0}, nid=f"h{i}")
            f.connect(fuente, hoja)
        salida = weight_material.desde_flow(f)
        self.assertIn("error", salida)
        self.assertIn("h0", salida["error"])

    def test_the_compiled_graph_is_always_structurally_valid(self):
        """Todo lo que sale del compilador tiene que pasar el oráculo estructural: si no, el emisor
        crea un asset roto en Unreal y el error aparece recién en un log de shaders."""
        for pasos in (
                (("weight_slope", {}),),
                (("weight_height", {}), ("weight_invert", {})),
                (("weight_radial", {}), ("weight_curve", {}), ("weight_cull", {})),
                (("weight_noise", {}), ("weight_power", {}), ("weight_noise", {"seed": 4})),
        ):
            with self.subTest(pasos=[p[0] for p in pasos]):
                compilado = compilar(*pasos)
                self.assertNotIn("error", compilado)
                self.assertEqual(shader.verificar(compilado["grafo"]), [])

    def test_a_slider_wired_to_a_parameter_reaches_the_material(self):
        """Un `number` cableado a un pin de parámetro manda sobre el campo, igual que en la
        evaluación. Si el material no lo respetara, mover el slider movería el scatter y no la
        pintura."""
        f = flow.Flow()
        fuente = f.add("source_surface", {}, nid="src")
        variable = f.add("number", {"name": "corte", "value": 33.0}, nid="n1")
        op = f.add("weight_slope", {"min": 0.0, "max": 90.0, "soft": 5.0}, nid="w0")
        f.connect(fuente, op)
        f.connect(variable, op, destino_pin="max")
        compilado = weight_material.desde_flow(f, op)
        valores = {n.props.get("parameter_name"): n.props.get("default_value")
                   for n in compilado["grafo"].nodos if n.tipo == "ScalarParameter"}
        self.assertEqual(valores["Slope1_Max"], 33.0)


class RegistroTests(unittest.TestCase):
    def test_the_terminal_op_is_registered_as_an_output_of_the_flow(self):
        self.assertIn("weight_material", flow.OPS_META)
        self.assertEqual(flow.OPS_META["weight_material"]["cat"], "Output")

    def test_evaluar_hands_the_graph_context_to_the_ops(self):
        """El nodo terminal compila el GRAFO, no el stream: sin `_flow`/`_nid` no puede hacer nada.
        Se comprueba por el camino real (`Flow.evaluar`), no llamando a la op a mano."""
        visto = {}

        def espia(entradas, p):
            visto.update({"flow": p.get("_flow"), "nid": p.get("_nid")})
            return entradas[0] if entradas else []

        f = flow.Flow()
        fuente = f.add("pts_line", {"count": 3}, nid="src")
        terminal = f.add("weight_material", {}, nid="fin")
        f.connect(fuente, terminal)
        f.evaluar(ops={"weight_material": (espia, 1)})
        self.assertIs(visto["flow"], f)
        self.assertEqual(visto["nid"], "fin")
        # Y no se queda pegado: los params del nodo son lo que se GUARDA en el .json del canvas.
        # Si el contexto se colara ahí, el grafo se volvería inserializable y arrastraría el Flow
        # entero en cada guardado.
        self.assertNotIn("_flow", f.nodos["fin"]["params"])
        self.assertNotIn("_nid", f.nodos["fin"]["params"])


if __name__ == "__main__":
    unittest.main()
