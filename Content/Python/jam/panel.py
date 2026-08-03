"""Puente Jam ↔ UI: ejecución del DSL y del grafo, con preview → Confirmar/Descartar.

Lo llama la UI en C++ (`JamEditor`: Dash Bar y Graph) vía `ejecutar_dsl` / `ejecutar_grafo`. Ya NO
arma ningún widget UMG: el viejo EditorUtilityWidget (`WBP_JamPanel`) y su cableado quedaron
reemplazados por el módulo C++/Slate. Acá vive sólo la lógica compartida: parsear→correr→verificar,
spawnear como PREVIEW (tag `jam:preview`) y resolver con Confirmar (fija) o Descartar (borra).
"""

from __future__ import annotations

import base64
import json
import re
import uuid

import unreal

from . import library

# Preview → Submit: las herramientas spawnean primero como PREVIEW (con veredicto); recién «Confirmar»
# las fija o «Descartar» las borra. Los TAGS del nivel son la fuente de verdad: sobreviven a reloads
# de Python y permiten que Graph y Dash mantengan previews independientes.
_TAG_PREVIEW = "jam:preview"
_TAG_OWNER = "jam:preview-owner="
_TAG_ASSETS = "jam:preview-assets="
_TAG_LABEL = "jam:preview-label="
_PREFIX_PREVIEW = "prev_"
_PREFIX_BAKE = "bake_"
_PREVIEW_CONTEXT: dict | None = None
# Los actores siguen siendo la fuente de verdad principal. Este índice cubre previews que producen
# solamente assets (por ejemplo Asset → Nanite) y los metadatos permiten reconstruirlo tras reload.
_PREVIEW_ASSETS_BY_OWNER: dict[str, list[dict]] = {}
_ASSET_META_OWNER = "JamPreviewOwner"
_ASSET_META_FINAL = "JamPreviewFinal"


def _asset_biblioteca():
    libro = library.buscar(limit=1)
    return libro[0]["ruta"] if libro else None


def _resolver_asset(nombre) -> str | None:
    """asset del comando (por nombre/ObjectPath) → si no se da, el ACTIVO de la sesión (lo que se
    eligió en Content) → y recién ahí el 1º de la biblioteca."""
    from . import session
    if nombre:
        if "/" in nombre or "." in nombre:   # ya es un ObjectPath
            return nombre
        hits = library.buscar(nombre, limit=1)
        return hits[0]["ruta"] if hits else None
    return session.asset() or _asset_biblioteca()


# ---- Preview → Submit ----

def _actor_sub():
    return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def _todos():
    return _actor_sub().get_all_level_actors()


def _tags_de(actor) -> list[str]:
    from . import ue
    return ue.tags(actor)


def _set_tags(actor, tags: list[str]) -> None:
    from . import ue
    ue.set_tags(actor, tags)
    actuales = _tags_de(actor)
    if set(actuales) != set(tags):
        raise RuntimeError(
            f"Unreal no aplicó los tags de Preview (esperados={tags!r}, actuales={actuales!r})")


def _owner_tag(owner: str) -> str:
    seguro = "".join(c for c in str(owner or "preview").lower() if c.isalnum() or c in "_-")
    return _TAG_OWNER + (seguro or "preview")


def _owner_de(actor) -> str | None:
    for tag in _tags_de(actor):
        if tag.startswith(_TAG_OWNER):
            return tag[len(_TAG_OWNER):]
    return None


def _encode_label(label: str) -> str:
    raw = str(label).encode("utf-8")
    return _TAG_LABEL + base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_label(tag: str) -> str | None:
    if not tag.startswith(_TAG_LABEL):
        return None
    try:
        raw = base64.urlsafe_b64decode(tag[len(_TAG_LABEL):].encode("ascii"))
        return raw.decode("utf-8")
    except Exception:  # noqa: BLE001
        return None


def _label_original(actor, tags: list[str] | None = None) -> str:
    for tag in tags if tags is not None else _tags_de(actor):
        original = _decode_label(tag)
        if original is not None:
            return original
    actual = str(actor.get_actor_label())
    # Compatibilidad con previews creados antes de guardar el nombre original en un tag.
    return actual[len(_PREFIX_PREVIEW):] if actual.startswith(_PREFIX_PREVIEW) else actual


def _set_actor_label(actor, label: str) -> None:
    actor.set_actor_label(str(label))


def _restaurar_estado_preview(estados: list[tuple[object, list[str], str]]) -> None:
    for actor, tags, original in estados:
        try:
            _set_tags(actor, tags)
        except Exception:  # noqa: BLE001
            pass
        try:
            _set_actor_label(actor, _PREFIX_PREVIEW + original)
        except Exception:  # noqa: BLE001
            pass


