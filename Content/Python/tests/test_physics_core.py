"""Asentar en TANDA — el núcleo del *physics paint*.

Lo que se fija acá es la diferencia entre sembrar y pintar: soltar N piezas a la vez no es soltar
una N veces. Si cada una cae contra la foto original del nivel, las N terminan a la misma cota,
atravesadas; si cada una es piso de la siguiente, se apilan.

Y el orden de caída no puede ser el de la lista, porque un grafo tiene que dar lo mismo cada vez
que corre.
"""

from __future__ import annotations

import inspect
import pathlib
import sys
import types
import unittest

# `physics_core` es puro, pero el último bloque mira `tools.py`, que sí importa el motor.
_unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal, "TopLevelAssetPath"):
    _unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import geometry, physics_core  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parents[1] / "jam"


def caja(nombre, x, y, z, *, semi=50.0, alto=50.0):
    """Pieza cúbica centrada en (x, y, z). `z` es el CENTRO, así que su base es z - alto."""
    a = geometry.AABB(geometry.Vec3(x, y, z), geometry.Vec3(semi, semi, alto))
    return geometry.Pieza(nombre, a, geometry.Vec3(x, y, z - alto), 0.0)


PISO = caja("Piso", 0.0, 0.0, -10.0, semi=5000.0, alto=10.0)   # top = 0


class ApilarTests(unittest.TestCase):
    def test_a_batch_stacks_on_itself_instead_of_landing_at_the_same_height(self):
        """Tres cajas sobre el mismo XY: la primera al piso, las otras dos encima.

        Es LA diferencia con llamar `soltar` en un bucle. Con la foto original del nivel las tres
        darían base 0 y quedarían las tres dentro de la misma.
        """
        piezas = [caja("a", 0, 0, 400), caja("b", 0, 0, 900), caja("c", 0, 0, 1500)]
        r = physics_core.asentar_tanda(piezas, [PISO])

        bases = [physics_core.base_de(x["pieza"].aabb) for x in r]
        self.assertEqual(bases, [0.0, 100.0, 200.0],
                         f"no se apilaron, quedaron en {bases}")
        self.assertTrue(all(x["apoyada"] for x in r))
        self.assertEqual(r[0]["soporte"], "Piso")
        self.assertEqual([x["soporte"] for x in r[1:]], ["a", "b"],
                         "cada una tiene que apoyarse en la anterior de la tanda")

    def test_the_result_does_not_depend_on_the_order_of_the_input(self):
        """Reproducibilidad: los mismos puntos en otro orden dan la MISMA pila.

        Es la razón de ordenar por base y no recorrer la lista: un grafo que da distinto según en
        qué orden salieron los puntos del scatter no se puede volver a correr.
        """
        piezas = [caja("a", 0, 0, 400), caja("b", 0, 0, 900), caja("c", 0, 0, 1500)]
        directo = {x["pieza"].nombre: physics_core.base_de(x["pieza"].aabb)
                   for x in physics_core.asentar_tanda(piezas, [PISO])}
        for perm in ([2, 0, 1], [1, 2, 0], [2, 1, 0]):
            revuelto = physics_core.asentar_tanda([piezas[i] for i in perm], [PISO])
            self.assertEqual(
                {x["pieza"].nombre: physics_core.base_de(x["pieza"].aabb) for x in revuelto},
                directo, f"la permutación {perm} dio otra pila")

    def test_pieces_far_apart_in_xy_do_not_stack(self):
        """Apilar es sólo cuando se pisan en XY: dos rocas a 10 m van las dos al piso."""
        piezas = [caja("a", 0, 0, 400), caja("b", 1000, 0, 900)]
        r = physics_core.asentar_tanda(piezas, [PISO])
        self.assertEqual([x["soporte"] for x in r], ["Piso", "Piso"])

    def test_settling_is_returned_in_input_order(self):
        """Se cae de abajo hacia arriba, pero se DEVUELVE en el orden de entrada: quien llama
        emparejó esa lista con sus actores y un reordenamiento silencioso movería los equivocados."""
        piezas = [caja("alta", 0, 0, 1500), caja("baja", 0, 0, 400)]
        r = physics_core.asentar_tanda(piezas, [PISO])
        self.assertEqual([x["pieza"].nombre for x in r], ["alta", "baja"])
        self.assertEqual(r[1]["soporte"], "Piso")
        self.assertEqual(r[0]["soporte"], "baja")


