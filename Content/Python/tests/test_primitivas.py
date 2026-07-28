"""Primitivas nuevas del tab Mesh: validación pura y contrato de grafo.

La geometría la hace Geometry Script; lo que se prueba acá es que ningún parámetro absurdo llegue al
motor —donde falla de formas raras o silenciosas— y que cada verbo declare bien su tipo.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest import mock

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import curve, mesh, tools  # noqa: E402


NUEVAS = ("mesh_box", "mesh_capsule", "mesh_torus", "mesh_disc", "mesh_round_rect",
          "mesh_stairs", "mesh_stairs_curved", "mesh_sphere_box", "mesh_revolve")


class ContratoTests(unittest.TestCase):
    def test_the_generators_are_sources_that_produce_a_mesh(self):
        for verbo in NUEVAS:
            if verbo == "mesh_revolve":
                continue
            with self.subTest(verbo=verbo):
                info = tools.REGISTRO[verbo]
                self.assertTrue(info["source"], "una primitiva no consume nada")
                self.assertEqual(info["in_name"], "")
                self.assertEqual(info["out_name"], "M")
                self.assertFalse(info["asset_required"])
                self.assertEqual(info["cat"], "Mesh")

    def test_revolve_is_a_lathe_that_consumes_a_curve(self):
        info = tools.REGISTRO["mesh_revolve"]
        self.assertFalse(info["source"])
        self.assertEqual(info["in_name"], "S")
        self.assertEqual(info["out_name"], "M")

    def test_every_source_verb_accepts_the_executor_call_shape(self):
        """El ejecutor llama SIEMPRE `fn(entrada, **params)`, también a las fuentes.

        Una fuente escrita con params sólo-keyword revienta con TypeError recién en el Run, y las
        pruebas que llaman a `mesh.box()` directo no lo ven: hay que probar la forma de la LLAMADA.
        """
        import inspect
        for verbo in NUEVAS:
            with self.subTest(verbo=verbo):
                firma = inspect.signature(tools.REGISTRO[verbo]["fn"])
                posicionales = [p for p in firma.parameters.values()
                                if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
                self.assertEqual(len(posicionales), 1,
                                 f"{verbo} tiene que aceptar la entrada como primer posicional")
                defaults = {k: v.default for k, v in firma.parameters.items()
                            if v.default is not inspect.Parameter.empty}
                # Y tiene que poder llamarse con la entrada en None, como hace una fuente.
                firma.bind(None, **{k: v for k, v in defaults.items()
                                    if k != posicionales[0].name})

    def test_every_new_primitive_is_in_the_palette_once(self):
        import json
        from jam import api
        verbos = [t["verbo"] for t in json.loads(api.spec_all())["tools"]]
        for verbo in NUEVAS:
            with self.subTest(verbo=verbo):
                self.assertEqual(verbos.count(verbo), 1)


class ValidacionTests(unittest.TestCase):
    """Ningún parámetro absurdo debería llegar a Geometry Script."""

    def test_sizes_must_be_positive(self):
        self.assertIn("mayores que cero", mesh.box(size_x=0)["error"])
        self.assertIn("mayores que cero", mesh.box(size_z=-10)["error"])
        self.assertIn("mayor que cero", mesh.capsule(radius=0)["error"])
        self.assertIn("mayor que cero", mesh.sphere_box(radius=-1)["error"])
        self.assertIn("mayor que cero", mesh.disc(radius=0)["error"])

    def test_a_torus_whose_tube_swallows_the_hole_is_rejected(self):
        # minor >= major cierra el agujero: Geometry Script devuelve una malla que se auto-interseca.
        self.assertIn("menor que major_radius",
                      mesh.torus(major_radius=50, minor_radius=50)["error"])
        self.assertIn("menor que major_radius",
                      mesh.torus(major_radius=50, minor_radius=80)["error"])

    def test_a_hole_bigger_than_the_disc_is_rejected(self):
        self.assertIn("entre 0 y radius", mesh.disc(radius=100, hole_radius=100)["error"])
        self.assertIn("entre 0 y radius", mesh.disc(radius=100, hole_radius=-5)["error"])

    def test_the_disc_angles_must_advance(self):
        self.assertIn("mayor que start_angle",
                      mesh.disc(start_angle=180, end_angle=90)["error"])
        self.assertIn("mayor que start_angle",
                      mesh.disc(start_angle=90, end_angle=90)["error"])

    def test_a_corner_radius_bigger_than_half_the_side_is_rejected(self):
        # Si el redondeo no entra, las esquinas se cruzan y la malla sale dada vuelta.
        self.assertIn("mitad del lado", mesh.round_rect(size_x=100, size_y=100,
                                                        corner_radius=60)["error"])
        self.assertIn("mitad del lado", mesh.round_rect(corner_radius=0)["error"])

    def test_stairs_bound_their_step_count(self):
        self.assertIn("entre 1 y 256", mesh.stairs(steps=0)["error"])
        self.assertIn("entre 1 y 256", mesh.stairs(steps=999)["error"])
        self.assertIn("mayores que cero", mesh.stairs(step_height=0)["error"])

    def test_curved_stairs_need_a_real_angle(self):
        self.assertIn("entre 1 y 360", mesh.stairs_curved(curve_angle=0)["error"])
        self.assertIn("entre 1 y 360", mesh.stairs_curved(curve_angle=400)["error"])
        self.assertIn("entre 1 y 360", mesh.stairs_curved(curve_angle=-400)["error"])

    def test_a_negative_curve_angle_is_valid_and_reverses_the_turn(self):
        """El signo elige el sentido del giro, así que -90 tiene que PASAR la validación."""
        capturado = {}

        class _Prims:
            @staticmethod
            def append_curved_stairs(target, opciones, transform, **kw):
                capturado.update(kw)
                return target

        with mock.patch.object(_unreal_fake, "GeometryScript_Primitives", _Prims, create=True), \
                mock.patch.object(_unreal_fake, "GeometryScriptPrimitiveOptions",
                                  object, create=True), \
                mock.patch.object(_unreal_fake, "Transform", lambda **k: object(), create=True), \
                mock.patch.object(_unreal_fake, "DynamicMesh", type("DM", (), {}), create=True), \
                mock.patch.object(mesh, "_info", return_value="DynamicMesh"):
            r = mesh.stairs_curved(curve_angle=-90.0, steps=6)

        self.assertNotIn("error", r)
        self.assertEqual(capturado["curve_angle"], -90.0)
        self.assertEqual(capturado["num_steps"], 6)

    def test_step_counts_are_bounded(self):
        self.assertIn("al menos 3", mesh.torus(major_steps=2)["error"])
        self.assertIn("al menos 3", mesh.disc(sides=2)["error"])
        self.assertIn("al menos 1", mesh.round_rect(steps_round=0)["error"])
        self.assertIn("entre 1 y 64", mesh.sphere_box(steps=100)["error"])
        self.assertIn("no pueden ser negativos", mesh.box(steps_x=-1)["error"])


class RevolveTests(unittest.TestCase):
    def test_it_needs_a_single_curve(self):
        self.assertIn("curva S válida", mesh.revolve(None)["error"])
        dos = curve.CurveSet((
            curve.CurvePath(((0.0, 0.0, 0.0), (10.0, 0.0, 10.0))),
            curve.CurvePath(((0.0, 0.0, 0.0), (20.0, 0.0, 20.0))),
        ))
        self.assertIn("UNA curva", mesh.revolve(dos)["error"])

    def test_a_profile_on_the_axis_is_rejected(self):
        """Girar algo que está sobre el eje no produce volumen: degenera en una línea."""
        sobre_el_eje = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        self.assertIn("sobre el eje", mesh.revolve(sobre_el_eje)["error"])

    def test_it_validates_steps_and_degrees(self):
        perfil = curve.CurvePath(((50.0, 0.0, 0.0), (60.0, 0.0, 100.0)))
        self.assertIn("al menos 3", mesh.revolve(perfil, steps=2)["error"])
        self.assertIn("entre 1 y 360", mesh.revolve(perfil, degrees=0)["error"])
        self.assertIn("entre 1 y 360", mesh.revolve(perfil, degrees=720)["error"])

    def test_the_profile_reads_x_as_radius_and_z_as_height(self):
        """El perfil de torno de toda la vida: x = distancia al eje, z = altura."""
        capturado = {}

        class _Prims:
            @staticmethod
            def append_revolve_path(target, opciones, transform, vertices, revolve, **kw):
                capturado["vertices"] = list(vertices)
                capturado["kw"] = kw
                return target

        perfil = curve.CurvePath(((30.0, 99.0, 0.0), (45.0, 99.0, 80.0), (20.0, 99.0, 160.0)))
        with mock.patch.object(_unreal_fake, "GeometryScript_Primitives", _Prims, create=True), \
                mock.patch.object(_unreal_fake, "GeometryScriptRevolveOptions",
                                  lambda: types.SimpleNamespace(
                                      set_editor_property=lambda *a: None), create=True), \
                mock.patch.object(_unreal_fake, "GeometryScriptPrimitiveOptions",
                                  object, create=True), \
                mock.patch.object(_unreal_fake, "Transform", lambda **k: object(), create=True), \
                mock.patch.object(_unreal_fake, "DynamicMesh", type("DM", (), {}), create=True), \
                mock.patch.object(_unreal_fake, "Vector2D", lambda x, y: (x, y), create=True), \
                mock.patch.object(mesh, "_info", return_value="DynamicMesh"):
            r = mesh.revolve(perfil, steps=8, degrees=180.0)

        self.assertNotIn("error", r)
        # La Y del mundo se IGNORA: el perfil vive en XZ.
        self.assertEqual(capturado["vertices"], [(30.0, 0.0), (45.0, 80.0), (20.0, 160.0)])
        self.assertEqual(capturado["kw"]["steps"], 8)

    def test_a_negative_x_is_folded_onto_the_axis(self):
        """Un perfil dibujado del lado negativo gira igual: se toma la distancia al eje."""
        capturado = {}

        class _Prims:
            @staticmethod
            def append_revolve_path(target, opciones, transform, vertices, revolve, **kw):
                capturado["vertices"] = list(vertices)
                return target

        perfil = curve.CurvePath(((-40.0, 0.0, 0.0), (-25.0, 0.0, 90.0)))
        with mock.patch.object(_unreal_fake, "GeometryScript_Primitives", _Prims, create=True), \
                mock.patch.object(_unreal_fake, "GeometryScriptRevolveOptions",
                                  lambda: types.SimpleNamespace(
                                      set_editor_property=lambda *a: None), create=True), \
                mock.patch.object(_unreal_fake, "GeometryScriptPrimitiveOptions",
                                  object, create=True), \
                mock.patch.object(_unreal_fake, "Transform", lambda **k: object(), create=True), \
                mock.patch.object(_unreal_fake, "DynamicMesh", type("DM", (), {}), create=True), \
                mock.patch.object(_unreal_fake, "Vector2D", lambda x, y: (x, y), create=True), \
                mock.patch.object(mesh, "_info", return_value="DynamicMesh"):
            mesh.revolve(perfil)

        self.assertEqual(capturado["vertices"], [(40.0, 0.0), (25.0, 90.0)])


if __name__ == "__main__":
    unittest.main()
