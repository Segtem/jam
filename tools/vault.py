"""Verificador e índice del Vault-kb — la convención de nombres, comprobable.

    python tools/vault.py            → verifica (sale != 0 si algo está mal)
    python tools/vault.py --indice   → verifica y reescribe README.md

Comprueba tres cosas, que son las tres que se rompen solas:

  1. **el nombre** sigue `AAAA-MM-DD-TIPO-Nombre-vX.X.md`, con TIPO de la lista y Nombre en ASCII;
  2. **el frontmatter** trae `title`, `tipo`, `version`, `date`, `updated`, y su `tipo:` coincide con
     el del nombre de archivo — si no, el archivo dice una cosa y el doc otra;
  3. **todo wikilink resuelve** a un archivo que existe.

La 3 es la que importa: un vault con enlaces rotos se degrada en silencio, igual que un test que no
discrimina. Ver la guía de convención en el propio vault.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1] / "Vault-kb"
TIPOS = {"INFORME", "PLAN", "ROADMAP", "CONCEPTO", "GUIA", "ESTADO", "ADR"}
NOMBRE = re.compile(r"^(\d{4}-\d{2}-\d{2})-([A-Z]+)-(.+)-v(\d+\.\d+)$")
OBLIGATORIOS = ("title", "tipo", "version", "date", "updated")

# (título del grupo, predicado sobre el nombre de archivo) — el primero que matchea gana
GRUPOS = [
    ("Dirección y proceso", lambda n: "ROADMAP" in n or "GUIA-Convencion" in n or "Relevo" in n),
    ("TreeGen — el árbol procedural", lambda n: "TreeGen" in n),
    ("Graph — el editor de nodos", lambda n: any(
        k in n for k in ("Graph", "Estetica-Nodos", "Seleccion-Multiple", "Accesibilidad",
                         "Nodos-De-Debug", "Puente-P-a-F"))),
    ("Mesh y materiales", lambda n: any(
        k in n for k in ("Mesh", "Materiales", "Nanite", "Vertex-Color", "Oraculo-De-Forma"))),
    ("Ejecución, presets y pruebas", lambda n: True),
]


def docs() -> list[Path]:
    return sorted(p for p in VAULT.glob("*.md") if p.name != "README.md")


def frontmatter(ruta: Path) -> dict:
    texto = ruta.read_text(encoding="utf-8")
    if not texto.startswith("---\n") or "\n---\n" not in texto:
        return {}
    d = {}
    for linea in texto[4:texto.index("\n---\n", 4)].split("\n"):
        m = re.match(r"^(\w+):\s*(.*)$", linea)
        if m:
            d[m.group(1)] = m.group(2).strip().strip('"')
    return d


def verificar() -> list[str]:
    fallas: list[str] = []
    nombres = {p.stem for p in VAULT.glob("*.md")}

    for p in docs():
        m = NOMBRE.match(p.stem)
        if not m:
            fallas.append(f"{p.name}: no sigue AAAA-MM-DD-TIPO-Nombre-vX.X")
            continue
        fecha, tipo, cuerpo, _version = m.groups()

        if tipo not in TIPOS:
            fallas.append(f"{p.name}: TIPO «{tipo}» no está en {sorted(TIPOS)}")
        # el nombre de archivo viaja por git, terminal y wikilinks: ASCII o nada
        plano = unicodedata.normalize("NFKD", cuerpo).encode("ascii", "ignore").decode("ascii")
        if plano != cuerpo:
            fallas.append(f"{p.name}: el Nombre tiene acentos o caracteres no-ASCII")

        fm = frontmatter(p)
        faltan = [k for k in OBLIGATORIOS if k not in fm]
        if faltan:
            fallas.append(f"{p.name}: al frontmatter le faltan {faltan}")
            continue
        if fm["tipo"] != tipo:
            fallas.append(f"{p.name}: el archivo dice {tipo} y el frontmatter dice {fm['tipo']}")
        if fm["updated"] != fecha:
            fallas.append(f"{p.name}: la fecha del nombre ({fecha}) no es `updated:` ({fm['updated']})")

    for p in sorted(VAULT.glob("*.md")):
        for destino in enlaces(p.read_text(encoding="utf-8")):
            if destino not in nombres:
                fallas.append(f"{p.name}: enlace roto → [[{destino}]]")
    return fallas


def enlaces(texto: str) -> list[str]:
    """Destinos de los wikilinks REALES del documento.

    Dos cosas que no son enlaces y parecen:
      · lo que está en un bloque o span de código (`[[destino]]` como ejemplo en la guía);
      · la barra escapada `\\|`, obligatoria cuando el enlace va dentro de una tabla de Markdown —
        el destino termina en la barra, no en la contrabarra.
    Sin esto el verificador reporta roto lo que está bien, que es peor que no verificar: enseña a
    ignorarlo.
    """
    limpio = re.sub(r"```.*?```", "", texto, flags=re.S)
    limpio = re.sub(r"`[^`\n]*`", "", limpio)
    salida = []
    for enlace in re.findall(r"\[\[([^\]]+)\]\]", limpio):
        destino = enlace.split("|")[0].split("#")[0]
        salida.append(destino.rstrip("\\").strip())
    return salida


def escribir_indice() -> None:
    todos = docs()
    grupos: dict[str, list[Path]] = {t: [] for t, _ in GRUPOS}
    for p in todos:
        for titulo, pred in GRUPOS:
            if pred(p.name):
                grupos[titulo].append(p)
                break

    lineas = [
        "# Vault-kb de Jam",
        "",
        f"{len(todos)} documentos. Nomenclatura `AAAA-MM-DD-TIPO-Nombre-vX.X.md` — la explica",
        "[[2026-07-29-GUIA-Convencion-Documentacion-Vault-v1.0|la guía de convención]].",
        "Este índice y las reglas los verifica `tools/vault.py`.",
        "",
        "`INFORME` = lo que pasó · `PLAN` = lo que falta · `ROADMAP` = hacia dónde ·",
        "`CONCEPTO` = un principio · `GUIA` = cómo se usa.",
        "",
    ]
    for titulo, _ in GRUPOS:
        if not grupos[titulo]:
            continue
        lineas += [f"## {titulo}", ""]
        for p in sorted(grupos[titulo], key=lambda x: x.name, reverse=True):
            fm = frontmatter(p)
            estado = fm.get("status", "")
            lineas.append(f"- [[{p.stem}|{fm.get('title', p.stem)}]]"
                          + (f" · *{estado}*" if estado else ""))
        lineas.append("")
    (VAULT / "README.md").write_text("\n".join(lineas), encoding="utf-8")


def main() -> int:
    if "--indice" in sys.argv:
        escribir_indice()
    fallas = verificar()
    if fallas:
        print(f"VAULT: {len(fallas)} problema(s)")
        for f in fallas:
            print("  ·", f)
        return 1
    print(f"VAULT OK · {len(docs())} docs · nombres, frontmatter y wikilinks en regla")
    return 0


if __name__ == "__main__":
    sys.exit(main())
