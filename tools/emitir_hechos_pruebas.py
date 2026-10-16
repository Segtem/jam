"""Hechos de pruebas para Oracle: corre los casos de contrato de un cambio de Factory y emite uno por caso.

    python tools/emitir_hechos_pruebas.py --cambio ID --salida "$(oracle-factory ruta ID evidencia)"

Los casos salen del contrato del cambio, `medidas/contratos/<ID>.json`, por requisito y escenario:

    {"<requisito corto>": {"<escenario>": ["modulo.Clase.test_x", ...], ...}, ...}

El requisito corto es lo que sigue al último punto de su id (`f2_renombra_el_nodo_seleccionado`) y el
escenario es su título en la spec del cambio (`renombrar con F2`).
Los casos se cargan desde `Content/Python/tests`, con `Content/Python` en el camino, como los corre
`relevo.py`. Escribe:

    {"prueba_caso":    [{"requisito", "caso", "codigo"}, ...],   # 0 si pasó; 1 si falló, dio error o se salteó
     "prueba_corrida": [{"cambio", "completa", "casos"}]}

`completa` vale 1 sólo si cada escenario de cada requisito del cambio (los de su registro,
`.factory/cambios/<ID>/`, con los escenarios de su spec) tiene al menos un caso en el contrato, el
contrato no nombra un requisito ni un escenario que el cambio no tiene ni un caso dos veces, y cada
caso corrió exactamente una vez. Así un caso, un escenario o un requisito que falta no pasa por verde
(hallazgos de codex y agy en las vueltas 1 y 3). Tarea 20261015-221410-renombrar-nodo.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import unicodedata
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


def _slug(texto: str) -> str:
    """El nombre corto de un requisito a partir de su título, como lo arma Factory al importarlo."""
    ascii_ = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_.lower()).strip("_")


def escenarios_de(spec: Path) -> dict[str, list[str]]:
    """{requisito corto: [títulos de sus escenarios]} de la spec del cambio (lo que REMOVED retira no cuenta)."""
    salida, actual, retirados = {}, None, False
    for linea in spec.read_text(encoding="utf-8").splitlines():
        delta = re.match(r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements\s*$", linea, re.I)
        if delta:
            retirados, actual = delta[1].upper() == "REMOVED", None
        elif m := re.match(r"^###\s+Requirement:\s*(.+?)\s*$", linea):
            actual = None if retirados else _slug(m[1])
            if actual:
                salida[actual] = []
        elif (m := re.match(r"^####\s+Scenario:\s*(.+?)\s*$", linea)) and actual:
            salida[actual].append(m[1])
    return salida


def contrato(cambio: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Los casos del contrato del cambio y lo que impide que la corrida sea completa."""
    problemas = []
    ruta = RAIZ / "medidas" / "contratos" / f"{cambio}.json"
    datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {}
    if not ruta.is_file():
        problemas.append(f"no hay contrato en {ruta.relative_to(RAIZ)}")
    registro = RAIZ / ".factory" / "cambios" / cambio / "factory.json"
    estado = json.loads(registro.read_text(encoding="utf-8")) if registro.is_file() else {}
    if not registro.is_file():
        problemas.append(f"no encuentro el registro del cambio {cambio}")
    spec = RAIZ / estado.get("spec", "") if estado.get("spec") else None
    escenarios = escenarios_de(spec) if spec and spec.is_file() else {}
    if registro.is_file() and not escenarios:
        problemas.append("no encuentro los escenarios de la spec del cambio")
    requisitos = {r.rsplit(".", 1)[-1] for r in estado.get("requisitos", [])}
    # La spec y el registro tienen que decir lo mismo: un requisito que la spec suma y el registro no importó
    # todavía (o al revés) también se exige (hallazgo de codex, vuelta 5).
    for r in sorted(set(escenarios) - requisitos):
        problemas.append(f"la spec tiene el requisito {r}, que el registro del cambio no importó")
    for r in sorted(requisitos - set(escenarios)) if escenarios else []:
        problemas.append(f"el registro tiene el requisito {r}, que la spec del cambio ya no tiene")
    requisitos |= set(escenarios)
    for r in sorted(requisitos - set(datos)):
        problemas.append(f"el requisito {r} no tiene casos en el contrato")
    for r in sorted(set(datos) - requisitos):
        problemas.append(f"el contrato nombra {r}, que no es un requisito del cambio")
    for r in sorted(requisitos & set(datos)):
        por_escenario = datos[r] if isinstance(datos[r], dict) else {}
        if not isinstance(datos[r], dict):
            problemas.append(f"el contrato de {r} no está por escenario")
        for e in escenarios.get(r, []):
            if not por_escenario.get(e):
                problemas.append(f"el escenario «{e}» de {r} no tiene casos en el contrato")
        for e in sorted(set(por_escenario) - set(escenarios.get(r, []))):
            problemas.append(f"el contrato nombra el escenario «{e}», que {r} no tiene")
    casos = [(r, c) for r, por in datos.items() if isinstance(por, dict) for lista in por.values() for c in lista]
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
