"""Contratos del IR de materiales: el oráculo estructural corre ANTES de tocar Unreal.

Un material mal armado no falla como una excepción de Python: crea un asset roto y el error sale en
un log de compilación de shaders, si sale. Por eso el grafo se verifica como dato puro primero — y
por eso lo que se fija acá no son los números del material de viento (esos se retocan mirando el
árbol moverse) sino que el verificador SEPA distinguir un grafo bueno de uno roto.
"""

from __future__ import annotations

import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import shader  # noqa: E402


def grafo_minimo(**cambios):
    base = {
        "nombre": "M_Test",
        "nodos": (shader.Nodo("c", "Constant3Vector", {"r": 1.0}),),
        "aristas": (shader.Arista("c", "MP_BASE_COLOR"),),
    }
    base.update(cambios)
    return shader.GrafoMaterial(**base)


class VerificadorTests(unittest.TestCase):
    def test_a_sound_graph_has_no_complaints(self):
        self.assertEqual(shader.verificar(grafo_minimo()), [])

    def test_it_catches_an_edge_from_a_node_that_does_not_exist(self):
        roto = grafo_minimo(aristas=(shader.Arista("fantasma", "MP_BASE_COLOR"),))
        self.assertTrue(any("fantasma" in p for p in shader.verificar(roto)))

    def test_it_catches_an_input_the_node_does_not_have(self):
        """El error más fácil de cometer: `Power` tiene Base/Exp, no A/B."""
        roto = shader.GrafoMaterial(
            nombre="M", nodos=(shader.Nodo("a", "Constant"), shader.Nodo("p", "Power")),
            aristas=(shader.Arista("a", "p", "A"), shader.Arista("p", "MP_BASE_COLOR")))
        problemas = shader.verificar(roto)
        self.assertTrue(any("no tiene la entrada" in p and "Base" in p for p in problemas),
                        problemas)

    def test_it_catches_two_wires_into_the_same_input(self):
        """En UE el segundo cable reemplaza al primero en silencio: el grafo queda distinto del
        que uno escribió y no hay ninguna señal."""
        roto = shader.GrafoMaterial(
            nombre="M",
            nodos=(shader.Nodo("a", "Constant"), shader.Nodo("b", "Constant"),
                   shader.Nodo("m", "Multiply")),
            aristas=(shader.Arista("a", "m", "A"), shader.Arista("b", "m", "A"),
                     shader.Arista("m", "MP_BASE_COLOR")))
        self.assertTrue(any("ya estaba conectada" in p for p in shader.verificar(roto)))

    def test_it_catches_a_cycle(self):
        """Un ciclo cuelga al compilador de materiales; verlo desde Python cuesta nada."""
        roto = shader.GrafoMaterial(
            nombre="M",
            nodos=(shader.Nodo("x", "Add"), shader.Nodo("y", "Add")),
            aristas=(shader.Arista("x", "y", "A"), shader.Arista("y", "x", "A"),
                     shader.Arista("x", "MP_BASE_COLOR")))
        self.assertTrue(any("ciclo" in p for p in shader.verificar(roto)))

    def test_it_catches_a_graph_that_feeds_no_output(self):
        huerfano = grafo_minimo(aristas=())
        self.assertTrue(any("no alimenta ninguna salida" in p
                            for p in shader.verificar(huerfano)))

    def test_it_catches_an_unknown_node_type(self):
        raro = grafo_minimo(nodos=(shader.Nodo("c", "NodoQueNoExiste"),))
        self.assertTrue(any("tipo desconocido" in p for p in shader.verificar(raro)))

    def test_it_catches_a_property_that_is_not_a_material_output(self):
        roto = grafo_minimo(aristas=(shader.Arista("c", "MP_INVENTADA"),))
        self.assertTrue(any("no es una salida" in p for p in shader.verificar(roto)))


