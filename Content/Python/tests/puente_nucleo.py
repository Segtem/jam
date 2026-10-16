"""El núcleo del editor web (jam.servidor.Nucleo) por la entrada y la salida estándar, sin sockets.

Lo usa `editor_en_node.js`: cada línea de entrada es {"fn": nombre, "args": [...]} y cada línea de salida es
{"resultado": <json>} o {"error": texto}. Es la misma lista blanca que el servidor HTTP del editor
(`Nucleo.PUBLICAS`). Sirve donde no se pueden abrir sockets, como el sandbox de un revisor.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("unreal", types.ModuleType("unreal"))

from jam import servidor  # noqa: E402

nucleo = servidor.Nucleo(sys.argv[1] if len(sys.argv) > 1 else "godot")
for linea in sys.stdin:
    pedido = json.loads(linea)
    try:
        if pedido["fn"] not in servidor.Nucleo.PUBLICAS:
            raise ValueError(f"{pedido['fn']} no es una función pública del núcleo")
        salida = {"resultado": json.dumps(getattr(nucleo, pedido["fn"])(*[str(a) for a in pedido.get("args") or []]),
                                          ensure_ascii=False)}
    except Exception as e:  # noqa: BLE001 — el editor lo informa como un error de la API
        salida = {"error": f"{type(e).__name__}: {e}"}
    sys.stdout.write(json.dumps(salida, ensure_ascii=False) + "\n")
    sys.stdout.flush()
