from __future__ import annotations

import contextlib
import json
from collections import namedtuple
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


unreal = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(unreal, "TopLevelAssetPath"):
    unreal.TopLevelAssetPath = lambda package, name: (package, name)

from jam import (  # noqa: E402
    api, curve, fields, graph, instances, mesh, panel, tools, variants,
)


class _DynamicMesh:
    pass


class _Options:
    def __init__(self):
        self.values = {}

    def set_editor_property(self, name, value):
        self.values[name] = value


class _AssetLibrary:
    def __init__(self):
        self.assets = set()

    def does_asset_exist(self, path):
        return path in self.assets

    def delete_asset(self, path):
        self.assets.discard(path)
        return True

    def save_asset(self, path, only_if_is_dirty=False):
        return path in self.assets and not only_if_is_dirty


_Vec = namedtuple("_Vec", "x y z")


class _Patches:
    """Agrupa varios ``mock.patch`` en un solo ``with``."""

    def __init__(self, *patches):
        self._patches = patches
        self._stack = contextlib.ExitStack()

    def __enter__(self):
        for patch in self._patches:
            self._stack.enter_context(patch)
        return self

    def __exit__(self, *exc_info):
        return self._stack.__exit__(*exc_info)


class InfoTests(unittest.TestCase):
    """`_info()` es lo único que Slate muestra de una malla. Antes mostraba la primera línea del
    volcado de debug del motor —sólo vértices— y `mesh_simplify_count` podía correr sin que se
    viera nunca si el objetivo, expresado en triángulos, se había cumplido."""

    def _consulta(self, *, vertices, triangulos, cerrada, piezas):
        class _Queries:
            @staticmethod
            def get_vertex_count(_target):
                return vertices

            @staticmethod
            def get_num_triangle_i_ds(_target):
                return triangulos

            @staticmethod
            def get_is_closed_mesh(_target):
                return cerrada

            @staticmethod
            def get_num_connected_components(_target):
                return piezas

        return _Queries

    def test_una_malla_cerrada_de_una_pieza_no_menciona_piezas(self):
        consulta = self._consulta(vertices=502, triangulos=1000, cerrada=True, piezas=1)
        with mock.patch.object(unreal, "GeometryScript_MeshQueries", consulta, create=True):
            self.assertEqual(mesh._info(object()), "1000 triángulos · 502 vértices · cerrada")

    def test_una_malla_abierta_de_varias_piezas_lo_dice_todo(self):
        consulta = self._consulta(vertices=224956, triangulos=17932, cerrada=False, piezas=53)
        with mock.patch.object(unreal, "GeometryScript_MeshQueries", consulta, create=True):
            self.assertEqual(
                mesh._info(object()),
                "17932 triángulos · 224956 vértices · abierta · 53 piezas")

    def test_una_consulta_que_falla_no_rompe_el_nodo(self):
        class _QueriesRotas:
            @staticmethod
            def get_vertex_count(_target):
                raise RuntimeError("motor no disponible")

        with mock.patch.object(unreal, "GeometryScript_MeshQueries", _QueriesRotas, create=True):
            self.assertEqual(mesh._info(object()), "DynamicMesh")


