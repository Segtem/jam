# Instalar Jam en otra máquina

Hace falta **Python 3.11 o más** (sólo la biblioteca estándar: no hay nada que instalar con pip) y
el motor: **Unreal 5.8.1**, **Godot 4.7** o **Unity 6 (6000.3)**. Linux o Windows.

```bash
git clone git@github.com:Segtem/jam.git          # el repo es privado: hace falta acceso
python jam/tools/instalar.py <carpeta del proyecto>
```

El instalador reconoce el motor por lo que hay en la carpeta y deja Jam enchufado:

| motor | qué hace | después |
|---|---|---|
| Unreal | `Plugins/Jam` → el repo | abrí el `.uproject`; Unreal ofrece compilar JamEditor y JamMass → **Sí** (necesita el toolchain de C++ de UE 5.8) |
| Godot | `addons/jam`, activa el plugin, escribe `[jam]` en `project.godot` | Proyecto ▸ Herramientas → **Jam: editor de nodos** |
| Unity | `Assets/Jam`, escribe `ProjectSettings/JamNucleo.json` | menú **Jam → Editor de nodos (web)** |

Por defecto **enlaza** (en Windows sin modo desarrollador, una *junction*): un `git pull` del repo
actualiza el proyecto. Con `--copiar` el proyecto queda independiente del repo (se copia el plugin y
el núcleo adentro). El Python con el que corrés el instalador es el que van a usar Godot y Unity para
el núcleo; `--python <ruta>` elige otro.

El editor de nodos se abre en una ventana propia si hay Chromium o Chrome (modo aplicación); si no,
en el navegador. El agente (`jam-mcp`) se instala aparte: ver su README.