class FirmaTests(unittest.TestCase):
    def test_the_signature_does_not_depend_on_the_order_things_were_written(self):
        """Es la propiedad que vuelve comparables dos materiales: si el orden contara, dos grafos
        idénticos armados distinto medirían distinto."""
        g = shader.viento_de_arbol()
        revuelto = shader.GrafoMaterial(nombre=g.nombre, nodos=tuple(reversed(g.nodos)),
                                        aristas=tuple(reversed(g.aristas)))
        self.assertEqual(shader.firma(g), shader.firma(revuelto))

    def test_depth_grows_with_the_chain_and_not_with_the_node_count(self):
        """La profundidad aproxima el costo: importa la cadena de dependencias, no cuántos nodos
        sueltos haya colgando."""
        cadena = shader.GrafoMaterial(
            nombre="M",
            nodos=tuple(shader.Nodo(f"n{i}", "Add") for i in range(4)),
            aristas=tuple(shader.Arista(f"n{i}", f"n{i + 1}", "A") for i in range(3))
                   + (shader.Arista("n3", "MP_BASE_COLOR"),))
        ancho = shader.GrafoMaterial(
            nombre="M",
            nodos=(shader.Nodo("suma", "Add"),)
                  + tuple(shader.Nodo(f"c{i}", "Constant") for i in range(8)),
            aristas=(shader.Arista("c0", "suma", "A"), shader.Arista("c1", "suma", "B"),
                     shader.Arista("suma", "MP_BASE_COLOR")))
        self.assertEqual(shader.profundidad(cadena), 4)
        self.assertEqual(shader.profundidad(ancho), 2)


class VientoDeArbolTests(unittest.TestCase):
    def setUp(self):
        self.grafo = shader.viento_de_arbol()

    def test_it_is_a_valid_graph(self):
        self.assertEqual(shader.verificar(self.grafo), [])

    def test_it_drives_world_position_offset(self):
        """Si no alimenta WPO no mueve nada, por más nodos que tenga."""
        salidas = shader.firma(self.grafo)["salidas"]
        self.assertIn("MP_WORLD_POSITION_OFFSET", salidas)

    def test_it_reads_the_two_uv_channels_the_pipeline_stamps(self):
        """El contrato con `mesh_pipe(pivot_uvs=True)`: UV1 y UV2, no otros."""
        indices = sorted(n.props.get("coordinate_index")
                         for n in self.grafo.nodos if n.tipo == "TextureCoordinate")
        self.assertEqual(indices, [1, 2])

    def test_the_rotation_pivots_on_the_reconstructed_pivot(self):
        """El punto de giro tiene que ser el pivote de la rama. Si ahí entrara la posición del
        vértice, la rama se trasladaría en vez de flexionar — que es el bug que este material
        existe para no tener."""
        giro = [a for a in self.grafo.aristas
                if a.hasta == "giro" and a.entrada == "PivotPoint"]
        self.assertEqual([a.desde for a in giro], ["pivote"])

    def test_the_vertex_colour_mask_can_veto_the_movement(self):
        """Un tronco pintado en cero tiene que quedarse quieto aunque tenga pivote: por eso la
        máscara MULTIPLICA, no suma."""
        desde_mascara = [a for a in self.grafo.aristas if a.desde == "mascara"]
        self.assertEqual(len(desde_mascara), 1)
        destino = self.grafo.nodo(desde_mascara[0].hasta)
        self.assertEqual(destino.tipo, "Multiply")

    def test_the_phase_is_offset_per_branch(self):
        """Sin desfase todas las ramas oscilan al unísono y el árbol late como un corazón."""
        entra_a_fase = {a.desde for a in self.grafo.aristas if a.hasta == "fase"}
        self.assertIn("desfase", entra_a_fase)
        self.assertEqual(self.grafo.nodo("desfase").tipo, "Length")
        self.assertIn("pivote", {a.desde for a in self.grafo.aristas if a.hasta == "desfase"})

    def test_everything_tweakable_is_a_named_parameter(self):
        """Lo que se retoca mirando el árbol tiene que poder cambiarse en una instancia, sin
        recompilar ni volver a correr el grafo."""
        self.assertEqual(
            shader.firma(self.grafo)["parametros"],
            ["Concentracion", "Corteza", "EjeViento", "Fuerza", "Rugosidad", "Velocidad"])

    def test_the_parameters_reach_the_graph(self):
        g = shader.viento_de_arbol(fuerza=0.8, velocidad=3.0, concentracion=4.0)
        valores = {n.props.get("parameter_name"): n.props.get("default_value")
                   for n in g.nodos if n.tipo == "ScalarParameter"}
        self.assertEqual(valores["Fuerza"], 0.8)
        self.assertEqual(valores["Velocidad"], 3.0)
        self.assertEqual(valores["Concentracion"], 4.0)


if __name__ == "__main__":
    unittest.main()
