---
title: "P3 de Oracle: autonomía de embedding antes de migrar Jam"
tipo: PLAN
version: "1.0"
date: 2026-07-31
updated: 2026-07-31
status: completo
area: 00-Proceso
tags:
  - oracle
  - arquitectura
  - embedding
  - autonomia
  - api
  - jam
aliases:
  - P3 de Oracle
  - Autonomía de embedding de Oracle
---

# P3 de Oracle: autonomía de embedding antes de migrar Jam

## Decisión

Oracle ya era independiente de Jam en su **semántica**: el núcleo consume relaciones de hechos,
selecciona medidas por sus entradas y no importa Unreal ni perfiles particulares. P3 cerró además su
autonomía como **biblioteca embebible**: el consumidor usa `oracle_metalenguaje.Motor`, cada instancia
posee su estado y el wheel sólo instala paquetes dentro de ese namespace.

Jam todavía no migró sus `oracle_*`. Esa integración es el paso siguiente y no forma parte del cierre
de la abstracción interna de Oracle.

## Evidencia de apertura

La comprobación del 2026-07-31 instaló `oracle-metalenguaje 0.1.0` en un virtualenv temporal, sin
dependencias. El entry point `oracle-medida` leyó `jam/medidas` correctamente desde fuera del checkout.
La misma instalación expuso los límites:

- instala `nucleo`, `catalogos`, `perfiles` y `tools` como paquetes de nivel superior;
- no existe una fachada pública en `nucleo/__init__.py`;
- `oracle-aceptacion` sin proyecto falla con `falta corpus/`, porque el wheel distribuye catálogos
  pero no el corpus de autocertificación;
- las herramientas capturan proyecto y argumentos al importarse;
- el registro de UDF se restaura entre contextos, pero sigue siendo global al proceso.

Esto no invalida P2: un proyecto externo completo ya recorre autoría, aceptación, diferencial,
mutación y estudio. P3 distingue ejecución externa por CLI de embedding dentro de otro producto.

## Contrato que se quiere obtener

```python
from oracle_metalenguaje import Motor

motor = Motor.desde_proyecto(
    "/ruta/al/proyecto",
    confiar_escalares=True,
)

informe = motor.evaluar({
    "pieza": [...],
    "vecina": [...],
})
```

El consumidor produce hechos y recibe un informe. No modifica `sys.path`, no importa `nucleo.*` y no
activa registros globales. Jam conserva el adaptador Unreal → hechos; Oracle conserva el juicio.

## Avance 1 — fachada y aislamiento (2026-07-31)

El primer bloque quedó implementado en Oracle, todavía sin migrar Jam:

- `oracle_metalenguaje.Motor` es la frontera pública de embedding;
- construye desde una ruta explícita, desde formas JSON en memoria o desde objetos `Medida`;
- selecciona juezas por las relaciones declaradas y levanta `SinMedidasAplicables` si no hay ninguna;
- límites, catálogo y UDF pertenecen a la instancia;
- las medidas se copian al entrar y al exponerse, de modo que una lista interna de `Medida` no
  permite mutar por referencia el catálogo del motor;
- `RegistroEscalares` viaja explícitamente por carga, validación y evaluación;
- dos proyectos con la misma UDF y funciones distintas se construyen y evalúan en paralelo sin
  tocar `ESCALARES` global;
- `escalares.py` continúa siendo código opt-in; una escritura directa al global desde un motor se
  rechaza y se revierte;
- `oracle.json` admite `"catalogo_base": false`; al omitirlo, proyectos v1 conservan `true`;
- el wheel se construye, instala en un virtualenv limpio y ejecuta `Motor` con `python -I` desde un
  directorio vacío; el programa consumidor sólo importa `oracle_metalenguaje`.

La evidencia al cerrar el bloque es:

- 327 tests;
- 129/129 mutantes de medida;
- particiones modificadas: `algebra` 245/245, `medida` 98/98, `proyecto` 93/93 y `Motor` 23/23;
- denominador de código ampliado de 1073 a 1118 sitios;
- corpus 42/42 y aceptación con 27 defectos rojos, 12 verdes correctos y cero huecos abiertos;
- Oracle sigue sin fixtures diferenciales propios: `oracle-diferencial` informa esa ausencia y sale
  distinto de cero; no se lo contabiliza como una verificación verde.

La mutación descubrió una reversión no fijada cuando fallaba el cuerpo del contexto de UDF. Se añadió
la regresión transaccional y la partición de proyecto cerró 93/93. No se declararon equivalentes.

