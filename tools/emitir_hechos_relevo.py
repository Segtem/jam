"""El dominio `relevo` de Jam, declarado. Genera su prueba diferencial contra `tools/relevo.py`.

    python tools/emitir_hechos_relevo.py

Lo particular de este dominio, y nada más: cómo se monta un relevo de prueba, cómo se extraen sus
hechos, qué defectos se le inyectan, y cuál es la implementación independiente.

La parte incómoda es que las reglas de `relevo.py` dependen del estado de **git** —que el commit de la
verificación exista, sea antecesor de HEAD, y que no se haya tocado código vivo desde entonces—, así
que cada escenario monta un **repositorio de verdad**. No alcanza con inventar archivos.

Y la referencia no es la CLI sino las FUNCIONES —`revisar_testigo` y `verde_editor_vigente`—
importadas y apuntadas a otra raíz: la CLI además corre los tests y el vault, que en un repo de
mentira fallarían por el motivo equivocado. Son las mismas funciones que gobiernan el relevo real.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "vendor" / "oracle-pkg"))

# Oracle viene del wheel de PyPI: los nombres internos (`nucleo`, `catalogos`) sólo
# existen después de importar la fachada, que es la que los registra.
import oracle_metalenguaje  # noqa: F401,E402

import catalogos.escalares                           # noqa: F401,E402
from nucleo.diferencial import Procedencia           # noqa: E402
from nucleo.dominio import Dominio, generar          # noqa: E402
from nucleo.medida import cargar_catalogo            # noqa: E402
from nucleo.proyecto import (Proyecto, catalogos_a_cargar,  # noqa: E402
                             escalares_del_proyecto)

PROYECTO = Proyecto(RAIZ / "medidas")
DESTINO = PROYECTO.diferencial / "relevo.json"

MEDIDAS = ("relevo.testigo_tiene_sus_campos", "relevo.testigo_tiene_sus_secciones",
           "relevo.agentes_conocidos", "relevo.el_relevo_tiene_dos_puntas",
           "relevo.verificacion_existe", "proceso.verificacion_vigente")

TESTIGO = """\
---
turno: 2026-01-01 · a → b
saliente: claude-code
entrante: codex
desde: 2026-01-01
verde_editor: {sha}
verde_editor_fecha: 2026-01-01
---

