---
title: "Biblioteca de ejemplos de malla procedural: TreeGen y ProceduralMeshDemos"
tipo: INFORME
version: "1.0"
date: 2026-08-09
updated: 2026-08-09
status: en-implementacion
area: 02-TreeGen
tags:
  - treegen
  - procedural-mesh
  - ejemplos
  - geometry-script
  - flow
aliases:
  - Biblioteca de ejemplos procedurales
  - ProceduralMeshDemos en Jam
---

# Biblioteca de ejemplos de malla procedural: TreeGen y ProceduralMeshDemos

## Resultado

Jam empezó una biblioteca de ejemplos procedurales como **grafos editables y portables**, no como
una colección de actores opacos. La primera incorporación es **Terreno con ruido**:

```text
Grid M → Ruido Perlin M → Normales M → Mesh to Static A → Place
```

El nodo nuevo `mesh_noise` es M → M, no destructivo y determinista por `seed`. Usa
`DynamicMesh.apply_perlin_noise_to_mesh2`, la variante corregida de UE 5.8. La función histórica
está deprecada desde 5.7 porque elevaba la frecuencia al cuadrado: exponerla habría hecho que la
perilla visible mintiera sobre su propia unidad.

La validación de amplitud, frecuencia y seed vive en `jam/mesh_noise_core.py`, sin `unreal`; el
adaptador arma los structs de Geometry Script y recalcula normales. El tutorial no referencia ningún
asset de `/Game`, por lo que corre fuera de BotOO.

El segundo corte separa `Range` y `Remap` como datos de Flow:

```text
Range N[] → Remap N[] → Debug M
```

`series_range` incluye ambos extremos y acepta rangos ascendentes o descendentes. `series_remap`
transforma cada valor entre dominios, con clamp opcional y soporte para dominios invertidos. El
tutorial **Rango y Remap** dibuja la lista resultante para que `N[]` sea visible, no una abstracción
que sólo se comprueba al conectarla a un pipe.

El tercer corte hace explícita la construcción y densidad de una curva:

```text
X N[] + Y N[] + Z N[] → Polyline S → Smooth S → Resample S → Pipe M
```

`curve_polyline` exige tres series del mismo largo y rechaza puntos consecutivos coincidentes;
`curve_smooth` reduce la aspereza con pasadas Laplacianas simultáneas, conserva opcionalmente los
extremos y no cambia la cantidad de puntos;
`curve_resample` distribuye muestras por longitud, incluye los extremos y conserva `scale`, seed,
procedencia y radio del padre cuando recibe un `CurveSet` de TreeGen. El tutorial **Cylinder Strip
continuo** usa un único sweep: a diferencia del demo original, no genera un cilindro desconectado
por cada tramo.

El cuarto corte completa la edición básica de discretización:

```text
Polyline S → Fuse Collinear S → Subdivide S → Smooth S → Resample S → Debug M
```

El tutorial **Preparar una curva** vuelve observable la diferencia: Fuse reduce una recta de siete
puntos a sus dos extremos; Subdivide inserta tres puntos por segmento y llega a cinco; Smooth
conserva cinco y Resample elige trece muestras por longitud.

El quinto corte abre la familia de caminos y contornos:

```text
Bezier S → Resample S → Offset S → Pipe M
```

`curve_offset` desplaza un recorrido en XY, XZ o YZ, hacia izquierda o derecha. Las esquinas usan
miter o bevel; un miter que supera el límite cae explícitamente a bevel. **Borde de camino** desplaza
el eje 180 cm y barre un cordón continuo sobre el recorrido lateral.

## Fuentes estudiadas

### TreeGen local

`/home/workstation/Dev/games/unreal/TreeGen` es el plugin content-only original para UE 4.24. No es
un repo Git y sus Blueprints son binarios. La auditoría anterior ya extrajo 1.769 nodos y reconstruyó
su contrato jerárquico; véase
[[2026-07-27-INFORME-TreeGen-Auditoria-Blueprints-Flow-Real-v1.0|la auditoría de TreeGen]].

El inventario actual confirma cuatro familias de ejemplo construidas con la misma composición:

- pino: tronco, ramas y frondas;
- abedul: dos niveles de rama, hojas y corteza separada;
- bambú: tallo más un set de variantes de hojas/brotes;
- palmera: tronco, corteza y dos distribuciones de frondas.