## Alcance

### P3.1 — fachada pública

- [x] Publicar `oracle_metalenguaje.Motor`.
- [x] Construirlo desde proyecto, catálogo, límites y confianza explícita.
- [x] Seleccionar automáticamente las medidas aplicables por relaciones.
- [x] Probarlo desde un wheel instalado y un directorio vacío.
- [x] Mantener temporalmente los imports internos mientras se fija el contrato.

### P3.2 — estado por instancia

- [x] Crear `RegistroEscalares` por motor.
- [x] Pasar el registro explícitamente por validación y evaluación.
- [x] Probar dos proyectos con UDF homónimas pero implementaciones distintas.
- [x] Hacer explícita la inclusión del catálogo base, compatible con proyectos v1.
- [x] Admitir raíces externas de perfiles sin modificar la instalación.
- [x] Mover la resolución de `sys.argv` dentro de cada `main`.

### P3.3 — namespace y recursos

- [x] Instalar la implementación sólo bajo `oracle_metalenguaje.*`, sin paquetes públicos genéricos.
- [x] Resolver catálogos y perfiles desde la raíz namespaced del paquete.
- [x] Fijar la semántica instalada: corpus y fixtures propios no se distribuyen; los comandos exigen
  proyecto explícito fuera del checkout y fallan sin traceback cuando falta.
- [x] Verificar los siete entry points, recursos empaquetados, perfil externo y dos motores aislados
  desde un wheel, un virtualenv y un cwd vacíos.

## Cierre P3 — embedding, namespace y recursos (2026-07-31)

P3 queda cerrado del lado de Oracle con esta evidencia:

- el wheel no contiene `nucleo/`, `catalogos/`, `perfiles/` ni `tools/` de nivel superior; instala
  exclusivamente `oracle_metalenguaje.*`;
- `_compat` es un puente de transición para ejecutar el checkout con los imports internos vigentes,
  no una segunda API instalada;
- los catálogos universales y el perfil `python` se resuelven dentro de la distribución;
- el host puede conceder raíces externas con forma `<raíz>/<perfil>/catalogos`; se rechazan raíces
  ausentes, symlinks y perfiles ambiguos, y el proyecto sólo elige nombres;
- ninguna herramienta consulta proyecto o argumentos durante el import; cada `main(argv)` crea su
  sesión después de parsear;
- el smoke instalado ejecuta los siete entry points, carga una UDF externa, un perfil externo y el
  perfil empaquetado, y evalúa dos proyectos con una UDF homónima de resultado distinto;
- una instalación sin proyecto exige `--proyecto` con diagnóstico breve; no depende del checkout;
- Oracle no tiene fixtures diferenciales propios: su ausencia devuelve estado no-verde. El flujo
  temporal externo cubre el diferencial positivo, y una regresión impide que cero fixtures sea verde.

Resultados al cierre original de P3:

- 335 tests;
- 129/129 mutantes de medida;
- 1129 sitios de mutación de código en el denominador;
- particiones modificadas: `algebra` 245/245, `medida` 98/98, `proyecto` 100/100, `Motor` 22/22 y
  `_compat` 5/5;
- corpus: 42 casos en regla;
- aceptación: 27 defectos rojos, 12 verdes correctos y cero huecos abiertos;
- wheel: namespace único, siete entry points y dos motores aislados fuera del checkout.

No se declararon equivalentes. No queda otra abstracción particular pendiente dentro de P3.

## Integración comprobada en Jam (2026-07-31)

Jam sincronizó el subtree hasta Oracle `ceab294` y quedó en `f4f33f6`. La integración no movió el
vendor a mano ni se superpuso con los cambios locales del Graph.

- `tools/vault.py` construye `oracle_metalenguaje.Motor` y dejó de importar el evaluador o el
  catálogo internos;
- `medidas/escalares.py` usa `oracle_metalenguaje.escalar`, sin insertar rutas ni importar
  `nucleo.algebra`;
- los emisores siguen usando las primitivas de autoría (`Dominio`, `Procedencia`) dentro de un
  contexto explícitamente confiado y transaccional;
- los tres fixtures firman también `medidas/escalares.py`: una UDF modificada ya no puede dejar una
  referencia aparentemente fresca;
- Jam declara nueve casos mínimos de corpus para fijar los bordes de interpenetración, grilla, yaw
  y contacto al ras, además de sus fixtures diferenciales;
