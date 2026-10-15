# Mudar Jam a Oracle Factory

- ESTADO: CERRADA
- PRIORIDAD: 50
- ETIQUETAS: 

### Nota (2026-10-15 19:46:03 UTC)

2026-10-15: mudado a Oracle Factory 0.1.0a10, que fija la misma Oracle que Jam (0.38.2): no hizo falta subir nada. Base medida antes: oracle test VERDE (aceptación 28 rojos / 9 sin evidencia esperada / 3 verdes, diferencial 1099, mutación 458/458). Factory instalado como herramienta (uv tool install oracle-factory==0.1.0a10), sin exponer dependencias; vendor/oracle-pkg/ no se toca. oracle-factory init --oracle medidas creó .factory/ ("oracle": "medidas", "confiar_escalares": true) sin tocar tareas/ ni medidas/ (hashes iguales). Prueba de humo en un clon descartable: un cambio importa su requisito en medidas/requisitos/, carga el catálogo con los escalares (colocacion.interpenetracion usa es_fondo) y lista las 44 medidas del proyecto. AGENTS.md suma «Cambios con Oracle Factory», para los dos agentes de turno. Tests 1448 OK. Sin probar: juzgar con hechos de las sondas (necesita el editor) y pedir-revision (sin revisores declarados).
