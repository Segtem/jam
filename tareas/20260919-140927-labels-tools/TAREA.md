# El registro conserva herramientas sin nombre visible

- ESTADO: CERRADA
- PRIORIDAD: 70
- ETIQUETAS: graph


## Qué se sabe

El corte histórico midió 136 defectos sin label y fijó un tope; no se asume que la cifra siga vigente.

## Evidencia

RELEVO.md, deuda del registro; Content/Python/jam/registro_core.py. Inventario del 2026-09-19; las cifras históricas no son mediciones nuevas.

## Próximo paso

Ejecutar la auditoría actual y nombrar primero las tools visibles en Dash, migrando por superficie y sin elevar la cota.

### Nota (2026-09-30 10:29:46 UTC)

HECHO 2026-09-30: registro_core.auditar da 0 defectos (eran 136, todos «sin label»). Repartido en worktrees: agy1 los 81 del REGISTRO de registro.py, agy2 las 29 ops de Flow (flow.OPS_META), Codex los 26 nodos de material (tabla de etiquetas en _registrar_nodos_material, sin tocar las tuplas que desempaqueta test_material_verbos). Faltaba una línea que ninguno tenía: _registrar_ops_flow no copiaba el label de OPS_META al registro (se lo había dicho mal a agy2). Revisado contra HEAD: los mismos verbos, ningún otro campo cambió, ninguna etiqueta repetida, ninguna que ya existiera tocada. test_la_deuda_de_declaracion_no_crece pasa de «<= 136» a «== 0». Suite OK; verifica_registro_neutro_58 VERDE en JamPlayground.
