# Vault-kb de Jam

54 documentos en 5 carpetas. Nomenclatura
`AAAA-MM-DD-TIPO-Nombre-vX.X.md` — la explica
[[2026-07-29-GUIA-Convencion-Documentacion-Vault-v1.0|la guía de convención]].
La carpeta es la taxonomía: cada doc vive en una sola y su `area:` lo dice.
Este índice y las reglas los verifica `tools/vault.py`.

`INFORME` = lo que pasó · `PLAN` = lo que falta · `ROADMAP` = hacia dónde ·
`CONCEPTO` = un principio · `GUIA` = cómo se usa.

## Proceso y dirección

`00-Proceso/` · 7 documentos

- [[2026-08-02-PLAN-Revision-Jam-Oracle-UE-5-8-v1.0|Revisión integral de Jam, Oracle y Unreal Engine 5.8.1]] · *en-progreso*
- [[2026-07-31-PLAN-Autonomia-Embedding-Oracle-P3-v1.0|P3 de Oracle: autonomía de embedding antes de migrar Jam]] · *completo*
- [[2026-07-30-INFORME-Oracle-Metalenguaje-De-Medidas-v1.0|Oracle: un metalenguaje de medidas para construir herramientas con un LLM]] · *implementado*
- [[2026-07-30-INFORME-Auditoria-Viabilidad-Lenguaje-Propio-Oracle-v1.0|Auditoría de viabilidad: un lenguaje propio para Oracle]] · *dictamen-desaconsejado*
- [[2026-07-29-GUIA-Relevo-Claude-Codex-v1.0|Guía: el relevo entre Claude Code y Codex]] · *vigente*
- [[2026-07-29-GUIA-Convencion-Documentacion-Vault-v1.0|Guía: convención de documentación del Vault-kb de Jam]] · *vigente*
- [[2026-07-25-ROADMAP-Vision-Producto-Jam-v1.0|Visión y roadmap de producto para Jam]] · *propuesta*

## Graph — el editor de nodos

`01-Graph/` · 13 documentos

- [[2026-08-02-PLAN-ABM-Funciones-Graph-v1.0|ABM de funciones del Graph: identidad, firma y cuerpo]] · *en-progreso*
- [[2026-07-29-ROADMAP-Accesibilidad-Graph-v1.0|Roadmap: accesibilidad y velocidad del Graph]] · *propuesta*
- [[2026-07-29-INFORME-Seleccion-Multiple-Alineacion-Nodos-v2.0|Selección múltiple y alineación de nodos Graph]] · *implementado*
- [[2026-07-29-INFORME-Historial-Deshacer-Rehacer-v1.0|Historial del Graph: deshacer y rehacer]] · *implementado*
- [[2026-07-29-INFORME-Funciones-Graph-Firma-v1.0|Funciones del Graph: un subgrafo con firma]] · *implementado*
- [[2026-07-29-INFORME-Docking-Paneles-Nomad-Tabs-v1.0|Docking: los tres paneles de Jam son nomad tabs]] · *implementado*
- [[2026-07-27-INFORME-Nodos-De-Debug-Ver-El-Stream-v1.0|Nodos de debug: ver el stream, no sólo medirlo]] · *implementado*
- [[2026-07-25-PLAN-Tipado-Cardinalidad-Conexiones-Graph-v1.0|Tipado y cardinalidad de conexiones Graph]] · *en-progreso*
- [[2026-07-25-PLAN-Persistencia-Segura-Diagramas-Graph-v1.0|Persistencia segura de diagramas Graph]] · *en-progreso*
- [[2026-07-25-INFORME-Graph-Eliminar-Conexiones-Alt-Click-v1.0|Graph: eliminar conexiones con Alt-click]] · *implementado*
- [[2026-07-25-INFORME-Fix-Graph-Cable-Fantasma-v1.0|Fix Graph: cable fantasma alineado al cursor]] · *implementado*
- [[2026-07-25-INFORME-Fix-Graph-Buscador-Doble-Clic-v1.0|Fix Graph: buscador alineado al doble clic]] · *implementado*
- [[2026-07-25-CONCEPTO-Estetica-Nodos-Grasshopper-v1.0|Estética de nodos Grasshopper para Jam]] · *implementado*

## TreeGen — el árbol procedural

`02-TreeGen/` · 18 documentos

