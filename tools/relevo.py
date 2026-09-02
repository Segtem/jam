"""El relevo entre Claude Code y Codex — el turno, comprobable.

    python tools/relevo.py            → LLEGADA: ¿está verde lo que recibo?
    python tools/relevo.py --cerrar   → SALIDA: el ritual de soltar el testigo

Dos agentes se turnan el proyecto cada 3-4 días y **ninguno recuerda el turno del otro**. Un
protocolo escrito en prosa se degrada en dos turnos, igual que un test que no discrimina. Así que el
protocolo es un comando.

`--cerrar` **se niega a bendecir un relevo rojo**. Comprueba, en este orden:

  1. el **testigo** (`RELEVO.md`) está bien formado y nombra a quién entra;
  2. los **tests** pasan;
  3. el **vault** está en regla;
  4. el **diferencial de Oracle** está vigente y sin desacuerdos;
  5. el árbol está **limpio** y **empujado** — el que entra clona, no adivina;
  6. la **verificación con motor sigue vigente**: `verde_editor` apunta a un commit real y desde ahí
     **no se tocó el runtime C++/Python** (`Source/`, `init_unreal.py`, `jam/` u `oraculo/`). Ésta es
     la que importa. Sin ella se puede soltar un turno entero de código que nadie probó en el motor,
     y el que entra construye encima.

Recién entonces marca el turno con un tag `relevo/AAAA-MM-DD-<saliente>`, que es lo que le permite
al que entra ver el turno ajeno con `git log` en vez de leerlo en prosa.

Lo que NO comprueba, porque no puede: que los gestos de Slate funcionen. Eso lo prueba Brian con las
manos, y por eso el testigo tiene una sección aparte para lo que quedó sin verificar.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TESTIGO = RAIZ / "RELEVO.md"

AGENTES = {"claude-code", "codex"}
CAMPOS = ("turno", "saliente", "entrante", "desde", "verde_editor", "verde_editor_fecha")
SECCIONES = (
    "## Verde al soltar",
    "## Frontera de verificación",
    "## Para las manos de Brian",
    "## Lo próximo",
    "## No toques esto",
    "## Lo que aprendí este turno",
)
# Lo que cambia el comportamiento del editor; tocarlo invalida la verificación con motor.
# `oraculo/` entra porque el plugin lo IMPORTA (`jam.nivel`, `jam.oracle_espacio` cuelgan de
# `oraculo.mazes.spacegraph`): quedaba afuera y una edición ahí pasaba como si no fuera código vivo.
VIVO = ("Source", "Content/Python/init_unreal.py", "Content/Python/jam", "oraculo")


def git(*args: str) -> str:
    r = subprocess.run(["git", "-C", str(RAIZ), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def frontmatter(ruta: Path) -> dict:
    texto = ruta.read_text(encoding="utf-8")
    if not texto.startswith("---\n") or "\n---\n" not in texto:
        return {}
    d = {}
    for linea in texto[4:texto.index("\n---\n", 4)].split("\n"):
        m = re.match(r"^(\w+):\s*(.*)$", linea)
        if m:
            d[m.group(1)] = m.group(2).strip().strip('"').split("#")[0].strip()
    return d


def revisar_testigo() -> tuple[dict, list[str]]:
    """El testigo se lee entero de una sentada o no se lee: forma fija, corto, siempre el mismo."""
    if not TESTIGO.exists():
        return {}, ["no existe RELEVO.md en la raíz — el testigo es un archivo, no una conversación"]

    fallas: list[str] = []
    fm = frontmatter(TESTIGO)
    texto = TESTIGO.read_text(encoding="utf-8")

    faltan = [k for k in CAMPOS if k not in fm]
    if faltan:
        return fm, [f"al frontmatter de RELEVO.md le faltan {faltan}"]

    for rol in ("saliente", "entrante"):
        if fm[rol] not in AGENTES:
            fallas.append(f"{rol}: «{fm[rol]}» no está en {sorted(AGENTES)}")
    if fm["saliente"] == fm["entrante"]:
        fallas.append("saliente y entrante son el mismo — un relevo tiene dos puntas")

    for s in SECCIONES:
        if s not in texto:
            fallas.append(f"falta la sección «{s}»")

    return fm, fallas


def verde_editor_vigente(fm: dict) -> list[str]:
    """¿La verificación con motor sigue hablando del código que hay?

    Un «corrió verde» es una foto con fecha. Si después se tocó el C++ o el cerebro, la foto es de
    otro código y afirmarla es mentir. Los commits de documentación no la invalidan: por eso se mira
    QUÉ cambió, no CUÁNTO.
    """
    sha = fm["verde_editor"]
    if not git("cat-file", "-t", sha):
        return [f"verde_editor: el commit {sha} no existe"]
    # `--is-ancestor` no imprime nada: contesta por código de salida, no por stdout
    ancestro = subprocess.run(
        ["git", "-C", str(RAIZ), "merge-base", "--is-ancestor", sha, "HEAD"],
        capture_output=True,
    ).returncode == 0
    if not ancestro:
        return [f"verde_editor: {sha} no es antecesor de HEAD"]

    # Lo commiteado desde la foto, MÁS lo que está sin commitear: mirar sólo el historial daba
    # «verde» con el código vivo modificado en el árbol de trabajo, que es justo cuando más miente.
    tocado = [f for f in git("diff", "--name-only", f"{sha}..HEAD", "--", *VIVO).split("\n") if f]
    sucio = [f for f in git("status", "--porcelain", "--", *VIVO).split("\n") if f]
    if tocado or sucio:
        detalle = (f"{len(tocado)} archivo(s) commiteados" if tocado else "")
        detalle += (" y " if tocado and sucio else "") + (f"{len(sucio)} sin commitear" if sucio else "")
        # porcelain es `XY ruta`, y la X puede ser un espacio: cortar en 3 se comía una letra
        ejemplo = (tocado or [s[2:].strip() for s in sucio])[0]
        return [
            f"verde_editor ({sha}, {fm['verde_editor_fecha']}) quedó VIEJO: cambiaron {detalle}, "
            f"p.ej. {ejemplo}. Volvé a correr la verificación con motor y actualizá el campo."
        ]
    return []


def correr(nombre: str, cmd: list[str], cwd: Path, env_extra: dict | None = None) -> list[str]:
    import os
    env = {**os.environ, **(env_extra or {})}
    r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=env)
    if r.returncode != 0:
        cola = (r.stdout + r.stderr).strip().split("\n")[-6:]
        return [f"{nombre} en ROJO:\n      " + "\n      ".join(cola)]
    return []


def tests() -> list[str]:
    return correr(
        "los tests",
        [sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py", "-q"],
        RAIZ / "Content" / "Python" / "tests",
        {"PYTHONPATH": str(RAIZ / "Content" / "Python")},
    )


def vault() -> list[str]:
    return correr("el vault", [sys.executable, "tools/vault.py"], RAIZ)


def oracle_diferencial() -> list[str]:
    """Exige fixtures vigentes además de acuerdo: un diferencial viejo no es evidencia.

    Oracle se instala desde PyPI (`uv tool install oracle-metalenguaje`), así que el comando
    viene del PATH y no de un archivo del repo. Si falta, se dice cómo traerlo: un relevo que
    se cae con un traceback no informa nada.
    """
    import shutil
    if shutil.which("oracle-diferencial") is None:
        return ["el diferencial de Oracle en ROJO:\n      "
                "falta el comando `oracle-diferencial` en el PATH — "
                "instalalo con `uv tool install oracle-metalenguaje` (ver AGENTS.md)"]
    return correr(
        "el diferencial de Oracle",
        ["oracle-diferencial", "--proyecto", "medidas", "--confiar-escalares"],
        RAIZ,
    )


def arbol_limpio_y_empujado() -> list[str]:
    fallas = []
    if git("status", "--porcelain"):
        fallas.append("el árbol tiene cambios sin commitear — el que entra clona, no adivina")
    rama = git("rev-parse", "--abbrev-ref", "HEAD")
    remoto = git("rev-parse", f"origin/{rama}")
    if not remoto:
        fallas.append(f"no hay origin/{rama} — el turno tiene que quedar empujado")
    elif remoto != git("rev-parse", "HEAD"):
        fallas.append(f"HEAD != origin/{rama} — falta empujar")
    return fallas


def tags_de_relevo() -> list[str]:
    t = git("tag", "-l", "relevo/*", "--sort=creatordate")
    return t.split("\n") if t else []


def abrir() -> int:
    fm, fallas = revisar_testigo()
    if fallas:
        print("TESTIGO ILEGIBLE:")
        for f in fallas:
            print("  ·", f)
        return 1

    print(f"TURNO · {fm['turno']}")
    print(f"  entra {fm['entrante']} — soltó {fm['saliente']} el {fm['desde']}")

    previos = tags_de_relevo()
    if previos:
        cuantos = git("rev-list", "--count", f"{previos[-1]}..HEAD")
        print(f"  el turno anterior ({previos[-1]}) dejó {cuantos or '0'} commits:")
        print(f"    git log {previos[-1]}..HEAD --oneline")

    problemas = tests() + vault() + oracle_diferencial() + verde_editor_vigente(fm)
    if problemas:
        print("\nLLEGÓ EN ROJO — esto es lo primero del turno, antes que el roadmap:")
        for p in problemas:
            print("  ·", p)
        return 1

    print("\nLLEGÓ VERDE · tests, vault, Oracle diferencial y verificación con motor vigente")
    print("Leé RELEVO.md entero antes de tocar nada — sobre todo «No toques esto».")
    return 0


def cerrar() -> int:
    fm, fallas = revisar_testigo()
    if fallas:
        print("NO SE SUELTA — el testigo no está en forma:")
        for f in fallas:
            print("  ·", f)
        return 1

    problemas = (arbol_limpio_y_empujado() + tests() + vault() + oracle_diferencial()
                 + verde_editor_vigente(fm))
    if problemas:
        print("NO SE SUELTA — no se bendice un relevo rojo:")
        for p in problemas:
            print("  ·", p)
        return 1

    tag = f"relevo/{date.today().isoformat()}-{fm['saliente']}"
    # el tag marca DÓNDE terminó el turno: si se cierra dos veces el mismo día, se mueve al final,
    # o el que entra leería `git log <tag>..HEAD` de menos y se perdería trabajo ajeno
    movido = tag in tags_de_relevo() and git("rev-list", "-n1", tag) != git("rev-parse", "HEAD")
    subprocess.run(["git", "-C", str(RAIZ), "tag", "-f", "-a", tag,
                    "-m", f"Relevo: {fm['saliente']} → {fm['entrante']}"],
                   check=True, capture_output=True)
    print(f"RELEVO OK · tag {tag} {'movido al final del turno' if movido else 'creado'}")

    print(f"  falta una sola cosa:  git push origin {tag}")
    print(f"  entra {fm['entrante']}: que corra `python tools/relevo.py` al empezar.")
    return 0


def main() -> int:
    return cerrar() if "--cerrar" in sys.argv else abrir()


if __name__ == "__main__":
    sys.exit(main())
