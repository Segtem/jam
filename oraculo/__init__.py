"""Oráculo de Jam — verificadores deterministas, agnósticos del motor.

Semilla rescatada del viejo monorepo `jamprotocol`. Se re-cablean imports a
medida que cada verificador entra en uso desde el plugin (era `src.*`, ahora
`oraculo.*`). El corazón para BotOO vive en `mazes.spacegraph`: el grafo del
espacio + el oráculo de winnability (BFS sobre el grafo anotado).
"""
