"""Oráculo agnóstico del DSL de Shape."""

from __future__ import annotations

import collections
import sys
from pathlib import Path

# assets/props/jammesh está fuera de src/ → al path (mismo patrón que families/bed.py)
JAMMESH_PATH = Path(__file__).resolve().parents[3] / "assets" / "props" / "jammesh"
if str(JAMMESH_PATH) not in sys.path:
    sys.path.insert(0, str(JAMMESH_PATH))

from core import Part, aabb, bottom_z, bbox, footprint, is_horizontal  # noqa: E402

from .ast import Assembly  # noqa: E402

EPS = 0.01
MIN_OVERLAP = 1e-4

def _overlap(min1: float, max1: float, min2: float, max2: float) -> float:
    return min(max1, max2) - max(min1, min2)

def check_assembly(assembly: Assembly, parts: list[Part]) -> list[str]:
    fails: list[str] = []

    # 5. Sanidad: número de partes
    if len(parts) < 2:
        fails.append(f"ensamble '{assembly.kind}' tiene {len(parts)} partes (mínimo 2)")
        return fails  # Si no hay partes suficientes, abortar para evitar crashes

    # 5. Sanidad: huella y altura
    w, l = footprint(parts)
    if w > 4.0 or l > 4.0:
        fails.append(f"ensamble '{assembly.kind}' excede huella máxima 4.0x4.0 m (es {w:.2f}x{l:.2f})")
    
    (lox, loy, loz), (hix, hiy, hiz) = bbox(parts)
    total_h = hiz - loz
    if total_h > 3.0:
        fails.append(f"ensamble '{assembly.kind}' excede altura máxima 3.0 m (es {total_h:.2f})")

    # 1. No degenerado y 2. Nada bajo el piso
    for p in parts:
        sx, sy, sz = p.size
        if sx <= EPS or sy <= EPS or sz <= EPS:
            fails.append(f"parte '{p.name}' degenerada (size <= {EPS} en algún eje)")
        
        bz = bottom_z(p)
        if bz < -EPS:
            fails.append(f"parte '{p.name}' hundida bajo el piso (z={bz:.3f})")

    # Grafo de contactos (3. Aterrizado y 4. Sostén)
    n = len(parts)
    adj = collections.defaultdict(list)
    supported_from_below = [False] * n
    touches_floor = [False] * n

    for i, p in enumerate(parts):
        if bottom_z(p) <= EPS:
            touches_floor[i] = True

    for i in range(n):
        for j in range(i + 1, n):
            pi = parts[i]
            pj = parts[j]
            (ailox, ailoy, ailoz), (aihix, aihiy, aihiz) = aabb(pi)
            (ajlox, ajloy, ajloz), (ajhix, ajhiy, ajhiz) = aabb(pj)

            ox = _overlap(ailox, aihix, ajlox, ajhix)
            oy = _overlap(ailoy, aihiy, ajloy, ajhiy)
            oz = _overlap(ailoz, aihiz, ajloz, ajhiz)

            # Contacto si hay toque en los 3 ejes (>= -EPS) y "solape real" en >= 2 ejes
            if ox >= -EPS and oy >= -EPS and oz >= -EPS:
                real_overlaps = sum(1 for o in (ox, oy, oz) if o > MIN_OVERLAP)
                if real_overlaps >= 2:
                    adj[i].append(j)
                    adj[j].append(i)
                    
                    # Sostén vertical: pj sostiene a pi desde abajo
                    if abs(ailoz - ajhiz) <= EPS and ox > MIN_OVERLAP and oy > MIN_OVERLAP:
                        supported_from_below[i] = True
                    # Sostén vertical: pi sostiene a pj desde abajo
                    if abs(ajloz - aihiz) <= EPS and ox > MIN_OVERLAP and oy > MIN_OVERLAP:
                        supported_from_below[j] = True

    # BFS para aterrizado
    visited = set()
    queue = collections.deque([i for i, tf in enumerate(touches_floor) if tf])
    while queue:
        curr = queue.popleft()
        if curr not in visited:
            visited.add(curr)
            for neighbor in adj[curr]:
                if neighbor not in visited:
                    queue.append(neighbor)
                    
    for i, p in enumerate(parts):
        if i not in visited:
            fails.append(f"parte '{p.name}' no está aterrizada (flota suelta o cadena rota)")

    # 4. Sostén de superficie
    for i, p in enumerate(parts):
        if is_horizontal(p) and not touches_floor[i]:
            if not supported_from_below[i]:
                fails.append(f"superficie '{p.name}' flota (no está sostenida desde abajo por otra parte)")

    return fails
