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

## Dos familias de icono, con contratos opuestos

`MakeBadge` las separa por el prefijo del archivo:

| | Trazo | Fondo | Tamaño |
|---|---|---|---|
| **Lucide** (`box.svg`) | `#FFFFFF` — es una **máscara** que Slate tiñe de tinta | color de categoría | 68% |
| **Jam** (`jam-box.svg`) | sus **propios colores** | gris casi blanco | 92% |

Teñir un icono propio lo arruinaría, y dejar uno de Lucide sin teñir lo haría invisible. Hay tests
que fijan las dos mitades.

## Los iconos propios: el vocabulario

La lección de la hoja de iconos de Grasshopper no son los dibujos sino cómo están hechos: **cada
icono diagrama el dato**, no una metáfora. «Divide Curve» es literalmente una curva con puntos
encima. Por eso quinientos iconos siguen siendo distinguibles — están compuestos de un vocabulario
compartido.

Acá ese vocabulario es el **sistema de tipos**, con los mismos colores que los pines y los cables:

| Concepto | Se dibuja | Color |
|---|---|---|
| `P` punto | círculo relleno | `#65B1D1` azul |
| `S` curva | línea fina | `#CBAD69` dorado |
| `F` frame | ángulo de dos ejes | `#DA90B8` rosa |
| `M` malla | facetas con relleno tenue | `#50C8CE` cian |
| `N[]` serie | barritas de alturas | `#F6C86F` ámbar |
| `A` asset | cajita | `#7CBF90` verde |
| `AF` variante | cajita lima | `#A6D490` |
| `H` instancias | cajitas verde azulado | `#6FBCB5` |

Consecuencia doble: dos verbos con firma distinta tienen iconos distintos **por construcción**, y el
icono **enseña el tipo** — se aprenden los colores una vez y todos se leen solos.

Los 44 iconos propios se generan con `tools/iconos_jam.py`, donde el vocabulario está escrito como
funciones (`punto()`, `curva()`, `frame()`, `malla()`, `barra()`, `caja()`). Agregar un icono nuevo es
componer esas piezas, no dibujar desde cero:

```bash
python3 tools/iconos_jam.py     # reescribe los jam-*.svg
```

## Estado

- **Tab Mesh: 0 colisiones.** Los 44 verbos tienen pictograma propio.
- El resto de los tabs sigue con Lucide y **comparte** algunos pictogramas. Como el ribbon muestra
  sólo el icono, ésa es la deuda pendiente: seguir el mismo método por tab.

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