class SinPisoTests(unittest.TestCase):
    def test_a_piece_with_nothing_below_stays_put_and_is_reported(self):
        """Sin soporte no se inventa un piso: queda donde estaba y se dice. Bajarla a z=0 «porque
        el suelo suele estar ahí» es exactamente cómo algo aparece enterrado sin que nadie sepa."""
        sola = caja("huerfana", 0, 0, 700)
        r = physics_core.asentar_tanda([sola], [])
        self.assertFalse(r[0]["apoyada"])
        self.assertEqual(r[0]["caida"], 0.0)
        self.assertEqual(physics_core.base_de(r[0]["pieza"].aabb), 650.0)

    def test_a_piece_without_floor_is_still_a_support_for_what_falls_on_it(self):
        """Está ahí igual: lo que caiga encima tiene que apoyarse, no atravesarla."""
        piezas = [caja("flotante", 0, 0, 700), caja("encima", 0, 0, 2000)]
        r = physics_core.asentar_tanda(piezas, [])
        self.assertFalse(r[0]["apoyada"])
        self.assertEqual(r[1]["soporte"], "flotante",
                         "la de arriba atravesó a la que no tenía piso")
        self.assertEqual(physics_core.base_de(r[1]["pieza"].aabb), 750.0)


class DesenterrarTests(unittest.TestCase):
    def test_a_buried_piece_comes_up(self):
        """`caida` negativa = subió. Es el mismo signo que usa `physics.soltar`, y es lo que saca
        del piso a una pieza que el scatter dejó clavada."""
        piezas = [caja("clavada", 0, 0, 20)]   # base -30, bajo el piso (top 0)
        r = physics_core.asentar_tanda(piezas, [PISO])
        self.assertLess(r[0]["caida"], 0.0)
        self.assertEqual(physics_core.base_de(r[0]["pieza"].aabb), 0.0)