Jam ya expresa la mayor parte del sustrato: `S`, `F`, `N[]`, `A[]`, `AF`, pipes con perfil, ramas por
frames, variantes, copias horneadas, HISM, materiales/sections, relieve y jerarquía de pivotes.

### ProceduralMeshDemos

Se estudió `TriAxis-Games/ProceduralMeshDemos` en el commit `d033e0e`, fork actual del repositorio de
Sigurdur Gunnarsson. Es un proyecto de UE 4.25 bajo licencia MIT. Sus ejemplos priorizan legibilidad
sobre reutilización y son una buena **secuencia pedagógica**, aunque el renderer histórico
RuntimeMeshComponent no es la arquitectura que Jam debe copiar.

No se incorporó código del repo externo. El heightfield se reimplementó con la API pública de
Geometry Script 5.8.1 y el contrato propio de Jam. Si en el futuro entra una porción sustancial de
ese código MIT, deberá conservar el aviso de copyright y licencia.

## Matriz de equivalencia

| Demo externo | En Jam | Decisión |
|---|---|---|
| Simple Cube | `mesh_box` | Ya cubierto por Primeros pasos |
| Simple Cylinder | `mesh_cylinder` | Agregar ejemplo corto sólo si enseña normales/caps |
| Cylinder Strip | `N[] × 3 → S → resample → mesh_pipe` | **Implementado: cerrado y una sola pieza** |
| Sphere | `mesh_sphere` / `mesh_sphere_box` | Comparar topologías, no duplicar una esfera |
| Branching Lines | TreeGen `S → F → S` | Ya cubierto; falta una versión “rayo” más pequeña |
| Noise Heightfield | `mesh_grid → mesh_noise` | **Implementado** |
| Animated Heightfield | material/WPO o estado temporal | No mezclar con autoría estática de M |
| Sierpinski Lines | repetición + pipe | Espera compound iterativo/recursivo |
| Sierpinski Tetrahedron | repetición + tetraedro/merge | Espera la misma base y un límite de explosión |

## Qué mejorar en verbos y Flow

La biblioteca no debería crecer mediante nodos monolíticos “Hacer terreno” o “Hacer fractal”. Cada
ejemplo tiene que revelar piezas reusables:

1. **Campos y deformación:** `mesh_noise` es el primer corte. Siguen selección por máscara/campo y
   deformación por textura, con el campo como dato observable.
2. **Barridos:** Cylinder Strip ya mide la unión continua y deja `miter_limit` visible. Falta medir
   auto-intersección y elongación de sección en ángulos extremos, no sólo cierre/conectividad.
3. **Iteración:** repeat de un compound con tope explícito; habilita Sierpinski, niveles de ramas y
   patrones sin copiar cadenas a mano.
4. **Atributos:** lectura/escritura explícita de `radius`, `parent_index`, `pivot_index`, `weight` y
   Material ID para que TreeGen no dependa de sidecars invisibles.
5. **Salidas temporales:** separar con claridad formas estáticas de deformación animada en material,
   Niagara o runtime. Un Graph de autoría no debe fingir que una animación es un asset quieto.

`Range` y `Remap`, antes parte de esta lista, quedaron implementados como fuente N[] y operador
N[] → N[] respectivamente. `graph_curve` conserva su identidad y compatibilidad: curva una serie;
no vuelve a absorber la responsabilidad de generarla o cambiarle el dominio.

`Polyline`, `Fuse Collinear`, `Subdivide`, `Smooth` y `Resample`, también resueltos, hacen visible la
frontera entre coordenadas, simplificación, inserción, forma y densidad de muestreo. No se absorbieron
dentro de Pipe: el mismo `S` procesado sigue sirviendo a frames, ramas, copias y debug.

## Evidencia

- Suite pura: **784 tests OK**.
- Mutación deliberada: permitir frecuencia cero volvió rojo
  `test_rechaza_parametros_que_geometry_script_no_puede_defender`.
- UE 5.8.1 por `api.compile_graph_json` y `api.run_graph_json`: **1.681 vértices**,
  `z=-85,39..70,61 cm`, mismo SHA-256 en dos ejecuciones con seed 1977.
