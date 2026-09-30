# Las matrices no tienen consumidor en el adaptador Unreal

- ESTADO: CERRADA
- PRIORIDAD: 84
- ETIQUETAS: graph


## Qué se sabe

Once verbos resuelven matrices en el cerebro. Jam y Unreal usan convenciones opuestas; la conversión pertenece exclusivamente a ue.py.

## Evidencia

RELEVO.md, agenda A y 0-decies; Content/Python/jam/math_core.py. Inventario del 2026-09-19; las cifras históricas no son mediciones nuevas.

## Próximo paso

Elegir el primer consumidor de escena y adaptar mediante transposición; verificar composición y traslación con objetos reales sin duplicar la convención del cerebro.

### Nota (2026-09-30 14:01:09 UTC)

HECHO 2026-09-30: primer consumidor de escena = mesh_transform, con un pin de datos opcional matrix (MX) que se aplica DESPUÉS de los campos. Núcleo (Godot/Unity): malla_ops._por_matriz, M·v, normales por la inversa transpuesta, caras al revés si espeja. Unreal: ue.transform_de_matriz, la ÚNICA transposición de convención (cada fila del FMatrix es una columna de la de Jam) → FTransform → Geometry Script. math_core.mx_trs rechaza, igual en los tres motores, lo que un FTransform no representa: proyección, eje aplastado, cizalla (con el motivo). test_mesh_transform_matriz.py (5); tools/experiments/verifica_matriz_transform_58.py VERDE en JamPlayground (rotar+trasladar, escala no uniforme con rotación oblicua, espejo con volumen positivo, campos y después matriz: caja idéntica a la del núcleo al centésimo; cizalla rechazada con su motivo); sin la transposición da ROJO en 3 de 4.
