"""El puente P → F y las ops de Flow como verbos del Graph.

Hasta este corte Jam tenía dos vocabularios que no se tocaban: 29 ops de Flow que producen un stream
de puntos `P`, y 50 verbos de herramienta de los que NINGUNO consumía `P`. Un canvas mixto caía
entero al runner de verbos, donde cada op de Flow era un verbo desconocido.
"""

from __future__ import annotations

import json
import sys
import types
import unittest
from unittest import mock

_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam import api, curve, flow, graph, scatter_core, tools  # noqa: E402


def puntos(n=6, *, pesos=None):
    from jam.geometry import Vec3
    return [
        scatter_core.Sample(
            pos=Vec3(float(i) * 100.0, 0.0, 0.0), normal=Vec3(0.0, 0.0, 1.0),
            slope=0.0, seed=1000 + i * 37, uv=(0.0, 0.0),
            weight=1.0 if pesos is None else pesos[i],
        )
        for i in range(n)
    ]


class PuenteTests(unittest.TestCase):
    def test_a_sample_carries_everything_a_frame_needs(self):
        r = curve.frames_desde_puntos(puntos(4), orientacion="vertical", giro_al_azar=False)

        self.assertNotIn("error", r)
        frames = r["frame_set"].frames
        self.assertEqual(len(frames), 4)
        self.assertEqual(frames[0].position, (0.0, 0.0, 0.0))
        self.assertEqual(frames[3].position, (300.0, 0.0, 0.0))
        # La semilla del punto viaja al frame: la variación de cada pieza sigue siendo estable.
        self.assertEqual([f.seed for f in frames], [1000 + i * 37 for i in range(4)])
        self.assertEqual([f.local_index for f in frames], [0, 1, 2, 3])
        self.assertAlmostEqual(frames[0].parameter, 0.0)
        self.assertAlmostEqual(frames[-1].parameter, 1.0)

    def test_the_mask_weight_becomes_the_piece_scale(self):
        """Lo que vuelve útil todo el tab Weight: el gris de la máscara pasa a ser el tamaño."""
        r = curve.frames_desde_puntos(
            puntos(4, pesos=[0.25, 0.5, 0.75, 1.0]), escala_desde_peso=True)
        self.assertEqual([f.scale for f in r["frame_set"].frames], [0.25, 0.5, 0.75, 1.0])
        self.assertIn("desde el peso", r["info"])

        # Y se puede apagar: entonces manda `escala` y el peso sólo sirve para cull.
        fijo = curve.frames_desde_puntos(
            puntos(4, pesos=[0.25, 0.5, 0.75, 1.0]), escala_desde_peso=False, escala=2.0)
        self.assertEqual({f.scale for f in fijo["frame_set"].frames}, {2.0})

    def test_orientation_is_a_parameter_not_an_invention(self):
        arriba = curve.frames_desde_puntos(puntos(3), orientacion="vertical", giro_al_azar=False)
        normal = curve.frames_desde_puntos(puntos(3), orientacion="normal", giro_al_azar=False)
        # Con estos puntos la normal ES vertical, así que las dos coinciden…
        self.assertEqual([f.tangent for f in arriba["frame_set"].frames],
                         [f.tangent for f in normal["frame_set"].frames])

        from jam.geometry import Vec3
        inclinado = [scatter_core.Sample(
            pos=Vec3(0.0, 0.0, 0.0), normal=Vec3(1.0, 0.0, 0.0), slope=90.0,
            seed=5, uv=(0.0, 0.0), weight=1.0)]
        # …pero en una pared se separan: «vertical» crece hacia arriba, «normal» sale de la pared.
        self.assertEqual(
            curve.frames_desde_puntos(inclinado, orientacion="vertical",
                                      giro_al_azar=False)["frame_set"].frames[0].tangent,
            (0.0, 0.0, 1.0))
        self.assertEqual(
            curve.frames_desde_puntos(inclinado, orientacion="normal",
                                      giro_al_azar=False)["frame_set"].frames[0].tangent,
            (1.0, 0.0, 0.0))

    def test_the_frames_are_deterministic_and_seed_dependent(self):
        a = curve.frames_desde_puntos(puntos(5), seed=7)["frame_set"].frames
        b = curve.frames_desde_puntos(puntos(5), seed=7)["frame_set"].frames
        c = curve.frames_desde_puntos(puntos(5), seed=8)["frame_set"].frames
        self.assertEqual([f.outward for f in a], [f.outward for f in b])
        self.assertNotEqual([f.outward for f in a], [f.outward for f in c])

    def test_frames_from_points_have_no_parent_curve(self):
        """Sin curva padre, `relative_to_parent` tiene que rechazarlos con su mensaje."""
        frames = curve.frames_desde_puntos(puntos(4))["frame_set"]
        self.assertTrue(all(f.parent_length == 0.0 for f in frames.frames))
        roto = curve.branch_from_frames(frames, length_min=0.2, length_max=0.3,
                                        relative_to_parent=True)
        self.assertIn("largo de padre", roto["error"])
        # En modo absoluto sí funciona.
        self.assertNotIn("error", curve.branch_from_frames(frames, length_min=50, length_max=80))

    def test_it_validates_its_input(self):
        self.assertIn("al menos un punto", curve.frames_desde_puntos([])["error"])
        self.assertIn("«normal» o «vertical»",
                      curve.frames_desde_puntos(puntos(2), orientacion="diagonal")["error"])
        self.assertIn("mayor que cero", curve.frames_desde_puntos(puntos(2), escala=0.0)["error"])
        self.assertIn("muestras válidas", curve.frames_desde_puntos([object()])["error"])