- Marcador: `JAM_MESH_NOISE_58 TODO VERDE`.
- Range/Remap por spec + Compile + Run: `(-1..1) → (0, 2.5, 5, 7.5, 10)` y salida Debug M.
- Marcador: `JAM_SERIES_FLOW_58 TODO VERDE`.
- Mutación deliberada: devolver el inicio como último punto volvió rojo el test de extremos.
- Mutación deliberada: ignorar `preserve_ends` movió el inicio de `(0,0,0)` a
  `(59,375,44,219,0)` y volvió rojo el test de extremos.
- Polyline/Smooth/Resample/Pipe en UE 5.8.1: 7→7→31 puntos, aspereza
  229,666→106,195 y ratio de separación 1,624→1,015,
  **740 triángulos/372 vértices, cerrada y una sola pieza**.
- Marcador: `JAM_CURVE_SAMPLING_58 TODO VERDE`.
- Fuse/Subdivide por spec + Compile + Run: `7→2→5→5→13`, extremos exactos y vértices originales
  conservados por Subdivide.
- Dos mutaciones deliberadas murieron: invertir el juicio angular de Fuse y usar una división menos
  en el modo `count` de Subdivide.
- Offset por spec + Compile + Run: 25→25 puntos, izquierda a 180 cm con error firmado máximo
  `0,0000 cm`; Pipe de **496 triángulos/250 vértices**, cerrado y una sola pieza.
- Marcador: `JAM_CURVE_OFFSET_58 TODO VERDE`.
- Mutación deliberada: invertir izquierda/derecha volvió rojo el test de distancia firmada.
- Catálogo completo en UE 5.8.1: **13/13 tutoriales compilan**, `VEREDICTO: TODO VERDE`.

## Lo que NO ve

- No hubo juicio visual del terreno en el viewport ni de su ficha en Slate.
- Repetibilidad en dos corridas de una build no promete identidad entre versiones de UE.
- El rango Z prueba deformación, no calidad artística, ausencia de auto-intersecciones ni buena
  distribución espectral.
- No se midieron UV, colisión, Nanite, costo de render ni calidad del StaticMesh horneado.
- `por_normal=false` está atado al binding y al contrato, pero la sonda real ejercitó el caso de
  terreno `por_normal=true`.
- Cierre y una sola componente detectan huecos/secciones desconectadas en Cylinder Strip, pero NO
  ven auto-intersecciones, torsión, pinching, estiramiento UV ni calidad visual del miter.
- La separación medida es distancia recta entre muestras consecutivas; cerca de un vértice queda
  por debajo del paso por arco aunque el parámetro de longitud sea uniforme.
- Offset es planar: conserva la tercera coordenada de cada vértice, pero no define todavía un frame
  transportado sobre curvas 3D arbitrarias.
- La distancia y el límite de miter NO detectan auto-intersecciones, colapso de contornos cóncavos ni
  calidad visual de una futura superficie vial.

## Próximo corte

Implementar `mesh_ribbon`/solidify con ancho, UV longitudinal y Material IDs para que el borde medido
se convierta en una superficie vial. Después siguen muro y carretera completos. `Repeat Compound` y
Sierpinski quedan después: antes de registrarlos hay que resolver qué función pura se repite y cómo
el límite evita explosiones de geometría. La investigación ampliada y sus licencias viven en
[[2026-08-09-INFORME-GitHub-Procedural-Mesh-Generation-v1.0|el corpus GitHub de PMG]].
El orden completo vive en
[[2026-08-09-ROADMAP-Verbos-Y-Ejemplos-PMG-v1.0|el roadmap de verbos y ejemplos PMG]].

## Relacionado

- [[2026-07-27-INFORME-TreeGen-Auditoria-Blueprints-Flow-Real-v1.0|TreeGen: auditoría de Blueprints y flow real]]
- [[2026-07-27-INFORME-TreeGen-Dos-Niveles-Presets-v1.0|TreeGen: ejemplo de dos niveles y presets]]
- [[2026-08-02-ROADMAP-Nodos-Unreal-Engine-5-8-1-v1.0|Roadmap de nodos UE 5.8.1]]
- [[2026-08-09-INFORME-GitHub-Procedural-Mesh-Generation-v1.0|GitHub como corpus de verbos de malla procedural]]
- [[2026-08-09-ROADMAP-Verbos-Y-Ejemplos-PMG-v1.0|Roadmap de verbos y ejemplos PMG]]
