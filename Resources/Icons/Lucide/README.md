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
