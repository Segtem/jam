# Capability: editor

## ADDED Requirements

### Requirement: F2 renombra el nodo seleccionado
Tipo: funcional
En el editor de nodos web, F2 con un solo nodo seleccionado SHALL abrir el mismo diálogo que «Renombrar…». El nombre nuevo SHALL ser un identificador (letras, dígitos y «_», sin empezar por dígito) que no use otro nodo; si no lo es, el nodo SHALL quedar como estaba y el editor SHALL decir por qué. Los cables del nodo SHALL seguir conectados con el nombre nuevo.

#### Scenario: renombrar con F2
- GIVEN un grafo con un nodo seleccionado que alimenta a otro
- WHEN se aprieta F2 y se escribe un nombre válido
- THEN el nodo se llama así y el JSON del grafo tiene el cable con el nombre nuevo

#### Scenario: un nombre inválido o repetido
- GIVEN un nodo seleccionado
- WHEN se le da un nombre que no es un identificador, o el de otro nodo
- THEN el nodo conserva su nombre y el editor dice por qué

### Requirement: la variable de un valor conserva su nombre al renombrar el nodo
Tipo: funcional
Al renombrar un nodo de valor que no tiene `name` propio, el editor SHALL fijarle `name` con el nombre viejo, de modo que su variable y las expresiones que la usan no cambien. Un nodo de valor con `name` propio SHALL conservarlo.

#### Scenario: un valor sin name propio
- GIVEN un nodo de valor sin name, usado por su nombre en una expresión
- WHEN se lo renombra
- THEN su name es el nombre viejo y la expresión sigue resolviendo la misma variable

#### Scenario: un valor con name propio
- GIVEN un nodo de valor con name propio
- WHEN se lo renombra
- THEN su name no cambia
