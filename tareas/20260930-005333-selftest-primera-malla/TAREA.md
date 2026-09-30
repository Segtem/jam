# Los selftest de snap y scatter usan la primera malla de la biblioteca: en JamPlayground es Pino y dan rojo

- ESTADO: CERRADA
- PRIORIDAD: 60
- ETIQUETAS: verificacion

## Qué se sabe

`verifica_oracle_shadow.py` (2026-09-30, con Oracle 0.36.2 ya evaluando dentro de Unreal): en BotOO
TODO VERDE; en JamPlayground ROJO con `snap FALLÓ (grilla True→True, ras clavado→al_ras)` y `scatter
FALLÓ (sano.ok=False, denso.interpenetra=36 pares)`. La sombra coincide con la referencia en los dos:
lo que falla es el selftest de Jam, no Oracle. `menu.selftest_*` toman `library.buscar(limit=1)`, la
primera StaticMesh por nombre, y en JamPlayground es `/Game/Jam/Meshes/Pino` (un árbol, desde el
2026-09-10): el reparto «sano» se encima con esa huella. El propio `menu.py` (línea ~180) ya advierte
que no hay que asumir un cubo de 100 cm. Nunca se verificó en JamPlayground (nació después de que
esos selftests se certificaran en BotOO).

## Qué hacer

Que los selftest elijan su malla a propósito (p. ej. `/Engine/BasicShapes/Cube`, que está en todo
proyecto) en vez de la primera de la biblioteca, y verlos verdes en JamPlayground y en BotOO.

## Próximo paso

Cambiar la elección de malla en `menu.selftest_snap` y `selftest_scatter`.

### Nota (2026-09-30 10:10:33 UTC)

HECHO: menu._malla_de_prueba() elige /Engine/BasicShapes/Cube (y si no existe, la primera de la biblioteca, como antes) para los ocho selftest. verifica_oracle_shadow: JamPlayground TODO VERDE (antes ROJO snap/scatter con Pino) y BotOO TODO VERDE, los dos con elegido «Cube» y 0 «NO EVALUÓ» con Oracle 0.36.2.
