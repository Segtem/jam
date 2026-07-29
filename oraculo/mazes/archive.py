"""Archivo MAP-Elites para mazes — el corazón de la emergencia (quality-diversity).

NO optimiza hacia un maze ideal (eso converge → Goodhart). Discretiza el espacio de
comportamiento en NICHOS (combinaciones de descriptores) y guarda el mejor individuo de
CADA nicho. El resultado es una colección DIVERSA de mazes ganables — descubiertos, no
inyectados. La métrica de éxito es la COBERTURA (nichos poblados), no un score único.

Nicho = (bin del largo de solución, bin de branching, bin de dead-end-density).
Calidad dentro del nicho = `states_explored` del BFS (proxy de dificultad de búsqueda).
  ⚠ proxy provisional; el upgrade principista es skill_depth/RAPP (gameenv.metrics), más caro.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Bins:
    """Ancho de los bines de cada eje del espacio de comportamiento."""
    solution_length: int = 4       # 1 bin cada 4 pasos
    branching: float = 0.05        # 1 bin cada 0.05 de densidad de cruces
    dead_end_density: float = 0.05


def niche_key(desc: dict[str, Any], bins: Bins) -> tuple[int, int, int] | None:
    """Discretiza los descriptores en un nicho. None si el maze no es ganable (no entra)."""
    if not desc.get("solvable") or desc.get("solution_length") is None:
        return None
    return (
        int(desc["solution_length"] // bins.solution_length),
        int(desc["branching"] / bins.branching),
        int(desc["dead_end_density"] / bins.dead_end_density),
    )


def niche_key_3d(desc: dict[str, Any], bins: Bins) -> tuple[int, int, int] | None:
    """Nicho para JamMaps COMPUESTOS (Maze3D): ejes = (largo, verticalidad, no-euclidianidad). Mide el
    espacio que abren los elementos estructurales, no solo el plano. None si no es ganable."""
    if not desc.get("solvable") or desc.get("solution_length") is None:
        return None
    return (
        int(desc["solution_length"] // bins.solution_length),
        int(round(desc.get("verticality", 0.0) / 0.2)),          # 5 bines de verticalidad
        int(desc.get("non_euclidean_steps", 0)),                  # pasos por portal/gravedad
    )


def niche_key_jammap(desc: dict[str, Any], bins: Bins) -> tuple[int, int, int] | None:
    """Nicho para JamMaps por COMPOSICIÓN.
    eje 0: largo de solución
    eje 1: height span (pisos que abarca el camino)
    eje 2: firma de composición (bits: 0=portales, 1=gravedad, 2=verticalidad, 3=gating, 4=mundo, 5=peligro)
    """
    if not desc.get("solvable") or desc.get("solution_length") is None:
        return None
    
    comp_sig = 0
    if desc.get("portal_steps", 0) > 0:
        comp_sig += 1
    if desc.get("fall_steps", 0) > 0:
        comp_sig += 2
    if desc.get("verticality", 0) > 0:
        comp_sig += 4
    if desc.get("lock_depth", 0) > 0 or desc.get("n_doors", 0) > 0:
        comp_sig += 8
    if desc.get("n_gates", 0) > 0:
        comp_sig += 16
    if desc.get("n_hazards", 0) > 0:
        comp_sig += 32
    if desc.get("impossibility_degree", 0) > 0:           # COSTURA IMPOSIBLE: el espacio es NO-EUCLIDIANO
        comp_sig += 64

    return (
        int(desc["solution_length"] // bins.solution_length),
        int(desc.get("height_span", 0)),
        comp_sig
    )


@dataclass
class Elite:
    niche: tuple[int, int, int]
    quality: float
    layout: list[str]
    descriptors: dict[str, Any]
    origin: dict[str, Any] = field(default_factory=dict)   # cómo se generó (params/seed)
    dsl: str | None = None                                  # JamMap del elite (modo compuesto)


@dataclass
class MapElitesArchive:
    bins: Bins = field(default_factory=Bins)
    cells: dict[tuple[int, int, int], Elite] = field(default_factory=dict)
    considered: int = 0
    admitted: int = 0          # ganables que entraron a algún nicho (nuevo o reemplazo)
    # función de nicho: por default la 2D; en modo JamMap compuesto se pasa `niche_key_3d`.
    niche_fn: Callable[[dict[str, Any], Bins], tuple[int, int, int] | None] | None = None

    def _niche(self, desc: dict[str, Any]) -> tuple[int, int, int] | None:
        return (self.niche_fn or niche_key)(desc, self.bins)

    def consider(self, layout: list[str], desc: dict[str, Any],
                 origin: dict[str, Any] | None = None, dsl: str | None = None) -> str:
        """Evalúa un candidato. Devuelve 'new' | 'improved' | 'kept' | 'rejected'."""
        self.considered += 1
        key = self._niche(desc)
        if key is None:
            return "rejected"                      # inganable: el oráculo lo filtra
        # CALIDAD dentro del nicho: en JamMap premia el INTERÉS (mecánicas que importan) y, a igualdad,
        # el VIAJE (camino más largo); en 2D cae al proxy viejo (states_explored).
        if desc.get("interest_score") is not None:
            quality = desc["interest_score"] * 1000.0 + min(desc.get("solution_length") or 0, 999)
        else:
            quality = float(desc.get("states_explored") or 0)
        cur = self.cells.get(key)
        if cur is None:
            self.cells[key] = Elite(key, quality, layout, desc, origin or {}, dsl)
            self.admitted += 1
            return "new"
        if quality > cur.quality:
            self.cells[key] = Elite(key, quality, layout, desc, origin or {}, dsl)
            self.admitted += 1
            return "improved"
        return "kept"

    # ── reportes ────────────────────────────────────────────────────────────
    def coverage(self) -> int:
        return len(self.cells)

    def stats(self) -> dict[str, Any]:
        if not self.cells:
            return {"coverage": 0, "considered": self.considered, "admitted": self.admitted}
        lengths = [e.descriptors["solution_length"] for e in self.cells.values()]
        return {
            "coverage":      len(self.cells),
            "considered":    self.considered,
            "admitted":      self.admitted,
            "rejected":      self.considered - self.admitted,
            "length_range":  [min(lengths), max(lengths)],
            "length_bins":   sorted({k[0] for k in self.cells}),
            "branching_bins": sorted({k[1] for k in self.cells}),
            "deadend_bins":  sorted({k[2] for k in self.cells}),
        }

    def elites(self) -> list[Elite]:
        return sorted(self.cells.values(), key=lambda e: e.niche)

    # ── selección de padre para ILUMINAR (mutación sesgada a nichos ESCASOS / frontera) ──────────
    @staticmethod
    def _neighbor_keys(key: tuple[int, ...]) -> set[tuple[int, ...]]:
        """Nichos adyacentes: ±1 en cada eje del key (genérico para cualquier niche_fn de 3 ejes)."""
        out: set[tuple[int, ...]] = set()
        for axis in range(len(key)):
            for delta in (-1, 1):
                nk = list(key); nk[axis] += delta
                out.add(tuple(nk))
        return out

    def sparsity(self, key: tuple[int, ...]) -> int:
        """Cuántos nichos VECINOS (±1 por eje) están VACÍOS. Alto = el elite está en la FRONTERA del
        espacio explorado → mutarlo es más probable que su variación caiga en un nicho NUEVO (sube
        cobertura). El centro denso (vecinos llenos) pesa menos = no se reexplota."""
        return sum(1 for nk in self._neighbor_keys(key) if nk not in self.cells)

    def select_parent(self, rng, candidates: list[Elite] | None = None) -> Elite | None:
        """Elige un elite-padre para mutar, SESGADO hacia nichos escasos: peso = 1 + sparsity. Concentra
        la mutación donde hay espacio vacío alrededor (vs random.choice, que reexplota el centro denso).
        `rng` = módulo random o instancia Random (necesita .choices). Devuelve None si no hay candidatos."""
        pool = candidates if candidates is not None else list(self.cells.values())
        if not pool:
            return None
        weights = [1 + self.sparsity(e.niche) for e in pool]
        return rng.choices(pool, weights=weights, k=1)[0]

    def diverse_context(self, rng, k: int = 3, exclude: Elite | None = None) -> list[Elite]:
        """K elites lo más DISTINTOS posible en ESPACIO DE COMPORTAMIENTO (in-context QD): se le muestran al
        LLM como la VARIEDAD ya cubierta para que diverja. Greedy farthest-point sobre `behavior_vector`
        (distancia euclidiana) — más fino que el niche-key (captura cómo se JUEGA, no sólo la celda del grid).
        SOTA: 'LLMs as in-context QD generators' + novelty search por distancia de comportamiento."""
        from oraculo.mazes.novelty import behavior_vector
        pool = [e for e in self.cells.values() if e.dsl and e is not exclude]
        if not pool:
            return []
        bvec = {id(e): behavior_vector(e.descriptors) for e in pool}

        def _dist(a: Elite, b: Elite) -> float:
            return sum((x - y) ** 2 for x, y in zip(bvec[id(a)], bvec[id(b)])) ** 0.5

        chosen = [rng.choice(pool)]
        while len(chosen) < k and len(chosen) < len(pool):
            rest = [e for e in pool if e not in chosen]
            nxt = max(rest, key=lambda e: min(_dist(e, c) for c in chosen))
            chosen.append(nxt)
        return chosen

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for e in self.elites():
                rec: dict[str, Any] = {
                    "niche": list(e.niche), "quality": e.quality,
                    "layout": e.layout, "descriptors": e.descriptors,
                    "origin": e.origin,
                }
                if e.dsl is not None:
                    rec["dsl"] = e.dsl                 # JamMap compuesto (lo lee el minimapa)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return path
