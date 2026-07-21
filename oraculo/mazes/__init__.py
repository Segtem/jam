"""Piloto de mazes — KB de craft como DIMENSIONES medibles + archivo MAP-Elites.

La tesis (ver vault: CONCEPTO Graybox Capa 0): no optimizar UN maze, sino DESCUBRIR
una colección DIVERSA de mazes ganables → emergencia. La receta:

  variación (generación libre)  →  selección (oráculos verificables)  →  archivo por NICHOS

Acá:
  - `descriptors.py`  el KB de craft de laberintos vuelto medible (largo de solución ×
                      branching × dead-ends) — las DIMENSIONES del espacio de comportamiento.
  - `archive.py`      MAP-Elites: cada nicho (combinación de descriptores) guarda su elite.
                      La COBERTURA (nichos llenos) es la señal de emergencia, no un score único.
  - `generate.py`     operador de variación procedural (recursive backtracker + braiding).
                      Pluggable: el LLM (anti-inyección) lo reemplaza más adelante.
  - `spec.py`         layout de chars → JamSpec de maze (jugable-verificable por JamEnv).
"""
