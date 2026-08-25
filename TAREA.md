# Tarea — tres medidas de Jam dan un rojo sin testigos útiles

Leé `DOCTRINA.md` primero. **Ojo: estás en el repositorio JAM, no en Oracle.** Las reglas de la
doctrina valen igual, pero los comandos llevan `--proyecto medidas` y salen de `vendor/oracle/`.

## El problema, exacto

Jam consume Oracle por subtree (`vendor/oracle`, no se edita a mano). Al actualizarlo, una medida
universal **nueva** encontró algo real en el catálogo de Jam:

    python vendor/oracle/tools/aceptacion.py --proyecto medidas --confiar-escalares

    ✗ meta.toda_medida_filtra_o_agrupa   3 (<= 0)
        → snap.al_ras · snap.comparte_cara · scatter.cobertura

Las tres miden la relación completa: no tienen `donde` ni `agrupar`.

**No es un problema de estilo.** Los testigos de una medida son las filas que sobrevivieron al
`donde`; sin `donde`, un rojo entrega TODAS las filas, incluidas las que no ofendieron. Medido sobre
`scatter.cobertura` con tres filas y una sola mala:

    como está      → ROJO, valor 0.2, testigos: 3 filas  (0.9, 0.2, 0.8)
    con el filtro  → ROJO, valor 0.2, testigos: 1 fila   (0.2)

Un rojo que no puede señalar qué ofendió obliga a la persona a buscarlo a mano, que es exactamente lo
que Oracle existe para evitar.

Fijate que la macro `peor` de Oracle (`vendor/oracle/nucleo/macros/peor.oracle`) emite ese filtro
sola — por eso el catálogo de Oracle nunca cae en esto y el de Jam sí: las tres están escritas a mano.

## Qué hay que hacer

Arreglar las tres medidas: `medidas/catalogos/geometria/snap.al_ras.json`,
`medidas/catalogos/geometria/snap.comparte_cara.json` y
`medidas/catalogos/scatter/scatter.cobertura.json`.

**La restricción dura, y es la que hace verificable la tarea: el VEREDICTO y el VALOR de cada medida
tienen que quedar IDÉNTICOS sobre todos los casos del corpus de Jam.** Lo único que cambia son los
testigos, que pasan a ser sólo las filas que ofenden. Si algún veredicto se mueve, la reescritura
está mal — no aflojes el caso, arreglá la medida.

Comprobalo ANTES y DESPUÉS y pegá las dos salidas en el informe:

```bash
python vendor/oracle/tools/aceptacion.py --proyecto medidas --confiar-escalares
python vendor/oracle/tools/mutar.py      --proyecto medidas --confiar-escalares
```

Dos caminos posibles, y elegís vos con argumento escrito:

1. **usar la macro `peor`**, si la medida encaja en su forma (`peor` toma la tolerancia UNA vez y con
   ella arma el filtro y el umbral — mirá `vendor/oracle/nucleo/macros/peor.oracle`);
2. **agregar el `donde` a mano**, si no encaja.

Ojo con los umbrales: `snap.comparte_cara` es `min ... umbral > 1.0` y `scatter.cobertura` es
`min ... umbral >= 0.6`. El filtro tiene que seleccionar **lo que ofende**, que es la negación del
umbral, no el umbral. Pensalo caso por caso y escribí en el informe cuál es la fila que ofende en
cada una.

## La deuda vieja, de paso

    python vendor/oracle/tools/corpus.py --proyecto medidas

falla porque `medidas/corpus/scatter/004-coberturas-distintas.json` tiene `id`
`scatter-004-coberturas-distintas` y el archivo se llama `004-coberturas-distintas`. El `id` de un
caso tiene que ser el nombre del archivo.

Arreglalo, y **decidí con argumento cuál de los dos es el correcto**: mirá cómo se llaman los otros
casos del corpus de Jam y seguí esa convención. Si cambiás el `id`, revisá que nada más lo referencie
—buscalo en todo el repo— porque un `id` de caso puede estar citado desde otro lado.

## Lo que NO tenés que hacer

- **NO toques `vendor/oracle/`.** Es un subtree: editarlo lo separa del upstream en silencio. Si algo
  de Oracle está mal, anotalo en `INFORME.md` y seguí.
- **NO toques `git stash`, `git clean`, `git checkout .` ni `git reset`.** El repositorio tiene
  trabajo del usuario en curso fuera de tu worktree.
- **No cambies ningún caso del corpus para que una medida pase.** Si una medida arreglada cambia un
  veredicto, la medida está mal. Esto no es negociable: es la falla que el proyecto entero existe
  para no cometer.
- **No agregues medidas nuevas.** Arreglás tres y un `id`.
- No toques las otras 38 medidas de Jam.

## Cómo sé que terminaste

1. `aceptacion.py` y `corpus.py` en verde, con la salida pegada.
2. `mutar.py` sin sobrevivientes, con la salida pegada.
3. La comparación antes/después mostrando que **ningún veredicto ni valor cambió**.
4. En el informe, la fila que ofende en cada una de las tres.

Commiteá en tu worktree. No pushees.