class SoltarDesdeArribaTests(unittest.TestCase):
    """EL bug que hacía inútil al pincel, con las medidas de la corrida real de Brian.

    24 barriles de 65×65×80 cm repartidos a 30 cm, todos apoyados en el piso por el scatter. El
    oráculo informó `caída media 0.0cm` Y `interpenetran 99 pares` a la vez: nada se movió y todo
    quedó cruzado.

    La causa: `soporte_top` descartaba un candidato que asoma por encima del CENTRO de la pieza.
    Preguntando «¿qué hay debajo de esto donde está?» esa regla es correcta —si no, una pieza junto
    a una pared se teletransporta al techo—. Pero soltando una tanda a la MISMA cota, cada pieza
    asoma sobre el centro de su vecina, las dos se descartan mutuamente y ninguna sube.
    """

    @staticmethod
    def _barril(nombre, x):
        return caja(nombre, x, 0.0, 40.0, semi=32.5, alto=40.0)   # 65×65×80, base en 0

    def test_pieces_born_at_the_same_height_still_stack(self):
        piezas = [self._barril("a", 0.0), self._barril("b", 30.0), self._barril("c", 60.0)]
        r = physics_core.asentar_tanda(piezas, [PISO])
        bases = [physics_core.base_de(x["pieza"].aabb) for x in r]
        self.assertEqual(bases, [0.0, 80.0, 160.0],
                         f"nacidas a la misma cota tienen que apilarse igual: {bases}")
        self.assertEqual([x["soporte"] for x in r], ["Piso", "a", "b"])

    def test_the_ones_that_ended_up_on_a_sibling_are_counted(self):
        piezas = [self._barril("a", 0.0), self._barril("b", 30.0)]
        r = physics_core.asentar_tanda(piezas, [PISO])
        self.assertEqual([x["sobre_hermana"] for x in r], [False, True])

    def test_the_sky_sphere_is_not_a_floor(self):
        """Soltando desde arriba se pierde la protección que daba la regla del centro: la SkySphere
        solapa en XY con TODO y su top está a 16 km. Sin filtrarla, la tanda aterriza en el cielo."""
        cielo = caja("SM_SkySphere", 0.0, 0.0, 0.0, semi=1e6, alto=1e6)
        r = physics_core.asentar_tanda([self._barril("a", 0.0)], [PISO, cielo])
        self.assertEqual(r[0]["soporte"], "Piso",
                         "aterrizó en el cielo en vez del piso")
        self.assertEqual(physics_core.base_de(r[0]["pieza"].aabb), 0.0)

    def test_resting_on_a_corner_topples_instead_of_stacking(self):
        """EL segundo bug: con «cualquier solape en XY» alcanzaba para apoyarse, y 24 piezas
        poisson a 30 cm formaban una CHIMENEA de 6,5 m con una sola tocando el piso.

        En el mundo, una pieza apoyada de refilón se voltea. El criterio es el centro de masa: si
        no cae sobre el soporte, sigue cayendo.
        """
        # Barriles de 65 cm de ancho (semi 32.5) separados 40 cm: se TOCAN, pero el centro de la
        # segunda queda fuera de la huella de la primera.
        piezas = [self._barril("a", 0.0), self._barril("b", 40.0)]
        r = physics_core.asentar_tanda(piezas, [PISO])
        self.assertEqual([x["soporte"] for x in r], ["Piso", "Piso"],
                         "apoyada de refilón no se sostiene: se voltea y va al piso")

    def test_it_still_stacks_when_the_centre_is_really_over_the_other(self):
        piezas = [self._barril("a", 0.0), self._barril("b", 20.0)]   # 20 < semi 32.5
        r = physics_core.asentar_tanda(piezas, [PISO])
        self.assertEqual(r[1]["soporte"], "a")
        self.assertEqual(physics_core.base_de(r[1]["pieza"].aabb), 80.0)

    def test_a_realistic_brush_batch_makes_a_heap_and_not_a_chimney(self):
        """La medida que importa, con los números de la corrida real: 24 piezas, poisson sep 30."""
        from jam import scatter_core as sc
        puntos = sc.poisson_disk((0.0, 0.0), (800.0, 800.0), 30.0, 7)[:24]
        piezas = [caja(f"p{i:02d}", x, y, 40.0, semi=32.5, alto=40.0)
                  for i, (x, y) in enumerate(puntos)]
        r = physics_core.asentar_tanda(piezas, [PISO])
        alturas = [physics_core.base_de(x["pieza"].aabb) for x in r]
        en_el_piso = sum(1 for h in alturas if h <= 0.1)
        self.assertLess(max(alturas), 400.0,
                        f"volvió la chimenea: {max(alturas):.0f}cm de alto")
        self.assertGreater(en_el_piso, len(piezas) // 2,
                           f"la mayoría tendría que quedar en el piso, no {en_el_piso}")

    def test_dropping_from_above_is_asked_for_explicitly_and_is_not_the_default(self):
        """`physics.soltar` y `oracle_physics` siguen preguntando «¿qué hay debajo de esto DONDE
        ESTÁ?». Volver `desde_arriba` el default les cambiaría el significado por atrás."""
        import inspect
        firma = inspect.signature(geometry.soporte_top)
        self.assertIs(firma.parameters["desde_arriba"].default, False)
        self.assertIn("desde_arriba=True",
                      inspect.getsource(physics_core.asentar_tanda))


class ResumenTests(unittest.TestCase):
    def test_the_summary_says_how_many_found_no_floor(self):
        piezas = [caja("a", 0, 0, 400), caja("lejos", 9e4, 0, 400)]
        texto = physics_core.resumen(physics_core.asentar_tanda(piezas, [PISO]))
        self.assertIn("1/2", texto)
        self.assertIn("1 sin piso", texto)

    def test_a_partial_batch_is_failure_not_a_green_check(self):
        from jam.graph import _estado
        piezas = [caja("a", 0, 0, 400), caja("lejos", 9e4, 0, 400)]
        texto = physics_core.resumen(physics_core.asentar_tanda(piezas, [PISO]))
        self.assertIn("✗", texto)
        self.assertNotIn("ASENTAR ✓", texto,
                         "una pieza apoyada no puede ocultar otra que quedó sin piso")
        self.assertEqual("warn", _estado(texto), "el nodo no puede pintar verde el lote parcial")

    def test_it_does_not_report_a_meaningless_average_fall(self):
        """Promediar subidas con bajadas daba «caída media -60cm», que no significa nada. Lo que
        importa es cuántas quedaron ENCIMA de otra pieza: es la diferencia entre pila y capa."""
        piezas = [caja("a", 0, 0, 400), caja("b", 20, 0, 400)]
        texto = physics_core.resumen(physics_core.asentar_tanda(piezas, [PISO]))
        self.assertNotIn("caída media", texto)
        self.assertIn("1 apiladas sobre otra pieza", texto)

    def test_all_floating_is_a_failure_and_not_a_silent_ok(self):
        texto = physics_core.resumen(physics_core.asentar_tanda([caja("a", 0, 0, 400)], []))
        self.assertIn("✗", texto)


