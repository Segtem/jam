"""El núcleo de Jam se importa sin Unreal (tarea `fuera-del-motor`, etapa 1).

El grafo, el DSL y el registro de verbos tienen que poder vivir fuera del motor: un servidor MCP, una
UI web o un adaptador de Godot los importan sin el intérprete del editor. Se prueba en un proceso
aparte, con `sys.modules["unreal"] = None`: en esta suite casi todos los tests instalan un `unreal`
falso, y con él cargado un import que sí depende del motor pasaría igual.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

RAIZ_PY = Path(__file__).resolve().parents[1]

#: Lo que tiene que cargar sin motor. Agregar acá un módulo es una promesa: si mañana importa
#: `unreal` (directo o por otro módulo), este test lo dice.
NUCLEO = ("registro", "registro_core", "dsl", "texto", "malla_core", "comun", "adaptador_godot", "graph", "flow", "math_core", "funcion", "letras",
          "shader", "layout", "display_core", "cache_core")

_SONDA = """
import importlib, sys
sys.modules["unreal"] = None
fallas = []
for nombre in sys.argv[1:]:
    try:
        importlib.import_module("jam." + nombre)
    except Exception as exc:
        fallas.append(f"{nombre}: {type(exc).__name__}: {exc}")
from jam import registro
print(len(registro.REGISTRO), sum("fn" in i for i in registro.REGISTRO.values()))
print("\\n".join(fallas))
"""


class NucleoSinMotor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        salida = subprocess.run([sys.executable, "-B", "-c", _SONDA, *NUCLEO], cwd=RAIZ_PY,
                                capture_output=True, text=True, check=True).stdout.splitlines()
        cls.cuantos, cls.con_fn = (int(x) for x in salida[0].split())
        cls.fallas = [linea for linea in salida[1:] if linea.strip()]

    def test_el_nucleo_importa_con_unreal_bloqueado(self):
        self.assertEqual(self.fallas, [], "módulos del núcleo que necesitan el motor")

    def test_el_registro_describe_todos_los_verbos(self):
        # Un número y no «más de cero»: un registro que se vació también pasaría el otro.
        self.assertGreaterEqual(self.cuantos, 171)

    def test_el_registro_neutro_no_trae_implementaciones(self):
        """`fn` la enchufa el adaptador (`tools.IMPLEMENTA`). Sin motor no hay ninguna."""
        self.assertEqual(self.con_fn, 0)


class AdaptadorUnreal(unittest.TestCase):
    def test_cada_verbo_del_registro_tiene_implementacion_en_unreal(self):
        import types
        falso = sys.modules.setdefault("unreal", types.ModuleType("unreal"))
        if not hasattr(falso, "TopLevelAssetPath"):
            falso.TopLevelAssetPath = lambda package, name: (package, name)
        from jam import registro, tools

        self.assertIs(tools.REGISTRO, registro.REGISTRO)
        sin = sorted(v for v, info in registro.REGISTRO.items() if not callable(info.get("fn")))
        self.assertEqual(sin, [])
        self.assertEqual(sorted(tools.IMPLEMENTA), sorted(registro.REGISTRO))


if __name__ == "__main__":
    unittest.main()