- la penetración publicada descuenta la tolerancia de contacto, tal como declaraba el umbral, y una
  regresión fija el valor efectivo de 0,5 cm;
- dos predicados de pares tienen una orientación única y `relevo.verificacion_existe` usa sólo
  `es_ancestro`, que ya implica existencia, eliminando conteos y condiciones redundantes.

La integración encontró además que el mutador de Oracle no comparaba el valor numérico del informe:
un `max→min` podía conservar color y testigos mientras cambiaba la magnitud publicada. Se corrigió en
el upstream (`ceab294`) y la partición cerró 149/149.

Puertas observadas en la rama aislada antes del fast-forward:

- 492 tests de Jam y 336 tests del vendor;
- wheel namespaced, siete entry points y dos motores aislados;
- corpus Jam: 6 casos, cero huecos;
- diferencial: 269 acuerdos globales y 1158 veredictos individuales estables;
- mutación de medidas Jam: 153/153, sin equivalentes declarados;
- vault: 48 documentos y ambos verificadores coincidentes.

Después del fast-forward, el árbol real —con 50 documentos y los cambios de Graph ajenos a esta
integración intactos— cerró 499 tests de Jam, 336 del vendor, 269/269 acuerdos diferenciales,
153/153 mutantes y ambos verificadores del vault coincidentes. `placement` y `snap` continúan siendo
referencias escritas a mano: todavía no se reemplazó ningún oráculo del editor.

### Comprobación por el camino real de Unreal

La prueba del 2026-07-31 ejecutó los adaptadores actuales de `placement` y `snap` contra BotOO. No
prueba todavía una evaluación de esos dos dominios mediante `Motor`; fija la referencia real que la
futura sombra deberá igualar.

- El modo commandlet `-run=pythonscript` no es un arnés válido para `placement`: no crea el
  `PlacementSubsystem` y cayó dentro de `UPlacementSubsystem::FindAssetFactoryFromAssetData` al
  comenzar `selftest_colocar`.
- En modo editor completo, `placement` comprobó solapamiento coincidente con 99,0 cm de penetración
  efectiva, separación limpia y exclusión del fondo; `snap` comprobó grilla y contacto al ras.
- El script alcanzó el marcador `JAM_ORACLE_INTEGRATION TODO VERDE — placement + snap por UE` antes
  de solicitar la salida.
- El proceso devolvió 139 después de `Editor shut down`, con `munmap_chunk(): invalid pointer`
  durante el desmontaje. Por eso la funcionalidad ejercitada queda comprobada, pero no se declara
  verde el ciclo de vida completo del editor ni se actualiza `verde_editor`.

La próxima etapa debe introducir la evaluación en sombra mediante `Motor`, comparar sus informes
con estas referencias y conservar ambos caminos hasta cerrar diferencial y mutación. Un marcador
funcional anterior al fallo de desmontaje no autoriza a retirar la implementación existente.

### Sombra de `Motor` en el adaptador Unreal

El siguiente bloque conectó las seis medidas geométricas ya declaradas al camino operativo, sin
darles todavía autoridad:

- `jam.bridge` incorpora en un único punto tanto los oráculos históricos como
  `vendor/oracle/oracle_metalenguaje`; ningún sensor añade rutas por su cuenta;
- `jam.oracle_shadow` aplana `geometry.Pieza` a relaciones L0 y sólo importa la fachada pública
  `Motor`, `Informe`;
- `jam.ue` ejecuta la referencia primero y luego compara `colocacion.bounds`,
  `colocacion.interpenetracion`, `snap.grilla`, `snap.yaw`, `snap.al_ras` y
  `snap.comparte_cara` con el informe de `Motor`;
- una diferencia, una medida ausente o una excepción se registra como error; la referencia conserva
  el resultado operativo durante la sombra;
- la configuración histórica de snap admite otros pasos y tolerancias, pero el catálogo actual fija
  100 cm, 90°, 1 cm y 0,5°. Una configuración distinta se informa como no declarada en vez de
  compararla falsamente con los defaults;
- `tools._veredicto_entorno` y los selftests pasan por `jam.ue`, no llaman por atajo al comparador.

Las regresiones puras suman 507 tests y prueban coincidencia, desacuerdo deliberado, configuración
no declarada y fallo explícito del motor. La ejecución real en BotOO produjo dos coincidencias de
sombra para `placement`, cuatro para snap, `colocar OK`, `snap OK` y el marcador
`JAM_ORACLE_SHADOW VERDE — placement=True snap=True por UE`.

