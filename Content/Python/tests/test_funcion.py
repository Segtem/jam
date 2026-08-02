"""Funciones del Graph: un subgrafo con firma, expandido inline.

La prueba que manda es la del roadmap: **un grafo que usa una función tiene que compilar al MISMO
plan que el grafo plano equivalente**. Se compara el plan (orden topológico y parámetros resueltos),
no la imagen — los ids cambian a propósito y no son parte del contrato.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

# Igual que en test_graph_preflight: `tools` se importa, Unreal no se ejecuta.
_unreal_fake = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
if not hasattr(_unreal_fake, "TopLevelAssetPath"):
    _unreal_fake.TopLevelAssetPath = lambda package, name: (package, name)

from jam.funcion import FuncionError, colapsar, expandir, firma, herramientas
from jam.graph import JamGraph, compilar


def _tool(*, source=False, asset_required=True, out="A", in_name="A", params=None):
    entrada = "" if source else in_name
    return {"source": source, "aridad": 0 if source else 1,
            "min_inputs": 0 if source else 1, "in_name": entrada, "out_name": out,
            "asset_required": asset_required, "asset_pin": bool(asset_required),
            "asset_row": bool(asset_required) and entrada != "A", "params": params or {}}


REGISTRY = {
    "mesh_cylinder": _tool(source=True, asset_required=False, out="M", params={"radius": 50.0}),
    "mesh_normals": _tool(asset_required=False, in_name="M", out="M"),
    "mesh_transform": _tool(asset_required=False, in_name="M", out="M",
                            params={"escala": 1.0}),
    "mesh_to_static": _tool(asset_required=False, in_name="M", out="A",
                            params={"name": "GeneratedMesh"}),
}


def _compilar(g: JamGraph):
    return compilar(g, registro=REGISTRY, resolver_asset=lambda n: None, resolver_pick=lambda: None)


def _perfil(g: JamGraph):
    """Lo que un plan promete, sin los ids: la secuencia de verbos y sus params resueltos.

    Los ids SÍ cambian al expandir (`n2__k`), y tienen que poder cambiar: si el contrato los
    incluyera, renombrar un nodo adentro del cuerpo rompería a los usuarios de la función.
    """
    plan = _compilar(g)
    return [(g.nodes[nid]["verb"], plan.params.get(nid, {})) for nid in plan.order]


def _cuerpo_escalar() -> JamGraph:
    """malla → mesh_transform → salida. Una función de verdad: recibe M y devuelve M."""
    c = JamGraph()
    c.add("input", {"name": "malla", "type": "M"}, nid="e", y=0.0)
    c.add("mesh_transform", {"escala": 2.0}, nid="k", y=10.0)
    c.add("output", {"name": "salida", "type": "M"}, nid="s", y=20.0)
    c.connect("e", "k")
    c.connect("k", "s")
    return c


class FirmaTests(unittest.TestCase):
    def test_la_firma_sale_en_el_orden_en_que_se_ven_los_pines(self) -> None:
        # Los ids van A PROPÓSITO al revés que la posición: si el orden saliera del id (o del orden
        # de inserción), este test pasaría igual y no estaría comprobando nada.
        c = JamGraph()
        c.add("input", {"name": "abajo", "type": "M"}, nid="a", y=100.0)
        c.add("input", {"name": "arriba", "type": "P"}, nid="b", y=0.0)
        c.add("output", {"name": "sale", "type": "M"}, nid="s")

        f = firma(c)

        self.assertEqual([e["name"] for e in f["entradas"]], ["arriba", "abajo"])
        self.assertEqual([e["tipo"] for e in f["entradas"]], ["P", "M"])
        self.assertEqual([e["name"] for e in f["salidas"]], ["sale"])

    def test_dos_pines_con_el_mismo_nombre_es_un_error(self) -> None:
        c = JamGraph()
        c.add("input", {"name": "malla"}, nid="a")
        c.add("input", {"name": "malla"}, nid="b")

        with self.assertRaises(FuncionError) as e:
            firma(c)

        self.assertIn("ambiguo", str(e.exception))

    def test_un_pin_sin_nombre_es_un_error(self) -> None:
        c = JamGraph()
        c.add("input", {}, nid="a")

        with self.assertRaises(FuncionError):
            firma(c)

    def test_el_spec_de_una_funcion_conserva_todos_los_pines_y_su_orden(self) -> None:
        c = JamGraph()
        c.add("input", {"name": "abajo", "type": "M"}, nid="a", y=100.0)
        c.add("input", {"name": "arriba", "type": "P"}, nid="b", y=0.0)
        c.add("output", {"name": "uno", "type": "M"}, nid="s1", y=0.0)
        c.add("output", {"name": "dos", "type": "A"}, nid="s2", y=100.0)

        tool = herramientas({"doble": c})[-1]

        self.assertEqual(tool["verbo"], "fn:doble")
        self.assertEqual(tool["label"], "doble")
        self.assertEqual(tool["inputs"], [
            {"name": "arriba", "tipo": "P"}, {"name": "abajo", "tipo": "M"}])
        self.assertEqual(tool["outputs"], [
            {"name": "uno", "tipo": "M"}, {"name": "dos", "tipo": "A"}])


class ColapsarTests(unittest.TestCase):
    def _grafo(self) -> JamGraph:
        g = JamGraph()
        g.add("mesh_cylinder", {"radius": 30.0}, nid="cil", x=0, y=20)
        g.add("mesh_transform", {"escala": 2.0}, nid="t1", x=200, y=20)
        g.add("mesh_normals", {}, nid="n1", x=400, y=20)
        g.add("mesh_to_static", {"name": "Muro"}, nid="fin", x=600, y=20)
        g.connect("cil", "t1")
        g.connect("t1", "n1")
        g.connect("n1", "fin")
        return g

    def test_colapsar_recablea_ambos_bordes_y_expandir_recupera_el_plan(self) -> None:
        original = self._grafo()

        padre, cuerpo = colapsar(original, {"t1", "n1"}, "preparar", registro=REGISTRY,
                                 biblio={})

        self.assertEqual(firma(cuerpo), {
            "entradas": [{"name": "in", "tipo": "M"}],
            "salidas": [{"name": "salida", "tipo": "M"}],
        })
        self.assertIn(("cil", "out", "f1", "in"), padre.edges)
        self.assertIn(("f1", "salida", "fin", "in"), padre.edges)
        self.assertEqual(_perfil(expandir(padre, {"preparar": cuerpo})), _perfil(original))

    def test_el_fanout_entrante_se_vuelve_un_solo_pin(self) -> None:
        g = self._grafo()
        g.add("mesh_normals", {}, nid="n2", x=400, y=100)
        g.connect("cil", "n2")

        padre, cuerpo = colapsar(g, {"t1", "n1", "n2"}, "rama", registro=REGISTRY, biblio={})

        self.assertEqual(len(firma(cuerpo)["entradas"]), 1)
        self.assertEqual(len([e for e in padre.edges if e[2] == "f1"]), 1)
        entrada = next(n for n in cuerpo.nodes.values() if n["verb"] == "input")
        bid = next(nid for nid, n in cuerpo.nodes.items() if n is entrada)
        self.assertEqual(len([e for e in cuerpo.edges if e[0] == bid]), 2)

    def test_seleccion_vacia_no_es_una_funcion(self) -> None:
        with self.assertRaises(FuncionError):
            colapsar(self._grafo(), set(), "nada", registro=REGISTRY, biblio={})

    def test_el_borde_de_api_guarda_el_cuerpo_y_devuelve_tool_mas_padre(self) -> None:
        from jam import api, funcion, preset
        g = self._grafo()
        with mock.patch.object(funcion, "biblioteca", return_value={}), \
             mock.patch.object(funcion, "nuevo_id", return_value="f_prueba"), \
             mock.patch.object(preset, "guardar", return_value="/tmp/preparar.json"):
            r = json.loads(api.collapse_function("preparar", g.to_json(), '["t1", "n1"]'))

        self.assertTrue(r["ok"], r["report"])
        self.assertEqual(r["tool"]["verbo"], "fn:f_prueba")
        self.assertEqual(r["tool"]["label"], "preparar")
        self.assertEqual(r["tool"]["inputs"][0]["name"], "in")
        self.assertEqual(r["tool"]["outputs"][0]["name"], "salida")
        self.assertEqual(r["graph"]["nodes"]["f1"]["verb"], "fn:f_prueba")

    def test_renombrar_no_es_parte_de_la_identidad_de_la_llamada(self) -> None:
        from jam import funcion, preset

        cuerpo = _cuerpo_escalar()
        presets = [{"kind": "funcion", "funcion_id": "f_estable", "nombre": "Nombre nuevo",
                    "graph": json.loads(cuerpo.to_json()), "scope": "local"}]
        with mock.patch.object(preset, "listar", return_value=presets):
            tool = funcion.herramientas()[-1]
            biblio = funcion.biblioteca()

        self.assertEqual(tool["verbo"], "fn:f_estable")
        self.assertEqual(tool["label"], "Nombre nuevo")
        self.assertIn("f_estable", biblio)

    def test_una_funcion_legada_conserva_fn_nombre(self) -> None:
        from jam import funcion, preset

        cuerpo = _cuerpo_escalar()
        presets = [{"kind": "funcion", "nombre": "escalar legado",
                    "graph": json.loads(cuerpo.to_json()), "scope": "local"}]
        with mock.patch.object(preset, "listar", return_value=presets):
            tool = funcion.herramientas()[-1]

        self.assertEqual(tool["verbo"], "fn:escalar legado")
        self.assertEqual(tool["label"], "escalar legado")

    def test_abm_crea_una_firma_editable_con_identidad_estable(self) -> None:
        from jam import api, funcion, preset

        with mock.patch.object(funcion, "listar_definiciones", return_value=[]), \
             mock.patch.object(funcion, "nuevo_id", return_value="f_nueva"), \
             mock.patch.object(preset, "guardar", return_value="/tmp/f_nueva.json") as guardar:
            r = json.loads(api.function_manage("create", payload="Preparar roca"))

        self.assertTrue(r["ok"], r["report"])
        self.assertEqual(r["tool"]["verbo"], "fn:f_nueva")
        self.assertEqual(r["tool"]["label"], "Preparar roca")
        self.assertEqual(r["tool"]["inputs"], [{"name": "entrada", "tipo": "*"}])
        self.assertEqual(r["tool"]["outputs"], [{"name": "salida", "tipo": "*"}])
        self.assertEqual(guardar.call_args.args[0]["funcion_id"], "f_nueva")

    def test_abm_renombra_sin_cambiar_el_verbo(self) -> None:
        from jam import api, funcion, preset

        definicion = {"funcion_id": "f_estable", "nombre": "Antes", "scope": "local",
                      "descripcion": "", "cuerpo": _cuerpo_escalar()}
        with mock.patch.object(funcion, "listar_definiciones", return_value=[definicion]), \
             mock.patch.object(preset, "guardar", return_value="/tmp/f_estable.json"):
            r = json.loads(api.function_manage("rename", "fn:f_estable", "Después"))

        self.assertTrue(r["ok"], r["report"])
        self.assertEqual(r["tool"]["verbo"], "fn:f_estable")
        self.assertEqual(r["tool"]["label"], "Después")


class SlateContratoTests(unittest.TestCase):
    """Las reglas forzosamente repetidas en Slate quedan atadas al contrato del cerebro."""

    RAIZ = Path(__file__).resolve().parents[3]

    def test_slate_lee_pines_nombrados_y_no_aplana_la_firma_a_in_out(self) -> None:
        modulo = (self.RAIZ / "Source/JamEditor/Private/JamEditorModule.cpp").read_text()
        editor = (self.RAIZ / "Source/JamEditor/Private/SJamGraphEditor.cpp").read_text()
        nodo = (self.RAIZ / "Source/JamEditor/Private/SJamGraphNode.cpp").read_text()

        self.assertIn('LeerPines(TEXT("inputs"), T.InputPins)', modulo)
        self.assertIn('LeerPines(TEXT("outputs"), T.OutputPins)', modulo)
        self.assertIn('FString::Join(Entradas, TEXT(", "))', editor)
        self.assertIn("OutputPinIndex(E.From, E.FromPin)", editor)
        self.assertIn("OnOutputClickedDelegate.ExecuteIfBound(Nombre)", nodo)
        # `in`/`out` son nombres legales de firma: la búsqueda dinámica tiene que ganarles a los
        # pines clásicos del header, que en una función están vacíos.
        self.assertLess(editor.index("T->OutputPins.FindByPredicate"),
                        editor.index('if (Pin == TEXT("out")) { return T->OutName; }'))
        self.assertLess(editor.index("T->InputPins.FindByPredicate"),
                        editor.index('if (Pin == TEXT("in"))'))

    def test_ctrl_g_pasa_por_el_borde_publico_y_no_colapsa_en_cpp(self) -> None:
        modulo = (self.RAIZ / "Source/JamEditor/Private/JamEditorModule.cpp").read_text()
        editor = (self.RAIZ / "Source/JamEditor/Private/SJamGraphEditor.cpp").read_text()

        self.assertIn("_a.collapse_function", modulo)
        self.assertIn('ResponseMarker(TEXT("JAMCOLLAPSE:"))', modulo)
        self.assertIn("Raw.Find(ResponseMarker, ESearchCase::CaseSensitive, ESearchDir::FromEnd)", modulo)
        self.assertIn("EKeys::G && InKeyEvent.IsControlDown()", editor)
        self.assertIn("OnCollapseFunction.Execute(Nombre, BuildJson(), SelectedJson)", editor)

    def test_slate_muestra_etiqueta_humana_y_tipo_en_los_pines(self) -> None:
        modulo = (self.RAIZ / "Source/JamEditor/Private/JamEditorModule.cpp").read_text()
        editor = (self.RAIZ / "Source/JamEditor/Private/SJamGraphEditor.cpp").read_text()
        nodo = (self.RAIZ / "Source/JamEditor/Private/SJamGraphNode.cpp").read_text()

        self.assertIn('TryGetStringField(TEXT("label"), T.Label)', modulo)
        self.assertIn('.DisplayName(T->Label.IsEmpty() ? Verb : T->Label)', editor)
        self.assertIn('TEXT("%s (%s)")', nodo)
        self.assertIn('DisplayName.IsEmpty() ? FriendlyVerbName(Verb) : DisplayName', nodo)

    def test_slate_ofrece_abm_y_guarda_el_cuerpo_por_el_borde_publico(self) -> None:
        modulo = (self.RAIZ / "Source/JamEditor/Private/JamEditorModule.cpp").read_text()
        editor = (self.RAIZ / "Source/JamEditor/Private/SJamGraphEditor.cpp").read_text()

        self.assertIn("_a.function_manage", modulo)
        for accion in ('TEXT("create")', 'TEXT("get")', 'TEXT("update")',
                       'TEXT("rename")', 'TEXT("delete")'):
            self.assertIn(accion, editor)
        self.assertIn("GuardarFuncion", editor)
        self.assertIn("BuildJson()", editor)
        self.assertIn("el grafo abierto todavía usa", editor)


class ExpansionTests(unittest.TestCase):
    def test_usar_la_funcion_dos_veces_compila_al_mismo_plan_que_el_grafo_plano(self) -> None:
        plano = JamGraph()
        plano.add("mesh_cylinder", {"radius": 30.0}, nid="cil")
        plano.add("mesh_transform", {"escala": 2.0}, nid="t1")
        plano.add("mesh_transform", {"escala": 2.0}, nid="t2")
        plano.add("mesh_to_static", {"name": "Muro"}, nid="fin")
        plano.connect("cil", "t1")
        plano.connect("t1", "t2")
        plano.connect("t2", "fin")

        con_funcion = JamGraph()
        con_funcion.add("mesh_cylinder", {"radius": 30.0}, nid="cil")
        con_funcion.add("fn:escalar", {}, nid="f1")
        con_funcion.add("fn:escalar", {}, nid="f2")
        con_funcion.add("mesh_to_static", {"name": "Muro"}, nid="fin")
        con_funcion.connect("cil", "f1", "malla")
        con_funcion.connect("f1", "f2", "malla", "salida")
        con_funcion.connect("f2", "fin", "in", "salida")

        expandido = expandir(con_funcion, {"escalar": _cuerpo_escalar()})

        self.assertEqual(_perfil(expandido), _perfil(plano))

    def test_los_nodos_de_dos_instancias_no_chocan(self) -> None:
        g = JamGraph()
        g.add("mesh_cylinder", {}, nid="cil")
        g.add("fn:escalar", {}, nid="f1")
        g.add("fn:escalar", {}, nid="f2")
        g.connect("cil", "f1", "malla")
        g.connect("f1", "f2", "malla", "salida")

        e = expandir(g, {"escalar": _cuerpo_escalar()})

        self.assertEqual(sorted(e.nodes), ["cil", "f1__k", "f2__k"])
        self.assertNotIn("input", [n["verb"] for n in e.nodes.values()])
        self.assertNotIn("output", [n["verb"] for n in e.nodes.values()])

    def test_expandir_no_toca_el_grafo_original(self) -> None:
        g = JamGraph()
        g.add("mesh_cylinder", {}, nid="cil")
        g.add("fn:escalar", {}, nid="f1")
        g.connect("cil", "f1", "malla")
        antes = g.to_json()

        expandir(g, {"escalar": _cuerpo_escalar()})

        self.assertEqual(g.to_json(), antes)

    def test_una_entrada_sin_cablear_no_explota_y_deja_el_nodo_suelto(self) -> None:
        g = JamGraph()
        g.add("fn:escalar", {}, nid="f1")

        e = expandir(g, {"escalar": _cuerpo_escalar()})

        self.assertEqual(list(e.nodes), ["f1__k"])
        self.assertEqual(e.edges, [])

    def test_una_funcion_que_devuelve_su_entrada_pasa_el_cable_de_largo(self) -> None:
        cuerpo = JamGraph()
        cuerpo.add("input", {"name": "malla", "type": "M"}, nid="e")
        cuerpo.add("output", {"name": "salida", "type": "M"}, nid="s")
        cuerpo.connect("e", "s")

        g = JamGraph()
        g.add("mesh_cylinder", {}, nid="cil")
        g.add("fn:pasa", {}, nid="f1")
        g.add("mesh_to_static", {}, nid="fin")
        g.connect("cil", "f1", "malla")
        g.connect("f1", "fin", "in", "salida")

        e = expandir(g, {"pasa": cuerpo})

        self.assertEqual(e.edges, [("cil", "out", "fin", "in")])

    def test_anidar_una_funcion_dentro_de_otra_funciona(self) -> None:
        externa = JamGraph()
        externa.add("input", {"name": "malla", "type": "M"}, nid="e", y=0.0)
        externa.add("fn:escalar", {}, nid="dentro", y=10.0)
        externa.add("mesh_normals", {}, nid="norm", y=20.0)
        externa.add("output", {"name": "salida", "type": "M"}, nid="s", y=30.0)
        externa.connect("e", "dentro", "malla")
        externa.connect("dentro", "norm", "in", "salida")
        externa.connect("norm", "s")

        g = JamGraph()
        g.add("mesh_cylinder", {}, nid="cil")
        g.add("fn:doble", {}, nid="f")
        g.add("mesh_to_static", {}, nid="fin")
        g.connect("cil", "f", "malla")
        g.connect("f", "fin", "in", "salida")

        e = expandir(g, {"doble": externa, "escalar": _cuerpo_escalar()})

        self.assertEqual([e.nodes[n]["verb"] for n in e.topo_order()],
                         ["mesh_cylinder", "mesh_transform", "mesh_normals", "mesh_to_static"])

    def test_una_funcion_que_se_contiene_a_si_misma_es_un_error_y_no_un_cuelgue(self) -> None:
        cuerpo = JamGraph()
        cuerpo.add("input", {"name": "malla"}, nid="e")
        cuerpo.add("fn:sola", {}, nid="yo")
        cuerpo.add("output", {"name": "salida"}, nid="s")
        cuerpo.connect("e", "yo", "malla")
        cuerpo.connect("yo", "s", "in", "salida")

        g = JamGraph()
        g.add("fn:sola", {}, nid="f")

        with self.assertRaises(FuncionError) as err:
            expandir(g, {"sola": cuerpo})

        self.assertIn("sola → sola", str(err.exception))

    def test_la_recursion_indirecta_tambien_se_detecta(self) -> None:
        a = JamGraph()
        a.add("fn:b", {}, nid="x")
        b = JamGraph()
        b.add("fn:a", {}, nid="y")

        g = JamGraph()
        g.add("fn:a", {}, nid="f")

        with self.assertRaises(FuncionError) as err:
            expandir(g, {"a": a, "b": b})

        self.assertIn("a → b → a", str(err.exception))

    def test_usar_una_funcion_que_no_existe_dice_cual(self) -> None:
        g = JamGraph()
        g.add("fn:fantasma", {}, nid="f")

        with self.assertRaises(FuncionError) as err:
            expandir(g, {})

        self.assertIn("fantasma", str(err.exception))


class CableadoTests(unittest.TestCase):
    """Que el motor exista no sirve de nada si no lo consume nadie: esto prueba el camino real,
    el mismo que llama Slate."""

    def _cuerpo_json(self) -> dict:
        c = JamGraph()
        c.add("input", {"name": "malla", "type": "M"}, nid="e", y=0.0)
        c.add("mesh_normals", {}, nid="k", y=10.0)
        c.add("output", {"name": "salida", "type": "M"}, nid="s", y=20.0)
        c.connect("e", "k")
        c.connect("k", "s")
        return json.loads(c.to_json())

    def test_un_grafo_con_pines_se_reconoce_solo_como_funcion(self) -> None:
        from jam import preset
        self.assertEqual(preset.kind_de_grafo(self._cuerpo_json()), "funcion")

    def test_un_grafo_sin_pines_sigue_siendo_graph(self) -> None:
        from jam import preset
        g = JamGraph()
        g.add("mesh_cylinder", {}, nid="c")
        self.assertEqual(preset.kind_de_grafo(json.loads(g.to_json())), "graph")

    def test_una_funcion_no_se_aplica_sola_y_lo_dice(self) -> None:
        from jam import preset
        r = preset.aplicar({"nombre": "tapa", "kind": "funcion", "graph": self._cuerpo_json()})

        self.assertFalse(r["ok"])
        self.assertIn("fn:tapa", r["texto"])

    def test_sin_instancias_el_json_vuelve_intacto(self) -> None:
        from jam import funcion
        g = JamGraph()
        g.add("mesh_cylinder", {}, nid="c")
        original = g.to_json()

        self.assertIs(funcion.expandir_json(original), original)

    def test_compile_del_canvas_acepta_un_grafo_con_funcion(self) -> None:
        from jam import api, funcion
        g = JamGraph()
        g.add("mesh_cylinder", {}, nid="cil")
        g.add("fn:tapa", {}, nid="f")
        g.connect("cil", "f", "malla")
        biblio = {"tapa": JamGraph.from_json(json.dumps(self._cuerpo_json()))}

        with mock.patch.object(funcion, "biblioteca", return_value=biblio):
            r = json.loads(api.compile_graph_json(g.to_json()))

        self.assertTrue(r["ok"], r["report"])
        self.assertIn("f__k", r["nodes"])

    def test_compile_del_canvas_reporta_la_recursion_en_vez_de_reventar(self) -> None:
        from jam import api, funcion
        cuerpo = JamGraph()
        cuerpo.add("fn:sola", {}, nid="yo")
        g = JamGraph()
        g.add("fn:sola", {}, nid="f")

        with mock.patch.object(funcion, "biblioteca", return_value={"sola": cuerpo}):
            r = json.loads(api.compile_graph_json(g.to_json()))

        self.assertFalse(r["ok"])
        self.assertIn("se contiene a sí misma", r["report"])


if __name__ == "__main__":
    unittest.main()