class OpsDeFlowComoVerbosTests(unittest.TestCase):
    def test_every_pure_flow_op_is_now_a_graph_verb(self):
        puras = {k for k in flow.OPS_META if k in flow.OPS and k not in graph.VALOR_KINDS}
        self.assertEqual(set(tools.OPS_FLOW_EN_GRAPH), puras)
        self.assertGreaterEqual(len(puras), 29)
        for kind in puras:
            with self.subTest(op=kind):
                info = tools.REGISTRO[kind]
                self.assertEqual(info["out_name"], "P")
                self.assertTrue(info["graph_only"])
                self.assertFalse(info["asset_required"])
                # Una fuente no tiene pin de entrada; el resto consume P.
                self.assertEqual(info["in_name"], "" if info["source"] else "P")

    def test_the_two_ops_that_need_unreal_stay_out(self):
        # Sus funciones viven en el adaptador `jam.scatter`, no en el cerebro puro.
        for kind in ("instance", "source_surface"):
            with self.subTest(op=kind):
                self.assertNotIn(kind, tools.OPS_FLOW_EN_GRAPH)

    def test_the_palette_lists_each_verb_once(self):
        spec = json.loads(api.spec_all())
        verbos = [t["verbo"] for t in spec["tools"]]
        self.assertEqual(len(verbos), len(set(verbos)), "hay verbos duplicados en la paleta")
        # Las categorías de Flow tienen que estar, o el canvas no dibuja su pestaña.
        for cat in ("Vector", "Mask", "Weight", "Sets", "Transform", "Combine"):
            self.assertIn(cat, spec["categorias"])

    def test_a_variadic_flow_op_keeps_its_arity(self):
        self.assertEqual(tools.REGISTRO["merge"]["aridad"], -1)
        self.assertEqual(tools.REGISTRO["merge"]["min_inputs"], 2)
        self.assertEqual(tools.REGISTRO["mask_slope"]["aridad"], 1)
        self.assertEqual(tools.REGISTRO["pts_line"]["aridad"], 0)


class CadenaMixtaTests(unittest.TestCase):
    """La cadena que antes de este corte era inexpresable."""

    GRAFO = {
        "nodes": {
            "pts": {"verb": "pts_rect",
                    "params": {"cx": "0", "cy": "0", "size_x": "800", "size_y": "800",
                               "cols": "4", "rows": "4", "seed": "3"}, "x": 0, "y": 0},
            "peso": {"verb": "weight_noise", "params": {}, "x": 300, "y": 0},
            "frames": {"verb": "points_to_frames",
                       "params": {"orientacion": "vertical", "escala": "1.0",
                                  "escala_desde_peso": "true", "giro_al_azar": "true",
                                  "seed": "7"}, "x": 600, "y": 0},
            "ramas": {"verb": "branch_from_frames",
                      "params": {"length_min": "120", "length_max": "200", "angle": "20",
                                 "angle_jitter": "0", "curl": "0", "curl_jitter": "0",
                                 "segments": "6", "inherit_scale": "true",
                                 "relative_to_parent": "false", "profile": "",
                                 "seed": "5"}, "x": 900, "y": 0},
        },
        "edges": [["pts", "out", "peso", "in"], ["peso", "out", "frames", "in"],
                  ["frames", "out", "ramas", "in"]],
    }

    def test_points_to_masks_to_frames_to_branches_compiles_and_runs(self):
        fuente = json.dumps(self.GRAFO)
        with mock.patch.object(graph, "_resolver_asset_runtime", side_effect=lambda p: p):
            compilado = json.loads(api.compile_graph_json(fuente))
        self.assertTrue(compilado["ok"], compilado["report"])

        try:
            reporte, estados = graph.ejecutar_detalle(graph.JamGraph.from_json(fuente))
            for nid in self.GRAFO["nodes"]:
                self.assertEqual(estados[nid]["estado"], "ok", reporte)
            self.assertIn("PTS RECT P ✓ — 16 puntos", reporte)
            self.assertIn("POINTS TO F ✓", reporte)
            self.assertIn("BRANCH FROM F ✓ — 16 ramas", reporte)
            # La máscara de ruido llegó hasta la escala de las piezas.
            self.assertIn("desde el peso", reporte)
        finally:
            for verbo in ("pts_rect", "weight_noise", "points_to_frames", "branch_from_frames"):
                tools.limpiar_asset_producido_runtime(verbo)

    def test_the_type_contract_is_enforced_across_the_bridge(self):
        # Un stream P no puede entrar donde se espera una curva S.
        roto = json.loads(json.dumps(self.GRAFO))
        roto["nodes"]["pipe"] = {"verb": "mesh_pipe", "params": {}, "asset": None, "x": 0, "y": 300}
        roto["edges"].append(["peso", "out", "pipe", "in"])
        with mock.patch.object(graph, "_resolver_asset_runtime", side_effect=lambda p: p):
            r = json.loads(api.compile_graph_json(json.dumps(roto)))
        self.assertFalse(r["ok"])
        self.assertIn("esperaba S, recibió P", r["nodes"]["pipe"]["texto"])

    def test_a_flow_only_graph_still_runs_on_the_flow_evaluator(self):
        # No se rompe el camino histórico: un grafo de puras ops sigue siendo `solo_flow`.
        solo = {"nodes": {k: {"kind": v["verb"], "params": v["params"]}
                          for k, v in self.GRAFO["nodes"].items() if k in ("pts", "peso")},
                "edges": [["pts", "out", "peso", "in"]]}
        self.assertTrue(flow.Flow.from_json(json.dumps(solo)).solo_flow())


if __name__ == "__main__":
    unittest.main()
