# Subir a Oracle 0.31.1 y regenerar medidas/diferencial/vault.json

- ESTADO: CERRADA
- PRIORIDAD: 70
- ETIQUETAS: oracle

### Nota (2026-09-25 22:16:37 UTC)

2026-09-25, Claude: con 0.31.0, vault.json sale vencido en este checkout y al día en un worktree limpio del mismo commit: Oracle contaba Vault-kb/.obsidian/workspace.json (ignorado por Git, lo reescribe Obsidian) en la huella de la referencia. Arreglado en Oracle (tarea huella-estado-local, sale en 0.31.1: la huella de un directorio ignora ocultos y __pycache__). Al subir a 0.31.1 la huella cambia una vez (deja de contar .obsidian/ entero): regenerar vault.json con el generador de Jam y medir en verde antes de subir el pin.

### Nota (2026-09-26 02:19:14 UTC)

2026-09-26, Claude: hecho. Con 0.31.1 vendorizado, vault.json se regeneró (sólo cambió la huella de la referencia, ya sin .obsidian/) y relevo.json también (sólo la huella del catálogo: 0.31.1 reescribió la defensa de proceso.verificacion_vigente, que este fixture usa). oracle test VERDE en este checkout: aceptación 32/3, diferencial 1099, mutación 448/448; suite 1241 OK.
