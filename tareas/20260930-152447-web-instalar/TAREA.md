# Una web que explique cómo instalar Jam, fácil y rápido

- ESTADO: ABIERTA
- PRIORIDAD: 85
- ETIQUETAS: instalacion, web, docs

## Por qué

2026-09-30, Brian: hace falta una web de cómo instalar Jam de forma fácil y rápida. Hoy la receta
existe pero es texto en el repo: `INSTALAR.md` y `tools/instalar.py <proyecto>` (reconoce Unreal,
Godot o Unity, enlaza o copia el plugin y configura el núcleo; probado en Linux, Windows escrito pero
sin probar). Quien llega a otra máquina no tiene una página que le diga, en orden y con lo que tiene
que ver en cada paso, qué hacer.

## Qué tiene que tener

- Los requisitos (Python ≥ 3.11, el motor y su versión), los pasos (clonar, `tools/instalar.py`,
  abrir el motor, abrir el editor de nodos web) y **qué se tiene que ver** en cada uno, como las guías
  de Oracle (`~/Dev/oracle/docs/`, generadas desde `.md` con `tools/sitio.py`, sin build).
- Un recorrido por motor (Unreal, Godot, Unity) y por sistema (Linux, Windows).
- Qué hacer cuando algo falla (puerto ocupado, Python viejo, UE que pide compilar), con los mensajes
  reales que da el instalador.
- Que sea la misma fuente que `INSTALAR.md` (una sola fuente; la página es su vista), así no se
  desincronizan.

## A decidir con Brian

- **Dónde se publica.** El repo `Segtem/jam` es PRIVADO: una página pública (GitHub Pages) explicaría
  cómo instalar algo que el lector no puede clonar. Opciones: publicarla igual (la página es pública,
  el clon pide acceso), servirla sólo dentro del editor web de Jam (una pestaña «Instalar»), o las dos.
- Si el instalador tiene que poder bajarse solo (un paquete o un script de una línea) en vez de
  clonar con git.

## Criterio de hecho

Alguien en una máquina limpia sigue la página y llega a ver el editor de nodos conectado a su motor,
sin preguntar nada; la página se genera desde `INSTALAR.md` y un test falla si se desincronizan.

## Próximo paso

Que Brian decida dónde se publica; mientras tanto, se puede escribir la guía en `INSTALAR.md` con el
formato de las guías de Oracle (pasos + salida esperada).
