# Actualizar Jam a Oracle 0.38.1 desde PyPI

- ESTADO: CERRADA
- PRIORIDAD: 80
- ETIQUETAS: oracle, release

### Nota (2026-10-02 18:00:46 UTC)

Instalé Oracle 0.38.1 desde PyPI en la herramienta global y actualicé vendor/oracle-pkg desde el wheel publicado para el intérprete embebido de Unreal. Actualicé ORACLE_VERSION, AGENTS.md, pin y scripts. Validación: suite Jam 1448 tests OK; test_oracle_embedding 43 OK; oracle test --proyecto medidas --confiar-escalares VERDE (194 corpus, 580 acuerdos diferenciales, 487/487 mutantes muertos). El paquete vendorizado debe conservar el .lock y no incluir bin/.

## Próximo paso

Tarea cerrada: Oracle 0.38.1 de PyPI quedó instalado en ambos caminos de Jam y la suite pasó.