def _encode_assets(records: list[dict]) -> str:
    raw = json.dumps(records, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return _TAG_ASSETS + base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_assets(tag: str) -> list[dict]:
    if not tag.startswith(_TAG_ASSETS):
        return []
    try:
        raw = base64.urlsafe_b64decode(tag[len(_TAG_ASSETS):].encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
        return [r for r in data if isinstance(r, dict) and r.get("temp") and r.get("final")]
    except Exception:  # noqa: BLE001
        return []


def _asset_records(actores) -> list[dict]:
    unicos: dict[tuple[str, str], dict] = {}
    for actor in actores:
        for tag in _tags_de(actor):
            for record in _decode_assets(tag):
                key = (str(record["temp"]), str(record["final"]))
                unicos[key] = {"temp": key[0], "final": key[1]}
    return list(unicos.values())


def _unique_asset_records(records: list[dict]) -> list[dict]:
    unicos: dict[tuple[str, str], dict] = {}
    for record in records:
        if not isinstance(record, dict) or not record.get("temp") or not record.get("final"):
            continue
        temp = str(record["temp"]).split(".", 1)[0]
        final = str(record["final"]).split(".", 1)[0]
        unicos[(temp, final)] = {"temp": temp, "final": final}
    return list(unicos.values())


def _recover_asset_records(owner: str | None) -> list[dict]:
    """Reconstruye assets-only Preview desde metadatos de Content tras recargar Python."""
    base = f"/Game/JamPreview/{owner}" if owner else "/Game/JamPreview"
    records: list[dict] = []
    try:
        paths = unreal.EditorAssetLibrary.list_assets(base, recursive=True, include_folder=False)
    except Exception:  # noqa: BLE001
        return records
    for path in paths:
        try:
            obj = _asset_load(path)
            record_owner = str(
                unreal.EditorAssetLibrary.get_metadata_tag(obj, _ASSET_META_OWNER) or "")
            final = str(unreal.EditorAssetLibrary.get_metadata_tag(obj, _ASSET_META_FINAL) or "")
            if obj is not None and final and (owner is None or record_owner == owner):
                records.append({"temp": str(path).split(".", 1)[0], "final": final})
        except Exception:  # noqa: BLE001
            continue
    return _unique_asset_records(records)


def _asset_records_for_owner(owner: str | None, actores=None) -> list[dict]:
    records = _asset_records(actores if actores is not None else _actores_preview(owner))
    if owner is None:
        for owned in _PREVIEW_ASSETS_BY_OWNER.values():
            records.extend(owned)
    else:
        records.extend(_PREVIEW_ASSETS_BY_OWNER.get(owner, []))
    records.extend(_recover_asset_records(owner))
    return _unique_asset_records(records)


def preview_asset_path(final_path: str) -> str:
    """Devuelve una ruta temporal durante `_preview` y registra cómo promoverla en Bake.

    Fuera de un Preview conserva la ruta solicitada, para no cambiar callers directos o de mantenimiento.
    """
    if _PREVIEW_CONTEXT is None:
        return final_path
    final = str(final_path).split(".", 1)[0]
    nombre = final.rsplit("/", 1)[-1]
    nombre = re.sub(r"[^A-Za-z0-9_]+", "_", nombre).strip("_") or "Asset"
    owner = _PREVIEW_CONTEXT["owner"]
    temp = f"/Game/JamPreview/{owner}/PV_{_PREVIEW_CONTEXT['id']}_{nombre}"
    record = {"temp": temp, "final": final}
    if record not in _PREVIEW_CONTEXT["assets"]:
        _PREVIEW_CONTEXT["assets"].append(record)
    return temp


def register_preview_asset(path: str) -> None:
    """Persiste owner/destino en un asset temporal ya creado.

    Los transformadores llaman esto después de guardar. Si no hay Preview activo no hace nada porque
    el asset ya está en su ruta final y no necesita Bake/Discard.
    """
    if _PREVIEW_CONTEXT is None:
        return
    temp = str(path).split(".", 1)[0]
    record = next((r for r in _PREVIEW_CONTEXT["assets"] if r["temp"] == temp), None)
    if record is None:
        raise RuntimeError(f"el asset «{temp}» no fue registrado por preview_asset_path")
    obj = _asset_load(temp)
    if obj is None:
        raise RuntimeError(f"no pude cargar el asset temporal «{temp}» para registrar su Preview")
    unreal.EditorAssetLibrary.set_metadata_tag(obj, _ASSET_META_OWNER, _PREVIEW_CONTEXT["owner"])
    unreal.EditorAssetLibrary.set_metadata_tag(obj, _ASSET_META_FINAL, record["final"])
    if not unreal.EditorAssetLibrary.save_asset(temp, only_if_is_dirty=False):
        raise RuntimeError(f"no pude guardar metadatos de Preview en «{temp}»")


def _clear_preview_asset_metadata(path: str) -> None:
    try:
        obj = _asset_load(path)
        if obj is None:
            return
        unreal.EditorAssetLibrary.remove_metadata_tag(obj, _ASSET_META_OWNER)
        unreal.EditorAssetLibrary.remove_metadata_tag(obj, _ASSET_META_FINAL)
        unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    except Exception:  # noqa: BLE001
        # El asset ya salió de /Game/JamPreview: un tag auxiliar remanente no compromete el Bake.
        pass


def _asset_exists(path: str) -> bool:
    return bool(unreal.EditorAssetLibrary.does_asset_exist(path))


def _asset_delete(path: str) -> bool:
    return not _asset_exists(path) or bool(unreal.EditorAssetLibrary.delete_asset(path))


def _asset_rename(source: str, destination: str) -> bool:
    return bool(unreal.EditorAssetLibrary.rename_asset(source, destination))


def _asset_load(path: str):
    return unreal.EditorAssetLibrary.load_asset(path)


def _discard_staged_assets(records: list[dict]) -> tuple[int, int]:
    borrados, fallidos = 0, 0
    for record in records:
        temp = str(record["temp"])
        try:
            if _asset_exists(temp):
                if _asset_delete(temp):
                    borrados += 1
                else:
                    fallidos += 1
        except Exception:  # noqa: BLE001
            fallidos += 1
    return borrados, fallidos


def _ruta_final_disponible(base: str, reservadas: set[str]) -> str:
    if base not in reservadas and not _asset_exists(base):
        return base
    indice = 2
    while True:
        candidata = f"{base}_{indice}"
        if candidata not in reservadas and not _asset_exists(candidata):
            return candidata
        indice += 1


def _promover_staged_assets(records: list[dict]) -> list[tuple[str, str]]:
    """Renombra temporales a Content definitivo sin sobrescribir. Revierte renames si uno falla."""
    plan: list[tuple[str, str]] = []
    reservadas: set[str] = set()
    for record in records:
        temp = str(record["temp"])
        if not _asset_exists(temp):
            continue
        destino = _ruta_final_disponible(str(record["final"]), reservadas)
        reservadas.add(destino)
        plan.append((temp, destino))

    promovidos: list[tuple[str, str]] = []
    try:
        for temp, destino in plan:
            if not _asset_rename(temp, destino):
                raise RuntimeError(f"no pude promover «{temp}» a «{destino}»")
            promovidos.append((temp, destino))
    except Exception:
        for temp, destino in reversed(promovidos):
            try:
                _asset_rename(destino, temp)
            except Exception:  # noqa: BLE001
                pass
        raise
    for _temp, destino in promovidos:
        _clear_preview_asset_metadata(destino)
    return promovidos


def _rollback_promotions(promociones: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], int]:
    """Devuelve assets promovidos a su ruta temporal. Retorna (revertidos, fallidos)."""
    revertidos: list[tuple[str, str]] = []
    fallidos = 0
    for temp, destino in reversed(promociones):
        try:
            if not _asset_exists(destino):
                continue
            if _asset_exists(temp) or not _asset_rename(destino, temp):
                fallidos += 1
                continue
            revertidos.append((destino, temp))
        except Exception:  # noqa: BLE001
            fallidos += 1
    return revertidos, fallidos


def _asset_path(asset) -> str | None:
    if asset is None:
        return None
    try:
        return str(asset.get_path_name()).split(".", 1)[0]
    except Exception:  # noqa: BLE001
        return None


def _component_graph(component):
    try:
        return component.get_graph()
    except Exception:  # noqa: BLE001
        try:
            return component.get_editor_property("graph")
        except Exception:  # noqa: BLE001
            return None


def _rebind_promoted_assets(actores, promociones: list[tuple[str, str]]) -> int:
    """Fija referencias PCG al asset ya promovido y verifica que no sigan apuntando a Preview.

    Un rename de Content puede dejar al `PCGComponent` con la referencia transitoria hasta que Unreal
    procesa redirectors/GC. Reasignarla explícitamente evita que el siguiente Run vacíe el volumen
    baked al liberar el objeto temporal.
    """
    if not promociones:
        return 0
    mapa = {temp: destino for temp, destino in promociones}
    reasignados = 0
    pcg_class = getattr(unreal, "PCGComponent", None)
    if pcg_class is None:
        return 0

    for actor in actores:
        try:
            component = actor.get_component_by_class(pcg_class)
        except Exception:  # noqa: BLE001
            continue
        if component is None:
            continue

        actual = _asset_path(_component_graph(component))
        destino = mapa.get(actual)
        # Después de rename algunas versiones ya reportan el destino; otras devuelven None. Cada
        # PCGVolume creado hoy registra un único PCGGraph, por lo que ese caso sigue siendo unívoco.
        if destino is None and actual in mapa.values():
            destino = actual
        if destino is None and len(promociones) == 1:
            destino = promociones[0][1]
        if destino is None:
            continue

        grafo = _asset_load(destino)
        if grafo is None:
            raise RuntimeError(f"no pude cargar el PCGGraph promovido «{destino}»")
        try:
            actor.modify()
        except Exception:  # noqa: BLE001
            pass
        try:
            component.modify()
        except Exception:  # noqa: BLE001
            pass
        component.set_graph(grafo)
        asignado = _asset_path(_component_graph(component))
        if asignado is not None and asignado != destino:
            raise RuntimeError(
                f"el PCGComponent conservó «{asignado}» en vez de «{destino}»")
        try:
            component.generate(True)
        except Exception:  # noqa: BLE001
            pass
        reasignados += 1
    return reasignados


def _actores_preview(owner: str | None = None) -> list:
    """Reconstruye el Preview desde el nivel; no depende de referencias guardadas en Python."""
    salida = []
    for actor in _todos():
        tags = _tags_de(actor)
        if _TAG_PREVIEW in tags and (owner is None or _owner_de(actor) == owner):
            salida.append(actor)
    return salida


def _marcar_preview(actores, owner: str = "dash", assets: list[dict] | None = None) -> None:
    marca_owner = _owner_tag(owner)
    marca_assets = _encode_assets(assets or []) if assets else ""
    for a in actores:
        tags = [t for t in _tags_de(a)
                if not t.startswith(_TAG_OWNER) and not t.startswith(_TAG_ASSETS)
                and not t.startswith(_TAG_LABEL)]
        original = str(a.get_actor_label())
        if _TAG_PREVIEW not in tags:
            tags.append(_TAG_PREVIEW)
        _set_tags(a, tags + [marca_owner, _encode_label(original)]
                  + ([marca_assets] if marca_assets else []))
        _set_actor_label(a, _PREFIX_PREVIEW + original)


def _destruir_actores(actores) -> tuple[int, int]:
    ed, borrados, fallidos = _actor_sub(), 0, 0
    for actor in list(actores):
        try:
            ed.destroy_actor(actor)
            borrados += 1
        except Exception:  # noqa: BLE001
            fallidos += 1
    return borrados, fallidos


def _descartar_preview_detalle(owner: str | None = None) -> tuple[int, int, int, int]:
    """Descarta un Preview sin perder el registro si Unreal no puede borrar un asset.

    Devuelve actores borrados/fallidos y assets borrados/fallidos. Los actores conservan sus tags
    mientras quede algún asset fallido, de modo que Discard pueda reintentarse después.
    """
    actores = _actores_preview(owner)
    records = _asset_records_for_owner(owner, actores)
    assets_borrados, assets_fallidos = _discard_staged_assets(records)
    if assets_fallidos:
        return 0, 0, assets_borrados, assets_fallidos
    if owner is None:
        _PREVIEW_ASSETS_BY_OWNER.clear()
    else:
        _PREVIEW_ASSETS_BY_OWNER.pop(owner, None)
    borrados, fallidos = _destruir_actores(actores)
    return borrados, fallidos, assets_borrados, 0


def _descartar_preview(owner: str | None = None) -> int:
    """Borra el Preview indicado (o todos si owner=None), incluso después de recargar Python."""
    borrados, _fallidos, _assets_borrados, _assets_fallidos = _descartar_preview_detalle(owner)
    return borrados


def _limpiar_huerfanos() -> int:
    """Borra restos jam:preview de sesiones cerradas sin confirmar/descartar. Devuelve cuántos."""
    return _descartar_preview(owner=None)


def _seleccionar(actores) -> None:
    from . import ue
    ue.seleccionar(actores)


def _preview(fn, widget=None, *, owner: str = "dash") -> str:
    """Ejecuta una Preview como staging transaccional de actores y assets de Content.

    El Preview anterior del mismo owner permanece hasta que la nueva ejecución termina. Ante una
    excepción se destruyen los actores/assets nuevos y se conserva el anterior; sólo un éxito hace
    el swap.
    """
    global _PREVIEW_CONTEXT
    anteriores = _actores_preview(owner)
    assets_anteriores = _asset_records_for_owner(owner, anteriores)
    antes = {a.get_path_name() for a in _todos()}
    contexto_anterior = _PREVIEW_CONTEXT
    contexto = {"owner": owner, "id": uuid.uuid4().hex[:10], "assets": []}
    _PREVIEW_CONTEXT = contexto
    try:
        texto = fn(widget)
    except Exception as exc:  # noqa: BLE001
        nuevos = [a for a in _todos() if a.get_path_name() not in antes]
        borrados, fallidos = _destruir_actores(nuevos)
        assets_borrados, assets_fallidos = _discard_staged_assets(contexto["assets"])
        extra = f"; {fallidos} no se pudieron borrar" if fallidos else ""
        extra_assets = (f" · {assets_borrados} asset(s) temporal(es) eliminado(s)"
                        + (f"; {assets_fallidos} fallaron" if assets_fallidos else ""))
        return (f"[error] PREVIEW revertida — {type(exc).__name__}: {exc}\n"
                f"ROLLBACK ✓ · {borrados} actor(es) nuevos eliminados{extra}; "
                f"se conserva el Preview anterior de «{owner}»{extra_assets}.")
    finally:
        _PREVIEW_CONTEXT = contexto_anterior

    nuevos = [a for a in _todos() if a.get_path_name() not in antes]
    # Marcar primero el staging: si luego falla la limpieza del anterior, ambos siguen recuperables.
    try:
        _marcar_preview(nuevos, owner, contexto["assets"])
    except Exception as exc:  # noqa: BLE001
        borrados, fallidos = _destruir_actores(nuevos)
        assets_borrados, assets_fallidos = _discard_staged_assets(contexto["assets"])
        return (f"[error] PREVIEW revertida — no pude marcar el staging: {exc}. "
                f"ROLLBACK ✓ · {borrados} actor(es) y {assets_borrados} asset(s) eliminado(s)"
                + (f"; fallaron {fallidos} actor(es) y {assets_fallidos} asset(s)"
                   if fallidos or assets_fallidos else "")
                + f"; se conserva el Preview anterior de «{owner}».")
    if contexto["assets"]:
        _PREVIEW_ASSETS_BY_OWNER[owner] = _unique_asset_records(contexto["assets"])
    else:
        _PREVIEW_ASSETS_BY_OWNER.pop(owner, None)
    assets_reemplazados, assets_fallidos = _discard_staged_assets(assets_anteriores)
    # Si queda un asset temporal sin borrar, el actor anterior conserva el tag que permite recuperar
    # su ruta y reintentar. Es preferible ver dos previews un instante a dejar Content huérfano.
    if assets_fallidos:
        _PREVIEW_ASSETS_BY_OWNER[owner] = _unique_asset_records(
            contexto["assets"] + assets_anteriores)
        reemplazados, fallidos = 0, 0
    else:
        reemplazados, fallidos = _destruir_actores(anteriores)
    # Dejarlas SELECCIONADAS en el editor: se ven resaltadas, aparecen en el Outliner y en Details,
    # y con F la cámara vuela hasta ellas. Es la diferencia entre "lo colocó" y "no veo nada".
    _seleccionar(nuevos)
    reemplazo = f" · reemplazó {reemplazados} anterior(es)" if reemplazados else ""
    advertencia = f" · {fallidos} anterior(es) no se pudieron borrar" if fallidos else ""
    assets_txt = f" · {len(contexto['assets'])} asset(s) temporal(es)" if contexto["assets"] else ""
    if assets_reemplazados:
        assets_txt += f" · limpió {assets_reemplazados} asset(s) anterior(es)"
    if assets_fallidos:
        assets_txt += (f" · {assets_fallidos} asset(s) anterior(es) no se pudieron borrar; "
                       "se conservó su Preview para reintentar")
    return (f"{texto}\n\nPREVIEW [{owner}] · {len(nuevos)} piezas en escena (seleccionadas)"
            f"{reemplazo}{advertencia}{assets_txt} — «Bake/Confirmar» las fija · «Descartar» las borra.")


def hay_preview(owner: str | None = None) -> bool:
    """¿Hay algo esperando que lo confirmen o descarten?"""
    actores = _actores_preview(owner)
    if actores:
        return True
    return any(_asset_exists(record["temp"])
               for record in _asset_records_for_owner(owner, actores))


def _h_confirmar(widget=None, *, owner: str | None = None) -> str:
    actores = _actores_preview(owner)
    records = _asset_records_for_owner(owner, actores)
    if not actores and not records:
        return "no hay preview activa para confirmar."
    estados = [(actor, _tags_de(actor), _label_original(actor)) for actor in actores]
    assets_promovidos: list[tuple[str, str]] = []
    try:
        # Nombre y tags cambian como una unidad lógica. Si la promoción de Content falla, ambos se
        # restauran y Discard sigue reconociendo exactamente el mismo Preview.
        for actor, tags, original in estados:
            _set_actor_label(actor, _PREFIX_BAKE + original)
            _set_tags(actor, [t for t in tags
                              if t != _TAG_PREVIEW and not t.startswith(_TAG_OWNER)
                              and not t.startswith(_TAG_ASSETS) and not t.startswith(_TAG_LABEL)])
        assets_promovidos = _promover_staged_assets(records)
        componentes_reasignados = _rebind_promoted_assets(actores, assets_promovidos)
    except Exception as exc:  # noqa: BLE001
        rollback_extra = ""
        if assets_promovidos:
            revertidos, fallidos = _rollback_promotions(assets_promovidos)
            try:
                _rebind_promoted_assets(actores, revertidos)
            except Exception:  # noqa: BLE001
                fallidos += 1
            if fallidos:
                rollback_extra = (f" Atención: {fallidos} operación(es) de rollback de Content "
                                  "requieren revisión manual.")
        _restaurar_estado_preview(estados)
        return (f"[error] BAKE cancelado — {type(exc).__name__}: {exc}. "
                "El Preview y sus assets temporales siguen disponibles para reintentar o descartar."
                + rollback_extra)
    confirmados = actores
    n = len(confirmados)
    if owner is None:
        _PREVIEW_ASSETS_BY_OWNER.clear()
    else:
        _PREVIEW_ASSETS_BY_OWNER.pop(owner, None)
    # decir QUÉ quedó y DÓNDE: sin esto, un confirm sobre algo fuera de cuadro no se distingue de
    # un confirm que no hizo nada.
    detalle = []
    for actor in confirmados[:4]:
        try:
            loc = actor.get_actor_location()
            detalle.append(
                f"«{actor.get_actor_label()}» ({loc.x:.0f}, {loc.y:.0f}, {loc.z:.0f})")
        except Exception:  # noqa: BLE001
            detalle.append("«actor sin referencia válida»")
    if n > 4:
        detalle.append(f"…+{n - 4}")
    scope = f" [{owner}]" if owner else ""
    destinos_promovidos = [destino for _temp, destino in assets_promovidos]
    assets_txt = (f" · {len(destinos_promovidos)} asset(s) promovido(s): "
                  + ", ".join(destinos_promovidos)) if destinos_promovidos else ""
    if componentes_reasignados:
        assets_txt += f" · {componentes_reasignados} referencia(s) PCG fijada(s)"
    piezas_txt = (f"{n} piezas fijadas en el nivel: " + ", ".join(detalle)) if n else \
        "sin actores; se fijó únicamente Content producido por el Graph"
    seleccion_txt = "\n    siguen seleccionadas: F en el viewport vuela hasta ellas." if n else ""
    return f"BAKE/CONFIRMADO{scope} ✓ — {piezas_txt}{assets_txt}{seleccion_txt}"


def _h_descartar(widget=None, *, owner: str | None = None) -> str:
    if not hay_preview(owner):
        return "no hay preview activa para descartar."
    n, actores_fallidos, assets_borrados, assets_fallidos = _descartar_preview_detalle(owner)
    scope = f" [{owner}]" if owner else ""
    if assets_fallidos:
        return (f"[error] DESCARTE incompleto{scope} — {assets_fallidos} asset(s) temporal(es) "
                "no se pudieron borrar; los actores y sus registros se conservaron para reintentar.")
    extra_assets = f" · {assets_borrados} asset(s) temporal(es) borrado(s)" if assets_borrados else ""
    extra_actores = f" · {actores_fallidos} actor(es) no se pudieron borrar" if actores_fallidos else ""
    return f"descartado{scope} ✗ — {n} piezas borradas{extra_assets}{extra_actores}."


# ---- Ejecución del DSL y del grafo (lo que llama la UI C++) ----

def ejecutar_dsl(linea: str, widget=None) -> str:
    """Corre una línea de DSL. Los verbos de spawn pasan por preview (Confirmar/Descartar los
    resuelven). `widget` se ignora (compat con la firma que llama el C++)."""
    from . import dsl, menu, tools
    r = dsl.parsear(linea)
    verbo = r["verbo"]
    if not verbo:
        return "escribí un comando. «help» lista los verbos."
    # keywords en inglés (primario) + alias español por comodidad
    if verbo in ("help", "?", "ayuda"):
        return dsl.ayuda()
    if verbo in ("confirm", "confirmar", "ok"):
        return _h_confirmar(owner="dash")
    if verbo in ("discard", "descartar", "cancel"):
        return _h_descartar(owner="dash")
    if verbo in ("verify", "verificar", "oracle"):
        return menu.on_verificar_espacio()
    if verbo == "preset":
        from . import preset
        nombre = (linea.split(None, 1)[1].strip() if len(linea.split(None, 1)) > 1 else "").strip('"')
        if not nombre or nombre in ("list", "listar"):
            ps = preset.listar()
            if not ps:
                return "no hay presets. Guardá uno con «guardar preset» o poné JSON en <plugin>/presets/."
            return "presets:\n" + "\n".join(
                f"  · {p['nombre']}  [{p.get('kind','tool')}·{p['scope']}]  {p.get('descripcion','')}"
                for p in ps)
        # aplicar por nombre pasa por preview (confirm/discard lo resuelven)
        p = preset.cargar(nombre)
        if not p:
            return f"preset «{nombre}» no encontrado. «preset list» los muestra."
        return preset.aplicar(p)["texto"]
    if verbo in ("search", "list", "buscar", "listar"):
        hits = library.buscar(r["asset"] or "", limit=15)
        if not hits:
            return f"sin resultados para «{r['asset'] or ''}»."
        nombres = ", ".join(h["nombre"] for h in hits)
        return f"{len(hits)} assets: {nombres}"
    if verbo in tools.SIN_SPAWN:
        # selección/estado, no spawn: no pasan por preview (no agregan actores al nivel)
        kw, _desc = dsl.coaccionar(verbo, r["params"])
        if verbo == "pick":
            return tools.t_pick(None)   # lee la selección del Content Browser de Unreal
        # `name` como nombre de asset es SÓLO para el verbo `asset` (en pcg, `name` es el del volumen).
        pedido = r["asset"] or (r["params"].get("name") if verbo == "asset" else "") or ""
        asset = _resolver_asset(pedido)
        if pedido and asset is None:
            return f"asset «{pedido}» no encontrado en la biblioteca."
        return tools.REGISTRO[verbo]["fn"](asset, **kw)
    if verbo in tools.REGISTRO:
        asset = _resolver_asset(r["asset"])
        if r["asset"] and asset is None:
            return f"asset «{r['asset']}» no encontrado en la biblioteca."
        if not asset:
            return "biblioteca vacía (no hay assets que colocar)."
        kw, desconocidos = dsl.coaccionar(verbo, r["params"])
        fn = tools.REGISTRO[verbo]["fn"]

        def _correr(_w, _verbo=verbo, _fn=fn, _kw=kw, _asset=asset):
            """Un COMANDO es «hacelo ahora»; un grafo es una descripción.

            Los verbos que ahora producen PUNTOS (P) describen dónde iría algo y no colocan nada —
            en el grafo eso es correcto, porque el que coloca es `instance` y es uno solo—. Pero
            desde la Dash Bar escribir «scatter SM_Rock» tiene que poner piedras. Acá, en el único
            lugar por donde pasan todos los comandos, se compone lo que en el grafo son dos nodos.
            """
            texto = _fn(_asset, **_kw)
            if not tools.necesita_instanciar(_verbo):
                return texto
            puntos = tools.dato_producido_runtime(_verbo)
            if not puntos:
                return texto
            return texto + "\n" + tools.t_place(
                _asset, points=puntos,
                scale_min=_kw.get("scale_min", 1.0), scale_max=_kw.get("scale_max", 1.0),
                anchor=_kw.get("anchor", "") or "base", align=_kw.get("align", False),
                sink=_kw.get("sink", 0.0))

        cuerpo = _preview(_correr, owner="dash")
        if desconocidos:
            cuerpo += f"\n(ignoré params desconocidos: {', '.join(desconocidos)})"
        return cuerpo
    return f"verbo desconocido: «{verbo}». «help» lista los verbos."


def _sin_efectos(g) -> bool:
    """El grafo sólo calcula/lee: no merece abrir ni reemplazar un Preview vacío.

    La marca es opt-in porque ``SIN_SPAWN`` no alcanza: Fracture no coloca actores pero sí escribe
    Content, y Normalize tampoco spawnea aunque modifica el asset. ``read_only`` declara una
    propiedad más fuerte y revisable por verbo.
    """
    from . import tools
    from .graph import VALOR_KINDS
    return bool(g.nodes) and all(
        nodo.get("verb") in VALOR_KINDS
        or tools.REGISTRO.get(nodo.get("verb"), {}).get("read_only", False)
        for nodo in g.nodes.values()
    )


def ejecutar_grafo(g_json: str, widget=None) -> str:
    """Corre un JamGraph; sólo abre Preview cuando algún nodo puede producir efectos en escena."""
    from . import graph
    g = graph.JamGraph.from_json(g_json)
    try:
        plan = graph.compilar(g)
    except graph.GraphValidationError as exc:
        return "\n".join(f"[{nid}] {' · '.join(mensajes)}"
                         for nid, mensajes in exc.diagnostics.items())
    def correr(_w):
        texto, por_nodo = graph.ejecutar_detalle(g, plan)
        if any(resultado.get("estado") == "error" for resultado in por_nodo.values()):
            raise RuntimeError(texto)
        return texto

    if _sin_efectos(g):
        try:
            return correr(widget) + f"\n\nRUN ✓ — {len(g.nodes)} nodo(s), sin efectos en la escena"
        except Exception as exc:  # noqa: BLE001 — error observable, sin transacción que revertir
            return f"[error] RUN sin efectos ✗ — {exc}"
    return _preview(correr, owner="graph")


def ejecutar_flow_json(g_json: str, widget=None, *, owner: str = "graph") -> str:
    """Corre un FLOW (cadena estilo Houdini: source → máscaras → instance) como UN preview, y devuelve
    JSON {report, nodes:{id:{estado,texto}}} para que el canvas pinte cada nodo. El estado sale del
    stream que produjo: verde = pasó puntos, naranja = quedó vacío (el filtro comió todo)."""
    import json

    from . import flow, graph, scatter

    f = flow.Flow.from_json(g_json)
    caja: dict = {}

    # Preflight ANTES de `_preview`: un grafo inválido no descarta el preview anterior ni ejecuta una
    # sola operación de Unreal. Cada diagnóstico vuelve asociado a su nodo para pintarlo rojo.
    diagnosticos = f.validar(ops=scatter.ops_flow())
    if diagnosticos:
        lineas = []
        globales = diagnosticos.get("_graph", [])
        for nid, nodo in f.nodos.items():
            mensajes = diagnosticos.get(nid, []) or globales
            if mensajes:
                texto = " · ".join(mensajes)
                caja[nid] = {"estado": "error", "texto": texto}
                lineas.append(f"[{nid}·{nodo['kind']}] {texto}")
        for nid, mensajes in diagnosticos.items():
            if nid in f.nodos:
                continue
            texto = " · ".join(mensajes)
            lineas.append(f"[flow] {texto}")
        return json.dumps({"ok": False, "preview": False,
                           "report": "\n".join(lineas), "nodes": caja}, ensure_ascii=True)

    def correr(_w):
        try:
            salida = f.evaluar(ops=scatter.ops_flow())
        except flow.FlowValidationError as e:
            caja["_err"] = str(e)
            raise RuntimeError(f"[flow] {e}") from e
        # El inspector mira la caché del último Run. Un grafo de puras ops corre por ACÁ y no por
        # `graph.ejecutar_detalle`, así que sin esto quedaba sin datos que mostrar — y el síntoma
        # era mudo: el panel decía «todavía no corriste el grafo» después de correrlo.
        graph._ULTIMA_CORRIDA.clear()
        graph._ULTIMA_CORRIDA.update({
            nid: (f.resultados.get(nid, {}).get("value")
                  if nodo["kind"] in flow.VALOR_KINDS else salida.get(nid))
            for nid, nodo in f.nodos.items()
            if (f.resultados.get(nid, {}).get("value")
                if nodo["kind"] in flow.VALOR_KINDS else salida.get(nid)) is not None
        })
        lineas = []
        for nid, nodo in f.nodos.items():
            stream = salida.get(nid, [])
            kind = nodo["kind"]
            if kind == "instance":
                out = f.resultados.get(nid, {}).get("out", {})
                txt = (f"{out.get('colocados', 0)} instancias"
                       + (f" · {out['pisados']} evitadas por huella" if out.get("pisados") else "")
                       + ("" if out.get("assets") else " · SIN asset activo ✗"))
                estado = "ok" if out.get("colocados") else "warn"
            elif kind in flow.VALOR_KINDS:
                # Nodos de valor: muestran lo que aportan a la tabla, incluido Text (antes aparecía
                # incorrectamente como un stream vacío de «0 puntos»).
                val = f.resultados.get(nid, {}).get("value")
                nombre = nodo["params"].get("name") or nid
                if isinstance(val, (int, float)):
                    txt = f"{nombre} = {val:.4g}"
                elif isinstance(val, str):
                    txt = f"{nombre} = {val}"
                else:
                    txt = f"{nombre} = (sin resolver)"
                estado = "ok" if val is not None else "warn"
            elif kind == "info":
                # Display: muestra las stats que midió el nodo (cantidad + caja).
                st = f.resultados.get(nid, {}).get("stats", {})
                txt = f"{st['n']} pts · caja {st['w']}×{st['h']}cm" if st.get("n") else "0 puntos"
                estado = "ok" if st.get("n") else "warn"
            else:
                txt = f"{len(stream)} puntos"
                estado = "ok" if stream else "warn"
            caja[nid] = {"estado": estado, "texto": f"{kind}: {txt}"}
            lineas.append(f"[{nid}·{kind}] {txt}")
        return "\n".join(lineas)

    if f.nodos and all(nodo["kind"] in flow.VALOR_KINDS for nodo in f.nodos.values()):
        reporte = correr(widget) + f"\n\nRUN ✓ — {len(f.nodos)} valor(es), sin efectos en la escena"
        return json.dumps({"ok": True, "preview": False, "report": reporte, "nodes": caja},
                          ensure_ascii=True)

    reporte = _preview(correr, owner=owner)
    if "_err" in caja:
        return json.dumps({"report": reporte, "nodes": {}}, ensure_ascii=True)
    return json.dumps({"report": reporte, "nodes": caja}, ensure_ascii=True)


def ejecutar_grafo_json(g_json: str, widget=None, *, owner: str = "graph") -> str:
    """Igual que `ejecutar_grafo` pero devuelve JSON {report, nodes:{nid:{estado,texto}}}: el canvas
    pinta cada nodo con SU veredicto (verde/naranja/rojo, como los estados de Grasshopper).

    `owner` aísla el Preview: la ventana Graph usa el suyo, pero un preset aplicado desde la Dash Bar
    corre como `dash` para que Confirmar/Descartar de esa barra lo resuelvan."""
    import json

    from . import graph
    g = graph.JamGraph.from_json(g_json)
    caja: dict = {}

    # Compile/Preflight ANTES de `_preview`: ningún error estructural, de parámetros o assets puede
    # descartar el preview anterior ni producir efectos parciales en la escena.
    try:
        plan = graph.compilar(g)
    except graph.GraphValidationError as exc:
        lineas = []
        globales = exc.diagnostics.get("_graph", [])
        for nid, nodo in g.nodes.items():
            mensajes = exc.diagnostics.get(nid, []) or globales
            if mensajes:
                texto = " · ".join(mensajes)
                caja[nid] = {"estado": "error", "texto": texto}
                lineas.append(f"[{nid}·{nodo['verb']}] {texto}")
        for nid, mensajes in exc.diagnostics.items():
            if nid in g.nodes:
                continue
            texto = " · ".join(mensajes)
            lineas.append(f"[grafo] {texto}")
        return json.dumps({"report": "\n".join(lineas), "nodes": caja}, ensure_ascii=True)

    def correr(_w):
        texto, por_nodo = graph.ejecutar_detalle(g, plan)
        caja.update(por_nodo)
        if any(resultado.get("estado") == "error" for resultado in por_nodo.values()):
            raise RuntimeError(texto)
        return texto

    if _sin_efectos(g):
        try:
            reporte = correr(widget) + f"\n\nRUN ✓ — {len(g.nodes)} nodo(s), sin efectos en la escena"
        except Exception as exc:  # noqa: BLE001 — el veredicto ya quedó asociado a cada nodo
            reporte = f"[error] RUN sin efectos ✗ — {exc}"
        ok = not any(resultado.get("estado") == "error" for resultado in caja.values())
        return json.dumps({"ok": ok, "preview": False, "report": reporte, "nodes": caja},
                          ensure_ascii=True)

    reporte = _preview(correr, owner=owner)
    ok = not any(resultado.get("estado") == "error" for resultado in caja.values())
    return json.dumps({"ok": ok, "preview": ok, "report": reporte, "nodes": caja},
                      ensure_ascii=True)