El ejecutable volvió a devolver 139 después de `Editor shut down`, esta vez con
`double free or corruption (out)` durante el desmontaje. La sombra completó y publicó su marcador
antes del fallo; el cierre completo del editor sigue sin estar verde y `verde_editor` no se mueve.

### `snap.al_ras`: contacto y cara compartida

`al_ras` no es sólo «distancia cero». Dos piezas diagonales pueden tener cero separación sobre `x`
sin compartir una cara. La traducción conserva esa distinción con dos medidas:

- `snap.al_ras`: máximo error absoluto entre las caras sobre el eje solicitado, `<= 1 cm`;
- `snap.comparte_cara`: mínimo solape sobre los otros dos ejes, `> 1 cm`.

El eje viaja como evidencia (`x`, `y` o `z`) y las regresiones ejercitan los tres. Si se presentan
varios objetivos, el máximo error y el mínimo solape exigen que todos cumplan. La mutación encontró
que esa semántica de lote y el flotante inmediato posterior a 1 cm no estaban fijados; tres casos de
corpus los cerraron sin declarar equivalencias.

Evidencia al cerrar el bloque:

- corpus: 9 casos válidos; aceptación: 9 defectos en rojo y cero huecos;
- diferencial: 419 acuerdos globales y 2558 veredictos individuales, sin cambios;
- mutación: 163/163;
- BotOO: cuatro coincidencias de `snap.al_ras`, transición `hueco→al_ras`, `snap OK` y marcador
  `JAM_ORACLE_SNAP_AL_RAS VERDE — snap=True por UE`.

El proceso volvió a terminar con estado 139 después de `Editor shut down`; el marcador funcional
precede al fallo, pero el ciclo de vida completo del editor continúa rojo. Ninguno de estos bloques
autoriza retirar todavía `oracle_placement.py` ni `oracle_snap.py`.

## Lo que P3 no hará

- No agrega operadores, macros ni sintaxis.
- No crea VM, bytecode o backend nativo.
- No introduce conocimiento de Unreal en Oracle.
- No entrega todavía autoridad a `Motor` ni migra `scatter`, `pared`, `physics`, `reemplazo` o
  `espacio`.
- No retira los verificadores escritos a mano de Jam durante la fase sombra.

## Criterios de salida

P3 queda cerrado cuando:

1. un consumidor sólo importa `Motor`, entrega hechos y recibe un `Informe`;
2. dos motores con UDF y límites distintos coexisten sin contaminación;
3. el wheel funciona fuera del checkout y todos sus recursos tienen una semántica deliberada;
4. el catálogo base y los perfiles se componen explícitamente;
5. Jam puede incorporar Oracle sin importar internals ni añadir rutas dispersas;
6. la suite, aceptación, diferencial y mutación mantienen sus denominadores;
7. la licencia y el consumidor real independiente permanecen como decisiones separadas de P3.

## Orden de trabajo

1. [x] Escribir regresiones de `Motor` y del wheel.
2. [x] Implementar la fachada sin mover todavía los internals.
3. [x] Aislar el registro de escalares.
4. [x] Cerrar namespace y recursos.
5. [x] Sincronizar el subtree de Jam e integrar `Motor` en la sombra del vault.
6. [x] Ejecutar en sombra las medidas declaradas de `placement` y snap grilla/yaw por Unreal.
7. [x] Declarar y sombrear `snap.al_ras` y la condición separada de cara compartida.
8. [ ] Acumular evidencia real sin diferencias antes de permitir que `Motor` gobierne.

## Rollback

La referencia escrita a mano de `tools/vault.py` permanece intacta y sigue gobernando la comparación.
Si la fachada no cierra, se revierte el consumo de `Motor` y los CLIs siguen usando el núcleo
vendorizado. `placement`, snap grilla/yaw y `snap.al_ras` ejecutan `Motor` después de la referencia;
una falla queda en el log y no cambia el resultado. El rollback consiste en retirar esas llamadas
desde `jam.ue` y la raíz vendorizada de `jam.bridge`. No se reemplazó ningún oráculo histórico.

## Relacionado

- [[2026-07-30-INFORME-Auditoria-Viabilidad-Lenguaje-Propio-Oracle-v1.0|Auditoría de viabilidad del lenguaje de Oracle]]
- [[2026-07-30-INFORME-Oracle-Metalenguaje-De-Medidas-v1.0|Oracle: un metalenguaje de medidas]]
