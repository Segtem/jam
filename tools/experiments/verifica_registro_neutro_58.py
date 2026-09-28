"""Sonda de editor: `fuera-del-motor`, etapa 1 — el registro partido anda en el motor de verdad.

    UnrealEditor <proyecto>.uproject -RenderOffScreen -unattended -nosplash \
      -ExecCmds="py <esta ruta>,QUIT_EDITOR"

Vuelca `api.spec()` (Dash Bar) y `api.spec_all()` (canvas) para compararlos contra los de antes del
corte, comprueba que cada verbo del registro neutro tiene su implementación de Unreal y corre
`Resources/Examples/Cylinder-Strip.jamgraph` por el Run del Graph. Resultado en
`Saved/jam_registro_neutro.json` del proyecto y la marca `JAM_REGISTRO_NEUTRO` en el log.
"""

import hashlib
import json
import os
import traceback

import unreal

MARCA = "JAM_REGISTRO_NEUTRO"
EJEMPLO = os.path.expanduser("~/Dev/jam/Resources/Examples/Cylinder-Strip.jamgraph")


def main():
    from jam import api, registro, tools

    r, fallas = {}, []
    r["mismo_dict"] = tools.REGISTRO is registro.REGISTRO
    r["verbos"] = len(registro.REGISTRO)
    r["sin_fn"] = sorted(v for v, i in registro.REGISTRO.items() if not callable(i.get("fn")))
    for nombre in ("spec", "spec_all"):
        texto = getattr(api, nombre)()
        r[nombre + "_sha"] = hashlib.sha256(texto.encode()).hexdigest()
        r[nombre + "_len"] = len(texto)
    if not r["mismo_dict"]:
        fallas.append("tools.REGISTRO no es registro.REGISTRO")
    if r["sin_fn"]:
        fallas.append(f"verbos sin implementación: {r['sin_fn'][:5]}")

    with open(EJEMPLO, encoding="utf-8") as f:
        envelope = json.loads(api.run_graph_json(f.read()))
    r["ejemplo_estados"] = {n: v.get("estado") for n, v in envelope.get("nodes", {}).items()}
    r["ejemplo_ok"] = envelope.get("ok")
    if envelope.get("ok") is not True:
        fallas.append("Cylinder-Strip no corrió en verde")
    r["descartar"] = api.discard() if hasattr(api, "discard") else None
    r["fallas"] = fallas
    return r


try:
    resultado = main()
    veredicto = "VERDE" if not resultado["fallas"] else "ROJO"
except Exception:  # noqa: BLE001
    resultado = {"excepcion": traceback.format_exc()}
    veredicto = "EXCEPCION"

destino = os.path.join(unreal.Paths.project_saved_dir(), "jam_registro_neutro.json")
with open(destino, "w", encoding="utf-8") as f:
    json.dump({"veredicto": veredicto, **resultado}, f, ensure_ascii=False, indent=2)
unreal.log(f"{MARCA} {veredicto} → {destino}")
