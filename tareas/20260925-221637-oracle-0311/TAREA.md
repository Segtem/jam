# Subir a Oracle 0.31.1 y regenerar medidas/diferencial/vault.json

- ESTADO: ABIERTA
- PRIORIDAD: 70
- ETIQUETAS: oracle

### Nota (2026-09-25 22:16:37 UTC)

2026-09-25, Claude: con 0.31.0, vault.json sale vencido en este checkout y al día en un worktree limpio del mismo commit: Oracle contaba Vault-kb/.obsidian/workspace.json (ignorado por Git, lo reescribe Obsidian) en la huella de la referencia. Arreglado en Oracle (tarea huella-estado-local, sale en 0.31.1: la huella de un directorio ignora ocultos y __pycache__). Al subir a 0.31.1 la huella cambia una vez (deja de contar .obsidian/ entero): regenerar vault.json con el generador de Jam y medir en verde antes de subir el pin.
