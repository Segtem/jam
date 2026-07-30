"""Emite los HECHOS del vault, y la prueba diferencial contra `tools/vault.py`.

    python tools/emitir_hechos_vault.py

`tools/vault.py` es un verificador escrito a mano: seis reglas en ramas `if`. Este script mira lo
mismo pero **no juzga**: produce relaciones planas (`documento`, `enlace`), que es lo que un sensor
debe hacer. Las reglas viven en `oracle`, como medidas declaradas con su umbral, su defensa y su
punto ciego.

Para que el reemplazo sea verificable y no un acto de fe, además genera casos con **un defecto
inyectado de cada tipo**: copia el vault a un temporal, lo rompe, corre `vault.py` ahí, y anota su
veredicto. El emisor se niega a escribir si su expectativa por medida no coincide con el veredicto
global del verificador de verdad.
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
DESTINO = Path.home() / "Dev" / "oracle" / "diferencial" / "vault.json"

NOMBRE = re.compile(r"^(\d{4}-\d{2}-\d{2})-([A-Z]+)-(.+)-v(\d+\.\d+)$")
TIPOS = {"INFORME", "PLAN", "ROADMAP", "CONCEPTO", "GUIA", "ESTADO", "ADR"}
CARPETAS = ("00-Proceso", "01-Graph", "02-TreeGen", "03-Mesh-y-materiales", "04-Ejecucion-y-pruebas")

MEDIDAS = ("vault.nombre_sigue_la_convencion", "vault.tipo_coincide", "vault.fecha_coincide",
           "vault.area_es_la_carpeta", "vault.nombre_es_ascii", "vault.enlace_resuelve")


def _frontmatter(texto: str) -> dict:
    if not texto.startswith("---\n") or "\n---\n" not in texto:
        return {}
    d = {}
    for linea in texto[4:texto.index("\n---\n", 4)].split("\n"):
        m = re.match(r"^(\w+):\s*(.*)$", linea)
        if m:
            d[m.group(1)] = m.group(2).strip().strip('"')
    return d


def _enlaces(texto: str) -> list[str]:
    limpio = re.sub(r"```.*?```", "", texto, flags=re.S)
    limpio = re.sub(r"`[^`\n]*`", "", limpio)
    return [e.split("|")[0].split("#")[0].rstrip("\\").strip()
            for e in re.findall(r"\[\[([^\]]+)\]\]", limpio)]


def hechos(vault: Path) -> dict:
    """Relaciones planas. Sin juicio: acá no hay ningún `if` que decida si algo está mal."""
    nombres = {p.stem for p in vault.rglob("*.md")}
    docs, enlaces = [], []

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
            "sigue_convencion": bool(m) and (m.group(2) in TIPOS if m else False),
            "tipo_en_nombre": m.group(2) if m else "",
            "tipo_declarado": fm.get("tipo", ""),
            "fecha_en_nombre": m.group(1) if m else "",
            "updated": fm.get("updated", ""),
            "area": fm.get("area", ""),
            "nombre_es_ascii": plano == cuerpo,
        })

    for p in sorted(vault.rglob("*.md")):
        for destino in _enlaces(p.read_text(encoding="utf-8")):
            enlaces.append({"origen": p.stem, "destino": destino, "resuelve": destino in nombres})

    return {"documento": docs, "enlace": enlaces}


def espera(h: dict) -> dict:
    """Qué debería decir cada medida sobre estos hechos. Se CONTRASTA contra `vault.py`."""
    d, e = h["documento"], h["enlace"]
    return {
        "vault.nombre_sigue_la_convencion": all(x["sigue_convencion"] for x in d),
        "vault.tipo_coincide": all(x["tipo_en_nombre"] == x["tipo_declarado"] for x in d),
        "vault.fecha_coincide": all(x["fecha_en_nombre"] == x["updated"] for x in d),
        "vault.area_es_la_carpeta": all(x["area"] == x["carpeta"] for x in d),
        "vault.nombre_es_ascii": all(x["nombre_es_ascii"] for x in d),
        "vault.enlace_resuelve": all(x["resuelve"] for x in e),
    }


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
    # sin este defecto, `vault.nombre_es_ascii` quedaba con una sola polaridad y no fijaba nada
    "nombre_con_acento": lambda p: p.rename(
        p.with_name(p.name.replace("INFORME-", "INFORME-Ación-", 1))),
}


def _copia_y_rompe(defecto: str | None) -> tuple[dict, bool]:
    """Copia vault + verificador a un temporal, aplica el defecto, y corre el verificador REAL."""
    with tempfile.TemporaryDirectory() as d:
        raiz = Path(d)
        (raiz / "tools").mkdir()
        shutil.copy(RAIZ / "tools" / "vault.py", raiz / "tools" / "vault.py")
        shutil.copytree(RAIZ / "Vault-kb", raiz / "Vault-kb")

        if defecto:
            objetivo = next((raiz / "Vault-kb" / "01-Graph").glob("*INFORME*.md"))
            DEFECTOS[defecto](objetivo)

        r = subprocess.run([sys.executable, "tools/vault.py"], cwd=str(raiz),
                           capture_output=True, text=True)
        return hechos(raiz / "Vault-kb"), r.returncode == 0


def main() -> int:
    grupos: dict[str, list[dict]] = {m: [] for m in MEDIDAS}
    problemas = []

    for defecto in [None, *DEFECTOS]:
        h, jam_ok = _copia_y_rompe(defecto)
        esperado = espera(h)
        # el amarre: mi expectativa por medida tiene que dar lo mismo que el verificador de verdad
        if all(esperado.values()) != jam_ok:
            problemas.append(f"«{defecto or 'sin defecto'}»: vault.py dice ok={jam_ok} y la "
                             f"conjunción de las medidas dice {all(esperado.values())}")
        for mid in MEDIDAS:
            grupos[mid].append({"evidencia": h, "esperado_ok": esperado[mid]})
        print(f"  {defecto or 'sin defecto':<16} vault.py ok={jam_ok:<5} "
              f"medidas en rojo: {[m for m, v in esperado.items() if not v] or '—'}")

    # la misma guarda que el emisor de geometría: sin las dos polaridades la medida no se fija
    for mid, casos in grupos.items():
        verdes = sum(1 for c in casos if c["esperado_ok"])
        if verdes == 0 or verdes == len(casos):
            problemas.append(f"{mid}: {verdes}/{len(casos)} verdes — falta una polaridad, "
                             f"hay que inyectar un defecto que la active")

    if problemas:
        print("\nNO SE ESCRIBE — el sensor y el verificador no coinciden:")
        for p in problemas:
            print("  ·", p)
        return 1

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(
        {"origen": "Brianholl/jam · tools/vault.py (verificador escrito a mano)",
         "mundos": len(DEFECTOS) + 1, "grupos": grupos}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print(f"\nescrito: {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
