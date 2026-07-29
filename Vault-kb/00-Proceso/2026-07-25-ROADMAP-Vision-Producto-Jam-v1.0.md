---
title: "Visión y roadmap de producto para Jam"
tipo: ROADMAP
version: "1.0"
date: 2026-07-25
updated: 2026-07-25
status: propuesta
area: 00-Proceso
tags:
  - jam
  - product-vision
  - roadmap
  - dash
  - graph-editor
  - procedural-authoring
  - oracle
aliases:
  - Futuro de Jam
  - Propuestas para mejorar Jam
---

# Visión y roadmap de producto para Jam

## Idea central

Jam puede unir la velocidad de una herramienta tipo Dash con la edición procedural de Grasshopper y
una capa de validación propia:

```text
Dash Bar → acción rápida
Graph    → procedimiento editable y repetible
Preset   → herramienta reutilizable
Oracle   → comprueba que el resultado realmente sirve
```

La oportunidad de Jam es convertirse en una capa de autoría procedural y validación dentro de Unreal,
no solamente en un editor de nodos.

Una acción debería poder evolucionar sin cambiar de sistema:

```text
comando de Dash → Graph editable → Compound reusable → herramienta validada por Oracle
```

## 1. El viewport como centro del trabajo

El Graph controla el procedimiento, mientras la edición se siente directamente en la escena:

- manipuladores visuales para radios, áreas, alturas, distancias y direcciones;
- actualización del parámetro del nodo al mover un gizmo;
- selección bidireccional entre actor y nodo;
- doble clic en un nodo para enfocar su resultado en el viewport;
- preview rápido mientras se arrastra un parámetro y cálculo completo al soltar;
- pintura de assets, densidad, máscaras y zonas de exclusión sobre superficies.

## 2. Biblioteca de assets inteligente

Jam debería analizar y guardar metadata útil de cada asset:

- dimensiones y footprint;
- orientación y eje principal;
- posición del pivote;
- anclas: base, centro, extremos y esquinas;
- colisión, sockets, materiales y LOD;
- categoría semántica: pared, puerta, roca, árbol, mueble o prop;
- compatibilidad y tamaño modular;
- capacidad de apoyarse, colgarse, apilarse o repetirse.

Con esa información podría sugerir el ancla, escala, separación y orientación correctas; detectar kits
modulares; y encontrar assets compatibles con un espacio o una función.

## 3. Operaciones espaciales de alto nivel

Además de `Place`, `Snap` y `Scatter`, conviene orientar las herramientas a tareas completas:

- `Fill Area`: rellenar una región sin intersecciones.
- `Along Spline`: cercas, calles, cables, molduras y paredes.
- `Between`: distribuir piezas entre dos puntos.
- `Stack`: apilar respetando footprint y estabilidad.
- `Attach`: colocar sobre sockets, bordes o superficies.
- `Replace Set`: reemplazar blockouts preservando tamaño y función.
- `Dress Room`: decorar una habitación respetando circulación.
- `Avoid`: excluir puertas, caminos, cámaras o zonas jugables.
- `Cluster`: generar grupos naturales de vegetación o props.
- `Facade`: distribuir ventanas, columnas y módulos sobre paredes.
- `Cable/Pipe`: construir recorridos con curvas y conectores.

Cada operación podría existir como comando rápido, nodo y Compound reusable.

## 4. Compounds creados por el usuario

Los Compounds pueden convertirse en herramientas de primera clase:

- colapsar una selección de nodos;
- elegir parámetros, inputs y outputs expuestos;
- conservar tipos en todos sus pines;
- guardar miniatura, descripción, categoría y tags;
- versionar sin romper grafos antiguos;
- crear instancias vinculadas o copias independientes;
- publicarlos automáticamente en la Dash Bar.

Ejemplo:

```text
Source Surface
→ Avoid Paths
→ Noise Density
→ Cluster
→ Instance Trees
→ Instance Rocks
```

El conjunto podría guardarse como una sola herramienta `Forest Dressing`.

## 5. Oracle como diferenciador

El Oracle puede verificar tanto corrección espacial como restricciones de producción:

- intersecciones y objetos flotando;
- circulación y ancho mínimo de caminos;
- puertas y accesos bloqueados;
- estabilidad de objetos apilados;
- densidad, cobertura y variedad de un scatter;
- continuidad de construcciones modulares;
- navegación y accesibilidad;
- presupuesto de actores, polígonos, materiales e instancias;
- distancias de gameplay, cobertura y líneas de visión.

