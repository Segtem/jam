"""Las filas de las salidas muestran la ETIQUETA del spec y los cables siguen usando el nombre
(tarea `etiquetas-pines`). La fila decía `out`, `eje_x`; la etiqueta ya viajaba en el spec y el C++
la descartaba en los tres lugares donde lo lee."""

import re
import sys
import unittest
from pathlib import Path

sys.modules.setdefault("unreal", None)

from jam import registro  # noqa: E402

SOURCE = Path(__file__).resolve().parents[3] / "Source" / "JamEditor"


def _spec(verbo):
    # El spec del canvas (`api.spec_all` lo arma igual): trae también los verbos de Maths.
    return next(t for t in registro.spec_canvas("unreal", None, [])["tools"] if t["verbo"] == verbo)


class ElSpec(unittest.TestCase):
    def test_las_salidas_extra_traen_una_etiqueta_distinta_del_nombre(self):
        outs = {o["name"]: o["label"] for o in _spec("matrix_decompose")["outs"]}
        self.assertEqual(outs["eje_x"], "eje X")
        self.assertEqual(_spec("domain_construct")["out_label"], "dominio")
        self.assertEqual(_spec("matrix_decompose")["out_label"], "traslación")


class ElCpp(unittest.TestCase):
    def test_cada_lector_del_spec_lee_la_etiqueta_del_pin(self):
        lectores = 0
        for archivo in ("Private/JamEditorModule.cpp", "Private/SJamGraphEditor.cpp"):
            texto = (SOURCE / archivo).read_text(encoding="utf-8")
            for cuerpo in re.findall(r"auto LeerPines = .*?\n\t*};", texto, re.S):
                lectores += 1
                self.assertIn('TryGetStringField(TEXT("label"), Pin.Label)', cuerpo, archivo)
        self.assertEqual(lectores, 3, "el spec se lee en tres lugares; los tres tienen que leerla")

    def test_la_fila_muestra_la_etiqueta_y_el_clic_sigue_usando_el_nombre(self):
        nodo = (SOURCE / "Private/SJamGraphNode.cpp").read_text(encoding="utf-8")
        self.assertIn("*OutPin.Visible(), *OutPin.TypeLabel", nodo)
        self.assertIn("[this, Nombre = OutPin.Name]()", nodo, "el cable se engancha por el nombre")
        editor = (SOURCE / "Private/SJamGraphEditor.cpp").read_text(encoding="utf-8")
        self.assertIn("DataColor(T->OutName), T->OutLabel}", editor, "la salida principal usa out_label")


if __name__ == "__main__":
    unittest.main()
