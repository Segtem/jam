---
title: "Nodo Graph: Convert to Nanite"
tipo: INFORME
version: "1.0"
date: 2026-07-26
updated: 2026-07-26
status: implementado
area: 03-Mesh-y-materiales
tags:
  - jam
  - graph
  - nanite
  - static-mesh
  - preview
---

# Nodo Graph: Convert to Nanite

## Contrato

`nanite` es un conversor de assets `A → A` para `StaticMesh`:

```text
Asset / Pick → Nanite → Place / Scatter / PCG / otro consumidor A
```

- Si la malla ya tiene Nanite habilitado, es un passthrough idempotente y devuelve el mismo asset.
- Si no tiene Nanite, duplica la malla y fuerza `enabled=true` mediante
  `StaticMeshEditorSubsystem.set_nanite_settings(..., apply_changes=True)`. Unreal ejecuta el
  `NaniteBuild` antes de guardar.
- Una `GeometryCollection` u otro tipo de asset falla con un diagnóstico explícito; el nodo sólo
  acepta `StaticMesh` aunque visualmente ambos pertenezcan por ahora al tipo general `A`.

## Decisión de seguridad

`Run graph` **no modifica la malla fuente**. La conversión se realiza sobre una copia bajo:

```text
/Game/JamPreview/graph/PV_<run-id>_<nombre>_Nanite
```

- `Discard` borra la copia temporal.
- `Bake` la promueve a `/Game/Jam/Nanite/<nombre>_Nanite`.
- Si el nombre final existe, Bake usa `_2`, `_3`, etc.; nunca lo sobreescribe.
- `Run → Bake → Run → Discard` conserva el primer asset baked.

Esto mantiene la semántica del Graph coherente con Fracture y PCG: Run prepara, Bake fija y Discard
revierte. Convertir directamente el asset de origen habría hecho que Discard fuera engañoso y habría
introducido una mutación permanente durante Preview.

## Preview sin actores

Este nodo puede usarse solo (`Asset → Nanite`) y producir cero actores de nivel. Se amplió la
transacción de `panel.py` para que Bake/Discard también reconozcan previews compuestos únicamente por
Content:

- índice por owner durante la sesión;
- metadatos `JamPreviewOwner` y `JamPreviewFinal` en el asset temporal;
- recuperación de esos metadatos después de recargar Python;
- limpieza de los metadatos al promover el asset.

## Interfaz

- Categoría: `Create`.
- Nombre/verbo: `nanite`.
- Entrada principal y campo cableable: asset `A`.
- Salida: asset `A`.
- Icono Lucide: `circle-pile`, reutilizado como representación de clusters Nanite.
- No tiene parámetros: siempre fuerza Nanite cuando hace falta.

## Verificación

- Suite Python headless: **37/37 tests OK**.
- Prueba real con Unreal Engine **5.7.4**:
  - duplicó una `StaticMesh` temporal;
  - ejecutó `NaniteBuild` sobre la copia;
  - verificó `enabled=true` en la salida y `enabled=false` en la fuente;
  - eliminó todo el contenido de prueba al terminar.
- Prueba real transaccional en proyecto temporal:
  `Run → Bake → Run → Discard`, con el asset baked preservado.
- La misma transacción se recuperó correctamente después de vaciar el índice de sesión, simulando
  una recarga de Python a partir de los metadatos persistentes del asset temporal.
- `BuildPlugin` para Linux con Unreal Engine **5.7.4**: **BUILD SUCCESSFUL**; el paquete incluye
  `nanite.py`, el mapa de iconos y la dependencia `EditorScriptingUtilities`.

## Archivos principales

- `Content/Python/jam/nanite.py`: adaptador de conversión y rutas.
- `Content/Python/jam/tools.py`: registro, ejecución y propagación `A → A`.
- `Content/Python/jam/panel.py`: soporte para Preview de Content sin actores.
- `Resources/Icons/Lucide/icon-map.json`: icono del nodo.
- `Content/Python/tests/test_nanite.py`: conversión e idempotencia.
- `Content/Python/tests/test_preview_transaction.py`: Bake/Discard asset-only.

## Relacionado

- [[2026-07-26-PLAN-Preview-Transaccional-Efectos-PCG-v1.0|Preview transaccional y efectos de PCG]]
- [[2026-07-25-PLAN-Compilacion-Estricta-Preview-Bake-v1.0|Compilación estricta y ciclo Preview/Bake]]
- [[2026-07-25-PLAN-Contratos-Defensivos-Tools-Assets-v1.0|Contratos defensivos de tools y assets]]
