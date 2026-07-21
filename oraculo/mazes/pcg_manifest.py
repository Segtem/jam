"""Manifest de FABRICACIÓN de JamPCG + GAP-REPORT — el lado OFERTA de la curaduría de assets. Ver [[jampcg-dsl-direction]].

El vocabulario (`pcg_vocab`) cerró la DEMANDA (qué tags/salas/espacios pide el DSL). Este módulo es la OFERTA: la
fuente de verdad de BINDINGS (tag semántico → asset concreto, POR MOTOR, con su LICENCIA) y el cruce demanda×oferta
que te dice qué falta conseguir/hacer.

Distinción clave (la que Brian tiene mapeada, [[capa2-edicion-y-props-libreria]] / [[umodel-extraccion-votv]]):
un asset EXTRAÍDO con copyright (VotV/HL2 vía umodel) es PLACEHOLDER — sirve para iterar el look, NO es shippable;
lo shippable es CC0 (o licencia libre con atribución). El gap-report separa 'tengo placeholder, necesito CC0' de
'no tengo nada' — y además caza los huecos de PARIDAD (bindeado en un motor pero no en el otro).

El manifest se carga desde `assets/pcg_manifest.json` (curable, diff-able). `binding_for` lo baja a un `AssetBinding`
(lo que consumen los receptores Godot/UE); `shippable_only=True` deja fuera los placeholders (build de release).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.mazes.pcg_vocab import SPACES, known_prop_tags, known_room_types

# Licencias que un build SHIPPABLE puede usar (el resto = placeholder / copyright / desconocida → no shippable).
SHIPPABLE_LICENSES = {"CC0", "CC-BY", "CC-BY-SA", "public-domain"}

_DEFAULT_MANIFEST = Path(__file__).resolve().parents[2] / "assets/pcg_manifest.json"
ENGINES = ("godot", "unreal")


def is_shippable(license: str | None) -> bool:
    """¿La licencia habilita un build de RELEASE? (CC0/libre sí; 'placeholder'/copyright/None no)."""
    return license in SHIPPABLE_LICENSES


@dataclass(frozen=True)
class AssetRef:
    """Un asset CONCRETO bindeado a un tag en UN motor, con su licencia. `asset` = ref del motor
    (`res://…`, `/Game/…`); `license` = 'CC0' | 'CC-BY' | 'placeholder' | …"""
    asset: str
    license: str

    @property
    def shippable(self) -> bool:
        return is_shippable(self.license)


@dataclass(frozen=True)
class AssetEntry:
    """Entrada del manifest para UN tag semántico: sus refs por motor (paridad = idealmente ambos) + procedencia."""
    key: str
    kind: str                                   # "prop" | "material"
    refs: dict[str, AssetRef] = field(default_factory=dict)   # motor → AssetRef
    source: str | None = None


@dataclass
class Manifest:
    """La OFERTA curada: bindings por tag de prop y por tipo de sala (material). Fuente de verdad, motor-agnóstica
    en la clave (el tag), motor-específica en el asset (cada motor su ref). Se serializa a/desde JSON."""
    props: dict[str, AssetEntry] = field(default_factory=dict)
    materials: dict[str, AssetEntry] = field(default_factory=dict)


# ── carga / guardado (JSON curable) ──
def _entry_from_json(key: str, kind: str, raw: dict) -> AssetEntry:
    refs = {eng: AssetRef(asset=r["asset"], license=r.get("license", "unknown"))
            for eng, r in raw.items() if eng in ENGINES and isinstance(r, dict) and r.get("asset")}
    return AssetEntry(key=key, kind=kind, refs=refs, source=raw.get("source"))


def load_manifest(path: str | Path = _DEFAULT_MANIFEST) -> Manifest:
    """Lee el manifest JSON. Las claves que empiezan con '_' (ej. `_meta`) se ignoran. Manifest vacío si no existe."""
    p = Path(path)
    if not p.is_file():
        return Manifest()
    data = json.loads(p.read_text(encoding="utf-8"))
    props = {k: _entry_from_json(k, "prop", v) for k, v in data.get("props", {}).items() if not k.startswith("_")}
    materials = {k: _entry_from_json(k, "material", v)
                 for k, v in data.get("materials", {}).items() if not k.startswith("_")}
    return Manifest(props=props, materials=materials)


def _entry_to_json(entry: AssetEntry) -> dict:
    out: dict[str, Any] = {eng: {"asset": r.asset, "license": r.license} for eng, r in sorted(entry.refs.items())}
    if entry.source:
        out["source"] = entry.source
    return out


def save_manifest(manifest: Manifest, path: str | Path = _DEFAULT_MANIFEST) -> None:
    """Serializa el manifest a JSON (orden canónico → diffs limpios). Preserva un `_meta` si el archivo ya lo tenía."""
    p = Path(path)
    meta = {}
    if p.is_file():
        meta = json.loads(p.read_text(encoding="utf-8")).get("_meta", {})
    data: dict[str, Any] = {}
    if meta:
        data["_meta"] = meta
    data["props"] = {k: _entry_to_json(manifest.props[k]) for k in sorted(manifest.props)}
    data["materials"] = {k: _entry_to_json(manifest.materials[k]) for k in sorted(manifest.materials)}
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ── manifest → AssetBinding (lo que consumen los receptores) ──
def binding_for(manifest: Manifest, engine: str, *, shippable_only: bool = False) -> "Any":
    """Baja el manifest a un `AssetBinding` de un motor: {tag→asset} para props, {tipo→asset} para materiales.
    `shippable_only`=True descarta los placeholders (build de RELEASE = sólo CC0/libre). Los tags sin ref para ese
    motor simplemente no entran (los caza `fabricate` como `missing_*`, no rompe)."""
    from src.mazes.pcg import AssetBinding

    def pick(entries: dict[str, AssetEntry]) -> dict[str, str]:
        out: dict[str, str] = {}
        for key, entry in entries.items():
            ref = entry.refs.get(engine)
            if ref is None:
                continue
            if shippable_only and not ref.shippable:
                continue
            out[key] = ref.asset
        return out

    return AssetBinding(props=pick(manifest.props), materials=pick(manifest.materials))


# ── GAP-REPORT: cruce DEMANDA (vocabulario) × OFERTA (manifest) ──
def _status(entry: AssetEntry | None, engine: str) -> str:
    """Estado de un tag en un motor: 'ready' (ref shippable) | 'placeholder' (ref no-shippable) | 'missing' (sin ref)."""
    ref = entry.refs.get(engine) if entry else None
    if ref is None:
        return "missing"
    return "ready" if ref.shippable else "placeholder"


def _bucket(entry: AssetEntry | None, engines: tuple[str, ...]) -> str:
    """Triage de un tag sobre TODOS los motores (paridad): 'missing' si falta en alguno (no fabricable/hueco de
    paridad); si no, 'placeholder' si alguno es placeholder (hay que conseguir el CC0); si no, 'ready'."""
    per = [_status(entry, e) for e in engines]
    if "missing" in per:
        return "missing"
    if "placeholder" in per:
        return "placeholder"
    return "ready"


def _report_kind(demand: set[str], offer: dict[str, AssetEntry], engines: tuple[str, ...]) -> dict[str, Any]:
    buckets: dict[str, list[str]] = {"ready": [], "placeholder": [], "missing": []}
    detail: dict[str, dict[str, str]] = {}
    paridad_gap: list[str] = []
    for key in sorted(demand):
        entry = offer.get(key)
        per = {e: _status(entry, e) for e in engines}
        detail[key] = per
        buckets[_bucket(entry, engines)].append(key)
        present = [e for e in engines if per[e] != "missing"]
        if 0 < len(present) < len(engines):        # bindeado en un motor pero no en todos = hueco de PARIDAD
            paridad_gap.append(key)
    total = len(demand)
    return {
        **buckets, "paridad_gap": paridad_gap, "detail": detail,
        "summary": {"ready": len(buckets["ready"]), "placeholder": len(buckets["placeholder"]),
                    "missing": len(buckets["missing"]), "total": total},
    }


def gap_report(manifest: Manifest, *, engines: tuple[str, ...] = ENGINES,
               spaces: list[str] | None = None) -> dict[str, Any]:
    """Cruza la DEMANDA del vocabulario con la OFERTA del manifest → qué falta, para curar. `spaces`=None → todo el
    vocabulario; si se pasa, sólo los tags/salas propios de esos espacios (curaduría dirigida, ej. 'primero el hospital').

    Buckets por tag (triage sobre todos los motores): `ready` (CC0/libre en todos), `placeholder` ('tengo pero necesito
    CC0'), `missing` ('no tengo nada' en al menos un motor). `paridad_gap` = bindeado en un motor y no en el otro."""
    if spaces:
        prop_demand: set[str] = set()
        room_demand: set[str] = set()
        for s in spaces:
            st = SPACES.get(s)
            if st:
                prop_demand |= set(st.props)
                room_demand |= set(st.room_types)
    else:
        prop_demand, room_demand = known_prop_tags(), known_room_types()
    # los tags PROCEDURALES (el receptor fabrica su visual: pipe_vertical, como los cables) no son gap de
    # curaduría → fuera de la demanda (si algún día se les bindea un mesh, el binding gana igual)
    from src.mazes.pcg_vocab import PROP_TAGS
    prop_demand = {t for t in prop_demand if not (t in PROP_TAGS and PROP_TAGS[t].procedural)}
    return {
        "engines": list(engines),
        "spaces": spaces or "all",
        "props": _report_kind(prop_demand, manifest.props, engines),
        "materials": _report_kind(room_demand, manifest.materials, engines),
    }


def format_gap_report(report: dict[str, Any]) -> str:
    """Render de terminal del gap-report = la LISTA DE COMPRAS: qué está listo (CC0), qué es placeholder (conseguir
    CC0) y qué falta del todo, por props y por materiales, con los huecos de paridad marcados."""
    lines = [f"gap-report  espacios={report['spaces']}  motores={','.join(report['engines'])}"]
    for kind in ("props", "materials"):
        k = report[kind]
        s = k["summary"]
        lines.append(f"\n{kind.upper()}  ready={s['ready']} placeholder={s['placeholder']} "
                     f"missing={s['missing']} / total={s['total']}")
        if k["ready"]:
            lines.append(f"  ✓ listos (CC0):        {', '.join(k['ready'])}")
        if k["placeholder"]:
            lines.append(f"  ~ placeholder→CC0:     {', '.join(k['placeholder'])}")
        if k["missing"]:
            lines.append(f"  ✗ faltan (conseguir):  {', '.join(k['missing'])}")
        if k["paridad_gap"]:
            lines.append(f"  ⚠ hueco de paridad:    {', '.join(k['paridad_gap'])}")
    return "\n".join(lines)


if __name__ == "__main__":                          # `python -m src.mazes.pcg_manifest [espacio]` → lista de compras
    import sys

    spaces_arg = sys.argv[1:] or None
    print(format_gap_report(gap_report(load_manifest(), spaces=spaces_arg)))
