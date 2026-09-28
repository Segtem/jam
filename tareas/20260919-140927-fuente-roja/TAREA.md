# Un nodo fuente rojo permite ejecutar dependientes

- ESTADO: ABIERTA
- PRIORIDAD: 77
- ETIQUETAS: graph


## Qué se sabe

El Run global queda rojo y revierte Preview, pero no cancela todos los dependientes.

## Evidencia

RELEVO.md, MassGameplay Fase 2; Vault-kb/04-Ejecucion-y-pruebas/2026-08-09-ROADMAP-MassEntity-En-Jam-v1.0.md, Fase 2. Inventario del 2026-09-19; las cifras históricas no son mediciones nuevas.

### Nota (2026-09-28 01:43:34 UTC)

2026-09-27, Claude: hecho. graph.ejecutar_detalle lleva «rotos» (nodo → fuente del fallo): un nodo con cualquier padre roto —por el stream, el asset o un pin de datos— no corre y queda en estado «cancelado» con «no corre: «X» falló aguas arriba», nombrando la fuente ORIGINAL también en los nietos; una rama independiente corre igual. Antes el hijo recibía None y corría: fallaba con un error espurio o, si toleraba la entrada vacía, hacía su efecto con nada. El Run ya quedaba rojo y revertía el Preview por la fuente; eso no cambia. Slate: estado nuevo «cancelado» en SJamGraphNode.cpp con glifo ↑ (verificado con fc-query en DroidSansFallback.ttf del motor; mismo método da ▲ sí y ⏻ no; sumado a PERMITIDOS de test_paleta), borde rojo apagado y tooltip con la causa. No se reusó «omitido»: su tooltip dice «se está viendo otro nodo», que sería mentir la causa. Flow no tiene la cascada (una op que revienta corta el evaluar entero). Tests: test_fuente_roja.py, 6; contra HEAD fallan 3 (los otros son controles). Compilado con tools/build.py (binario al día). Editor (JamPlayground, verifica_params_y_fuente_roja_58.py, Run del Graph por panel.ejecutar_grafo_json): curve_bezier → curve_frames(37) → mass_spec(budget=5) → mass_spawn → mass_inspect da receta=error, poblacion=cancelado, medir=cancelado nombrando «receta», ok=false. Suite 1258 OK; oracle test VERDE. Lo que queda para las manos de Brian: ver el ↑ y el color en el canvas.

## Próximo paso

Ninguno de código. Mirar en el canvas que un nodo cancelado se lee (glifo ↑, borde rojo apagado, tooltip).
