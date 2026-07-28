# Lucide para los nodos de Jam

Set inicial de 45 iconos SVG descargado del repositorio oficial de Lucide:

- Fuente: <https://github.com/lucide-icons/lucide>
- Commit: `d29db5e98e194c05469dd6dba855aef4c48b8048`
- Licencia: ISC, incluida en `LICENSE.txt` (algunos iconos derivados de Feather conservan además MIT)
- Formato: SVG `24×24`, trazo de 2 unidades

## Adaptación para Slate

La geometría de los iconos no fue alterada. Se reemplazó `stroke="currentColor"` por
`stroke="#FFFFFF"`, porque los SVG incluidos por Unreal usan colores explícitos y el blanco permite
teñir el brush completo mediante `FSlateColor`. Jam aplica un gris casi negro para que el pictograma
se lea como tinta sobre el cuerpo claro de los componentes y los badges de categoría.

**Nueve iconos NO son de Lucide**: `stairs`, `stairs-curved`, `capsule`, `torus`, `normals`,
`square`, `bake`, `frames` y `bark` están dibujados para Jam en el mismo estilo (24×24, trazo 2,
extremos redondeados). Son obra propia y **no** están cubiertos por `LICENSE.txt`.

## Deuda: iconos únicos

El ribbon muestra **sólo el icono**, con el nombre en el tooltip (el modelo de Grasshopper). Eso
vuelve crítico que cada verbo tenga pictograma propio: dos fichas con el mismo SVG son literalmente
indistinguibles.

Quedan **21 verbos de 95** compartiendo icono, todos en la pestaña Mesh, que es la más grande:

| Icono | Verbos que lo comparten |
|---|---|
| `copy` | copy_asset_selection · copy_mesh_to_frames · mesh_from_asset |
| `boxes` | asset_set · hism_output |
| `circle` | mesh_disc · mesh_sphere |
| `circle-pile` | mesh_cylinder · mesh_sphere_box |
| `git-merge` | curve_branches · curve_child |
| `move-3d` | mesh_transform · transform_frames |
| `palette` | mesh_color · mesh_material |
| `route` | mesh_pipe · mesh_pipe_profile |
| `scan` | mesh_round_rect · mesh_uv_scale |
| `spline-pointer` | curve_bezier · mesh_along_curve |

Es la lista de trabajo para la tanda de iconos propios.

`icon-map.json` propone un icono para cada verbo existente en `jam.tools` y `jam.flow`. Varios verbos
comparten pictograma deliberadamente; primero hay que probar la lectura real a 16–20 px antes de crear
variantes más específicas.

`JamEditor` lee el mapping una vez al abrir la interfaz. Los SVG aparecen en el centro de los nodos y
en las fichas de herramientas; si falta una entrada o un archivo, vuelve automáticamente al nombre
vertical/código corto anterior.

## Cómo cambiar o agregar un icono

1. Descarga el SVG desde <https://lucide.dev/icons/> y guárdalo en esta carpeta con nombre minúsculo.
2. Cambia `stroke="currentColor"` por `stroke="#FFFFFF"`. El blanco es la máscara que Slate tiñe con
   el color de categoría.
3. Abre `icon-map.json` y asigna el nombre exacto del verbo al nombre del archivo, sin `.svg`:

   ```json
   "scatter": "chart-scatter"
   ```

4. Valida el JSON con `jq -e . Resources/Icons/Lucide/icon-map.json`.
5. Reinicia Unreal para recargar el mapping. Cambiar solamente el SVG o el JSON no requiere recompilar
   `JamEditor`.

Para un verbo nuevo, la clave debe coincidir exactamente con el campo `verbo` emitido por el spec de
`jam.tools` o `jam.flow`. No borres `LICENSE.txt` al distribuir el plugin.