- [[2026-07-27-INFORME-TreeGen-UV-Materiales-Sections-HISM-v1.0|TreeGen: UV, materiales, sections y salida HISM]] · *implementado*
- [[2026-07-27-INFORME-TreeGen-Transform-Frames-v1.0|TreeGen: Transform Frames F]] · *implementado*
- [[2026-07-27-INFORME-TreeGen-Relieve-De-Corteza-v1.0|TreeGen: relieve de corteza]] · *implementado*
- [[2026-07-27-INFORME-TreeGen-Dos-Niveles-Presets-v1.0|TreeGen: ejemplo de dos niveles y presets de Graph]] · *implementado*
- [[2026-07-27-INFORME-TreeGen-Distribute-Frames-v1.0|TreeGen: Distribute Frames F]] · *implementado*
- [[2026-07-27-INFORME-TreeGen-Curve-N-Array-Pipe-With-Profile-v1.0|TreeGen: Graph Curve N[] y Pipe with Profile]] · *implementado*
- [[2026-07-27-INFORME-TreeGen-Curve-Frames-FrameStream-v1.0|TreeGen: Curve Frames y contrato FrameStream F]] · *implementado-base*
- [[2026-07-27-INFORME-TreeGen-Copy-Mesh-To-Frames-v1.0|TreeGen: Copy Mesh to Frames A + F a M]] · *implementado*
- [[2026-07-27-INFORME-TreeGen-Branch-From-Frames-v1.0|TreeGen: Branch From Frames F a S]] · *implementado*
- [[2026-07-27-INFORME-TreeGen-Auditoria-Blueprints-Flow-Real-v1.0|TreeGen: auditoría de Blueprints, funciones y flow real]] · *en-implementacion*
- [[2026-07-27-INFORME-TreeGen-Asset-Set-Choose-Copy-Variants-v1.0|TreeGen: Asset Set, Choose Asset y Copy Variants]] · *implementado*
- [[2026-07-26-INFORME-TreeGen-Replica-Jerarquica-Branch-Leaf-v1.0|TreeGen: réplica jerárquica real de Branch y Leaf]] · *implementado*
- [[2026-07-26-INFORME-TreeGen-Mesh-Leaf-StaticMesh-Opcional-v1.0|TreeGen: Mesh Leaf con StaticMesh opcional]] · *implementado*
- [[2026-07-26-INFORME-TreeGen-Mesh-From-Asset-Along-Curve-v1.0|TreeGen: Mesh From Asset y Mesh Along Curve]] · *implementado-historico*
- [[2026-07-26-INFORME-TreeGen-Follaje-Procedural-Variacion-v1.0|TreeGen: follaje procedural con variación]] · *historico-superado*
- [[2026-07-26-INFORME-TreeGen-Curve-Child-Ramas-Jerarquicas-v1.0|TreeGen: Curve Child y ramas jerárquicas]] · *implementado-historico*
- [[2026-07-26-INFORME-TreeGen-Curvas-Pipe-Arbol-Ramificado-v1.0|TreeGen: curvas, Pipe y árbol ramificado]] · *implementado-historico*
- [[2026-07-26-GUIA-Ejemplo-Graph-Pino-Procedural-v1.0|Ejemplo Graph: pino procedural TreeGen]] · *implementado*

## Mesh y materiales

`03-Mesh-y-materiales/` · 7 documentos

- [[2026-08-02-INFORME-Nanite-Fracture-Dataflow-UE-5-8-v1.0|Nanite a Fracture en UE 5.8: Geometry Collection sin perder materiales]] · *implementado*
- [[2026-07-28-INFORME-Primitivas-Tab-Mesh-v1.0|Primitivas del tab Mesh]] · *implementado*
- [[2026-07-28-INFORME-Materiales-Avanzados-Layers-Substrate-Substance-v1.0|Investigación — materiales avanzados: Layers, Substrate, Material Functions y Substance]] · *investigacion-completa*
- [[2026-07-27-INFORME-Oraculo-De-Forma-Malla-Referencia-v1.0|Oráculo de forma: comparar contra la malla de referencia]] · *implementado*
- [[2026-07-26-INFORME-Nodo-Mesh-Color-Vertex-Color-v1.0|Nodo Graph: Mesh Color y Vertex Color]] · *implementado-mvp*
- [[2026-07-26-INFORME-Nodo-Convert-To-Nanite-v1.0|Nodo Graph: Convert to Nanite]] · *implementado*
- [[2026-07-26-INFORME-Graph-Tab-Mesh-Verbos-Malla-v1.0|Graph: tab Mesh y verbos de malla procedural]] · *implementado-mvp*

## Ejecución, presets y pruebas

`04-Ejecucion-y-pruebas/` · 9 documentos

- [[2026-08-02-INFORME-Certificacion-Jam-UE-5-8-1-v1.0|Certificación de Jam en Unreal Engine 5.8.1]] · *en-progreso*
- [[2026-07-27-INFORME-Puente-P-a-F-Ops-Flow-v1.0|Puente P → F: las ops de Flow como verbos del Graph]] · *implementado*
- [[2026-07-26-PLAN-Preview-Transaccional-Efectos-PCG-v1.0|Preview transaccional y efectos de PCG]] · *en-progreso*
- [[2026-07-25-PLAN-Infraestructura-Pruebas-Jam-Oraculo-v1.0|Infraestructura de pruebas de Jam y Oráculo]] · *pendiente*
- [[2026-07-25-PLAN-Errores-Resultados-Observables-Flow-v1.0|Errores y resultados observables de Flow]] · *pendiente*
- [[2026-07-25-PLAN-Contratos-Defensivos-Tools-Assets-v1.0|Contratos defensivos de tools y assets]] · *pendiente*
- [[2026-07-25-PLAN-Contrato-Unificado-Graph-Flow-Presets-Web-v1.0|Contrato unificado de Graph, Flow, Presets y Web]] · *pendiente*
- [[2026-07-25-PLAN-Compilacion-Estricta-Preview-Bake-v1.0|Compilación estricta y ciclo Preview/Bake del Graph]] · *en-progreso*
- [[2026-07-25-INFORME-Auditoria-Proactiva-Jam-v1.0|Auditoría proactiva de Jam]] · *revision-completa*
