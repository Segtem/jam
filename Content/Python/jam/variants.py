"""Sets de assets y selección determinista por frame para el Graph de TreeGen."""

from __future__ import annotations

import random
from dataclasses import dataclass

from .curve import FrameSet


@dataclass(frozen=True)
class AssetSet:
    """Colección ordenada ``A[]``; repetir una ruta aumenta intencionalmente su peso."""

    assets: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.assets)


@dataclass(frozen=True)
class FrameAssetSelection:
    """Stream ``AF``: un asset elegido para cada frame, conservando el FrameSet original."""

    frames: FrameSet
    assets: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.assets)


def make_asset_set(values) -> dict:
    if isinstance(values, (str, bytes)):
        return {"error": "asset_set necesita una lista de entradas A."}
    try:
        items = tuple(str(value).strip() for value in values if str(value).strip())
    except TypeError:
        return {"error": "asset_set necesita una lista de entradas A."}
    if len(items) < 2:
        return {"error": "asset_set necesita al menos dos assets A."}
    if len(items) > 64:
        return {"error": "asset_set no puede contener más de 64 assets."}
    result = AssetSet(items)
    return {
        "asset_set": result,
        "info": f"{len(result)} assets · {len(set(result.assets))} únicos",
    }


def choose_assets(frames, assets, *, mode: str = "random", seed: int = 7) -> dict:
    try:
        seed = int(seed)
    except (TypeError, ValueError):
        return {"error": "seed de choose_asset debe ser entero."}
    if not isinstance(frames, FrameSet) or not frames.frames:
        return {"error": "choose_asset necesita un stream F válido y no vacío."}
    if not isinstance(assets, AssetSet) or not assets.assets:
        return {"error": "choose_asset necesita un Asset Set A[] válido."}
    mode = str(mode or "random").strip().lower()
    if mode not in {"random", "cycle", "parent"}:
        return {"error": "mode debe ser random, cycle o parent."}

    selected = []
    for frame in frames.frames:
        if mode == "cycle":
            index = frame.local_index % len(assets.assets)
        elif mode == "parent":
            index = frame.parent_index % len(assets.assets)
        else:
            frame_seed = (
                seed * 1_000_003 + frame.seed * 9_176
                + frame.parent_index * 97_409 + frame.local_index * 65_537
            ) & 0x7fffffff
            index = random.Random(frame_seed).randrange(len(assets.assets))
        selected.append(assets.assets[index])

    result = FrameAssetSelection(frames, tuple(selected))
    used = len(set(result.assets))
    return {
        "selection": result,
        "info": f"{len(result)} frames · {used}/{len(set(assets.assets))} variantes · {mode} · seed {seed}",
    }
