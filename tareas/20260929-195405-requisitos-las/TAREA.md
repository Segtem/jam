# requisitos: las promesas de Jam con su cobertura

- ESTADO: CERRADA
- PRIORIDAD: 60
- ETIQUETAS: 

### Nota (2026-09-29 19:54:05 UTC)

2026-09-29. 16 requisitos en medidas/requisitos/, escritos por agy1 (Docker, clon aparte) y revisados por Claude: espacio (misión ganable), colocación (bounds válidos, sin interpenetración), snap (cuadrar a grilla, encajar al ras), scatter (reparto en área), physics (asentamiento estable), reemplazo (preserva footprint), spline (distribución continua), malla (superficie orientada, sólido cerrado), relevo (testigo íntegro, verificación reproducible), vault (enlaces válidos, nomenclatura estable, taxonomía y metadatos). Cobertura: 16 en parte, 0 medidos enteros, 0 sin medir; las 41 medidas cubren algún requisito. Cada fuente verificada: las 25 citas de agy coinciden con los documentos (sólo le sacó el formato Markdown). oracle test VERDE con la meta el_requisito_nombra_medidas_que_existen; suite 1429 OK; vault.py en verde. oracle cobertura en este repo necesita Oracle 0.36.1 (la 0.36.0 revienta con escalares propias).

### Nota (2026-09-29 23:14:38 UTC)

Con Oracle 0.36.1 publicado: oracle cobertura da 16 requisitos (16 en parte, 0 sin medir, 0 con medidas inexistentes), y las 41 medidas cubren alguno. Las 25 citas de las fuentes verificadas por script contra los documentos (sólo difieren en el formato Markdown).
