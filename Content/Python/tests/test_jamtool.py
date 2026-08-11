"""El `.jamtool`: armar una tool en el Graph y llevarla a la Dash Bar.

Las tres piezas que faltaban para que una tool no haya que programarla en Python: el artefacto
portable, su superficie, y qué input recibe la selección cuando corre desde la barra.
"""

from __future__ import annotations

import sys
import types
import unittest

sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import jamtool_core  # noqa: E402


def firma(*entradas, entrada_seleccion=None):
    f = {"inputs": [{"nombre": n, "tipo": t} for n, t in entradas], "outputs": []}
    if entrada_seleccion is not None:
        f["entrada_seleccion"] = entrada_seleccion
    return f


def preset(**extra):
    base = {
        "kind": "funcion", "funcion_id": "fn-0001", "nombre": "Muro rápido",
        "firma": firma(("malla", "A")),
        "grafo": {"nodes": {"a": {"verb": "input"}, "b": {"verb": "mesh_extrude"},
                            "c": {"verb": "mesh_to_static"}, "d": {"verb": "output"}}},
    }
    base.update(extra)
    return base


class EntradaDeSeleccionTests(unittest.TestCase):
    """En el Graph una función se alimenta por cables; en la barra, por la selección. Alguien tiene
    que decidir por dónde entra, y esa decisión no puede quedar en el orden de dibujo."""

    def test_con_un_solo_input_compatible_no_hace_falta_declarar_nada(self):
        self.assertEqual(jamtool_core.entrada_de_seleccion(firma(("malla", "A"))), "malla")

    def test_con_dos_gana_lo_declarado_y_no_el_orden(self):
        f = firma(("base", "A"), ("pieza", "A"), entrada_seleccion="pieza")
        self.assertEqual(jamtool_core.entrada_de_seleccion(f), "pieza")

    def test_sin_declarar_entra_por_el_primero_compatible(self):
        """El default tiene que servir para el caso simple sin obligar a declarar."""
        f = firma(("cantidad", "N"), ("malla", "A"))
        self.assertEqual(jamtool_core.entrada_de_seleccion(f), "malla")

    def test_el_comodin_de_la_firma_acepta_la_seleccion(self):
        """`funcion.firma()` marca `*` cuando el borde no declara un tipo concreto, que hoy es el
        caso más común. Sin esto una tool recién colapsada no encontraba por dónde recibir la
        selección y quedaba inaplicable en la barra."""
        self.assertEqual(jamtool_core.entrada_de_seleccion(
            {"entradas": [{"name": "malla", "tipo": "*"}]}), "malla")

    def test_una_tool_que_no_se_alimenta_de_la_escena_lo_dice(self):
        """Devolver None es una respuesta: la barra le pide todo por parámetros en vez de inventar
        una entrada que la tool no tiene."""
        self.assertIsNone(jamtool_core.entrada_de_seleccion(firma(("cantidad", "N"))))

    def test_declarar_un_input_inexistente_es_un_error_visible(self):
        f = firma(("malla", "A"), entrada_seleccion="fantasma")
        with self.assertRaises(jamtool_core.JamToolInvalido):
            jamtool_core.entrada_de_seleccion(f)


class SuperficieDeUnaFuncionTests(unittest.TestCase):
    def test_una_funcion_recien_colapsada_vive_solo_en_el_graph(self):
        """Publicarla a la barra es deliberado. Si apareciera sola se repetiría el error que tenía
        el registro: estar en la Dash Bar por omisión."""
        self.assertEqual(jamtool_core.superficies_de_funcion({}), frozenset({"graph"}))

    def test_publicarla_a_la_barra_es_declararlo(self):
        self.assertEqual(
            jamtool_core.superficies_de_funcion({"superficies": ("dash", "graph")}),
            frozenset({"dash", "graph"}))


