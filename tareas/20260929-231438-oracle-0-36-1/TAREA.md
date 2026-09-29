# Oracle 0.36.1, vendorizado, y oracle cambios antes de cada push

- ESTADO: ABIERTA
- PRIORIDAD: 50
- ETIQUETAS: 

### Nota (2026-09-29 23:14:38 UTC)

2026-09-29, Claude: medido con 0.36.1 antes de subir el pin: VERDE, aceptación 28/4/3, diferencial 1099, mutación 448/448 (igual que con 0.36.0). Pin a 0.36.1 en AGENTS.md (dos) y ORACLE_VERSION; vendor/oracle-pkg reinstalado sin el dist-info viejo; suite 1429 OK (rc 0). Nuevo: .githooks/pre-push (el mismo de LyraGASP, probado allí contra un remoto) corre oracle cambios --desde <sha remoto> --proyecto medidas --confiar-escalares y bloquea si el catálogo se afloja sin reescribir su porque; AGENTS.md lo explica junto con oracle cobertura. Hook activado en este clon (core.hooksPath). El relevo sigue llegando en rojo por verde_editor (d207caf, 2026-08-14), que es anterior a esto.