class MeshTests(unittest.TestCase):
    def test_bezier_curve_has_stable_endpoints_and_bend(self):
        result = curve.bezier(
            start_x=0, start_y=0, start_z=0,
            end_x=100, end_y=0, end_z=100,
            bend_y=50, segments=4,
        )

        self.assertNotIn("error", result)
        path = result["curve"]
        self.assertEqual(len(path.points), 5)
        self.assertEqual(path.points[0], (0.0, 0.0, 0.0))
        self.assertEqual(path.points[-1], (100.0, 0.0, 100.0))
        self.assertAlmostEqual(path.points[2][1], 25.0)
        self.assertGreater(path.length, 100.0)

    def test_curve_frames_are_equidistant_and_stable_on_vertical_paths(self):
        path = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))

        result = curve.frames(
            path, count=3, start=0.0, end=1.0, radial_offset=10.0,
            turns=0.5, angle_offset=0.0)

        self.assertNotIn("error", result)
        frames = result["frames"]
        self.assertEqual([round(frame.position[2]) for frame in frames], [0, 50, 100])
        self.assertEqual(frames[0].tangent, (0.0, 0.0, 1.0))
        self.assertAlmostEqual(frames[0].position[1], 10.0)
        self.assertAlmostEqual(frames[1].position[0], -10.0)
        self.assertAlmostEqual(frames[2].position[1], -10.0)

    def test_curve_frame_stream_preserves_hierarchy_scale_radius_and_seed(self):
        parents = curve.CurveSet((
            curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)), scale=1.0),
            curve.CurvePath(((20.0, 0.0, 0.0), (20.0, 0.0, 50.0)), scale=0.5),
        ))

        first = curve.frame_stream(
            parents, count=3, start=0.0, end=1.0,
            radius_start=10.0, radius_end=2.0, seed=31,
        )
        second = curve.frame_stream(
            parents, count=3, start=0.0, end=1.0,
            radius_start=10.0, radius_end=2.0, seed=31,
        )

        self.assertNotIn("error", first)
        stream = first["frame_set"]
        self.assertIsInstance(stream, curve.FrameSet)
        self.assertEqual(stream, second["frame_set"])
        self.assertEqual(len(stream), 6)
        self.assertEqual(stream.parent_count, 2)
        self.assertEqual([frame.parent_index for frame in stream.frames], [0, 0, 0, 1, 1, 1])
        self.assertEqual([frame.local_index for frame in stream.frames], [0, 1, 2, 0, 1, 2])
        self.assertEqual([frame.pivot_index for frame in stream.frames], list(range(6)))
        self.assertEqual([frame.scale for frame in stream.frames], [1.0] * 3 + [0.5] * 3)
        self.assertEqual([frame.radius for frame in stream.frames], [10.0, 6.0, 2.0, 5.0, 3.0, 1.0])
        self.assertEqual(len({frame.seed for frame in stream.frames}), 6)
        self.assertIn("6 frames/2 curvas", first["info"])

    def test_curve_frame_stream_validates_limits(self):
        path = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))

        self.assertIn("error", curve.frame_stream(None))
        self.assertIn("error", curve.frame_stream(path, count=0))
        self.assertIn("error", curve.frame_stream(path, start=0.8, end=0.2))
        self.assertIn("error", curve.frame_stream(path, radius_start=-1.0))

    def test_curve_frames_tool_publishes_the_runtime_f_stream(self):
        path = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        try:
            message = tools.t_curve_frames(path, count=4, radius_start=8.0, radius_end=2.0)
            output = tools.dato_producido_runtime("curve_frames")

            self.assertIn("FRAMES F ✓", message)
            self.assertIsInstance(output, curve.FrameSet)
            self.assertEqual(len(output), 4)
            self.assertEqual([frame.radius for frame in output.frames], [8.0, 6.0, 4.0, 2.0])
        finally:
            tools.limpiar_asset_producido_runtime("curve_frames")

    def test_distribute_frames_resamples_each_parent_and_preserves_attributes(self):
        parents = curve.CurveSet((
            curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)), scale=1.0),
            curve.CurvePath(((20.0, 0.0, 0.0), (20.0, 0.0, 50.0)), scale=0.5),
        ))
        source = curve.frame_stream(
            parents, count=5, radius_start=10.0, radius_end=2.0, seed=3,
        )["frame_set"]

        result = curve.distribute_frames(
            source, count=3, start=0.25, end=0.75,
            rotate_per_index=90.0, angle_offset=0.0, seed=41,
        )

        self.assertNotIn("error", result)
        stream = result["frame_set"]
        self.assertEqual(len(stream), 6)
        self.assertEqual(stream.parent_count, 2)
        self.assertEqual([frame.parent_index for frame in stream.frames], [0, 0, 0, 1, 1, 1])
        self.assertEqual([frame.local_index for frame in stream.frames], [0, 1, 2, 0, 1, 2])
        self.assertEqual([frame.pivot_index for frame in stream.frames], list(range(6)))
        self.assertEqual([frame.parameter for frame in stream.frames[:3]], [0.25, 0.5, 0.75])
        self.assertEqual([frame.radius for frame in stream.frames[:3]], [8.0, 6.0, 4.0])
        self.assertEqual([frame.radius for frame in stream.frames[3:]], [4.0, 3.0, 2.0])
        self.assertAlmostEqual(stream.frames[0].outward[1], 1.0)
        self.assertAlmostEqual(stream.frames[1].outward[0], -1.0)
        self.assertEqual(len({frame.seed for frame in stream.frames}), 6)

    def test_distribute_frames_jitter_is_deterministic_and_validated(self):
        path = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        source = curve.frame_stream(path, count=8)["frame_set"]
        params = dict(
            count=5, angle_jitter=12.0, parameter_jitter=0.08, seed=1977,
        )

        first = curve.distribute_frames(source, **params)
        second = curve.distribute_frames(source, **params)

        self.assertEqual(first["frame_set"], second["frame_set"])
        self.assertIn("error", curve.distribute_frames(None))
        self.assertIn("error", curve.distribute_frames(source, count=0))
        self.assertIn("error", curve.distribute_frames(source, start=0.8, end=0.2))
        self.assertIn("error", curve.distribute_frames(source, angle_jitter=-1.0))
        self.assertIn("error", curve.distribute_frames(source, parameter_jitter=1.1))

    def test_distribute_frames_tool_publishes_the_runtime_f_stream(self):
        path = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        source = curve.frame_stream(path, count=4)["frame_set"]
        try:
            message = tools.t_distribute_frames(source, count=3, rotate_per_index=120.0)
            output = tools.dato_producido_runtime("distribute_frames")

            self.assertIn("DISTRIBUTE F ✓", message)
            self.assertIsInstance(output, curve.FrameSet)
            self.assertEqual(len(output), 3)
        finally:
            tools.limpiar_asset_producido_runtime("distribute_frames")

    def test_transform_frames_uses_local_axes_and_inherits_parent_scale(self):
        source = curve.FrameSet((curve.CurveFrame(
            position=(0.0, 0.0, 0.0), tangent=(0.0, 0.0, 1.0),
            outward=(0.0, 1.0, 0.0), parameter=0.4,
            parent_index=2, local_index=3, scale=0.5, radius=7.0,
            seed=19, pivot_index=11,
        ),), parent_count=3)

        result = curve.transform_frames(
            source, offset_x=10.0, offset_y=20.0, offset_z=30.0,
            yaw=90.0, scale=2.0, inherit_scale=True, seed=41,
        )

        self.assertNotIn("error", result)
        frame = result["frame_set"].frames[0]
        self.assertEqual(frame.position, (10.0, 15.0, 5.0))
        self.assertAlmostEqual(frame.tangent[0], 1.0)
        self.assertAlmostEqual(frame.tangent[1], 0.0)
        self.assertAlmostEqual(frame.tangent[2], 0.0)
        self.assertAlmostEqual(frame.outward[1], 1.0)
        self.assertEqual(frame.scale, 1.0)
        self.assertEqual(frame.radius, 7.0)
        self.assertEqual(frame.parent_index, 2)
        self.assertEqual(frame.local_index, 3)
        self.assertEqual(frame.pivot_index, 11)
        self.assertEqual(result["frame_set"].parent_count, 3)

        independent = curve.transform_frames(
            source, offset_x=10.0, offset_y=20.0, offset_z=30.0,
            scale=2.0, inherit_scale=False,
        )["frame_set"].frames[0]
        self.assertEqual(independent.position, (20.0, 30.0, 10.0))
        self.assertEqual(independent.scale, 2.0)

    def test_transform_frames_jitter_is_deterministic_and_validated(self):
        path = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        source = curve.frame_stream(path, count=5)["frame_set"]
        params = dict(
            offset_jitter_x=5.0, offset_jitter_y=3.0, offset_jitter_z=2.0,
            pitch_jitter=8.0, yaw_jitter=12.0, roll_jitter=15.0,
            scale=1.0, scale_jitter=0.2, seed=1977,
        )

        first = curve.transform_frames(source, **params)
        second = curve.transform_frames(source, **params)

        self.assertEqual(first["frame_set"], second["frame_set"])
        self.assertEqual(len({frame.seed for frame in first["frame_set"].frames}), 5)
        self.assertIn("error", curve.transform_frames(None))
        self.assertIn("error", curve.transform_frames(source, scale=0.0))
        self.assertIn("error", curve.transform_frames(source, yaw_jitter=-1.0))
        self.assertIn("error", curve.transform_frames(source, scale=0.2, scale_jitter=0.2))

    def test_transform_frames_tool_publishes_the_runtime_f_stream(self):
        path = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        source = curve.frame_stream(path, count=4)["frame_set"]
        try:
            message = tools.t_transform_frames(source, offset_z=12.0, roll=15.0, scale=0.8)
            output = tools.dato_producido_runtime("transform_frames")

            self.assertIn("TRANSFORM F ✓", message)
            self.assertIsInstance(output, curve.FrameSet)
            self.assertEqual(len(output), 4)
        finally:
            tools.limpiar_asset_producido_runtime("transform_frames")

    def test_branch_from_frames_creates_one_hierarchical_curve_per_frame(self):
        source = curve.FrameSet((curve.CurveFrame(
            position=(0.0, 0.0, 10.0), tangent=(0.0, 0.0, 1.0),
            outward=(0.0, 1.0, 0.0), parameter=0.4,
            parent_index=2, local_index=3, scale=0.5, radius=7.0,
            seed=19, pivot_index=11,
        ),), parent_count=3)

        result = curve.branch_from_frames(
            source, length_min=100.0, length_max=100.0,
            angle=90.0, curl=0.0, segments=4,
            inherit_scale=True, seed=41,
        )

        self.assertNotIn("error", result)
        collection = result["curve"]
        self.assertIsInstance(collection, curve.CurveSet)
        self.assertEqual(len(collection.paths), 1)
        branch = collection.paths[0]
        self.assertEqual(len(branch.points), 5)
        self.assertEqual(branch.points[0], (0.0, 0.0, 10.0))
        self.assertAlmostEqual(branch.points[-1][0], 0.0)
        self.assertAlmostEqual(branch.points[-1][1], 50.0)
        self.assertAlmostEqual(branch.points[-1][2], 10.0)
        self.assertAlmostEqual(branch.length, 50.0)
        self.assertEqual(branch.scale, 0.5)
        self.assertEqual(branch.source_parent_index, 2)
        self.assertEqual(branch.source_local_index, 3)
        self.assertEqual(branch.pivot_index, 11)
        self.assertEqual(branch.parent_radius, 7.0)

    @staticmethod
    def _frames_sobre(largo, *, n=6):
        """Frames repartidos sobre una curva vertical de `largo` cm, con su parent_length."""
        return curve.FrameSet(tuple(
            curve.CurveFrame(
                (0.0, 0.0, largo * i / (n - 1)), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0),
                i / (n - 1), local_index=i, scale=1.0, parent_length=largo,
            )
            for i in range(n)
        ), parent_count=1)

    def test_branch_length_relative_to_parent_scales_with_the_parent(self):
        corto = curve.branch_from_frames(
            self._frames_sobre(600.0), length_min=0.20, length_max=0.20,
            relative_to_parent=True, angle=90, curl=0, segments=4, seed=1)
        largo = curve.branch_from_frames(
            self._frames_sobre(3000.0), length_min=0.20, length_max=0.20,
            relative_to_parent=True, angle=90, curl=0, segments=4, seed=1)

        self.assertNotIn("error", corto)
        self.assertNotIn("error", largo)
        # 20% del padre: el tronco de 600 da ramas de 120, el de 3000 da 600.
        self.assertAlmostEqual(corto["curve"].paths[0].length, 120.0, delta=1.0)
        self.assertAlmostEqual(largo["curve"].paths[0].length, 600.0, delta=1.0)
        # Éste es el bug que motivó todo: en absoluto, el largo NO cambia al alargar el tronco.
        absoluto_corto = curve.branch_from_frames(
            self._frames_sobre(600.0), length_min=120, length_max=120,
            angle=90, curl=0, segments=4, seed=1)["curve"].paths[0].length
        absoluto_largo = curve.branch_from_frames(
            self._frames_sobre(3000.0), length_min=120, length_max=120,
            angle=90, curl=0, segments=4, seed=1)["curve"].paths[0].length
        self.assertAlmostEqual(absoluto_corto, absoluto_largo, delta=1.0)
        self.assertIn("% del padre", largo["info"])

    def test_branch_profile_tapers_the_length_along_the_parent(self):
        perfil = fields.graph_curve(start_value=1.0, end_value=0.2, shape="linear", samples=9)
        result = curve.branch_from_frames(
            self._frames_sobre(1000.0, n=5), length_min=0.30, length_max=0.30,
            relative_to_parent=True, profile=perfil["series"],
            angle=90, curl=0, segments=4, seed=1)

        self.assertNotIn("error", result)
        largos = [p.length for p in result["curve"].paths]
        # La rama de la base mide 1.0× y la de la punta 0.2× ⇒ silueta cónica.
        self.assertAlmostEqual(largos[0], 300.0, delta=2.0)
        self.assertAlmostEqual(largos[-1], 60.0, delta=2.0)
        self.assertEqual(largos, sorted(largos, reverse=True))
        self.assertIn("perfil linear", result["info"])

    def test_branch_relative_and_profile_validate_their_inputs(self):
        frames = self._frames_sobre(1000.0)
        # En modo relativo, length_max es una fracción: 200 sería 200 veces el padre.
        self.assertIn("fracciones del padre", curve.branch_from_frames(
            frames, length_min=100, length_max=200, relative_to_parent=True)["error"])
        # Frames sin curva padre (armados a mano) no pueden usar el modo relativo.
        sueltos = curve.FrameSet((curve.CurveFrame(
            (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), 0.0),), parent_count=1)
        self.assertIn("largo de padre", curve.branch_from_frames(
            sueltos, length_min=0.2, length_max=0.2, relative_to_parent=True)["error"])
        self.assertIn("serie N[] válida", curve.branch_from_frames(
            frames, profile=object())["error"])
        cero = fields.ScalarSeries((0.0, 0.0), "linear")
        self.assertIn("completamente cero", curve.branch_from_frames(
            frames, profile=cero)["error"])

    def test_parent_length_survives_the_whole_frame_chain(self):
        path = curve.bezier(start_z=0, end_z=1000, segments=8)["curve"]
        f = curve.frame_stream(path, count=6, start=0.1, end=0.9)["frame_set"]
        d = curve.distribute_frames(f, count=5)["frame_set"]
        t = curve.transform_frames(d, scale=0.8)["frame_set"]

        # Sin propagación por las cuatro etapas, el modo relativo no tendría contra qué medir.
        for etapa, conjunto in (("frames", f), ("distribute", d), ("transform", t)):
            with self.subTest(etapa=etapa):
                self.assertTrue(all(fr.parent_length > 0 for fr in conjunto.frames))
                self.assertAlmostEqual(conjunto.frames[0].parent_length, path.length, delta=1.0)

    def test_the_bundled_tree_keeps_its_proportions_when_the_trunk_changes_size(self):
        """La prueba de que el arreglo es estructural y no un ajuste de números.

        Con el largo en centímetros absolutos, duplicar el tronco dejaba las ramas donde estaban y
        el árbol se volvía un poste. Con el largo relativo al padre, todo escala junto.
        """
        documento = json.loads((
            Path(__file__).resolve().parents[3]
            / "Resources" / "Examples" / "TreeGen-Two-Level.jamgraph"
        ).read_text(encoding="utf-8"))

        def arbol(altura_tronco):
            p = dict(documento["nodes"]["trunk"]["params"], end_z=str(altura_tronco))
            tronco = curve.bezier(**{k: (int(v) if k == "segments" else float(v))
                                     for k, v in p.items()})["curve"]
            def n(nodo, ints, textos=()):
                """Params del nodo tal como los guarda el .jamgraph (todo string) a tipos Python."""
                salida = {}
                for k, v in documento["nodes"][nodo]["params"].items():
                    if k == "profile":
                        continue          # llega por cable, no por campo
                    if k in textos:
                        salida[k] = v
                    elif v.lower() in ("true", "false"):
                        salida[k] = v.lower() == "true"
                    else:
                        salida[k] = int(v) if k in ints else float(v)
                return salida
            f = curve.frame_stream(tronco, **n("l1_frames", {"count", "samples", "seed"}))
            d = curve.distribute_frames(f["frame_set"], **n("l1_distribute", {"count", "seed"}))
            t = curve.transform_frames(d["frame_set"], **n("l1_transform", {"seed"}))
            # El perfil llega por cable en el grafo, así que acá se arma desde su nodo.
            serie = fields.graph_curve(**n("l1_length_profile", {"samples"}, {"shape"}))["series"]
            b = curve.branch_from_frames(
                t["frame_set"], profile=serie, **n("l1_branches", {"segments", "seed"}))
            self.assertNotIn("error", b, b)
            frames = t["frame_set"].frames
            # Emparejado con el parámetro de cada frame: 0 en la base del tronco, 1 en la punta.
            return tronco.length, [(fr.parameter, p.length)
                                   for fr, p in zip(frames, b["curve"].paths)]

        alto_a, ramas_a = arbol(1650)
        alto_b, ramas_b = arbol(3300)

        # El tronco se duplica…
        self.assertAlmostEqual(alto_b / alto_a, 2.0, delta=0.05)
        # …y las ramas también, rama por rama: la proporción se conserva.
        for (_pa, corta), (_pb, larga) in zip(ramas_a, ramas_b):
            self.assertAlmostEqual(larga / corta, 2.0, delta=0.05)
        media = lambda rs, alto: sum(l for _p, l in rs) / len(rs) / alto  # noqa: E731
        self.assertAlmostEqual(media(ramas_a, alto_a), media(ramas_b, alto_b), delta=0.01)

        # Y el perfil sigue afinando de la base a la punta en los dos tamaños: las ramas del tercio
        # bajo son bastante más largas que las del tercio alto.
        for etiqueta, ramas in (("chico", ramas_a), ("grande", ramas_b)):
            with self.subTest(arbol=etiqueta):
                bajas = [l for p, l in ramas if p <= 0.35]
                altas = [l for p, l in ramas if p >= 0.75]
                self.assertTrue(bajas and altas, ramas)
                self.assertGreater(sum(bajas) / len(bajas), 1.5 * sum(altas) / len(altas))

    def test_branch_from_frames_curl_and_jitter_are_deterministic(self):
        path = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        frames = curve.frame_stream(path, count=4)["frame_set"]
        params = dict(
            length_min=80.0, length_max=120.0, angle=20.0,
            angle_jitter=8.0, curl=70.0, curl_jitter=12.0,
            segments=6, seed=1977,
        )

        first = curve.branch_from_frames(frames, **params)
        second = curve.branch_from_frames(frames, **params)

        self.assertEqual(first["curve"], second["curve"])
        self.assertEqual(len(first["curve"].paths), 4)
        self.assertTrue(all(len(path.points) == 7 for path in first["curve"].paths))
        self.assertTrue(any(abs(path.points[-1][1]) > 1.0 for path in first["curve"].paths))
        self.assertEqual(len({path.seed for path in first["curve"].paths}), 4)
        self.assertIn("error", curve.branch_from_frames(None))
        self.assertIn("error", curve.branch_from_frames(frames, length_min=0.0))
        self.assertIn("error", curve.branch_from_frames(frames, length_min=2.0, length_max=1.0))
        self.assertIn("error", curve.branch_from_frames(frames, angle=181.0))
        self.assertIn("error", curve.branch_from_frames(frames, curl_jitter=-1.0))
        self.assertIn("error", curve.branch_from_frames(frames, segments=1))

    def test_branch_from_frames_tool_publishes_the_runtime_s_stream(self):
        path = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        source = curve.frame_stream(path, count=4)["frame_set"]
        try:
            message = tools.t_branch_from_frames(
                source, length_min=100.0, length_max=100.0, segments=4,
            )
            output = tools.dato_producido_runtime("branch_from_frames")

            self.assertIn("BRANCH FROM F ✓", message)
            self.assertIsInstance(output, curve.CurveSet)
            self.assertEqual(len(output.paths), 4)
        finally:
            tools.limpiar_asset_producido_runtime("branch_from_frames")

    def test_curve_child_uses_parent_frame_instead_of_world_coordinates(self):
        parent = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))

        result = curve.child(
            parent, at=0.5, length=100.0, angle=90.0, azimuth=0.0,
            bend=0.0, radial_offset=10.0, segments=4,
        )

        self.assertNotIn("error", result)
        child = result["curve"]
        self.assertEqual(len(child.points), 5)
        self.assertAlmostEqual(child.points[0][0], 0.0)
        self.assertAlmostEqual(child.points[0][1], 10.0)
        self.assertAlmostEqual(child.points[0][2], 50.0)
        self.assertAlmostEqual(child.points[-1][0], 0.0)
        self.assertAlmostEqual(child.points[-1][1], 110.0)
        self.assertAlmostEqual(child.points[-1][2], 50.0)

    def test_curve_child_validates_parent_and_normalized_attachment(self):
        parent = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))

        self.assertIn("error", curve.child(None))
        self.assertIn("error", curve.child(parent, at=1.1))
        self.assertIn("error", curve.child(parent, length=0.0))
        self.assertIn("error", curve.child(parent, angle=181.0))

    def test_curve_branches_builds_a_seeded_tapered_curve_set(self):
        parent = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))

        first = curve.branches(
            parent, count=3, start=0.2, end=0.8, length_min=100, length_max=100,
            parent_scale_start=1.0, parent_scale_end=0.5,
            angle=90, angle_jitter=0, rotate_per_index=90,
            azimuth_jitter=0, bend=0, bend_jitter=0, segments=4, seed=33,
        )
        second = curve.branches(
            parent, count=3, start=0.2, end=0.8, length_min=100, length_max=100,
            parent_scale_start=1.0, parent_scale_end=0.5,
            angle=90, angle_jitter=0, rotate_per_index=90,
            azimuth_jitter=0, bend=0, bend_jitter=0, segments=4, seed=33,
        )

        self.assertNotIn("error", first)
        self.assertIsInstance(first["curve"], curve.CurveSet)
        self.assertEqual(first["curve"], second["curve"])
        self.assertEqual(len(first["curve"].paths), 3)
        self.assertEqual([item.scale for item in first["curve"].paths], [1.0, 0.75, 0.5])
        self.assertAlmostEqual(first["curve"].paths[0].length, 100.0)
        self.assertAlmostEqual(first["curve"].paths[-1].length, 50.0)
        self.assertIn("3 ramas/1 padres", first["info"])
        self.assertIn("error", curve.branches(parent, count=129))

    def test_bundled_tree_example_compiles_as_a_typed_graph(self):
        example_path = (
            Path(__file__).resolve().parents[3]
            / "Resources" / "Examples" / "TreeGen-Stylized-Pine.jamgraph"
        )
        source = example_path.read_text(encoding="utf-8")
        document = json.loads(source)
        result = json.loads(api.compile_graph_json(source))

        self.assertTrue(result["ok"], result)
        self.assertEqual(len(document["nodes"]), 11)
        self.assertEqual(len(document["edges"]), 10)
        self.assertEqual(document["nodes"]["assemble_tree"]["verb"], "mesh_merge")
        self.assertEqual(document["nodes"]["tree_asset"]["verb"], "mesh_to_static")
        self.assertEqual(document["nodes"]["preview_tree"]["verb"], "place")

    def test_bundled_branched_tree_compiles_curve_to_pipe_to_mesh(self):
        example_path = (
            Path(__file__).resolve().parents[3]
            / "Resources" / "Examples" / "TreeGen-Branched-Tree.jamgraph"
        )
        source = example_path.read_text(encoding="utf-8")
        document = json.loads(source)
        with mock.patch.object(graph, "_resolver_asset_runtime", side_effect=lambda path: path):
            result = json.loads(api.compile_graph_json(source))

        self.assertTrue(result["ok"], result)
        self.assertEqual(len(document["nodes"]), 15)
        self.assertEqual(len(document["edges"]), 18)
        nodes = list(document["nodes"].values())
        by_verb = {}
        for node in nodes:
            by_verb.setdefault(node["verb"], []).append(node)
        self.assertEqual(len(by_verb["curve_bezier"]), 1)
        self.assertEqual(len(by_verb["curve_branches"]), 1)
        branches = by_verb["curve_branches"][0]
        self.assertEqual(branches["params"]["count"], "64")
        self.assertEqual(branches["params"]["start"], "0.20")
        self.assertEqual(branches["params"]["end"], "0.92")
        self.assertEqual(len(by_verb["mesh_pipe"]), 2)
        self.assertNotIn("mesh_sphere", by_verb)
        self.assertEqual(
            {node["params"]["color"] for node in by_verb["mesh_color"]},
            {"#70452A", "#3F7D3B"},
        )
        leaves = sorted(by_verb["mesh_leaf"], key=lambda node: int(node["params"]["count"]))
        self.assertEqual([node["params"]["count"] for node in leaves], ["4", "20"])
        self.assertEqual(leaves[0]["params"]["inherit_scale"].lower(), "true")
        self.assertEqual(len(by_verb["asset"]), 1)

    def test_bundled_curve_frames_example_compiles_with_f_output(self):
        example_path = (
            Path(__file__).resolve().parents[3]
            / "Resources" / "Examples" / "TreeGen-Curve-Frames.jamgraph"
        )
        source = example_path.read_text(encoding="utf-8")
        with mock.patch.object(graph, "_resolver_asset_runtime", side_effect=lambda path: path):
            result = json.loads(api.compile_graph_json(source))

        self.assertTrue(result["ok"], result)
        document = json.loads(source)
        self.assertEqual(document["nodes"]["frames"]["verb"], "curve_frames")
        self.assertEqual(document["nodes"]["distribute"]["verb"], "distribute_frames")
        self.assertEqual(document["nodes"]["transform"]["verb"], "transform_frames")
        self.assertEqual(document["nodes"]["branches"]["verb"], "branch_from_frames")
        self.assertEqual(document["nodes"]["foliage_set"]["verb"], "asset_set")
        self.assertEqual(document["nodes"]["foliage_choose"]["verb"], "choose_asset")
        # Este ejemplo demuestra la salida INSTANCIADA; el de dos niveles hornea el follaje.
        self.assertEqual(document["nodes"]["foliage"]["verb"], "hism_output")
        self.assertEqual(document["nodes"]["trunk_profile"]["verb"], "graph_curve")
        self.assertEqual(document["nodes"]["trunk_pipe"]["verb"], "mesh_pipe_profile")
        self.assertEqual(document["nodes"]["branch_profile"]["verb"], "graph_curve")
        self.assertEqual(document["nodes"]["branch_pipe"]["verb"], "mesh_pipe_profile")
        self.assertEqual(document["nodes"]["wood_uv"]["verb"], "mesh_uv_scale")
        self.assertEqual(document["nodes"]["wood_material"]["verb"], "mesh_material")
        self.assertEqual(document["nodes"]["tree_asset"]["verb"], "mesh_to_static")
        self.assertEqual(document["nodes"]["preview"]["verb"], "place")
        self.assertEqual(len(document["nodes"]), 21)
        self.assertEqual(len(document["edges"]), 21)
        self.assertEqual(document["edges"][:4], [
            ["curve", "out", "frames", "in"],
            ["frames", "out", "distribute", "in"],
            ["distribute", "out", "transform", "in"],
            ["transform", "out", "branches", "in"],
        ])
        self.assertIn(["branches", "out", "branch_pipe", "in"], document["edges"])
        self.assertIn(["trunk_profile", "out", "trunk_pipe", "profile"], document["edges"])
        self.assertIn(["branch_profile", "out", "branch_pipe", "profile"], document["edges"])
        self.assertIn(["frond_asset", "out", "foliage_set", "in"], document["edges"])
        self.assertIn(["leaf_card_asset", "out", "foliage_set", "in"], document["edges"])
        self.assertIn(["foliage_set", "out", "foliage_choose", "assets"], document["edges"])
        self.assertIn(["transform", "out", "foliage_choose", "in"], document["edges"])
        self.assertIn(["foliage_choose", "out", "foliage", "in"], document["edges"])
        self.assertIn(["tree_asset", "out", "preview", "in"], document["edges"])

        # La madera termina en un asset con UV tiladas y material explícito; el follaje sale por HISM
        # y no vuelve a la malla, así que el árbol tiene dos salidas y ningún merge final.
        self.assertEqual(
            [edge for edge in document["edges"] if edge[2] in ("wood_uv", "wood_material")],
            [
                ["color", "out", "wood_uv", "in"],
                ["wood_uv", "out", "wood_material", "in"],
            ],
        )
        self.assertIn(["wood_material", "out", "normals", "in"], document["edges"])
        self.assertEqual([edge for edge in document["edges"] if edge[0] == "foliage"], [])
        self.assertEqual(tools.REGISTRO["hism_output"]["out_name"], "H")
        # Un material explícito reemplaza al lector implícito de Vertex Color de ``mesh_to_static``,
        # por eso el ejemplo apaga la bandera y elige a mano el material que sí lee el color.
        self.assertEqual(document["nodes"]["tree_asset"]["params"]["show_vertex_colors"], "false")
        self.assertEqual(
            document["nodes"]["wood_material"]["params"]["material"], mesh.VERTEX_COLOR_MATERIAL)

        runtime_document = {
            "nodes": {
                key: document["nodes"][key]
                for key in ("curve", "frames", "distribute", "transform", "branches")
            },
            "edges": document["edges"][:4],
        }
        try:
            report, states = graph.ejecutar_detalle(
                graph.JamGraph.from_json(json.dumps(runtime_document))
            )
            self.assertEqual(states["curve"]["estado"], "ok", report)
            self.assertEqual(states["frames"]["estado"], "ok", report)
            self.assertEqual(states["distribute"]["estado"], "ok", report)
            self.assertEqual(states["transform"]["estado"], "ok", report)
            self.assertEqual(states["branches"]["estado"], "ok", report)
            self.assertIn("DISTRIBUTE F ✓ — 18 frames/1 padres", report)
            self.assertIn("TRANSFORM F ✓ — 18 frames", report)
            self.assertIn("BRANCH FROM F ✓ — 18 ramas", report)
        finally:
            for verb in (
                "curve_bezier", "curve_frames", "distribute_frames",
                "transform_frames", "branch_from_frames",
            ):
                tools.limpiar_asset_producido_runtime(verb)

        document["nodes"]["pipe"] = {
            "verb": "mesh_pipe", "params": {}, "asset": None, "x": 700, "y": 40,
        }
        document["edges"].append(["transform", "out", "pipe", "in"])
        with mock.patch.object(graph, "_resolver_asset_runtime", side_effect=lambda path: path):
            incompatible = json.loads(api.compile_graph_json(json.dumps(document)))
        self.assertFalse(incompatible["ok"])
        self.assertIn("esperaba S, recibió F", incompatible["nodes"]["pipe"]["texto"])

        no_variants = json.loads(source)
        no_variants["edges"].remove(["foliage_set", "out", "foliage_choose", "assets"])
        with mock.patch.object(graph, "_resolver_asset_runtime", side_effect=lambda path: path):
            missing = json.loads(api.compile_graph_json(json.dumps(no_variants)))
        self.assertFalse(missing["ok"])
        self.assertIn("requiere conexión A[]", missing["nodes"]["foliage_choose"]["texto"])

    def test_bundled_two_level_example_builds_a_real_branch_hierarchy(self):
        example_path = (
            Path(__file__).resolve().parents[3]
            / "Resources" / "Examples" / "TreeGen-Two-Level.jamgraph"
        )
        source = example_path.read_text(encoding="utf-8")
        with mock.patch.object(graph, "_resolver_asset_runtime", side_effect=lambda path: path):
            result = json.loads(api.compile_graph_json(source))

        self.assertTrue(result["ok"], result)
        document = json.loads(source)
        self.assertEqual(len(document["nodes"]), 34)
        self.assertEqual(len(document["edges"]), 36)

        # Los dos niveles son la MISMA cadena de cuatro verbos aplicada dos veces; que el segundo
        # arranque desde la salida S del primero es lo que hace la jerarquía real.
        for prefijo in ("l1", "l2"):
            self.assertEqual(document["nodes"][f"{prefijo}_frames"]["verb"], "curve_frames")
            self.assertEqual(document["nodes"][f"{prefijo}_distribute"]["verb"],
                             "distribute_frames")
            self.assertEqual(document["nodes"][f"{prefijo}_transform"]["verb"], "transform_frames")
            self.assertEqual(document["nodes"][f"{prefijo}_branches"]["verb"],
                             "branch_from_frames")
        self.assertIn(["l1_branches", "out", "l2_frames", "in"], document["edges"])
        # El largo de las ramas es una FRACCIÓN del padre y lo modula un perfil N[]: eso es lo que
        # hace que el árbol escale como una unidad y tenga silueta cónica en vez de cilíndrica.
        for nivel in ("l1", "l2"):
            self.assertEqual(document["nodes"][f"{nivel}_branches"]["params"]["relative_to_parent"],
                             "true")
            self.assertLessEqual(
                float(document["nodes"][f"{nivel}_branches"]["params"]["length_max"]), 1.0)
            self.assertIn([f"{nivel}_length_profile", "out", f"{nivel}_branches", "profile"],
                          document["edges"])
        self.assertIn(["l2_branches", "out", "leaf_frames", "in"], document["edges"])
        # Un barrido con perfil propio por nivel, los tres al mismo Merge variádico. El tronco
        # entra por la corteza: va sobre él y no sobre el merge porque las ramitas de 1.2cm de
        # radio no tolerarían un relieve de ±1.2cm sin invertirse.
        self.assertEqual(
            sorted(edge[0] for edge in document["edges"] if edge[2] == "merge"),
            ["branch_pipe", "trunk_bark", "twig_pipe"],
        )
        self.assertIn(["trunk_pipe", "out", "trunk_bark", "in"], document["edges"])
        self.assertEqual(document["nodes"]["trunk_bark"]["verb"], "mesh_bark")
        # El relieve tiene que ser MENOR que el radio más fino del tronco: si no, la punta cruza
        # el eje y la geometría se invierte.
        self.assertLess(float(document["nodes"]["trunk_bark"]["params"]["amplitud"]),
                        float(document["nodes"]["trunk_pipe"]["params"]["radius"])
                        * float(document["nodes"]["trunk_profile"]["params"]["end_value"]))
        for pipe, curva in (("trunk_pipe", "trunk"), ("branch_pipe", "l1_branches"),
                            ("twig_pipe", "l2_branches")):
            self.assertIn([curva, "out", pipe, "in"], document["edges"])
        # El follaje se HORNEA en la malla como segunda sección, igual que TreeGen: su Pine tiene
        # slot 0 M_Pine y slot 1 M_PineFrond en la misma StaticMesh.
        self.assertEqual(document["nodes"]["foliage"]["verb"], "copy_asset_selection")
        self.assertEqual(document["nodes"]["leaf_material"]["verb"], "mesh_material")
        self.assertEqual(
            sorted(edge[0] for edge in document["edges"] if edge[2] == "tree_merge"),
            ["leaf_material", "wood_material"],
        )
        self.assertNotEqual(
            document["nodes"]["wood_material"]["params"]["material"],
            document["nodes"]["leaf_material"]["params"]["material"],
        )

        runtime_keys = (
            "trunk", "l1_frames", "l1_distribute", "l1_transform", "l1_branches",
            "l2_frames", "l2_distribute", "l2_transform", "l2_branches", "leaf_frames",
        )
        runtime_document = {
            "nodes": {key: document["nodes"][key] for key in runtime_keys},
            "edges": [edge for edge in document["edges"]
                      if edge[0] in runtime_keys and edge[2] in runtime_keys and edge[3] == "in"],
        }
        try:
            report, states = graph.ejecutar_detalle(
                graph.JamGraph.from_json(json.dumps(runtime_document))
            )
            for key in runtime_keys:
                self.assertEqual(states[key]["estado"], "ok", report)
            # 28 ramas madre; cada una recibe frames propios y produce 4 ramitas.
            self.assertIn("BRANCH FROM F ✓ — 28 ramas", report)
            self.assertIn("FRAMES F ✓ — 168 frames/28 curvas", report)
            self.assertIn("BRANCH FROM F ✓ — 112 ramas", report)
            self.assertIn("FRAMES F ✓ — 448 frames/112 curvas", report)

            # La escala cae en cascada: tronco → rama → ramita. El helper de runtime guarda el
            # ÚLTIMO resultado por verbo, así que acá vuelven las 60 ramitas del nivel 2.
            ramitas = tools.dato_producido_runtime("branch_from_frames")
            self.assertEqual(len(ramitas.paths), 112)
            escalas = [path.scale for path in ramitas.paths]
            promedio = sum(escalas) / len(escalas)
            nominal_l2 = float(document["nodes"]["l2_transform"]["params"]["scale"])
            nominal_l1 = float(document["nodes"]["l1_transform"]["params"]["scale"])
            # Sin herencia el promedio daría el nominal del nivel 2 (0.62); con herencia da el
            # producto de los dos niveles. Eso es lo que separa una jerarquía real de dos cadenas
            # independientes pegadas una al lado de la otra.
            self.assertAlmostEqual(promedio, nominal_l1 * nominal_l2, delta=0.05)
            self.assertLess(promedio, nominal_l2)
            self.assertGreater(min(escalas), 0.0)
        finally:
            for verb in ("curve_bezier", "curve_frames", "distribute_frames",
                         "transform_frames", "branch_from_frames"):
                tools.limpiar_asset_producido_runtime(verb)

    def test_asset_path_is_stable_sanitized_and_prefixed(self):
        self.assertEqual(mesh.asset_path_for("Column 01"), "/Game/Jam/Meshes/SM_Column_01")
        self.assertEqual(
            mesh.asset_path_for("SM_Column", "/Game/Generated"),
            "/Game/Generated/SM_Column",
        )
        self.assertEqual(
            mesh.asset_path_for("Bad", "/Engine/Unsafe"),
            "/Game/Jam/Meshes/SM_Bad",
        )

    def test_mesh_tab_is_graph_only_and_uses_typed_m_pins(self):
        import json

        dash = json.loads(api.spec())
        graph = json.loads(api.spec_all())
        dash_verbs = {item["verbo"] for item in dash["tools"]}
        graph_tools = {item["verbo"]: item for item in graph["tools"]}

        self.assertNotIn("mesh_cylinder", dash_verbs)
        self.assertIn("Mesh", graph["categorias"])
        self.assertEqual(graph_tools["mesh_cylinder"]["out_name"], "M")
        self.assertTrue(graph_tools["mesh_cylinder"]["source"])
        self.assertEqual(graph_tools["mesh_normals"]["in_name"], "M")
        self.assertEqual(graph_tools["mesh_normals"]["out_name"], "M")
        self.assertEqual(graph_tools["mesh_to_static"]["in_name"], "M")
        self.assertEqual(graph_tools["mesh_to_static"]["out_name"], "A")
        self.assertEqual(graph_tools["mesh_merge"]["aridad"], -1)
        self.assertEqual(graph_tools["curve_bezier"]["out_name"], "S")
        self.assertEqual(graph_tools["curve_child"]["in_name"], "S")
        self.assertEqual(graph_tools["curve_child"]["out_name"], "S")
        self.assertFalse(graph_tools["curve_child"]["source"])
        self.assertEqual(graph_tools["curve_frames"]["in_name"], "S")
        self.assertEqual(graph_tools["curve_frames"]["out_name"], "F")
        self.assertFalse(graph_tools["curve_frames"]["source"])
        frame_params = {item["nombre"]: item for item in graph_tools["curve_frames"]["params"]}
        self.assertEqual(frame_params["count"]["tipo"], "int")
        self.assertEqual(frame_params["radius_start"]["tipo"], "float")
        self.assertEqual(frame_params["seed"]["tipo"], "int")
        self.assertEqual(graph_tools["distribute_frames"]["in_name"], "F")
        self.assertEqual(graph_tools["distribute_frames"]["out_name"], "F")
        self.assertFalse(graph_tools["distribute_frames"]["source"])
        distribute_params = {
            item["nombre"]: item for item in graph_tools["distribute_frames"]["params"]
        }
        self.assertEqual(distribute_params["count"]["tipo"], "int")
        self.assertEqual(distribute_params["rotate_per_index"]["tipo"], "float")
        self.assertEqual(distribute_params["seed"]["tipo"], "int")
        self.assertEqual(graph_tools["transform_frames"]["in_name"], "F")
        self.assertEqual(graph_tools["transform_frames"]["out_name"], "F")
        self.assertFalse(graph_tools["transform_frames"]["source"])
        transform_params = {
            item["nombre"]: item for item in graph_tools["transform_frames"]["params"]
        }
        self.assertEqual(transform_params["offset_x"]["tipo"], "float")
        self.assertEqual(transform_params["scale_jitter"]["tipo"], "float")
        self.assertEqual(transform_params["inherit_scale"]["tipo"], "bool")
        self.assertEqual(transform_params["seed"]["tipo"], "int")
        self.assertEqual(graph_tools["branch_from_frames"]["in_name"], "F")
        self.assertEqual(graph_tools["branch_from_frames"]["out_name"], "S")
        self.assertFalse(graph_tools["branch_from_frames"]["source"])
        branch_params = {
            item["nombre"]: item for item in graph_tools["branch_from_frames"]["params"]
        }
        self.assertEqual(branch_params["length_min"]["tipo"], "float")
        self.assertEqual(branch_params["segments"]["tipo"], "int")
        self.assertEqual(branch_params["inherit_scale"]["tipo"], "bool")
        self.assertEqual(graph_tools["asset_set"]["in_name"], "A")
        self.assertEqual(graph_tools["asset_set"]["out_name"], "A[]")
        self.assertEqual(graph_tools["asset_set"]["aridad"], -1)
        self.assertEqual(graph_tools["choose_asset"]["in_name"], "F")
        self.assertEqual(graph_tools["choose_asset"]["out_name"], "AF")
        choose_params = {
            item["nombre"]: item for item in graph_tools["choose_asset"]["params"]
        }
        self.assertEqual(choose_params["assets"]["data_type"], "A[]")
        self.assertEqual(choose_params["mode"]["opciones"], ["random", "cycle", "parent"])
        self.assertEqual(graph_tools["curve_branches"]["in_name"], "S")
        self.assertEqual(graph_tools["curve_branches"]["out_name"], "S")
        self.assertEqual(graph_tools["mesh_pipe"]["in_name"], "S")
        self.assertEqual(graph_tools["mesh_pipe"]["out_name"], "M")
        self.assertTrue(graph_tools["graph_curve"]["source"])
        self.assertEqual(graph_tools["graph_curve"]["out_name"], "N[]")
        graph_curve_params = {
            item["nombre"]: item for item in graph_tools["graph_curve"]["params"]
        }
        self.assertEqual(
            graph_curve_params["shape"]["opciones"],
            ["linear", "ease_in", "ease_out", "smooth", "custom"],
        )
        self.assertEqual(graph_tools["mesh_pipe_profile"]["in_name"], "S")
        self.assertEqual(graph_tools["mesh_pipe_profile"]["out_name"], "M")
        pipe_profile_params = {
            item["nombre"]: item for item in graph_tools["mesh_pipe_profile"]["params"]
        }
        self.assertEqual(pipe_profile_params["profile"]["data_type"], "N[]")
        self.assertEqual(graph_tools["mesh_sphere"]["out_name"], "M")
        self.assertEqual(graph_tools["mesh_from_asset"]["in_name"], "A")
        self.assertEqual(graph_tools["mesh_from_asset"]["out_name"], "M")
        self.assertEqual(graph_tools["mesh_along_curve"]["in_name"], "S")
        self.assertEqual(graph_tools["mesh_along_curve"]["out_name"], "M")
        self.assertTrue(graph_tools["mesh_along_curve"]["asset_pin"])
        along_params = {item["nombre"]: item for item in graph_tools["mesh_along_curve"]["params"]}
        self.assertEqual(along_params["orientation"]["opciones"],
                         ["outward", "world_up", "random"])
        self.assertEqual(along_params["crossed"]["tipo"], "bool")
        self.assertEqual(graph_tools["copy_mesh_to_frames"]["in_name"], "F")
        self.assertEqual(graph_tools["copy_mesh_to_frames"]["out_name"], "M")
        self.assertTrue(graph_tools["copy_mesh_to_frames"]["asset_pin"])
        copy_params = {
            item["nombre"]: item for item in graph_tools["copy_mesh_to_frames"]["params"]
        }
        self.assertEqual(copy_params["asset_scale"]["tipo"], "float")
        self.assertEqual(copy_params["inherit_scale"]["tipo"], "bool")
        self.assertEqual(graph_tools["copy_asset_selection"]["in_name"], "AF")
        self.assertEqual(graph_tools["copy_asset_selection"]["out_name"], "M")
        self.assertFalse(graph_tools["copy_asset_selection"]["asset_pin"])
        self.assertEqual(graph_tools["mesh_leaf"]["in_name"], "S")
        self.assertEqual(graph_tools["mesh_leaf"]["out_name"], "M")
        self.assertTrue(graph_tools["mesh_leaf"]["asset_pin"])
        leaf_params = {item["nombre"]: item for item in graph_tools["mesh_leaf"]["params"]}
        self.assertEqual(leaf_params["inherit_scale"]["tipo"], "bool")
        self.assertEqual(leaf_params["double_sided"]["tipo"], "bool")
        self.assertEqual(leaf_params["asset_scale"]["tipo"], "float")
        self.assertEqual(graph_tools["mesh_color"]["in_name"], "M")
        self.assertEqual(graph_tools["mesh_color"]["out_name"], "M")
        self.assertEqual(graph_tools["mesh_uv_scale"]["in_name"], "M")
        self.assertEqual(graph_tools["mesh_uv_scale"]["out_name"], "M")
        uv_params = {item["nombre"]: item for item in graph_tools["mesh_uv_scale"]["params"]}
        self.assertEqual(uv_params["u"]["tipo"], "float")
        self.assertEqual(uv_params["channel"]["tipo"], "int")
        self.assertEqual(graph_tools["mesh_material"]["in_name"], "M")
        self.assertEqual(graph_tools["mesh_material"]["out_name"], "M")
        self.assertFalse(graph_tools["mesh_material"]["asset_pin"])
        # HISM es terminal: consume AF y no devuelve M, así que nada puede seguir la cadena de malla.
        self.assertEqual(graph_tools["hism_output"]["in_name"], "AF")
        self.assertEqual(graph_tools["hism_output"]["out_name"], "H")
        self.assertFalse(graph_tools["hism_output"]["source"])
        self.assertFalse(graph_tools["hism_output"]["asset_pin"])
        self.assertNotIn("hism_output", dash_verbs)
        self.assertNotIn("hism_output", tools.SIN_SPAWN)
        # El oráculo consume M, exige una referencia A por cable y DEJA PASAR la malla intacta.
        self.assertEqual(graph_tools["mesh_compare"]["in_name"], "M")
        self.assertEqual(graph_tools["mesh_compare"]["out_name"], "M")
        self.assertTrue(graph_tools["mesh_compare"]["asset_pin"])
        self.assertTrue(tools.REGISTRO["mesh_compare"]["asset_required"])
        self.assertNotIn("mesh_compare", dash_verbs)
        compare_params = {item["nombre"]: item for item in graph_tools["mesh_compare"]["params"]}
        self.assertEqual(compare_params["franjas"]["tipo"], "int")
        self.assertEqual(compare_params["perfil"]["tipo"], "float")
        self.assertEqual(compare_params["silueta"]["tipo"], "float")
        self.assertEqual(compare_params["esbeltez"]["tipo"], "float")
        # Comparar la forma sin exigir el mismo tamaño que el ejemplo de referencia.
        self.assertEqual(compare_params["solo_forma"]["tipo"], "bool")
        self.assertEqual(graph_tools["mesh_bark"]["in_name"], "M")
        self.assertEqual(graph_tools["mesh_bark"]["out_name"], "M")
        self.assertFalse(graph_tools["mesh_bark"]["asset_pin"])
        bark_params = {item["nombre"]: item for item in graph_tools["mesh_bark"]["params"]}
        self.assertEqual(bark_params["amplitud"]["tipo"], "float")
        self.assertEqual(bark_params["octavas"]["tipo"], "int")
        hism_params = {item["nombre"]: item for item in graph_tools["hism_output"]["params"]}
        self.assertEqual(hism_params["name"]["tipo"], "str")
        self.assertEqual(hism_params["inherit_scale"]["tipo"], "bool")

    def test_cylinder_validates_and_calls_geometry_script(self):
        calls = []

        class _Primitives:
            @staticmethod
            def append_cylinder(target, options, transform, **kwargs):
                calls.append((target, options, transform, kwargs))
                return target

        class _Queries:
            @staticmethod
            def get_vertex_count(_target):
                return 34

            @staticmethod
            def get_num_triangle_i_ds(_target):
                return 64

            @staticmethod
            def get_is_closed_mesh(_target):
                return True

            @staticmethod
            def get_num_connected_components(_target):
                return 1

        origin = types.SimpleNamespace(BASE="base")
        with mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True), \
                mock.patch.object(unreal, "GeometryScriptPrimitiveOptions", _Options, create=True), \
                mock.patch.object(unreal, "Transform", lambda **_kwargs: object(), create=True), \
                mock.patch.object(unreal, "GeometryScript_Primitives", _Primitives, create=True), \
                mock.patch.object(unreal, "GeometryScript_MeshQueries", _Queries, create=True), \
                mock.patch.object(unreal, "GeometryScriptPrimitiveOriginMode", origin, create=True):
            result = mesh.cylinder(radius=80, height=250, sides=20, height_steps=3, capped=True)

        self.assertNotIn("error", result)
        self.assertEqual(calls[0][3]["radius"], 80.0)
        self.assertEqual(calls[0][3]["radial_steps"], 20)
        self.assertEqual(result["info"], "64 triángulos · 34 vértices · cerrada")
        self.assertIn("error", mesh.cylinder(radius=0))

    def test_transform_maps_pitch_yaw_and_roll_by_name(self):
        source = _DynamicMesh()
        rotations = []
        transformed = []

        class _MeshEdits:
            @staticmethod
            def append_mesh(target, input_mesh, _transform):
                self.assertIs(input_mesh, source)
                return target

        class _MeshTransforms:
            @staticmethod
            def transform_mesh(target, transform):
                transformed.append((target, transform))

        def make_rotator(**kwargs):
            rotations.append(kwargs)
            return kwargs

        with mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True), \
                mock.patch.object(unreal, "GeometryScript_MeshEdits", _MeshEdits, create=True), \
                mock.patch.object(unreal, "GeometryScript_MeshTransforms", _MeshTransforms, create=True), \
                mock.patch.object(unreal, "Transform", lambda **kwargs: kwargs, create=True), \
                mock.patch.object(unreal, "Vector", lambda x, y, z: (x, y, z), create=True), \
                mock.patch.object(unreal, "Rotator", make_rotator, create=True), \
                mock.patch.object(mesh, "_info", return_value="DynamicMesh"):
            result = mesh.transform(source, pitch=10, yaw=20, roll=30)

        self.assertNotIn("error", result)
        self.assertEqual(rotations, [{"pitch": 10.0, "yaw": 20.0, "roll": 30.0}])
        self.assertEqual(len(transformed), 1)

    def test_vertex_color_clones_mesh_and_converts_hex_srgb_to_linear(self):
        source = _DynamicMesh()
        calls = []

        class _MeshEdits:
            @staticmethod
            def append_mesh(target, input_mesh, _transform):
                self.assertIs(input_mesh, source)
                return target

        class _VertexColors:
            @staticmethod
            def set_mesh_constant_vertex_color(target, color, flags, clear_existing=False):
                calls.append((target, color, flags, clear_existing))
                return target

        with mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True), \
                mock.patch.object(unreal, "GeometryScript_MeshEdits", _MeshEdits, create=True), \
                mock.patch.object(unreal, "GeometryScript_VertexColors", _VertexColors, create=True), \
                mock.patch.object(unreal, "GeometryScriptColorFlags", object, create=True), \
                mock.patch.object(unreal, "Transform", lambda **_kwargs: object(), create=True), \
                mock.patch.object(unreal, "LinearColor", lambda *rgba: tuple(rgba), create=True), \
                mock.patch.object(mesh, "_info", return_value="DynamicMesh"):
            result = mesh.vertex_color(source, color="#70452A")
            invalid = mesh.vertex_color(source, color="brown")

        self.assertNotIn("error", result)
        self.assertTrue(calls[0][3])
        self.assertAlmostEqual(calls[0][1][0], 0.1620, places=3)
        self.assertAlmostEqual(calls[0][1][1], 0.0595, places=3)
        self.assertAlmostEqual(calls[0][1][2], 0.0232, places=3)
        self.assertEqual(calls[0][1][3], 1.0)
        self.assertIn("#70452A", result["info"])
        self.assertIn("formato", invalid["error"])

    def test_uv_scale_clones_the_mesh_and_validates_channel_and_factors(self):
        source = _DynamicMesh()
        calls = []

        class _UVs:
            @staticmethod
            def scale_mesh_u_vs(target, channel, scale, origin, selection):
                calls.append((target, channel, scale, origin, selection))
                return target

        with self._mesh_edits(source), \
                mock.patch.object(unreal, "GeometryScript_UVs", _UVs, create=True), \
                mock.patch.object(unreal, "GeometryScriptMeshSelection", object, create=True), \
                mock.patch.object(unreal, "Vector2D", lambda x, y: (x, y), create=True), \
                mock.patch.object(mesh, "_info", return_value="Triangles count 64"):
            result = mesh.uv_scale(source, u=2.0, v=6.0, channel=1, origin_u=0.5, origin_v=0.25)
            zero = mesh.uv_scale(source, u=0.0, v=1.0)
            out_of_range = mesh.uv_scale(source, channel=8)
            not_finite = mesh.uv_scale(source, u=float("inf"))
            not_a_mesh = mesh.uv_scale(object())

        self.assertNotIn("error", result)
        self.assertIsNot(result["mesh"], source)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], 1)
        self.assertEqual(calls[0][2], (2.0, 6.0))
        self.assertEqual(calls[0][3], (0.5, 0.25))
        self.assertIn("UV1 × (2, 6)", result["info"])
        self.assertIn("no pueden ser cero", zero["error"])
        self.assertIn("entre 0 y 7", out_of_range["error"])
        self.assertIn("no finito", not_finite["error"])
        self.assertIn("malla procedural M", not_a_mesh["error"])

    def test_material_assigns_a_slot_and_merge_keeps_one_section_per_input(self):
        bark_source = _DynamicMesh()
        leaf_source = _DynamicMesh()
        bark_material = types.SimpleNamespace(get_name=lambda: "M_Bark")
        leaf_material = types.SimpleNamespace(get_name=lambda: "M_Leaf")
        cleared = []
        remapped = []

        class _Materials:
            @staticmethod
            def clear_material_i_ds(target, clear_value=0):
                cleared.append((target, clear_value))

            @staticmethod
            def remap_material_i_ds(target, from_id, to_id):
                remapped.append((target, from_id, to_id))

        loaded = {"/Game/M_Bark": bark_material, "/Game/M_Leaf": leaf_material}
        with self._mesh_edits(), \
                mock.patch.object(unreal, "GeometryScript_Materials", _Materials, create=True), \
                mock.patch.object(unreal, "load_asset", loaded.get, create=True), \
                mock.patch.object(mesh, "_info", return_value="Triangles count 64"):
            bark = mesh.assign_material(bark_source, material="/Game/M_Bark")
            leaf = mesh.assign_material(leaf_source, material="/Game/M_Leaf")
            empty = mesh.assign_material(bark_source, material="   ")
            missing = mesh.assign_material(bark_source, material="/Game/Nope")
            merged = mesh.merge([bark["mesh"], leaf["mesh"]])
            # ``_materials()`` necesita reconocer la malla, así que se consulta con el stub vivo.
            merged_materials = mesh._materials(merged.get("mesh"))

        try:
            self.assertNotIn("error", bark)
            self.assertIn("material slot 0: M_Bark", bark["info"])
            self.assertEqual([entry[1] for entry in cleared], [0, 0])
            self.assertIn("ObjectPath", empty["error"])
            self.assertIn("no pude cargar", missing["error"])

            # Cada entrada llega con su ID local 0; el merge desplaza la segunda para que las dos
            # sections sobrevivan juntas hasta ``to_static``.
            self.assertNotIn("error", merged)
            self.assertEqual([(entry[1], entry[2]) for entry in remapped], [(0, 1)])
            self.assertEqual(merged_materials, (bark_material, leaf_material))
        finally:
            for produced in (bark, leaf, merged):
                mesh._MESH_MATERIALS.pop(id(produced.get("mesh")), None)

    def test_to_static_prefers_the_explicit_material_over_vertex_colors(self):
        source = _DynamicMesh()
        assets = _AssetLibrary()
        temp = "/Game/JamPreview/graph/PV_test_SM_Tree"
        assigned_materials = []
        bark = object()
        leaf = object()

        class _CreatedMesh:
            def set_material(self, index, material):
                assigned_materials.append((index, material))

        class _NewAssetUtils:
            @staticmethod
            def create_new_static_mesh_asset_from_mesh(input_mesh, path, options):
                assets.assets.add(path)
                return _CreatedMesh(), "success"

        mesh._MESH_MATERIALS[id(source)] = (bark, leaf)
        try:
            with mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True), \
                    mock.patch.object(unreal, "GeometryScriptCreateNewStaticMeshAssetOptions",
                                      _Options, create=True), \
                    mock.patch.object(unreal, "GeometryScript_NewAssetUtils", _NewAssetUtils,
                                      create=True), \
                    mock.patch.object(unreal, "EditorAssetLibrary", assets, create=True), \
                    mock.patch.object(unreal, "load_asset", return_value=object(), create=True), \
                    mock.patch.object(panel, "preview_asset_path", return_value=temp), \
                    mock.patch.object(panel, "register_preview_asset"), \
                    mock.patch.object(mesh, "_has_vertex_colors", return_value=True), \
                    mock.patch.object(mesh, "_info", return_value="Triangles count 64"):
                result = mesh.to_static(source, name="Tree", show_vertex_colors=True)
        finally:
            mesh._MESH_MATERIALS.pop(id(source), None)

        self.assertEqual(result["ruta"], temp)
        # Las dos sections viajan a la StaticMesh y el lector de Vertex Color no pisa el slot 0.
        self.assertEqual(assigned_materials, [(0, bark), (1, leaf)])

    def _mesh_edits(self, expected_source=None):
        """Patchea el clon de ``mesh``: cada ``_clone()`` devuelve una malla nueva y verificable."""
        class _MeshEdits:
            @staticmethod
            def append_mesh(target, input_mesh, _transform):
                if expected_source is not None:
                    assert input_mesh is expected_source
                return target

        return _Patches(
            mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True),
            mock.patch.object(unreal, "GeometryScript_MeshEdits", _MeshEdits, create=True),
            mock.patch.object(unreal, "Transform", lambda **_kwargs: object(), create=True),
            mock.patch.object(mesh, "_new_mesh", side_effect=_DynamicMesh),
        )

    def test_pipe_sweeps_a_circle_and_tapers_to_end_radius(self):
        path = curve.CurvePath(((0.0, 0.0, 0.0), (25.0, 10.0, 100.0)))
        calls = []

        class _Primitives:
            @staticmethod
            def append_simple_swept_polygon(target, options, transform, profile, sweep_path, **kwargs):
                calls.append((target, profile, sweep_path, kwargs))
                return target

        with mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True), \
                mock.patch.object(unreal, "GeometryScriptPrimitiveOptions", _Options, create=True), \
                mock.patch.object(unreal, "Transform", lambda **_kwargs: object(), create=True), \
                mock.patch.object(unreal, "Vector2D", lambda x, y: (x, y), create=True), \
                mock.patch.object(unreal, "Vector", lambda *xyz: tuple(xyz), create=True), \
                mock.patch.object(unreal, "GeometryScript_Primitives", _Primitives, create=True), \
                mock.patch.object(mesh, "_info", return_value="DynamicMesh"):
            result = mesh.pipe(path, radius_start=40, radius_end=4, sides=8)

        self.assertNotIn("error", result)
        self.assertEqual(len(calls[0][1]), 8)
        self.assertEqual(calls[0][2][-1], (25.0, 10.0, 100.0))
        self.assertEqual(calls[0][3]["start_scale"], 1.0)
        self.assertAlmostEqual(calls[0][3]["end_scale"], 0.1)

    def test_graph_curve_builds_exact_reusable_falloffs(self):
        linear = fields.graph_curve(
            start_value=1.0, end_value=0.2, shape="linear", samples=5)
        custom = fields.graph_curve(
            start_value=1.0, end_value=0.1, shape="custom",
            midpoint=0.5, mid_value=0.8, samples=5)

        self.assertNotIn("error", linear)
        expected = (1.0, 0.8, 0.6, 0.4, 0.2)
        for actual, wanted in zip(linear["series"].values, expected):
            self.assertAlmostEqual(actual, wanted)
        self.assertAlmostEqual(linear["series"].at(0.375), 0.7)
        self.assertEqual(custom["series"].values[0], 1.0)
        self.assertEqual(custom["series"].values[2], 0.8)
        self.assertAlmostEqual(custom["series"].values[-1], 0.1)
        self.assertIn("error", fields.graph_curve(shape="unknown"))
        self.assertIn("error", fields.graph_curve(samples=1))

    def test_pipe_profile_uses_one_radius_scale_per_path_point(self):
        path = curve.CurvePath((
            (0.0, 0.0, 0.0), (0.0, 0.0, 50.0), (0.0, 0.0, 100.0)))
        profile = fields.ScalarSeries((1.0, 0.5, 0.25), "custom")
        calls = []

        class _Math:
            @staticmethod
            def make_rot_from_xz(x, z):
                return (x, z)

        class _Primitives:
            @staticmethod
            def append_sweep_polygon(target, options, transform, polygon, sweep_path, **kwargs):
                calls.append((target, polygon, sweep_path, kwargs))
                return target

        with mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True), \
                mock.patch.object(unreal, "GeometryScriptPrimitiveOptions", _Options, create=True), \
                mock.patch.object(unreal, "Transform", lambda **kw: kw, create=True), \
                mock.patch.object(unreal, "Vector2D", lambda x, y: (x, y), create=True), \
                mock.patch.object(unreal, "Vector", lambda *xyz: tuple(xyz), create=True), \
                mock.patch.object(unreal, "MathLibrary", _Math, create=True), \
                mock.patch.object(unreal, "GeometryScript_Primitives", _Primitives, create=True), \
                mock.patch.object(mesh, "_info", return_value="DynamicMesh"):
            result = mesh.pipe_profile(path, profile, radius=40, sides=8)

        self.assertNotIn("error", result)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0][1]), 8)
        scales = [transform["scale"] for transform in calls[0][2]]
        self.assertEqual(scales, [(1.0, 40.0, 40.0), (1.0, 20.0, 20.0),
                                  (1.0, 10.0, 10.0)])
        self.assertEqual(calls[0][3]["start_scale"], 1.0)
        self.assertEqual(calls[0][3]["end_scale"], 1.0)
        self.assertIn("perfil custom", result["info"])
        self.assertIn("error", mesh.pipe_profile(path, None))

    def test_pipe_profile_graph_injects_a_typed_number_series(self):
        diagram = graph.JamGraph()
        diagram.add("curve_bezier", {}, nid="curve")
        diagram.add("graph_curve", {"shape": "ease_in", "samples": 7}, nid="profile")
        diagram.add("mesh_pipe_profile", {"radius": 42.0}, nid="pipe")
        diagram.connect("curve", "pipe")
        diagram.connect("profile", "pipe", "profile")

        plan = graph.compilar(diagram)
        received = []
        original = tools.REGISTRO["mesh_pipe_profile"]["fn"]

        def capture(curve_input, *, profile=None, **_kwargs):
            received.append((curve_input, profile))
            return "PIPE PROFILE M ✓"

        tools.REGISTRO["mesh_pipe_profile"]["fn"] = capture
        try:
            report, states = graph.ejecutar_detalle(diagram, plan)
            self.assertEqual(states["profile"]["estado"], "ok", report)
            self.assertEqual(states["pipe"]["estado"], "ok", report)
            self.assertIsInstance(received[0][0], curve.CurvePath)
            self.assertIsInstance(received[0][1], fields.ScalarSeries)
            self.assertEqual(len(received[0][1].values), 7)
        finally:
            tools.REGISTRO["mesh_pipe_profile"]["fn"] = original
            for verb in ("curve_bezier", "graph_curve", "mesh_pipe_profile"):
                tools.limpiar_asset_producido_runtime(verb)

        disconnected = graph.JamGraph.from_json(diagram.to_json())
        disconnected.edges.remove(("profile", "out", "pipe", "profile"))
        with self.assertRaises(graph.GraphValidationError) as caught:
            graph.compilar(disconnected)
        self.assertIn("requiere conexión N[]", " ".join(caught.exception.diagnostics["pipe"]))

        wrong_type = graph.JamGraph.from_json(diagram.to_json())
        wrong_type.edges.remove(("profile", "out", "pipe", "profile"))
        wrong_type.add("number", {"value": 0.5}, nid="number")
        wrong_type.connect("number", "pipe", "profile")
        with self.assertRaises(graph.GraphValidationError) as caught_type:
            graph.compilar(wrong_type)
        self.assertIn("esperaba N[], recibió N", " ".join(
            caught_type.exception.diagnostics["pipe"]))

    def test_from_asset_copies_static_mesh_geometry(self):
        class _StaticMesh:
            def get_name(self):
                return "Leaf"

        source = _StaticMesh()
        calls = []

        class _Struct:
            def __init__(self):
                self.values = {}

            def set_editor_property(self, name, value):
                self.values[name] = value

        class _LODType:
            MAX_AVAILABLE = "MAX_AVAILABLE"

        class _AssetUtils:
            @staticmethod
            def copy_mesh_from_static_mesh_v2(asset, target, options, lod,
                                              use_section_materials=True):
                calls.append((asset, target, options, lod))
                return target, "SUCCESS"

            @staticmethod
            def get_section_material_list_from_static_mesh(asset, lod):
                return ["Mat"], [0], ["Slot"], "SUCCESS"

        with mock.patch.object(unreal, "StaticMesh", _StaticMesh, create=True), \
                mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True), \
                mock.patch.object(unreal, "GeometryScript_AssetUtils", _AssetUtils, create=True), \
                mock.patch.object(unreal, "GeometryScriptCopyMeshFromAssetOptions", _Struct,
                                  create=True), \
                mock.patch.object(unreal, "GeometryScriptMeshReadLOD", _Struct, create=True), \
                mock.patch.object(unreal, "GeometryScriptLODType", _LODType, create=True), \
                mock.patch.object(mesh, "_info", return_value="Triangles count 2"):
            try:
                result = mesh.from_asset(source)
                materials = mesh._materials(result["mesh"])
            finally:
                if "result" in locals() and result.get("mesh") is not None:
                    mesh._MESH_MATERIALS.pop(id(result["mesh"]), None)

        self.assertNotIn("error", result)
        self.assertIs(calls[0][0], source)
        self.assertIs(result["mesh"], calls[0][1])
        self.assertIn("Leaf", result["info"])
        self.assertEqual(materials, ("Mat",))

    def test_along_curve_appends_one_oriented_copy_per_frame(self):
        path = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        template = _DynamicMesh()
        result_mesh = _DynamicMesh()
        transforms = []
        rotations = []

        class _Asset:
            def get_name(self):
                return "Leaf"

        class _MeshEdits:
            @staticmethod
            def append_mesh(target, source, transform):
                self.assertIs(target, result_mesh)
                self.assertIs(source, template)
                transforms.append(transform)
                return target

        class _Math:
            @staticmethod
            def make_rot_from_xz(x, z):
                rotations.append((x, z))
                return (x, z)

        meshes = iter((result_mesh,))
        with mock.patch.object(unreal, "DynamicMesh", side_effect=lambda: next(meshes), create=True), \
                mock.patch.object(unreal, "GeometryScript_MeshEdits", _MeshEdits, create=True), \
                mock.patch.object(unreal, "MathLibrary", _Math, create=True), \
                mock.patch.object(unreal, "Vector", lambda *xyz: tuple(xyz), create=True), \
                mock.patch.object(unreal, "Transform", lambda **kwargs: kwargs, create=True), \
                mock.patch.object(mesh, "_copy_static_mesh", return_value=(template, _Asset())), \
                mock.patch.object(mesh, "_info", return_value="Triangles count 6"):
            result = mesh.along_curve(
                path, "/Game/Leaf", count=3, start=0.0, end=1.0,
                radial_offset=10.0, turns=0.5, scale_start=1.0, scale_end=0.5)

        self.assertNotIn("error", result)
        self.assertEqual(len(transforms), 3)
        self.assertEqual(rotations[0][0], (0.0, 0.0, 1.0))
        self.assertEqual(transforms[0]["scale"], (1.0, 1.0, 1.0))
        self.assertEqual(transforms[-1]["scale"], (0.5, 0.5, 0.5))

    def test_copy_mesh_to_frames_uses_frame_transform_scale_and_asset_correction(self):
        frames = curve.FrameSet((
            curve.CurveFrame(
                (10.0, 20.0, 30.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0), 0.2,
                scale=0.5, seed=3,
            ),
            curve.CurveFrame(
                (40.0, 50.0, 60.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.8,
                scale=1.0, seed=5,
            ),
        ), parent_count=1)
        template = _DynamicMesh()
        result_mesh = _DynamicMesh()
        asset = types.SimpleNamespace(get_name=lambda: "PineFrond")
        corrections = []
        copies = []
        rotations = []

        class _MeshTransforms:
            @staticmethod
            def transform_mesh(target, transform):
                self.assertIs(target, template)
                corrections.append(transform)

        class _MeshEdits:
            @staticmethod
            def append_mesh(target, source, transform):
                self.assertIs(target, result_mesh)
                self.assertIs(source, template)
                copies.append(transform)

        class _Math:
            @staticmethod
            def make_rot_from_xz(x, z):
                rotations.append((x, z))
                return x, z

        with mock.patch.object(mesh, "_copy_static_mesh", return_value=(template, asset)), \
                mock.patch.object(mesh, "_new_mesh", return_value=result_mesh), \
                mock.patch.object(unreal, "GeometryScript_MeshTransforms", _MeshTransforms,
                                  create=True), \
                mock.patch.object(unreal, "GeometryScript_MeshEdits", _MeshEdits, create=True), \
                mock.patch.object(unreal, "MathLibrary", _Math, create=True), \
                mock.patch.object(unreal, "Vector", lambda *xyz: tuple(xyz), create=True), \
                mock.patch.object(unreal, "Rotator", lambda **kwargs: kwargs, create=True), \
                mock.patch.object(unreal, "Transform", lambda **kwargs: kwargs, create=True), \
                mock.patch.object(mesh, "_info", return_value="Triangles count 24"):
            result = mesh.copy_to_frames(
                frames, "/Game/Foliage/PineFrond", asset_offset_x=4.0,
                asset_pitch=-90.0, asset_scale=2.0,
                scale_x=2.0, scale_y=0.5, scale_z=1.0,
                inherit_scale=True,
            )

        self.assertNotIn("error", result)
        self.assertEqual(len(corrections), 1)
        self.assertEqual(corrections[0]["location"], (4.0, 0.0, 0.0))
        self.assertEqual(corrections[0]["rotation"]["pitch"], -90.0)
        self.assertEqual(len(copies), 2)
        self.assertEqual(copies[0]["location"], (10.0, 20.0, 30.0))
        self.assertEqual(copies[0]["scale"], (2.0, 0.5, 1.0))
        self.assertEqual(copies[1]["scale"], (4.0, 1.0, 2.0))
        self.assertEqual(rotations[0], ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)))
        self.assertIn("2 copias × 1 asset(s) [PineFrond]", result["info"])

    def test_copy_mesh_to_frames_validates_input_and_publishes_runtime_mesh(self):
        valid = curve.FrameSet((curve.CurveFrame(
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.0,
            scale=1.0,
        ),), parent_count=1)
        invalid_scale = curve.FrameSet((curve.CurveFrame(
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 0.0,
            scale=0.0,
        ),), parent_count=1)
        self.assertIn("error", mesh.copy_to_frames(None, "/Game/Leaf"))
        self.assertIn("error", mesh.copy_to_frames(valid, "/Game/Leaf", asset_scale=0.0))
        self.assertIn("error", mesh.copy_to_frames(invalid_scale, "/Game/Leaf"))

        output = _DynamicMesh()
        asset = types.SimpleNamespace(get_name=lambda: "Leaf")
        with mock.patch.object(mesh, "_copy_static_mesh", return_value=(_DynamicMesh(), asset)), \
                mock.patch.object(mesh, "_new_mesh", return_value=output), \
                mock.patch.object(unreal, "GeometryScript_MeshEdits",
                                  types.SimpleNamespace(append_mesh=lambda *_args: None), create=True), \
                mock.patch.object(unreal, "MathLibrary",
                                  types.SimpleNamespace(make_rot_from_xz=lambda x, z: (x, z)),
                                  create=True), \
                mock.patch.object(unreal, "Vector", lambda *xyz: tuple(xyz), create=True), \
                mock.patch.object(unreal, "Transform", lambda **kwargs: kwargs, create=True), \
                mock.patch.object(mesh, "_info", return_value="Triangles count 8"):
            try:
                message = tools.t_copy_mesh_to_frames(valid, asset="/Game/Leaf")
                self.assertIn("COPY TO FRAMES M ✓", message)
                self.assertIs(tools.dato_producido_runtime("copy_mesh_to_frames"), output)
            finally:
                tools.limpiar_asset_producido_runtime("copy_mesh_to_frames")

    def test_asset_set_and_choose_asset_preserve_weight_and_are_deterministic(self):
        result = variants.make_asset_set(("/Game/LeafA", "/Game/LeafB", "/Game/LeafB"))
        self.assertNotIn("error", result)
        asset_set = result["asset_set"]
        self.assertEqual(asset_set.assets, ("/Game/LeafA", "/Game/LeafB", "/Game/LeafB"))
        self.assertIn("3 assets · 2 únicos", result["info"])
        self.assertIn("error", variants.make_asset_set("/Game/LeafA"))
        self.assertIn("error", variants.make_asset_set(("/Game/LeafA",)))

        path = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        frames = curve.frame_stream(path, count=6, seed=19)["frame_set"]
        cycle = variants.choose_assets(frames, asset_set, mode="cycle", seed=7)
        first = variants.choose_assets(frames, asset_set, mode="random", seed=1977)
        second = variants.choose_assets(frames, asset_set, mode="random", seed=1977)

        self.assertEqual(
            cycle["selection"].assets,
            ("/Game/LeafA", "/Game/LeafB", "/Game/LeafB") * 2,
        )
        self.assertEqual(first["selection"], second["selection"])
        self.assertEqual(first["selection"].frames, frames)
        self.assertIn("error", variants.choose_assets(None, asset_set))
        self.assertIn("error", variants.choose_assets(frames, None))
        self.assertIn("error", variants.choose_assets(frames, asset_set, mode="unknown"))

    def test_choose_asset_graph_injects_a_typed_asset_set_parameter(self):
        diagram = graph.JamGraph()
        diagram.add("asset", {"name": "LeafA"}, nid="a")
        diagram.add("asset", {"name": "LeafB"}, nid="b")
        diagram.add("asset_set", {}, nid="set")
        diagram.add("curve_bezier", {}, nid="curve")
        diagram.add("curve_frames", {"count": 4}, nid="frames")
        diagram.add("choose_asset", {"mode": "cycle", "seed": 5}, nid="choose")
        diagram.connect("a", "set")
        diagram.connect("b", "set")
        diagram.connect("curve", "frames")
        diagram.connect("frames", "choose")
        diagram.connect("set", "choose", "assets")

        plan = graph.compilar(
            diagram, resolver_asset=lambda name: f"/Game/{name}.{name}",
        )
        original_asset_fn = tools.REGISTRO["asset"]["fn"]
        tools.REGISTRO["asset"]["fn"] = lambda _input=None, **_kwargs: "ASSET ✓"
        try:
            report, states = graph.ejecutar_detalle(diagram, plan)
            self.assertEqual(states["set"]["estado"], "ok", report)
            self.assertEqual(states["choose"]["estado"], "ok", report)
            self.assertIn("ASSET SET A[] ✓ — 2 assets", report)
            self.assertIn("CHOOSE ASSET AF ✓ — 4 frames", report)
        finally:
            tools.REGISTRO["asset"]["fn"] = original_asset_fn
            for verb in ("asset_set", "curve_bezier", "curve_frames", "choose_asset"):
                tools.limpiar_asset_producido_runtime(verb)

        disconnected = graph.JamGraph.from_json(diagram.to_json())
        disconnected.edges.remove(("set", "out", "choose", "assets"))
        with self.assertRaises(graph.GraphValidationError) as caught:
            graph.compilar(disconnected, resolver_asset=lambda name: f"/Game/{name}.{name}")
        self.assertIn("requiere conexión A[]", " ".join(caught.exception.diagnostics["choose"]))

        one_asset = graph.JamGraph.from_json(diagram.to_json())
        one_asset.edges.remove(("b", "out", "set", "in"))
        one_asset.nodes.pop("b")
        with self.assertRaises(graph.GraphValidationError) as caught_set:
            graph.compilar(one_asset, resolver_asset=lambda name: f"/Game/{name}.{name}")
        self.assertIn("al menos 2 conexión(es) A", " ".join(caught_set.exception.diagnostics["set"]))

        wrong_type = graph.JamGraph.from_json(diagram.to_json())
        wrong_type.edges.remove(("set", "out", "choose", "assets"))
        wrong_type.connect("a", "choose", "assets")
        with self.assertRaises(graph.GraphValidationError) as caught_type:
            graph.compilar(wrong_type, resolver_asset=lambda name: f"/Game/{name}.{name}")
        self.assertIn("esperaba A[], recibió A", " ".join(caught_type.exception.diagnostics["choose"]))

    def test_copy_asset_selection_loads_each_variant_once(self):
        frames = curve.FrameSet(tuple(
            curve.CurveFrame(
                (float(index), 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0),
                index / 3, local_index=index, scale=1.0,
            )
            for index in range(4)
        ), parent_count=1)
        selection = variants.FrameAssetSelection(
            frames, ("/Game/LeafA", "/Game/LeafB", "/Game/LeafA", "/Game/LeafB"),
        )
        result_mesh = _DynamicMesh()
        loaded = []
        copies = []

        def copy_asset(path):
            loaded.append(path)
            return _DynamicMesh(), types.SimpleNamespace(get_name=lambda: path.rsplit("/", 1)[-1])

        with mock.patch.object(mesh, "_copy_static_mesh", side_effect=copy_asset), \
                mock.patch.object(mesh, "_new_mesh", return_value=result_mesh), \
                mock.patch.object(unreal, "GeometryScript_MeshEdits",
                                  types.SimpleNamespace(
                                      append_mesh=lambda target, source, transform:
                                      copies.append((target, source, transform))), create=True), \
                mock.patch.object(unreal, "MathLibrary",
                                  types.SimpleNamespace(make_rot_from_xz=lambda x, z: (x, z)),
                                  create=True), \
                mock.patch.object(unreal, "Vector", lambda *xyz: tuple(xyz), create=True), \
                mock.patch.object(unreal, "Transform", lambda **kwargs: kwargs, create=True), \
                mock.patch.object(mesh, "_info", return_value="Triangles count 16"):
            try:
                message = tools.t_copy_asset_selection(selection)
                self.assertIn("COPY VARIANTS M ✓", message)
                self.assertIs(tools.dato_producido_runtime("copy_asset_selection"), result_mesh)
            finally:
                tools.limpiar_asset_producido_runtime("copy_asset_selection")

        self.assertEqual(loaded, ["/Game/LeafA", "/Game/LeafB"])
        self.assertEqual(len(copies), 4)

    @staticmethod
    def _selection(paths, scales=None):
        frames = curve.FrameSet(tuple(
            curve.CurveFrame(
                (float(index), 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0),
                index / max(len(paths) - 1, 1), local_index=index,
                scale=1.0 if scales is None else scales[index],
            )
            for index in range(len(paths))
        ), parent_count=1)
        return variants.FrameAssetSelection(frames, tuple(paths))

    def _hism_world(self, loader):
        """Stub del actor, el subsistema y las matemáticas que usa ``instances.from_selection``."""
        class _Actor:
            def __init__(self):
                self.label = ""

            def set_actor_label(self, value):
                self.label = value

        self.hism_actors = []
        self.hism_destroyed = []
        self.hism_components = []

        def spawn(_klass, _location, _rotation):
            actor = _Actor()
            self.hism_actors.append(actor)
            return actor

        subsystem = types.SimpleNamespace(
            spawn_actor_from_class=spawn,
            destroy_actor=self.hism_destroyed.append,
        )

        def add_component(actor, name):
            component = types.SimpleNamespace(
                actor=actor, name=name, mesh=None, instances=[])
            component.set_static_mesh = lambda asset: setattr(component, "mesh", asset)
            component.add_instance = (
                lambda transform, world_space=False: component.instances.append(transform))
            self.hism_components.append(component)
            return component

        return _Patches(
            mock.patch.object(instances, "_actor_sub", return_value=subsystem),
            mock.patch.object(instances, "_add_hism_component", side_effect=add_component),
            mock.patch.object(unreal, "Actor", object, create=True),
            mock.patch.object(unreal, "load_asset", side_effect=loader, create=True),
            # ``_Vec`` es un namedtuple: expone ``.x/.y/.z`` como el Vector real y además compara
            # como tupla, para poder afirmar posiciones y escalas sin envoltorios.
            mock.patch.object(unreal, "Vector", _Vec, create=True),
            mock.patch.object(unreal, "Rotator",
                              lambda pitch=0.0, yaw=0.0, roll=0.0: ("rot", pitch, yaw, roll),
                              create=True),
            mock.patch.object(unreal, "Transform", lambda **kwargs: kwargs, create=True),
            mock.patch.object(unreal, "MathLibrary", types.SimpleNamespace(
                make_rot_from_xz=lambda x, z: ("base", x, z),
                compose_rotators=lambda a, b: ("composed", a, b),
            ), create=True),
        )

    def test_hism_output_groups_one_component_per_variant_and_one_instance_per_frame(self):
        selection = self._selection(
            ("/Game/LeafA", "/Game/LeafB", "/Game/LeafA", "/Game/LeafB"),
            scales=(1.0, 2.0, 1.0, 2.0),
        )
        loaded = []

        def loader(path):
            loaded.append(path)
            return types.SimpleNamespace(get_name=lambda: path.rsplit("/", 1)[-1])

        with self._hism_world(loader):
            result = instances.from_selection(
                selection, name="Foliage", asset_offset_z=5.0, asset_scale=3.0)

        self.assertNotIn("error", result)
        # Una sola carga y un solo componente por variante, aunque la variante se repita por frame.
        self.assertEqual(loaded, ["/Game/LeafA", "/Game/LeafB"])
        self.assertEqual(len(self.hism_components), 2)
        self.assertEqual(self.hism_actors[0].label, "Jam_HISM_Foliage")
        by_name = {component.mesh.get_name(): component for component in self.hism_components}
        self.assertEqual([len(component.instances) for component in by_name.values()], [2, 2])
        self.assertIn("4 instancias · 2 HISM", result["info"])

        first = by_name["LeafA"].instances[0]
        self.assertEqual(first["location"], (0.0, 0.0, 5.0))
        self.assertEqual(first["scale"], (3.0, 3.0, 3.0))
        # ``inherit_scale`` multiplica la escala del frame por la corrección del asset.
        self.assertEqual(by_name["LeafB"].instances[0]["scale"], (6.0, 6.0, 6.0))

        with self._hism_world(loader):
            fixed = instances.from_selection(selection, asset_scale=3.0, inherit_scale=False)
        self.assertNotIn("error", fixed)
        self.assertEqual(
            {component.instances[0]["scale"] for component in self.hism_components},
            {(3.0, 3.0, 3.0)},
        )

    def test_hism_output_validates_input_and_destroys_the_actor_when_a_variant_fails(self):
        selection = self._selection(("/Game/LeafA", "/Game/Missing"))

        def loader(path):
            if path.endswith("Missing"):
                return None
            return types.SimpleNamespace(get_name=lambda: path.rsplit("/", 1)[-1])

        with self._hism_world(loader):
            broken = instances.from_selection(selection)
        self.assertIn("no pude cargar el StaticMesh «/Game/Missing»", broken["error"])
        # El actor a medio poblar no queda en el nivel.
        self.assertEqual(self.hism_destroyed, self.hism_actors)

        with self._hism_world(loader):
            not_a_selection = instances.from_selection(object())
            empty = instances.from_selection(
                variants.FrameAssetSelection(curve.FrameSet((), parent_count=0), ()))
            not_numeric = instances.from_selection(selection, asset_scale="grande")
            not_positive = instances.from_selection(selection, asset_scale=0.0)
            not_finite = instances.from_selection(selection, asset_offset_z=float("nan"))
        for failure in (not_a_selection, empty, not_numeric, not_positive, not_finite):
            self.assertIn("error", failure)
        self.assertIn("selección AF válida", not_a_selection["error"])
        self.assertIn("deben ser numéricos", not_numeric["error"])
        self.assertIn("finitos y positivos", not_positive["error"])
        # Ninguna validación llega a crear un actor.
        self.assertEqual(self.hism_actors, [])

    def test_hism_output_tool_publishes_the_runtime_actor(self):
        selection = self._selection(("/Game/LeafA", "/Game/LeafA"))

        with self._hism_world(lambda path: types.SimpleNamespace(get_name=lambda: "LeafA")):
            try:
                message = tools.t_hism_output(selection, name="Foliage")
                self.assertIn("HISM H ✓", message)
                self.assertIs(
                    tools.dato_producido_runtime("hism_output"), self.hism_actors[0])
            finally:
                tools.limpiar_asset_producido_runtime("hism_output")

            with self.assertRaises(RuntimeError):
                tools.t_hism_output(object())

    def test_along_curve_variation_is_seeded_and_builds_crossed_double_sided_cards(self):
        path = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        template = _DynamicMesh()

        class _Asset:
            def get_name(self):
                return "Leaf"

        class _MeshEdits:
            calls = []

            @classmethod
            def append_mesh(cls, _target, _source, transform):
                cls.calls.append(transform)

        class _Math:
            @staticmethod
            def make_rot_from_xz(x, z):
                return x, z

        def run_once():
            _MeshEdits.calls = []
            with mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True), \
                    mock.patch.object(unreal, "GeometryScript_MeshEdits", _MeshEdits, create=True), \
                    mock.patch.object(unreal, "MathLibrary", _Math, create=True), \
                    mock.patch.object(unreal, "Vector", lambda *xyz: tuple(xyz), create=True), \
                    mock.patch.object(unreal, "Transform", lambda **kwargs: kwargs, create=True), \
                    mock.patch.object(mesh, "_copy_static_mesh", return_value=(template, _Asset())), \
                    mock.patch.object(mesh, "_info", return_value="Triangles count 16"):
                result = mesh.along_curve(
                    path, "/Game/Leaf", count=2, start=0.0, end=1.0,
                    scale_start=1.0, scale_end=0.5, scale_x=2.0, scale_y=0.5,
                    orientation="random", rotation_jitter=15.0, scale_jitter=0.0,
                    offset_jitter=8.0, seed=123, crossed=True, double_sided=True)
            return result, list(_MeshEdits.calls)

        first_result, first = run_once()
        second_result, second = run_once()

        self.assertNotIn("error", first_result)
        self.assertNotIn("error", second_result)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 8)
        self.assertEqual(first[0]["scale"], (2.0, 0.5, 1.0))
        self.assertEqual(first[-1]["scale"], (1.0, 0.25, 0.5))
        self.assertNotEqual(first[0]["location"], (0.0, 0.0, 0.0))
        self.assertIn("8 copias/2 frames", first_result["info"])
        self.assertIn("error", mesh.along_curve(path, "/Game/Leaf", orientation="sideways"))
        self.assertIn("error", mesh.along_curve(path, "/Game/Leaf", scale_jitter=1.0))

    def test_leaf_builds_compound_clusters_for_every_curve_in_the_set(self):
        paths = curve.CurveSet((
            curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)), scale=1.0),
            curve.CurvePath(((20.0, 0.0, 0.0), (20.0, 0.0, 100.0)), scale=0.5),
        ))
        template = _DynamicMesh()
        result_mesh = _DynamicMesh()
        outlines = []
        transforms = []

        class _Primitives:
            @staticmethod
            def append_triangulated_polygon(target, _options, _transform, points, **_kwargs):
                self.assertIs(target, template)
                outlines.append(points)

        class _MeshEdits:
            @staticmethod
            def append_mesh(target, source, transform):
                self.assertIs(target, result_mesh)
                self.assertIs(source, template)
                transforms.append(transform)

        class _Math:
            @staticmethod
            def make_rot_from_xz(x, z):
                return x, z

        meshes = iter((template, result_mesh))
        with mock.patch.object(unreal, "DynamicMesh", side_effect=lambda: next(meshes), create=True), \
                mock.patch.object(unreal, "GeometryScriptPrimitiveOptions", _Options, create=True), \
                mock.patch.object(unreal, "GeometryScript_Primitives", _Primitives, create=True), \
                mock.patch.object(unreal, "GeometryScript_MeshEdits", _MeshEdits, create=True), \
                mock.patch.object(unreal, "MathLibrary", _Math, create=True), \
                mock.patch.object(unreal, "Vector2D", lambda x, y: (x, y), create=True), \
                mock.patch.object(unreal, "Vector", lambda *xyz: tuple(xyz), create=True), \
                mock.patch.object(unreal, "Transform", lambda **kwargs: kwargs, create=True), \
                mock.patch.object(mesh, "_info", return_value="Triangles count 144"):
            result = mesh.leaf(
                paths, count=2, start=0.0, end=1.0, leaves_per_cluster=3,
                length=80, width=40, scale_jitter=0, rotation_jitter=0,
                offset_jitter=0, inherit_scale=True, double_sided=True, seed=17,
            )

        self.assertNotIn("error", result)
        self.assertEqual(len(outlines), 1)
        self.assertEqual(len(outlines[0]), 8)
        self.assertEqual(len(transforms), 24)
        self.assertEqual(transforms[0]["scale"], (80.0, 40.0, 1.0))
        self.assertEqual(transforms[-1]["scale"], (28.0, 14.0, 1.0))
        self.assertIn("24 hojas/4 racimos", result["info"])
        self.assertIn("error", mesh.leaf(paths, leaves_per_cluster=13))

    def test_leaf_uses_an_optional_static_mesh_without_procedural_duplication(self):
        path = curve.CurvePath(((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)))
        template = _DynamicMesh()
        result_mesh = _DynamicMesh()
        asset = types.SimpleNamespace(get_name=lambda: "PineFrond")
        transforms = []
        template_transforms = []

        class _MeshEdits:
            @staticmethod
            def append_mesh(target, source, transform):
                self.assertIs(target, result_mesh)
                self.assertIs(source, template)
                transforms.append(transform)

        class _MeshTransforms:
            @staticmethod
            def transform_mesh(target, transform):
                self.assertIs(target, template)
                template_transforms.append(transform)

        class _Math:
            @staticmethod
            def make_rot_from_xz(x, z):
                return x, z

        meshes = iter((result_mesh,))
        with mock.patch.object(unreal, "DynamicMesh", side_effect=lambda: next(meshes), create=True), \
                mock.patch.object(unreal, "GeometryScript_MeshEdits", _MeshEdits, create=True), \
                mock.patch.object(unreal, "GeometryScript_MeshTransforms", _MeshTransforms,
                                  create=True), \
                mock.patch.object(unreal, "MathLibrary", _Math, create=True), \
                mock.patch.object(unreal, "Vector", lambda *xyz: tuple(xyz), create=True), \
                mock.patch.object(unreal, "Rotator", lambda **kwargs: kwargs, create=True), \
                mock.patch.object(unreal, "Transform", lambda **kwargs: kwargs, create=True), \
                mock.patch.object(mesh, "_copy_static_mesh", return_value=(template, asset)), \
                mock.patch.object(mesh, "_info", return_value="Triangles count 24"):
            result = mesh.leaf(
                path, asset="/Game/Foliage/PineFrond", count=2,
                leaves_per_cluster=1, double_sided=True, scale_jitter=0,
                rotation_jitter=0, offset_jitter=0, asset_scale=0.5,
                asset_pitch=-90, asset_yaw=10, asset_roll=5,
            )

        self.assertNotIn("error", result)
        self.assertEqual(len(template_transforms), 1)
        self.assertEqual(template_transforms[0]["scale"], (0.5, 0.5, 0.5))
        self.assertEqual(
            template_transforms[0]["rotation"],
            {"pitch": -90.0, "yaw": 10.0, "roll": 5.0},
        )
        self.assertEqual(len(transforms), 2)
        self.assertEqual(transforms[0]["scale"], (1.0, 1.0, 1.0))
        self.assertEqual(transforms[-1]["scale"], (0.7, 0.7, 0.7))
        self.assertIn("PineFrond", result["info"])

    def test_to_static_registers_an_asset_only_preview(self):
        source = _DynamicMesh()
        assets = _AssetLibrary()
        temp = "/Game/JamPreview/graph/PV_test_SM_Column"
        assigned_materials = []

        class _CreatedMesh:
            def set_material(self, index, material):
                assigned_materials.append((index, material))

        created_mesh = _CreatedMesh()
        vertex_material = object()

        class _NewAssetUtils:
            @staticmethod
            def create_new_static_mesh_asset_from_mesh(input_mesh, path, options):
                self.assertIs(input_mesh, source)
                self.assertEqual(path, temp)
                self.assertTrue(options.values["enable_collision"])
                assets.assets.add(path)
                return created_mesh, "success"

        with mock.patch.object(unreal, "DynamicMesh", _DynamicMesh, create=True), \
                mock.patch.object(unreal, "GeometryScriptCreateNewStaticMeshAssetOptions", _Options,
                                  create=True), \
                mock.patch.object(unreal, "GeometryScript_NewAssetUtils", _NewAssetUtils, create=True), \
                mock.patch.object(unreal, "EditorAssetLibrary", assets, create=True), \
                mock.patch.object(unreal, "load_asset", return_value=vertex_material, create=True), \
                mock.patch.object(panel, "preview_asset_path", return_value=temp), \
                mock.patch.object(panel, "register_preview_asset") as register, \
                mock.patch.object(mesh, "_has_vertex_colors", return_value=True), \
                mock.patch.object(mesh, "_info", return_value="Triangles count 64"):
            result = mesh.to_static(source, name="Column")

        self.assertEqual(result["ruta"], temp)
        self.assertEqual(result["final"], "/Game/Jam/Meshes/SM_Column")
        self.assertEqual(assigned_materials, [(0, vertex_material)])
        register.assert_called_once_with(temp)


if __name__ == "__main__":
    unittest.main()