Cada problema debería señalarse en el nodo, el viewport y un panel de diagnóstico, acompañado por una
explicación y una corrección sugerida.

## 6. Exploración de variantes

Jam puede facilitar la búsqueda de resultados sin destruir el trabajo actual:

- cambiar seeds rápidamente;
- guardar y comparar variantes A/B/C;
- bloquear elementos aceptados y regenerar el resto;
- comparar cantidad, cobertura, colisiones y rendimiento;
- puntuar alternativas con el Oracle;
- promover la variante elegida a Preview y luego Bake.

Esto sería especialmente valioso para vegetación, dressing, blockouts y construcción modular.

## 7. IA como autora de procedimientos

La IA debería proponer procedimientos inspeccionables, no ejecutar efectos opacos:

```text
pedido natural
→ propuesta de Graph
→ Compile/Preflight
→ explicación del plan
→ Preview
→ Confirm/Bake
```

Ejemplos de intención:

- “Llena esta zona con rocas, pero deja libre el camino”.
- “Reemplaza estos blockouts por un kit medieval”.
- “Crea una cerca siguiendo el spline con una puerta cada 20 metros”.
- “Reduce este scatter hasta cumplir un presupuesto de 500 instancias”.

También puede explicar grafos existentes, encontrar parámetros relevantes y sugerir simplificaciones.

## 8. Mejoras pequeñas de alto impacto

- Favoritos y herramientas recientes.
- Búsqueda por verbo, categoría y descripción.
- Historial de acciones y conversión de una acción de Dash en Graph.
- Copiar y pegar parámetros entre nodos.
- Selección por cuadro de arrastre, movimiento/eliminación múltiple y herramientas Align/Distribute.
- Inspector que explique qué produjo cada nodo y por qué.
- Overlay de footprints, anclas, normales y exclusiones.
- Tiempo de ejecución y cantidad de resultados por nodo.
- Selección bidireccional Graph ↔ viewport.
- Guardado automático recuperable.
- Undo/Redo integrado con transacciones de Unreal.

## Roadmap recomendado

### Fase 1 — Confianza

1. Compile/Preflight tipado.
2. Preview/Bake transaccional y Undo.
3. Persistencia segura y tests reproducibles.
4. Resultado y diagnósticos estructurados por nodo.

### Fase 2 — Velocidad

5. Selección múltiple, movimiento grupal y Align/Distribute en el Graph.
6. Sincronización Graph ↔ viewport.
7. Biblioteca inteligente de assets.
8. `Fill Area`, `Along Spline`, `Replace Set` y herramientas de pintura.
9. Compounds reutilizables y versionados.

### Fase 3 — Inteligencia

10. Oracle espacial, de gameplay y rendimiento.
11. Variantes comparables y evaluadas.
12. Lenguaje natural que genere grafos compilables y verificables.

## Principio de diseño

Toda herramienta de Jam debería responder claramente:

1. **Qué necesita:** inputs y tipos explícitos.
2. **Qué va a hacer:** plan o Compile sin efectos.
3. **Qué produjo:** resultados vinculados a nodos y actores.
4. **Si el resultado sirve:** diagnóstico del Oracle.
5. **Cómo revertirlo:** Preview, Discard, Bake y Undo.

## Relacionado

- [[2026-07-25-INFORME-Auditoria-Proactiva-Jam-v1.0|Auditoría proactiva de Jam]]
- [[2026-07-25-PLAN-Compilacion-Estricta-Preview-Bake-v1.0|Compilación estricta y ciclo Preview/Bake]]
- [[2026-07-25-PLAN-Tipado-Cardinalidad-Conexiones-Graph-v1.0|Tipado y cardinalidad de conexiones]]
- [[2026-07-25-PLAN-Contrato-Unificado-Graph-Flow-Presets-Web-v1.0|Contrato unificado de ejecución]]
- [[2026-07-26-PLAN-Preview-Transaccional-Efectos-PCG-v1.0|Preview transaccional y efectos de PCG]]
- [[2026-07-25-PLAN-Infraestructura-Pruebas-Jam-Oraculo-v1.0|Infraestructura de pruebas]]
- [[2026-07-29-INFORME-Seleccion-Multiple-Alineacion-Nodos-v2.0|Selección múltiple y alineación]]
