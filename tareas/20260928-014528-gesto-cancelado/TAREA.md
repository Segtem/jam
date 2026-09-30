# Verificar con Brian: un nodo cancelado por un fallo aguas arriba se lee en el canvas

- ESTADO: CERRADA
- PRIORIDAD: 58
- ETIQUETAS: gestos


## Por qué

`fuente-roja` agregó el estado `cancelado`: un nodo que no corrió porque falló algo de lo que
depende. Tiene glifo `↑`, borde rojo apagado y tooltip «no corrió: falló un nodo aguas arriba». El
contrato con el C++ está atado por test y el binario compiló, pero nadie lo vio dibujado.

## Qué hacer

Abrir el Graph en JamPlayground, cargar un grafo con una fuente que falle en Run (por ejemplo
`curve_bezier → curve_frames count=37 → mass_spec budget=5 → mass_spawn`), correrlo y mirar: ¿el `↑`
se ve (no un rombo con «?»), el borde se distingue del rojo de error, y el tooltip dice la causa?

## Próximo paso

El gesto de Brian.

### Nota (2026-09-30 14:11:42 UTC)

2026-09-30: reemplazado por la decisión de Brian de una sola interfaz (tarea mudar-a-web). Este gesto revisaba la interfaz de C++, que queda congelada y se reemplaza; lo que verificaba se revisa UNA vez en el editor web, cuando esa capacidad llegue ahí (el inventario de mudar-a-web la incluye).
