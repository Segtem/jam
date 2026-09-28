# El contrato del motor

Lo que el núcleo de Jam (Python, fuera del motor) le pide al plugin de cada motor. Todo lo demás se
calcula en el núcleo, igual en los tres. Implementaciones: `Godot/addons/jam/plugin.gd` (8792) y
`Unity/Assets/Jam/Editor/JamServidor.cs` (8793). Unreal no habla este contrato: su adaptador
(`jam.tools`) es Python dentro del editor.

**Transporte.** TCP en 127.0.0.1, una línea de JSON por pedido (`{"op": …, …}`) y otra por respuesta
(`{"ok": true, …}` o `{"ok": false, "error": "…"}`). La lista de operaciones es CERRADA: no se evalúa
código.

**Marco.** Todo viaja en el marco del núcleo, que es el de Unreal: centímetros, Z arriba, mano
izquierda, `yaw` en grados alrededor de Z con `(1,0,0) → (cos, sin, 0)`. El plugin traduce a lo
suyo y devuelve los hechos traducidos de vuelta, MEDIDOS sobre lo que el motor guardó.

**Preview.** Lo que Jam muestra y todavía no se fijó cuelga de un nodo `JamPreview` de la escena y
no se guarda. `fijar` lo vuelve escena normal; `descartar` lo borra.

## Operaciones

| op | pide | responde |
|---|---|---|
| `hola` | — | `motor`, `contrato` (1), `version`, `primitivas`: la lista de ops que implementa |
| `mostrar_malla` | `nombre`, `malla` (`vertices`, `triangulos`, `normales`, `uv0`) | `nodo`, `hechos` de la malla |
| `descartar` | — | `descartados` |
| `fijar` | — | `fijados` |
| `hechos` | — | `mallas`: `[{nodo, hechos}]` del Preview |
| `guardar_malla` | `nombre`, `malla` | `ruta`: la malla guardada como asset del motor (pisa la anterior del mismo nombre) |
| `resolver_asset` | `nombre`: ruta del motor o nombre de archivo sin extensión | `ruta`, `min`, `max`: la caja LOCAL del asset (cm) |
| `colocar` | `ruta`, `nombre`, `instancias`: `[{pos: [x,y,z], yaw, escala: [sx,sy,sz]}]` | `nodo`, `instancias`: `[{min, max}]`, la caja de MUNDO de cada una, medida |
| `raycast` | `rayos`: `[{desde: [x,y,z], hacia: [x,y,z]}]` | `golpes`: `[{golpe, punto, normal}]` |

Las tres últimas más `guardar_malla` son las primitivas de colocación (2026-09-28). Un plugin que no
las anuncia en `hola` sigue funcionando para lo demás.

- **`resolver_asset`.** Con un nombre suelto, tiene que haber EXACTAMENTE un asset de malla o escena
  con ese nombre de archivo (sin distinguir mayúsculas); si hay cero o varios, `ok: false` diciendo
  cuál de los dos casos es (y, si hay varios, cuáles).
- **`colocar`.** Un nodo de grupo `nombre` bajo `JamPreview` (reemplaza al anterior del mismo nombre:
  correr dos veces no apila copias), con un hijo por instancia. El orden de la transformación es
  escala, después `yaw`, después posición. En Godot y Unity el `yaw` del núcleo es un giro de
  `-yaw` alrededor del eje vertical (la traducción de marco es una reflexión) y la escala
  `(sx, sy, sz)` pasa a `(sx, sz, sy)`. `min`/`max` de cada instancia es la caja envolvente de mundo
  de la instancia —la del asset transformada por sus 8 esquinas—, en el orden en que llegaron.
- **`raycast`.** Contra la geometría de malla de la escena abierta, el golpe más cercano a `desde`
  sobre el segmento. IGNORA el Preview sin fijar, como Unreal ignora lo de Jam sin confirmar: si no,
  cada Run se apoyaría encima del anterior. `normal` es la de la cara golpeada, unitaria, del lado
  de `desde`. Sin golpe: `{golpe: false}`.

## Lo que el núcleo hace con ellas

`asset`, `mesh_to_static` y `place` corren con estas primitivas (`jam.colocacion`): el núcleo
decide dónde va cada instancia —reparto por huella, variación por semilla, ancla sobre la caja
girada y escalada, `surface` por raycast— y el motor sólo instancia. La verificación cruzada
(`tools/experiments/verifica_colocar.py`) compara la caja de mundo de cada instancia contra lo que
coloca Unreal.
