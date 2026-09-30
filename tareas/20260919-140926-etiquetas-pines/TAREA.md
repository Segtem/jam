# Las salidas múltiples muestran identificadores en vez de etiquetas

- ESTADO: ABIERTA
- PRIORIDAD: 90
- ETIQUETAS: graph


## Qué se sabe

La fila usa OutPin.Name; dominio aparece como out y los ejes como eje_x. La etiqueta ya existe en el spec.

## Evidencia

RELEVO.md, 0-decies-bis; Reference/Dominio.png; Source/JamEditor/Private/SJamGraphNode.cpp, filas OutPin.Name. Inventario del 2026-09-19; las cifras históricas no son mediciones nuevas.

## Próximo paso

Separar identidad y etiqueta en la presentación; conservar ids de cables y presets, compilar y verificar dominio y matriz por el camino real.

### Nota (2026-09-30 10:16:23 UTC)

2026-09-30, Claude: las filas de salida muestran la ETIQUETA del spec y los cables siguen enganchando por el NOMBRE. El spec ya la mandaba (outs[].label, out_label); el C++ la descartaba en los tres lectores (JamEditorModule.cpp y los dos LeerPines de SJamGraphEditor.cpp). FPin y FJamNodePin ganan Label; la fila usa Visible() (etiqueta o nombre), el tooltip dice «salida «eje X» (eje_x) · tipo V», el clic y los cables usan Name, la salida principal usa out_label («dominio», «traslación»). Compilado con BUILD-JAM.sh; test_etiquetas_pines.py (3; con el C++ viejo fallan 2); en el editor verifica_texto_canvas_58 VERDE y verifica_multi_salida_58 TODO VERDE. Falta VERLO: agregado al gesto-618.
