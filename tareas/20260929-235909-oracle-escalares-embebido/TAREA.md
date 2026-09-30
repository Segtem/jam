# Dentro de Unreal la sombra de Oracle no evalúa: el trabajador de escalares se lanza con sys.executable, que ahí es UnrealEditor

- ESTADO: CERRADA
- PRIORIDAD: 90
- ETIQUETAS: oracle, verificacion

## Qué se ve

`tools/experiments/verifica_oracle_shadow.py` en JamPlayground (2026-09-29, tarea `editor-vigente`):
`JAM_ORACLE_SHADOW_58 ROJO — placement=True snap=False scatter=False spline=True physics=True
reemplazo=True espacio=True`, y TODOS los dominios en el log con
`[Jam][Oracle sombra] <dominio> NO EVALUÓ — EscalaresInvalidas: falló medidas/escalares.py: el
trabajador de escalares emitió datos inválidos`. La sombra no gobierna, así que nada se rompe a la
vista: sólo se deja de medir, y lo dice un error en el log.

## Causa (medida)

Oracle aísla `escalares.py` en un proceso aparte (`nucleo/aislamiento/escalares.py`,
`TrabajadorEscalares.iniciar`, desde el commit de Oracle `ba9f2ff`): lo lanza con
`[sys.executable, "-B", "-m", "nucleo.aislamiento.escalares", …]`. En el Python embebido de Unreal
`sys.executable` es `…/Engine/Binaries/Linux/UnrealEditor` (sonda del 2026-09-29: `executable=
…/UnrealEditor version=3.11.8`), así que el «trabajador» es otro editor, no un Python. Fuera del
motor (`oracle test`, `oracle juzgar`, `colocar_y_juzgar.py`) anda: ahí `sys.executable` es Python.

## Qué hacer

El arreglo es de Oracle (repo aparte, `~/Dev/oracle`): elegir el intérprete del trabajador sin
confiar en `sys.executable` cuando no es un Python (p. ej. una variable `ORACLE_PYTHON`, o
`sys._base_executable`/`python3` del PATH si el ejecutable no se llama python), publicar, y subir Jam
por el camino de siempre (medir antes de tocar el número; no editar `vendor/oracle-pkg/`). Del lado
de Jam, `jam/bridge.py` podría fijar esa variable al Python de UE
(`Engine/Binaries/ThirdParty/Python3/Linux/bin/python3`). Criterio: `verifica_oracle_shadow.py`
en VERDE con todos los dominios evaluados.

## Próximo paso

Decidir con Brian si se arregla ahora en Oracle.

### Nota (2026-09-30 00:54:08 UTC)

2026-09-30: arreglado en Oracle 0.36.2 (tag v0.36.2, Oracle 38c1ed4; el trabajador elige su intérprete: ORACLE_PYTHON primero). En Jam, bridge.py fija ORACLE_PYTHON al python3 de Unreal (Engine/Binaries/ThirdParty/Python3/Linux/bin/python3, 3.11.8). Medido con el wheel local en vendor/ antes del pin: verifica_oracle_shadow en BotOO TODO VERDE (24 evaluaciones, 0 NO EVALUÓ); en JamPlayground la sombra evalúa todo, y el ROJO que queda es de los selftest de Jam (tarea selftest-primera-malla). Falta: publicación en PyPI (Brian) y el pin a 0.36.2.

### Nota (2026-09-30 10:06:19 UTC)

2026-09-30, Claude: Oracle 0.36.2 publicado en PyPI (sha256 verificados) y vendorizado en Jam; el pin está en la tarea oracle-0-36-2. Con esto se cierra: bridge.py fija ORACLE_PYTHON y el vendor ya trae el trabajador que lo respeta. El rojo de los selftest de JamPlayground sigue en su propia tarea (selftest-primera-malla).
