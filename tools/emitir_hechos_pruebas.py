"""Hechos de pruebas para Oracle: corre los casos de contrato de un cambio de Factory y emite uno por caso.

    python tools/emitir_hechos_pruebas.py --cambio ID --salida "$(oracle-factory ruta ID evidencia)"

Los casos salen del contrato del cambio, `medidas/contratos/<ID>.json`:

    {"<requisito corto>": ["modulo.Clase.test_x", ...], ...}

El requisito corto es lo que sigue al último punto de su id (`f2_renombra_el_nodo_seleccionado`).
Los casos se cargan desde `Content/Python/tests`, con `Content/Python` en el camino, como los corre
`relevo.py`. Escribe:

    {"prueba_caso":    [{"requisito", "caso", "codigo"}, ...],   # 0 si pasó; 1 si falló, dio error o se salteó
     "prueba_corrida": [{"cambio", "completa", "casos"}]}

`completa` vale 1 sólo si cada requisito del cambio (los de su registro, `.factory/cambios/<ID>/`)
tiene al menos un caso en el contrato, el contrato no nombra un requisito que el cambio no tiene ni un
caso dos veces, y cada caso corrió exactamente una vez. Así un caso o un requisito que falta no pasa
por verde (hallazgo de codex y agy en la vuelta 1). Tarea 20261015-221410-renombrar-nodo.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PRUEBAS = RAIZ / "Content" / "Python" / "tests"


class _Resultado(unittest.TextTestResult):
    """Anota el resultado de cada caso por su nombre (módulo.Clase.test_x)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.codigos: dict[str, int] = {}
        self.cantidad: Counter = Counter()

    def startTest(self, test):
        super().startTest(test)
        self.cantidad[test.id()] += 1

    def _marcar(self, test, codigo: int):
        self.codigos[test.id()] = max(codigo, self.codigos.get(test.id(), 0))

    def addSuccess(self, test):
        super().addSuccess(test)
        self._marcar(test, 0)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._marcar(test, 1)

    def addError(self, test, err):
        super().addError(test, err)
        self._marcar(test, 1)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._marcar(test, 1)  # un caso salteado no prueba nada


def contrato(cambio: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Los casos del contrato del cambio y lo que impide que la corrida sea completa."""
    problemas = []
    ruta = RAIZ / "medidas" / "contratos" / f"{cambio}.json"
    datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {}
    if not ruta.is_file():
        problemas.append(f"no hay contrato en {ruta.relative_to(RAIZ)}")
    registro = RAIZ / ".factory" / "cambios" / cambio / "factory.json"
    requisitos = ({r.rsplit(".", 1)[-1] for r in json.loads(registro.read_text(encoding="utf-8")).get("requisitos", [])}
                  if registro.is_file() else set())
    if not registro.is_file():
        problemas.append(f"no encuentro el registro del cambio {cambio}")
    for r in sorted(requisitos - set(datos)):
        problemas.append(f"el requisito {r} no tiene casos en el contrato")
    for r in sorted(set(datos) - requisitos):
        problemas.append(f"el contrato nombra {r}, que no es un requisito del cambio")
    for r, lista in datos.items():
        if not lista:
            problemas.append(f"el requisito {r} no tiene casos en el contrato")
    casos = [(r, c) for r, lista in datos.items() for c in lista]
    repetidos = sorted(c for c, n in Counter(c for _r, c in casos).items() if n > 1)
    problemas += [f"el caso {c} figura dos veces" for c in repetidos]
    return casos, problemas


def correr(casos: list[tuple[str, str]]) -> tuple[dict, str]:
    sys.path.insert(0, str(RAIZ / "Content" / "Python"))
    sys.path.insert(0, str(PRUEBAS))
    nombres = [c for _r, c in casos]
    suite = unittest.defaultTestLoader.loadTestsFromNames(nombres)
    flujo = io.StringIO()
    resultado = unittest.TextTestRunner(stream=flujo, verbosity=2, resultclass=_Resultado).run(suite)
    # Completa: cada caso nombrado corrió exactamente una vez, y no se nombró ninguno dos veces.
    completa = len(set(nombres)) == len(nombres) and all(resultado.cantidad.get(n) == 1 for n in nombres)
    hechos = {"prueba_caso": [{"requisito": r, "caso": c, "codigo": resultado.codigos.get(c, 1)} for r, c in casos],
              "prueba_corrida": [{"completa": int(completa), "casos": len(nombres)}]}
    return hechos, flujo.getvalue()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cambio", required=True, help="id del cambio de Factory")
    p.add_argument("--salida", type=Path, required=True, help="carpeta nueva de evidencia (oracle-factory ruta ID evidencia)")
    args = p.parse_args(argv)
    casos, problemas = contrato(args.cambio)
    hechos, salida = correr(casos)
    for fila in hechos["prueba_corrida"]:
        fila["cambio"] = args.cambio
        if problemas:
            fila["completa"] = 0
    for problema in problemas:
        print(f"Contrato incompleto: {problema}", file=sys.stderr)
    args.salida.mkdir(parents=True, exist_ok=False)
    (args.salida / "hechos.json").write_text(json.dumps(hechos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.salida / "pruebas.txt").write_text(salida, encoding="utf-8")
    ok = all(f["codigo"] == 0 for f in hechos["prueba_caso"]) and hechos["prueba_corrida"][0]["completa"]
    print(f"Hechos de {len(casos)} casos en {args.salida / 'hechos.json'}; corrida completa: {bool(hechos['prueba_corrida'][0]['completa'])}; "
          f"{'todos pasaron' if ok else 'hay casos que no pasaron'}.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