class NoSeDuplicaLaReglaTests(unittest.TestCase):
    def test_the_batch_asks_geometry_what_is_below_instead_of_reimplementing_it(self):
        """«¿Qué hay debajo?» la contesta `geometry.soporte_top` y nadie más.

        Ya la usan `physics.soltar` y `oracle_physics.verificar`. Una cuarta copia acá se separaría
        en silencio y el oráculo diría FLOTANDO sobre algo que el asentado creyó apoyado.
        """
        fuente = inspect.getsource(physics_core)
        self.assertIn("geometry.soporte_top(", fuente)
        for sospechoso in ("origin.x) >", "extent.x +", "s_top"):
            self.assertNotIn(sospechoso, fuente,
                             "parece haber una segunda copia del test de solape XY")


class PlaceRepartteYDropApilaTests(unittest.TestCase):
    """Los dos verbos son hermanos y se diferencian en UNA cosa.

    `place` reparte en un plano y descarta por huella lo que se cruzaría. `drop` deja caer: no
    descarta nada —solaparse es la condición de apilarse— y después asienta la tanda.

    Vivían en el mismo verbo con una perilla `physics`, y era confuso de la peor manera: el mismo
    nodo hacía dos cosas distintas y había que acordarse de cuál estaba prendida. Ahora lo dice el
    nombre.
    """

    def test_place_no_longer_has_a_physics_knob(self):
        from jam import tools
        self.assertNotIn("physics", tools.REGISTRO["place"]["params"],
                         "hacer caer es `drop`; `place` coloca en un plano")

    def test_drop_takes_points_and_a_set_of_variants_like_place(self):
        from jam import tools
        drop = tools.REGISTRO["drop"]
        self.assertEqual(drop["data_params"].get("points"), "P")
        self.assertIn("points", drop.get("optional_data_params", ()))
        self.assertEqual(drop.get("in_accepts"), {"A[]": ("points",)})

    def test_only_drop_stacks(self):
        """La única diferencia, leída en la fuente: `place` llama con apilar=False y `drop` con True."""
        fuente = (RAIZ / "tools.py").read_text(encoding="utf-8")
        for verbo, esperado in (("t_place", "apilar=False"), ("t_drop", "apilar=True")):
            cuerpo = fuente[fuente.index(f"def {verbo}("):]
            cuerpo = cuerpo[:cuerpo.index("\ndef ", 1)]
            self.assertIn(esperado, cuerpo, f"`{verbo}` no pide {esperado}")

    def test_both_share_the_same_placement_body(self):
        """El dedup, el oráculo doble y el veredicto viven UNA vez: si se separan, uno de los dos
        verbos deja de verificar lo que el otro sí."""
        from jam import tools
        self.assertTrue(hasattr(tools, "_en_puntos"))
        fuente = (RAIZ / "tools.py").read_text(encoding="utf-8")
        self.assertEqual(fuente.count("_en_puntos(asset, points"), 2)

    def test_a_saved_graph_says_where_the_knob_moved(self):
        """Un grafo guardado con `physics` no puede decir sólo «parámetro desconocido»: obliga a
        adivinar qué pasó y en qué commit."""
        from jam.graph import JamGraph, validar
        g = JamGraph()
        g.add("asset", {"name": "/A.A"}, nid="a")
        g.add("place", {"physics": "True"}, nid="p")
        g.connect("a", "p")
        mensajes = validar(g).get("p", [])
        self.assertTrue(any("drop" in m for m in mensajes),
                        f"tendría que nombrar adónde se mudó: {mensajes}")

    def test_drop_no_longer_lands_at_the_world_origin(self):
        """Caía SIEMPRE en (0,0): en un mundo abierto, a kilómetros de la cámara."""
        from jam import tools
        self.assertIn("x", tools.REGISTRO["drop"]["params"])
        self.assertIn("view", tools.REGISTRO["drop"]["params"])
        self.assertEqual(tools.CAPTURA_LA_MIRA.get("drop"), ("x", "y"))


