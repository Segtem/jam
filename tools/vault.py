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

## Modo sombra (migración a `oracle`)

Las mismas reglas están re-expresadas como **diez medidas declaradas** en
`vendor/oracle/catalogos/vault/`, con su umbral, su defensa y —lo que este archivo nunca pudo decir—
**su punto ciego**. Mientras dure la migración se calculan LOS DOS veredictos y se comparan: si
difieren, esto sale con código 2 y no deja pasar nada. Un reemplazo que se declara sin comparar es un
acto de fe.

El informe que se imprime es el del oráculo, porque enumera lo que NO mira. Las reglas de acá siguen
siendo la referencia hasta que el diferencial lleve tiempo en verde.

Si el vendor no está disponible (una copia suelta de este archivo, por ejemplo), la sombra se saltea
y se dice: el verificador a mano tiene que seguir funcionando solo.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1] / "Vault-kb"
TIPOS = {"INFORME", "PLAN", "ROADMAP", "CONCEPTO", "GUIA", "ESTADO", "ADR"}
NOMBRE = re.compile(r"^(\d{4}-\d{2}-\d{2})-([A-Z]+)-(.+)-v(\d+\.\d+)$")
OBLIGATORIOS = ("title", "tipo", "version", "date", "updated", "area")

# La CARPETA es la taxonomía: un documento vive en una y sólo una, y su `area:` lo dice.
# Antes esto era una heurística de palabras clave sobre el nombre; la carpeta es un dato.
CARPETAS = {
    "00-Proceso": "Proceso y dirección",
    "01-Graph": "Graph — el editor de nodos",
    "02-TreeGen": "TreeGen — el árbol procedural",
    "03-Mesh-y-materiales": "Mesh y materiales",
    "04-Ejecucion-y-pruebas": "Ejecución, presets y pruebas",
}


def docs() -> list[Path]:
    return sorted(p for p in VAULT.rglob("*.md") if p.name != "README.md")


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
    nombres = {p.stem for p in VAULT.rglob("*.md")}

    # un wikilink apunta por NOMBRE, no por ruta: dos archivos homónimos en carpetas distintas
    # dejan el enlace a cara o cruz, y el verificador lo daría por bueno
    vistos: dict[str, Path] = {}
    for p in docs():
        if p.stem in vistos:
            fallas.append(f"{p.stem}: el mismo nombre en dos carpetas "
                          f"({vistos[p.stem].parent.name} y {p.parent.name})")
        vistos[p.stem] = p

    for p in sorted(VAULT.glob("*.md")):
        if p.name != "README.md":
            fallas.append(f"{p.name}: suelto en la raíz del vault — va en una de {list(CARPETAS)}")

    for p in docs():
        carpeta = p.parent.name
        if p.parent == VAULT or carpeta not in CARPETAS:
            fallas.append(f"{p.name}: vive en «{carpeta}», que no es una carpeta del vault")
            continue

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
        if fm["area"] != carpeta:
            fallas.append(f"{p.name}: está en {carpeta} y su `area:` dice {fm['area']}")

    for p in sorted(VAULT.rglob("*.md")):
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
    lineas = [
        "# Vault-kb de Jam",
        "",
        f"{len(todos)} documentos en {len(CARPETAS)} carpetas. Nomenclatura",
        "`AAAA-MM-DD-TIPO-Nombre-vX.X.md` — la explica",
        "[[2026-07-29-GUIA-Convencion-Documentacion-Vault-v1.0|la guía de convención]].",
        "La carpeta es la taxonomía: cada doc vive en una sola y su `area:` lo dice.",
        "Este índice y las reglas los verifica `tools/vault.py`.",
        "",
        "`INFORME` = lo que pasó · `PLAN` = lo que falta · `ROADMAP` = hacia dónde ·",
        "`CONCEPTO` = un principio · `GUIA` = cómo se usa.",
        "",
    ]
    for carpeta, titulo in CARPETAS.items():
        dentro = [p for p in todos if p.parent.name == carpeta]
        if not dentro:
            continue
        lineas += [f"## {titulo}", "", f"`{carpeta}/` · {len(dentro)} documentos", ""]
        for p in sorted(dentro, key=lambda x: x.name, reverse=True):
            fm = frontmatter(p)
            estado = fm.get("status", "")
            lineas.append(f"- [[{p.stem}|{fm.get('title', p.stem)}]]"
                          + (f" · *{estado}*" if estado else ""))
        lineas.append("")
    (VAULT / "README.md").write_text("\n".join(lineas), encoding="utf-8")


def veredicto_del_oraculo():
    """(informe, None) con las medidas del vendor, o (None, motivo) si no se puede calcular.

    Nunca levanta: el verificador a mano tiene que seguir funcionando aunque el vendor falte.
    """
    try:
        raiz = VAULT.parent
        sys.path.insert(0, str(raiz / "vendor" / "oracle"))
        sys.path.insert(0, str(raiz / "tools"))
        import catalogos  # noqa: F401  registra las escalares declaradas
        from emitir_hechos_vault import hechos
        from nucleo.medida import cargar_catalogo, evaluar

        medidas = [m for k, m in cargar_catalogo(raiz / "vendor" / "oracle" / "catalogos").items()
                   if k.startswith("vault.")]
        return evaluar(medidas, hechos(VAULT)), None
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def main() -> int:
    if "--indice" in sys.argv:
        escribir_indice()
    fallas = verificar()
    a_mano_ok = not fallas
    informe, motivo = veredicto_del_oraculo()

    # La comparación es el punto de la migración: dos implementaciones que no coinciden significan
    # que una de las dos miente, y no se sabe cuál.
    if informe is not None and informe.ok != a_mano_ok:
        print("VAULT ✗✗ — LOS DOS VERIFICADORES NO COINCIDEN, y eso es peor que cualquier falla")
        print(f"  a mano: {'ok' if a_mano_ok else f'{len(fallas)} problema(s)'}")
        print(f"  oráculo: {'ok' if informe.ok else 'rojo'}")
        print("\n" + informe.texto())
        for f in fallas:
            print("  ·", f)
        return 2

    if fallas:
        print(f"VAULT: {len(fallas)} problema(s)")
        for f in fallas:
            print("  ·", f)
        if informe is not None:
            print("\n" + informe.texto())
        return 1

    if informe is None:
        print(f"VAULT OK · {len(docs())} docs · nombres, frontmatter y wikilinks en regla")
        print(f"  (sin sombra del oráculo: {motivo})")
        return 0

    print(f"VAULT OK · {len(docs())} docs · las dos implementaciones coinciden\n")
    print(informe.texto())
    return 0


if __name__ == "__main__":
    sys.exit(main())
