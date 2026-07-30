"""Emite los HECHOS del relevo, y la prueba diferencial contra `tools/relevo.py`.

    python tools/emitir_hechos_relevo.py

Igual que con el vault: el sensor no juzga, produce relaciones. Las reglas viven en `oracle` como
medidas declaradas.

La parte incómoda es que las reglas de `relevo.py` dependen del estado de **git** —que el commit de la
verificación exista, sea antecesor de HEAD, y que no se haya tocado código vivo desde entonces—, así
que el diferencial monta un **repositorio de verdad** en un temporal para cada escenario. No alcanza
con inventar archivos.

Y no se compara contra la CLI sino contra las FUNCIONES de `relevo.py` (`revisar_testigo`,
`verde_editor_vigente`), porque la CLI además corre los tests y el vault, que en un repo de mentira
fallarían por el motivo equivocado. Se importan y se les cambia la raíz: son las mismas funciones que
gobiernan el relevo real.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "medidas" / "diferencial" / "relevo.json"

MEDIDAS = ("relevo.testigo_tiene_sus_campos", "relevo.testigo_tiene_sus_secciones",
           "relevo.agentes_conocidos", "relevo.el_relevo_tiene_dos_puntas",
           "relevo.verificacion_existe", "proceso.verificacion_vigente")


def _cargar_relevo(raiz: Path):
    """Importa `tools/relevo.py` apuntado a otra raíz. Es el verificador REAL, no una copia."""
    spec = importlib.util.spec_from_file_location(f"relevo_{raiz.name}", raiz / "tools" / "relevo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.RAIZ = raiz
    mod.TESTIGO = raiz / "RELEVO.md"
    return mod


def _git(raiz: Path, *args) -> str:
    r = subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, text=True)
    return r.stdout.strip()


def hechos(raiz: Path, mod) -> dict:
    """Relaciones planas sobre el estado del relevo. Ningún `if` que decida si algo está mal."""
    fm = mod.frontmatter(mod.TESTIGO) if mod.TESTIGO.exists() else {}
    texto = mod.TESTIGO.read_text(encoding="utf-8") if mod.TESTIGO.exists() else ""

    campos = [{"nombre": c, "presente": c in fm} for c in mod.CAMPOS]
    secciones = [{"nombre": s, "presente": s in texto} for s in mod.SECCIONES]
    agentes = [{"rol": rol, "nombre": fm.get(rol, ""), "conocido": fm.get(rol, "") in mod.AGENTES}
               for rol in ("saliente", "entrante")]

    sha = fm.get("verde_editor", "")
    existe = bool(_git(raiz, "cat-file", "-t", sha)) if sha else False
    ancestro = existe and subprocess.run(
        ["git", "-C", str(raiz), "merge-base", "--is-ancestor", sha, "HEAD"],
        capture_output=True).returncode == 0
    verificacion = [{"que": "motor", "commit": sha, "existe": existe, "es_ancestro": ancestro}]

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

    return {"testigo_campo": campos, "testigo_seccion": secciones, "agente": agentes,
            "verificacion": verificacion, "cambio": cambios}


def espera(h: dict) -> dict:
    a = h["agente"]
    return {
        "relevo.testigo_tiene_sus_campos": all(x["presente"] for x in h["testigo_campo"]),
        "relevo.testigo_tiene_sus_secciones": all(x["presente"] for x in h["testigo_seccion"]),
        "relevo.agentes_conocidos": all(x["conocido"] for x in a),
        "relevo.el_relevo_tiene_dos_puntas": a[0]["nombre"] != a[1]["nombre"],
        "relevo.verificacion_existe": all(x["existe"] and x["es_ancestro"]
                                          for x in h["verificacion"]),
        "proceso.verificacion_vigente": not any(x["es_codigo_vivo"] for x in h["cambio"]),
    }


TESTIGO_MINIMO = """\
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


def _escenario(defecto: str | None) -> tuple[dict, bool]:
    with tempfile.TemporaryDirectory() as d:
        raiz = Path(d)
        (raiz / "tools").mkdir()
        (raiz / "Source").mkdir()
        shutil.copy(RAIZ / "tools" / "relevo.py", raiz / "tools" / "relevo.py")
        (raiz / "Source" / "vivo.cpp").write_text("int main(){return 0;}\n", encoding="utf-8")

        subprocess.run(["git", "init", "-q", "-b", "main", str(raiz)], check=True)
        for k, v in (("user.email", "t@t"), ("user.name", "t")):
            subprocess.run(["git", "-C", str(raiz), "config", k, v], check=True)
        (raiz / "RELEVO.md").write_text(TESTIGO_MINIMO.format(sha="PENDIENTE"), encoding="utf-8")
        subprocess.run(["git", "-C", str(raiz), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(raiz), "commit", "-qm", "base"], check=True)
        sha = _git(raiz, "rev-parse", "--short", "HEAD")

        testigo = TESTIGO_MINIMO.format(
            sha="0000000" if defecto == "commit_inexistente" else sha)
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
            subprocess.run(["git", "-C", str(raiz), "commit", "-qam", "toca vivo"], check=True)
        elif defecto == "codigo_vivo_sin_commitear":
            (raiz / "Source" / "vivo.cpp").write_text("int main(){return 2;}\n", encoding="utf-8")
        else:
            subprocess.run(["git", "-C", str(raiz), "commit", "-qam", "testigo"], check=True)

        mod = _cargar_relevo(raiz)
        _fm, fallas = mod.revisar_testigo()
        if not fallas:
            fallas = mod.verde_editor_vigente(mod.frontmatter(mod.TESTIGO))
        return hechos(raiz, mod), not fallas


def main() -> int:
    grupos: dict[str, list[dict]] = {m: [] for m in MEDIDAS}
    problemas = []

    for defecto in [None, *DEFECTOS]:
        h, jam_ok = _escenario(defecto)
        esperado = espera(h)
        if all(esperado.values()) != jam_ok:
            problemas.append(f"«{defecto or 'sin defecto'}»: relevo.py dice ok={jam_ok} y la "
                             f"conjunción de las medidas dice {all(esperado.values())}")
        for mid in MEDIDAS:
            grupos[mid].append({"evidencia": h, "esperado_ok": esperado[mid]})
        print(f"  {defecto or 'sin defecto':<26} relevo.py ok={jam_ok:<5} "
              f"rojas: {[m.split('.')[-1] for m, v in esperado.items() if not v] or '—'}")

    for mid, casos in grupos.items():
        verdes = sum(1 for c in casos if c["esperado_ok"])
        if verdes == 0 or verdes == len(casos):
            problemas.append(f"{mid}: {verdes}/{len(casos)} verdes — falta una polaridad")

    if problemas:
        print("\nNO SE ESCRIBE:")
        for p in problemas:
            print("  ·", p)
        return 1

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(
        {"origen": "Brianholl/jam · tools/relevo.py (revisar_testigo + verde_editor_vigente)",
         "mundos": len(DEFECTOS) + 1, "grupos": grupos}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print(f"\nescrito: {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