class VeredictoHonestoTests(unittest.TestCase):
    """«PLACE ✓ — 0 en 8 punto(s)» pintaba el nodo de VERDE.

    Un tilde sobre cero piezas es exactamente la clase de veredicto que este proyecto existe para
    no dar: se ve verde, no colocó nada, y el que mira sigue construyendo encima.
    """

    def test_zero_placed_is_never_a_check(self):
        from jam.graph import _estado
        from jam.tools import _veredicto_place
        texto = _veredicto_place(0, 8, 1, "", "ORACULO")
        self.assertIn("✗", texto)
        self.assertNotIn("✓", texto)
        self.assertNotEqual(_estado(texto), "ok", "cero colocados no puede pintar verde")

    def test_it_says_how_many_it_failed_to_place_and_where_to_look(self):
        texto = _v = None
        from jam.tools import _veredicto_place
        texto = _veredicto_place(0, 8, 0, "", "ORACULO")
        self.assertIn("8", texto)
        self.assertIn("[Jam] colocar", texto,
                      "sin decir dónde mirar, el veredicto obliga a adivinar")

    def test_placing_something_still_reports_the_settling_and_the_oracle(self):
        from jam.graph import _estado
        from jam.tools import _veredicto_place
        texto = _veredicto_place(7, 8, 1, "\nASENTAR ✓ — 7/7", "ORACULO")
        self.assertEqual(_estado(texto), "ok")
        self.assertIn("ASENTAR", texto)
        self.assertIn("ORACULO", texto)

    def test_the_engine_side_says_out_loud_when_the_spawn_fails(self):
        """`colocar` devolvía None sin decir nada y costó una ronda entera de diagnóstico."""
        fuente = (RAIZ / "place.py").read_text(encoding="utf-8")
        tramo = fuente[fuente.index("spawn_actor_from_object"):]
        tramo = tramo[:tramo.index("return None")]
        self.assertIn("log_error", tramo,
                      "un spawn que falla en silencio parece un bug de Jam")


