"""El dominio `vault` de Jam, declarado. Genera su prueba diferencial contra `tools/vault.py`.

    python tools/emitir_hechos_vault.py

Acá vive **sólo lo particular de este dominio**: cómo se arma un vault de prueba, cómo se extraen sus
hechos, qué defectos se le pueden inyectar, y cuál es la implementación independiente contra la que se
contrasta. Todo lo demás —comprobar que el sensor y la referencia coincidan, exigir las dos
polaridades, escribir el fixture— lo pone `nucleo.dominio` de oracle.

Antes esto eran 193 líneas, y treinta eran una función `espera()` que reimplementaba las medidas en
Python para saber qué debería dar cada una. Ya no existe: el fixture guarda los hechos y el veredicto
de la referencia, que es la única información independiente que hay.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "vendor" / "oracle"))

from nucleo.diferencial import Procedencia           # noqa: E402
from nucleo.dominio import Dominio, generar          # noqa: E402
from nucleo.medida import cargar_catalogo            # noqa: E402
from nucleo.proyecto import (Proyecto, catalogos_a_cargar,  # noqa: E402
                             registrar_escalares)

PROYECTO = Proyecto(RAIZ / "medidas")
DESTINO = PROYECTO.diferencial / "vault.json"

NOMBRE = re.compile(r"^(\d{4}-\d{2}-\d{2})-([A-Z]+)-(.+)-v(\d+\.\d+)$")
TIPOS = {"INFORME", "PLAN", "ROADMAP", "CONCEPTO", "GUIA", "ESTADO", "ADR"}
CARPETAS = ("00-Proceso", "01-Graph", "02-TreeGen", "03-Mesh-y-materiales", "04-Ejecucion-y-pruebas")
_TEMPORALES: list[str] = []
PROCEDENCIA = Procedencia(
    raiz=RAIZ,
    emisor=("tools/emitir_hechos_vault.py",),
    referencia=("tools/vault.py", "Vault-kb"),
    desde_proyecto="..",
)


# ---- el SENSOR: hechos, sin un solo `if` que decida si algo está mal ----

def _frontmatter(texto: str) -> dict:
    if not texto.startswith("---\n") or "\n---\n" not in texto:
        return {}
    return {m.group(1): m.group(2).strip().strip('"')
            for m in (re.match(r"^(\w+):\s*(.*)$", l)
                      for l in texto[4:texto.index("\n---\n", 4)].split("\n")) if m}


def _enlaces(texto: str) -> list[str]:
    limpio = re.sub(r"`[^`\n]*`", "", re.sub(r"```.*?```", "", texto, flags=re.S))
    return [e.split("|")[0].split("#")[0].rstrip("\\").strip()
            for e in re.findall(r"\[\[([^\]]+)\]\]", limpio)]


def hechos(raiz: Path) -> dict:
    vault = raiz / "Vault-kb"
    nombres = {p.stem for p in vault.rglob("*.md")}
    docs = []
    for p in sorted(vault.rglob("*.md")):
        if p.name == "README.md":
            continue
        m = NOMBRE.match(p.stem)
        fm = _frontmatter(p.read_text(encoding="utf-8"))
        cuerpo = m.group(3) if m else ""
        plano = unicodedata.normalize("NFKD", cuerpo).encode("ascii", "ignore").decode("ascii")
        docs.append({
            "nombre": p.stem,
            "carpeta": p.parent.name if p.parent != vault else "",
            "sigue_convencion": bool(m) and m.group(2) in TIPOS,
            "tipo_en_nombre": m.group(2) if m else "",
            "tipo_declarado": fm.get("tipo", ""),
            "fecha_en_nombre": m.group(1) if m else "",
            "updated": fm.get("updated", ""),
            "area": fm.get("area", ""),
            "nombre_es_ascii": plano == cuerpo,
            "carpeta_conocida": (p.parent.name in CARPETAS) if p.parent != vault else False,
            "frontmatter_completo": all(
                k in fm for k in ("title", "tipo", "version", "date", "updated", "area")),
        })
    enlaces = [{"origen": p.stem, "destino": d, "resuelve": d in nombres}
               for p in sorted(vault.rglob("*.md"))
               for d in _enlaces(p.read_text(encoding="utf-8"))]
    return {"documento": docs, "enlace": enlaces}


# ---- los DEFECTOS: uno por medida, o la medida no queda fijada ----

DEFECTOS = {
    "nombre_roto": lambda p: p.rename(p.with_name("archivo-sin-convencion.md")),
    "tipo_distinto": lambda p: p.write_text(
        p.read_text(encoding="utf-8").replace("tipo: INFORME", "tipo: PLAN", 1), encoding="utf-8"),
    "fecha_distinta": lambda p: p.write_text(
        re.sub(r"^updated: .*$", "updated: 2020-01-01", p.read_text(encoding="utf-8"),
               count=1, flags=re.M), encoding="utf-8"),
    "area_distinta": lambda p: p.write_text(
        re.sub(r"^area: .*$", "area: 99-Inventada", p.read_text(encoding="utf-8"),
               count=1, flags=re.M), encoding="utf-8"),
    "enlace_roto": lambda p: p.write_text(
        p.read_text(encoding="utf-8") + "\n\n[[documento-que-no-existe]]\n", encoding="utf-8"),
    "nombre_con_acento": lambda p: p.rename(
        p.with_name(p.name.replace("INFORME-", "INFORME-Ación-", 1))),
    "suelto_en_la_raiz": lambda p: shutil.copy(p, p.parents[1] / p.name),
    "carpeta_inventada": lambda p: ((p.parents[1] / "99-Inventada").mkdir(exist_ok=True),
                                    shutil.move(str(p), str(p.parents[1] / "99-Inventada" / p.name))),
    "nombre_duplicado": lambda p: shutil.copy(p, p.parents[1] / "02-TreeGen" / p.name),
    "frontmatter_incompleto": lambda p: p.write_text(
        re.sub(r"^version: .*$\n", "", p.read_text(encoding="utf-8"), count=1, flags=re.M),
        encoding="utf-8"),
}


def montar(defecto: str | None, i: int = 0) -> Path:
    """Copia el vault y su verificador a un temporal, y aplica el defecto si hay."""
    raiz = Path(tempfile.mkdtemp())
    _TEMPORALES.append(str(raiz))
    (raiz / "tools").mkdir()
    shutil.copy(RAIZ / "tools" / "vault.py", raiz / "tools" / "vault.py")
    shutil.copytree(RAIZ / "Vault-kb", raiz / "Vault-kb")
    if defecto:
        DEFECTOS[defecto](next((raiz / "Vault-kb" / "01-Graph").glob("*INFORME*.md")))
    return raiz


def referencia(raiz: Path) -> bool:
    """La implementación INDEPENDIENTE: el verificador escrito a mano, corrido de verdad."""
    return subprocess.run([sys.executable, "tools/vault.py"], cwd=str(raiz),
                          capture_output=True, text=True).returncode == 0


VAULT = Dominio(
    nombre="vault", montar=montar, hechos=hechos, referencia=referencia,
    defectos=tuple(DEFECTOS),
    descripcion="Brianholl/jam · tools/vault.py (verificador escrito a mano)")


def main() -> int:
    registrar_escalares(PROYECTO)
    catalogo = cargar_catalogo(catalogos_a_cargar(PROYECTO))
    medidas = [m for k, m in catalogo.items() if k.startswith("vault.")]
    try:
        fixture = generar(VAULT, medidas, procedencia=PROCEDENCIA)
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