class ArtefactoPortableTests(unittest.TestCase):
    def test_el_artefacto_lleva_esquema_identidad_y_dependencias(self):
        a = jamtool_core.exportar(preset())
        self.assertEqual(a["esquema"], jamtool_core.ESQUEMA)
        self.assertEqual(a["funcion_id"], "fn-0001")
        self.assertEqual(a["requiere"], ["mesh_extrude", "mesh_to_static"])

    def test_los_bordes_de_la_firma_no_son_dependencias(self):
        """`input` y `output` son la firma, no verbos que haya que tener instalados."""
        self.assertNotIn("input", jamtool_core.exportar(preset())["requiere"])
        self.assertNotIn("output", jamtool_core.exportar(preset())["requiere"])

    def test_no_se_exporta_algo_sin_identidad_estable(self):
        """Sin `funcion_id` renombrar rompería todos los grafos que la llaman."""
        with self.assertRaises(jamtool_core.JamToolInvalido):
            jamtool_core.exportar(preset(funcion_id=""))

    def test_solo_una_funcion_puede_exportarse(self):
        with self.assertRaises(jamtool_core.JamToolInvalido):
            jamtool_core.exportar(preset(kind="tool"))

    def test_ida_y_vuelta_conserva_lo_que_importa(self):
        vuelto = jamtool_core.importar(jamtool_core.exportar(preset()))
        self.assertEqual(vuelto["funcion_id"], "fn-0001")
        self.assertEqual(vuelto["nombre"], "Muro rápido")
        self.assertEqual(vuelto["grafo"], preset()["grafo"])

    def test_un_esquema_de_otra_version_se_rechaza_con_su_numero(self):
        """Abrir a ciegas un formato futuro es peor que negarse: falla tarde y sin explicación."""
        a = jamtool_core.exportar(preset())
        a["esquema"] = 99
        with self.assertRaises(jamtool_core.JamToolInvalido) as e:
            jamtool_core.importar(a)
        self.assertIn("99", str(e.exception))

    def test_avisa_al_importar_si_faltan_verbos_y_no_al_ejecutar(self):
        a = jamtool_core.exportar(preset())
        with self.assertRaises(jamtool_core.JamToolInvalido) as e:
            jamtool_core.importar(a, verbos_disponibles={"mesh_extrude"})
        self.assertIn("mesh_to_static", str(e.exception))

    def test_con_todos_los_verbos_presentes_importa(self):
        a = jamtool_core.exportar(preset())
        self.assertEqual(
            jamtool_core.importar(a, verbos_disponibles={"mesh_extrude", "mesh_to_static"})["nombre"],
            "Muro rápido")

    def test_un_artefacto_con_la_entrada_rota_falla_al_IMPORTAR(self):
        """Es un archivo roto: conviene saberlo al abrirlo y no cuando alguien le da Run."""
        a = jamtool_core.exportar(preset(firma=firma(("malla", "A"), entrada_seleccion="fantasma")))
        with self.assertRaises(jamtool_core.JamToolInvalido):
            jamtool_core.importar(a)


if __name__ == "__main__":
    unittest.main()


class ArchivoEnDiscoTests(unittest.TestCase):
    """El `.jamtool` como archivo. JSON a propósito: una tool que alguien armó tiene que poder
    mirarse, compartirse por chat y meterse en un repo."""

    def setUp(self):
        import tempfile

        from jam import jamtool

        self.jamtool = jamtool
        self.dir = tempfile.mkdtemp()

    def ruta(self, nombre="muro"):
        import os

        return os.path.join(self.dir, nombre)

    def test_ida_y_vuelta_por_el_disco(self):
        escrita = self.jamtool.escribir(preset(), self.ruta())
        self.assertTrue(escrita.endswith(".jamtool"))
        self.assertEqual(self.jamtool.leer(escrita)["funcion_id"], "fn-0001")

    def test_le_pone_la_extension_si_falta(self):
        """Guardar «muro» a secas no puede dejar un archivo que después no se reconozca."""
        self.assertTrue(self.jamtool.escribir(preset(), self.ruta("muro")).endswith(".jamtool"))

    def test_un_json_cualquiera_no_es_una_tool(self):
        import pathlib

        otro = pathlib.Path(self.dir) / "cosa.json"
        otro.write_text("{}", encoding="utf-8")
        with self.assertRaises(jamtool_core.JamToolInvalido):
            self.jamtool.leer(str(otro))

    def test_un_archivo_roto_dice_por_que(self):
        import pathlib

        roto = pathlib.Path(self.dir) / "roto.jamtool"
        roto.write_text("{no es json", encoding="utf-8")
        with self.assertRaises(jamtool_core.JamToolInvalido) as e:
            self.jamtool.leer(str(roto))
        self.assertIn("no se pudo leer", str(e.exception))

    def test_el_listado_muestra_lo_justo_sin_abrir_todo(self):
        self.jamtool.escribir(preset(), self.ruta("uno"))
        fila = self.jamtool.listar(self.dir)[0]
        self.assertEqual(fila["nombre"], "Muro rápido")
        self.assertEqual(fila["requiere"], ["mesh_extrude", "mesh_to_static"])

    def test_una_tool_corrupta_no_esconde_a_las_demas(self):
        """Que un archivo roto vacíe el listado sería peor que mostrarlo roto."""
        import pathlib

        self.jamtool.escribir(preset(), self.ruta("buena"))
        (pathlib.Path(self.dir) / "mala.jamtool").write_text("{", encoding="utf-8")
        filas = self.jamtool.listar(self.dir)
        self.assertEqual(len(filas), 2)
        self.assertEqual(sum(1 for f in filas if "error" in f), 1)

    def test_una_carpeta_que_no_existe_no_es_un_error(self):
        self.assertEqual(self.jamtool.listar("/no/existe/nada"), [])