class ElSueloSeMideConUnRayoTests(unittest.TestCase):
    """Un AABB no puede describir un terreno.

    Medido contra un landscape real de 121 m con lomas: su caja dice `top = 3 m`, y tres piezas
    soltadas desde 15 m quedaron LAS TRES a esa misma cota — flotando sobre el suelo real en todo
    punto que no fuera la loma más alta. Es lo que Brian vio: «drop no hace que toquen el suelo».

    La altura del terreno bajo CADA pieza sólo la sabe un raycast. Entra acá ya medida, como dato,
    para que el núcleo siga siendo puro.
    """

    @staticmethod
    def _pieza(nombre, x, z):
        return caja(nombre, x, 0.0, z, semi=50.0, alto=50.0)

    def test_each_piece_lands_on_its_own_ground_height(self):
        piezas = [self._pieza("a", 0.0, 1500.0), self._pieza("b", 400.0, 1500.0)]
        # Una loma: bajo «a» el terreno está a 0, bajo «b» a 620.
        suelos = [(0.0, "Landscape1"), (620.0, "Landscape1")]
        r = physics_core.asentar_tanda(piezas, [], suelos=suelos)
        self.assertEqual([physics_core.base_de(x["pieza"].aabb) for x in r], [0.0, 620.0],
                         "las dos aterrizaron a la misma cota: eso es el AABB, no el terreno")

    def test_a_sibling_higher_than_the_ground_still_wins(self):
        """Apilar sigue funcionando: lo que sostiene es lo MÁS ALTO, sea suelo o hermana."""
        piezas = [self._pieza("a", 0.0, 50.0), self._pieza("b", 20.0, 50.0)]
        suelos = [(0.0, "Landscape1"), (0.0, "Landscape1")]
        r = physics_core.asentar_tanda(piezas, [], suelos=suelos)
        self.assertEqual(r[1]["soporte"], "a")
        self.assertTrue(r[1]["sobre_hermana"])
        self.assertEqual(physics_core.base_de(r[1]["pieza"].aabb), 100.0)

    def test_the_ground_wins_over_a_sibling_that_sits_lower(self):
        """Una pieza en el valle no sostiene a otra que está sobre la loma."""
        piezas = [self._pieza("valle", 0.0, 50.0), self._pieza("loma", 20.0, 50.0)]
        suelos = [(0.0, "Landscape1"), (900.0, "Landscape1")]
        r = physics_core.asentar_tanda(piezas, [], suelos=suelos)
        self.assertEqual(r[1]["soporte"], "Landscape1")
        self.assertEqual(physics_core.base_de(r[1]["pieza"].aabb), 900.0)

    def test_no_ground_measured_is_not_an_invented_floor(self):
        """Rayo al vacío = None. No se inventa z=0."""
        piezas = [self._pieza("a", 0.0, 700.0)]
        r = physics_core.asentar_tanda(piezas, [], suelos=[None])
        self.assertFalse(r[0]["apoyada"])
        self.assertEqual(physics_core.base_de(r[0]["pieza"].aabb), 650.0)

    def test_the_adapter_casts_one_ray_per_piece_ignoring_the_batch(self):
        """Sin ignorar la tanda, una pieza se apoyaría en sí misma y el resultado dependería del
        orden en que se tiraron los rayos."""
        import inspect
        from jam import physics
        cuerpo = inspect.getsource(physics.asentar_actores)
        self.assertIn("ue.raycast(", cuerpo)
        self.assertIn("ignorar=list(actores)", cuerpo)

    def test_the_adapter_shadows_the_actual_final_actor_bounds(self):
        """La sombra debe mirar dónde quedaron los actores, no repetir la predicción del núcleo."""
        import inspect
        from jam import physics
        cuerpo = inspect.getsource(physics.asentar_actores)
        self.assertIn('r | {"pieza": ue.pieza(actor)}', cuerpo)
        self.assertIn("ue.physics_tanda(observados", cuerpo)


class ElPreviewAnteriorNoEsPisoTests(unittest.TestCase):
    """Un barril quedó FLOTANDO en el aire, con su sombra abajo.

    El Preview de Jam es transaccional: el anterior sigue vivo hasta que el nuevo termina bien, para
    poder revertir. O sea que en el instante del asentado está ahí. Una pieza que se apoya en él
    queda en el aire cuando lo reemplazan — y el reporte lo decía sin que yo lo leyera: «12 pisados
    contra lo que ya estaba: prev_Jam_place_0».

    `ue.raycast` ya excluía lo no confirmado (`ignorar_jam`), y el docstring de `actores_de_jam`
    describe este mismo bug para los rayos. Faltaba aplicar la MISMA regla a la lista por caja.
    Excluirlo de un camino y no del otro es peor que no excluirlo: el resultado pasa a depender de
    cuál de los dos ganó.
    """

    def test_the_settling_skips_jams_unconfirmed_actors(self):
        import inspect

        from jam import physics
        cuerpo = inspect.getsource(physics.asentar_actores)
        self.assertIn("ue.actores_de_jam()", cuerpo,
                      "la lista por caja tiene que excluir lo mismo que el rayo")

    def test_the_oracle_does_not_count_the_previous_preview_as_scene(self):
        """«Lo que ya estaba» es la ESCENA. El Preview anterior se borra en la misma corrida, así
        que avisar de haberlo pisado es avisar de algo que no existe."""
        import inspect

        from jam import ue
        firma = inspect.signature(ue.vecinos_en_zona)
        self.assertIn("ignorar_jam", firma.parameters)
        self.assertIs(firma.parameters["ignorar_jam"].default, True)
        self.assertIn("actores_de_jam()", inspect.getsource(ue.vecinos_en_zona))

    def test_the_three_paths_agree_on_what_is_not_scene(self):
        """Rayo, asentado y oráculo preguntan lo mismo a la MISMA función. Si mañana una lo decide
        por su cuenta, vuelve el barril flotando."""
        import inspect

        from jam import physics, ue
        for donde in (ue.raycast_entre, ue.vecinos_en_zona, physics.asentar_actores):
            self.assertIn("actores_de_jam", inspect.getsource(donde),
                          f"{donde.__name__} decide por su cuenta qué es escena")