## Verde al soltar
## Frontera de verificación
## Para las manos de Brian
## Lo próximo
## No toques esto
## Lo que aprendí este turno
"""

DEFECTOS = ("falta_campo", "falta_seccion", "mismo_agente", "agente_desconocido",
            "commit_inexistente", "codigo_vivo_commiteado", "codigo_vivo_sin_commitear")
_TEMPORALES: list[str] = []
PROCEDENCIA = Procedencia(
    raiz=RAIZ,
    emisor=("tools/emitir_hechos_relevo.py", "medidas/escalares.py"),
    referencia=("tools/relevo.py",),
    desde_proyecto="..",
)
_GIT_ENV = {**os.environ,
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00"}


def _cargar_relevo(raiz: Path):
    """El verificador REAL, apuntado a otra raíz. No es una copia reescrita."""
    spec = importlib.util.spec_from_file_location(f"relevo_{raiz.name}", raiz / "tools" / "relevo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.RAIZ = raiz
    mod.TESTIGO = raiz / "RELEVO.md"
    return mod


def _git(raiz: Path, *args) -> str:
    return subprocess.run(["git", "-C", str(raiz), *args],
                          capture_output=True, text=True).stdout.strip()


def montar(defecto: str | None, i: int = 0) -> Path:
    """Un repositorio git de verdad, con el defecto puesto. Determinista."""
    raiz = Path(tempfile.mkdtemp())
    _TEMPORALES.append(str(raiz))
    (raiz / "tools").mkdir()
    (raiz / "Source").mkdir()
    shutil.copy(RAIZ / "tools" / "relevo.py", raiz / "tools" / "relevo.py")
    (raiz / "Source" / "vivo.cpp").write_text("int main(){return 0;}\n", encoding="utf-8")

    subprocess.run(["git", "init", "-q", "-b", "main", str(raiz)], check=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(raiz), "config", k, v], check=True)
    (raiz / "RELEVO.md").write_text(TESTIGO.format(sha="PENDIENTE"), encoding="utf-8")
    subprocess.run(["git", "-C", str(raiz), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(raiz), "commit", "-qm", "base"],
                   check=True, env=_GIT_ENV)
    sha = _git(raiz, "rev-parse", "--short", "HEAD")

    testigo = TESTIGO.format(sha="0000000" if defecto == "commit_inexistente" else sha)
    if defecto == "falta_campo":
        testigo = re.sub(r"^desde: .*$\n", "", testigo, flags=re.M)
    elif defecto == "falta_seccion":
        testigo = testigo.replace("## No toques esto\n", "")
    elif defecto == "mismo_agente":
        testigo = testigo.replace("entrante: codex", "entrante: claude-code")
    elif defecto == "agente_desconocido":
        testigo = testigo.replace("entrante: codex", "entrante: gemini")
    (raiz / "RELEVO.md").write_text(testigo, encoding="utf-8")

    if defecto == "codigo_vivo_commiteado":
        (raiz / "Source" / "vivo.cpp").write_text("int main(){return 1;}\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(raiz), "commit", "-qam", "toca vivo"],
                       check=True, env=_GIT_ENV)
    elif defecto == "codigo_vivo_sin_commitear":
        (raiz / "Source" / "vivo.cpp").write_text("int main(){return 2;}\n", encoding="utf-8")
    else:
        subprocess.run(["git", "-C", str(raiz), "commit", "-qam", "testigo"],
                       check=True, env=_GIT_ENV)
    return raiz


def hechos(raiz: Path) -> dict:
    """Relaciones planas sobre el estado del relevo. Ningún `if` que decida si algo está mal."""
    mod = _cargar_relevo(raiz)
    fm = mod.frontmatter(mod.TESTIGO) if mod.TESTIGO.exists() else {}
    texto = mod.TESTIGO.read_text(encoding="utf-8") if mod.TESTIGO.exists() else ""

    sha = fm.get("verde_editor", "")
    existe = bool(_git(raiz, "cat-file", "-t", sha)) if sha else False
    ancestro = existe and subprocess.run(
        ["git", "-C", str(raiz), "merge-base", "--is-ancestor", sha, "HEAD"],
        capture_output=True).returncode == 0

    cambios = []
    if ancestro:
        for f in _git(raiz, "diff", "--name-only", f"{sha}..HEAD", "--", *mod.VIVO).split("\n"):
            if f:
                cambios.append({"archivo": f, "commiteado": True, "es_codigo_vivo": True})
    for linea in _git(raiz, "status", "--porcelain", "--", *mod.VIVO).split("\n"):
        if linea:
            cambios.append({"archivo": linea[2:].strip(), "commiteado": False,
                            "es_codigo_vivo": True})
    if not cambios:
        cambios.append({"archivo": "(ninguno)", "commiteado": True, "es_codigo_vivo": False})

    return {
        "testigo_campo": [{"nombre": c, "presente": c in fm} for c in mod.CAMPOS],
        "testigo_seccion": [{"nombre": s, "presente": s in texto} for s in mod.SECCIONES],
        "agente": [{"rol": rol, "nombre": fm.get(rol, ""),
                    "conocido": fm.get(rol, "") in mod.AGENTES}
                   for rol in ("saliente", "entrante")],
        "verificacion": [{"que": "motor", "commit": sha, "existe": existe,
                          "es_ancestro": ancestro}],
        "cambio": cambios,
    }


def referencia(raiz: Path) -> bool:
    """La implementación INDEPENDIENTE: las funciones que gobiernan el relevo real."""
    mod = _cargar_relevo(raiz)
    _fm, fallas = mod.revisar_testigo()
    if not fallas:
        fallas = mod.verde_editor_vigente(mod.frontmatter(mod.TESTIGO))
    return not fallas


RELEVO = Dominio(
    nombre="relevo", montar=montar, hechos=hechos, referencia=referencia, defectos=DEFECTOS,
    descripcion="Brianholl/jam · tools/relevo.py (revisar_testigo + verde_editor_vigente)")


def main() -> int:
    try:
        with escalares_del_proyecto(PROYECTO, confiar=True):
            catalogo = cargar_catalogo(catalogos_a_cargar(PROYECTO))
            medidas = [catalogo[m] for m in MEDIDAS if m in catalogo]
            fixture = generar(RELEVO, medidas, procedencia=PROCEDENCIA)
    finally:
        for d in _TEMPORALES:
            shutil.rmtree(d, ignore_errors=True)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")
    print(f"{len(medidas)} medidas × {fixture['mundos']} escenarios · escrito: {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
